//! Built-in video radio: Aviateur's receive path (devourer userspace driver
//! for RTL8812AU-class adapters + wfb-ng) linked in from native/.
//!
//! The link decrypts the camera's wfb-ng stream and sends the video RTP to
//! UDP 127.0.0.1:<video port>, where `video::Receiver` picks it up, so the
//! decode and display path is the same as with an external ground station.

use crate::config::RadioConfig;
use std::collections::VecDeque;
use std::ffi::{c_char, c_int, CStr, CString};
use std::net::UdpSocket;
use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex, MutexGuard, OnceLock};
use std::thread::JoinHandle;
use std::time::{Duration, Instant};

#[repr(C)]
#[derive(Clone, Copy)]
struct RawDevice {
    vendor_id: u16,
    product_id: u16,
    bus_num: u8,
    port_num: u8,
    known_adapter: bool,
    name: [c_char; 128],
}

#[repr(C)]
#[derive(Default)]
struct RawStats {
    wifi_frames: i64,
    wfb_frames: i64,
    rtp_packets: i64,
    link_score: [c_int; 2],
    packet_loss: c_int,
    codec: c_int,
    payload_type: c_int,
    running: bool,
    stopped_by_device: bool,
}

extern "C" {
    fn rcwfb_set_log(sink: Option<extern "C" fn(c_int, *const c_char)>);
    fn rcwfb_list_devices(out: *mut RawDevice, max: c_int) -> c_int;
    fn rcwfb_start(device: *const RawDevice, channel: u8, width_mode: c_int, key_path: *const c_char, video_port: c_int) -> bool;
    fn rcwfb_stop();
    fn rcwfb_stats(out: *mut RawStats);
}

/// Failed starts in a row before asking for the adapter to be re-plugged.
/// (A software USB reset was tried and can leave a hung RTL8812AU off the
/// bus entirely, so recovery is left to the user.)
const REPLUG_AFTER_FAILURES: u32 = 3;

/// Wireless broadcast ground-station key that OpenIPC cameras ship with.
const DEFAULT_KEY: &[u8] = include_bytes!("../../third_party/aviateur/assets/gs.key");

/// UDP port the radio code binds for its uplink (TxFrame). A clash throws a
/// C++ exception in a radio thread, which would abort the whole program, so
/// it is checked first. (8000 and 14550 are only send targets.)
const SIDE_PORTS: [u16; 1] = [8001];

const LOG_LINES: usize = 40;

#[derive(Debug, Clone)]
pub struct Adapter {
    pub name: String,
    pub known: bool,
    raw: RawDevice,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum State {
    Disabled,
    /// No compatible USB Wi-Fi adapter plugged in.
    NoAdapter,
    Starting,
    Receiving,
    Error(String),
}

#[derive(Debug, Clone)]
pub struct Status {
    pub state: State,
    pub adapter: String,
    pub channel: u8,
    pub width_mhz: u16,
    pub wifi_frames: i64,
    pub wfb_frames: i64,
    pub rtp_packets: i64,
    /// Per-antenna link score as reported by Aviateur's quality estimator.
    pub link_score: [i32; 2],
    pub packet_loss: i32,
    /// "H264" / "H265" once the stream has been seen.
    pub codec: Option<&'static str>,
    pub since: Option<Instant>,
}

impl Default for Status {
    fn default() -> Self {
        Status {
            state: State::Disabled,
            adapter: String::new(),
            channel: 0,
            width_mhz: 20,
            wifi_frames: 0,
            wfb_frames: 0,
            rtp_packets: 0,
            link_score: [0, 0],
            packet_loss: 0,
            codec: None,
            since: None,
        }
    }
}

impl std::fmt::Debug for RawDevice {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{:04x}:{:04x}@{}.{}", self.vendor_id, self.product_id, self.bus_num, self.port_num)
    }
}

fn logs() -> &'static Mutex<VecDeque<String>> {
    static LOGS: OnceLock<Mutex<VecDeque<String>>> = OnceLock::new();
    LOGS.get_or_init(|| Mutex::new(VecDeque::with_capacity(LOG_LINES)))
}

extern "C" fn log_sink(level: c_int, msg: *const c_char) {
    if msg.is_null() {
        return;
    }
    // SAFETY: rcwfb passes a NUL-terminated string valid for this call.
    let text = unsafe { CStr::from_ptr(msg) }.to_string_lossy().into_owned();
    let tag = ["I", "D", "W", "E"].get(level as usize).copied().unwrap_or("?");
    let mut q = logs().lock().unwrap_or_else(|e| e.into_inner());
    if q.len() == LOG_LINES {
        q.pop_front();
    }
    q.push_back(format!("[{tag}] {text}"));
}

/// Recent messages from the radio code, oldest first.
pub fn recent_log() -> Vec<String> {
    logs().lock().unwrap_or_else(|e| e.into_inner()).iter().cloned().collect()
}

pub fn list_adapters() -> Vec<Adapter> {
    let mut raw = [RawDevice { vendor_id: 0, product_id: 0, bus_num: 0, port_num: 0, known_adapter: false, name: [0; 128] }; 16];
    // SAFETY: the buffer holds 16 entries and we pass that bound.
    let n = unsafe { rcwfb_list_devices(raw.as_mut_ptr(), raw.len() as c_int) }.clamp(0, 16) as usize;
    raw[..n]
        .iter()
        .map(|d| Adapter {
            // SAFETY: rcwfb always NUL-terminates `name` (snprintf).
            name: unsafe { CStr::from_ptr(d.name.as_ptr()) }.to_string_lossy().into_owned(),
            known: d.known_adapter,
            raw: *d,
        })
        .collect()
}

fn stats() -> RawStats {
    let mut s = RawStats::default();
    // SAFETY: `s` is a valid, writable RawStats.
    unsafe { rcwfb_stats(&mut s) };
    s
}

fn busy_side_port() -> Option<u16> {
    SIDE_PORTS.into_iter().find(|&p| UdpSocket::bind(("0.0.0.0", p)).is_err())
}

fn key_path(cfg: &RadioConfig) -> std::io::Result<PathBuf> {
    if let Some(k) = cfg.key.as_ref().filter(|k| !k.is_empty()) {
        return Ok(PathBuf::from(k));
    }
    let path = std::env::temp_dir().join("rc-control-gs.key");
    std::fs::write(&path, DEFAULT_KEY)?;
    Ok(path)
}

/// The configured adapter by name, or in "auto" mode the first one devourer
/// recognises. The device list covers every USB device on the bus, so auto
/// mode must never fall back to an unrecognised one.
fn pick(adapters: &[Adapter], wanted: &str) -> Option<Adapter> {
    if wanted != "auto" {
        return adapters.iter().find(|a| a.name.contains(wanted)).cloned();
    }
    adapters.iter().find(|a| a.known).cloned()
}

pub struct Shared {
    status: Mutex<Status>,
}

impl Shared {
    pub fn status(&self) -> MutexGuard<'_, Status> {
        self.status.lock().unwrap_or_else(|e| e.into_inner())
    }
}

pub struct Radio {
    pub shared: Arc<Shared>,
    stop: Arc<AtomicBool>,
    handle: Mutex<Option<JoinHandle<()>>>,
}

impl Radio {
    pub fn start(cfg: RadioConfig, video_port: u16) -> Radio {
        let shared = Arc::new(Shared { status: Mutex::new(Status::default()) });
        let stop = Arc::new(AtomicBool::new(false));
        let handle = cfg.enabled.then(|| {
            let (shared, stop) = (shared.clone(), stop.clone());
            std::thread::Builder::new()
                .name("radio".into())
                .spawn(move || supervise(cfg, video_port, shared, stop))
                .expect("spawn radio thread")
        });
        Radio { shared, stop, handle: Mutex::new(handle) }
    }

    /// Stops the link and waits for the adapter to be released. Must run
    /// before the process exits: an adapter abandoned mid-stream fails its
    /// next initialisation.
    pub fn shutdown(&self) {
        self.stop.store(true, Ordering::Relaxed);
        if let Some(h) = self.handle.lock().unwrap_or_else(|e| e.into_inner()).take() {
            let _ = h.join();
        }
    }
}

impl Drop for Radio {
    fn drop(&mut self) {
        self.shutdown();
    }
}

fn wait(stop: &AtomicBool, d: Duration) {
    let until = Instant::now() + d;
    while Instant::now() < until && !stop.load(Ordering::Relaxed) {
        std::thread::sleep(Duration::from_millis(50));
    }
}

fn supervise(cfg: RadioConfig, video_port: u16, shared: Arc<Shared>, stop: Arc<AtomicBool>) {
    // SAFETY: `log_sink` is a plain extern "C" fn valid for the whole program.
    unsafe { rcwfb_set_log(Some(log_sink)) };
    let width_mode = if cfg.width_mhz >= 40 { 1 } else { 0 };
    let set = |f: &dyn Fn(&mut Status)| f(&mut shared.status());
    set(&|s| {
        s.channel = cfg.channel;
        s.width_mhz = if width_mode == 1 { 40 } else { 20 };
    });

    // Once we have run a link ourselves, a busy port means our previous link
    // is still letting go of it rather than another program holding it.
    let mut restarted = false;
    let mut failures = 0u32;
    while !stop.load(Ordering::Relaxed) {
        let Some(adapter) = pick(&list_adapters(), &cfg.adapter) else {
            set(&|s| {
                s.state = State::NoAdapter;
                s.adapter.clear();
            });
            wait(&stop, Duration::from_secs(2));
            continue;
        };
        if let Some(port) = busy_side_port() {
            let msg = if restarted {
                format!("等待上一次连接释放 UDP {port}")
            } else {
                format!("UDP 端口 {port} 被占用，Aviateur 是否还开着？关掉后会自动连接")
            };
            set(&|s| s.state = State::Error(msg.clone()));
            wait(&stop, Duration::from_secs(2));
            continue;
        }
        let key = match key_path(&cfg).map(|p| CString::new(p.to_string_lossy().into_owned())) {
            Ok(Ok(k)) => k,
            _ => {
                set(&|s| s.state = State::Error("无法写入 wfb 密钥文件".into()));
                wait(&stop, Duration::from_secs(5));
                continue;
            }
        };

        let name = adapter.name.clone();
        set(&|s| {
            s.state = State::Starting;
            s.adapter = name.clone();
        });
        // SAFETY: pointers are valid for the duration of the call.
        let ok = unsafe { rcwfb_start(&adapter.raw, cfg.channel, width_mode, key.as_ptr(), video_port as c_int) };
        // A start that fails, or a link that dies before receiving a single
        // frame, means the adapter is not answering.
        let mut failed = |shared: &Shared, msg: String| {
            failures += 1;
            shared.status().state = if failures >= REPLUG_AFTER_FAILURES {
                State::Error("网卡没有响应，请拔下图传网卡再插上".into())
            } else {
                State::Error(msg)
            };
        };
        if !ok {
            let last = recent_log().pop().unwrap_or_default();
            failed(&shared, format!("网卡启动失败 {last}"));
            wait(&stop, Duration::from_secs(3));
            continue;
        }
        set(&|s| {
            s.state = State::Receiving;
            s.since = Some(Instant::now());
        });

        // Poll until stopped, or until the adapter goes away.
        while !stop.load(Ordering::Relaxed) {
            let st = stats();
            {
                let mut s = shared.status();
                s.wifi_frames = st.wifi_frames;
                s.wfb_frames = st.wfb_frames;
                s.rtp_packets = st.rtp_packets;
                s.link_score = st.link_score;
                s.packet_loss = st.packet_loss;
                s.codec = match st.codec {
                    1 => Some("H264"),
                    2 => Some("H265"),
                    _ => None,
                };
            }
            if !st.running {
                break;
            }
            std::thread::sleep(Duration::from_millis(200));
        }
        // SAFETY: stopping an idle or running link is fine.
        unsafe { rcwfb_stop() };
        restarted = true;
        if !stop.load(Ordering::Relaxed) {
            if shared.status().wifi_frames == 0 {
                failed(&shared, "网卡没有响应，正在重试".into());
            } else {
                failures = 0;
                set(&|s| s.state = State::Error("网卡断开，正在重连".into()));
            }
            wait(&stop, Duration::from_secs(2));
        }
    }
    set(&|s| s.state = State::Disabled);
}

/// Centre frequency of a Wi-Fi channel number.
pub fn channel_mhz(ch: u8) -> u32 {
    match ch {
        14 => 2484,
        1..=13 => 2407 + 5 * ch as u32,
        _ => 5000 + 5 * ch as u32,
    }
}

/// Link score on OpenIPC's adaptive-link scale (1000..=2000) as 0..=1.
pub fn score_frac(score: i32) -> f32 {
    ((score - 1000) as f32 / 1000.0).clamp(0.0, 1.0)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn channel_frequencies() {
        assert_eq!(channel_mhz(161), 5805);
        assert_eq!(channel_mhz(36), 5180);
        assert_eq!(channel_mhz(6), 2437);
        assert_eq!(channel_mhz(14), 2484);
    }

    #[test]
    fn score_scale() {
        assert_eq!(score_frac(2000), 1.0);
        assert_eq!(score_frac(800), 0.0);
        assert!((score_frac(1830) - 0.83).abs() < 1e-6);
    }

    fn adapter(name: &str, known: bool) -> Adapter {
        Adapter { name: name.into(), known, raw: RawDevice { vendor_id: 0, product_id: 0, bus_num: 0, port_num: 0, known_adapter: known, name: [0; 128] } }
    }

    #[test]
    fn auto_only_picks_recognised_adapters() {
        let list = [adapter("FT260 [8:1]", false), adapter("RTL8812AU-VS [0:1]", true)];
        assert_eq!(pick(&list, "auto").unwrap().name, "RTL8812AU-VS [0:1]");
        // Only unrelated USB devices present: auto must pick nothing.
        assert!(pick(&[adapter("FT260 [8:1]", false)], "auto").is_none());
        assert_eq!(pick(&list, "FT260").unwrap().name, "FT260 [8:1]");
        assert!(pick(&list, "missing").is_none());
        assert!(pick(&[], "auto").is_none());
    }

    #[test]
    fn default_key_is_bundled() {
        assert!(!DEFAULT_KEY.is_empty());
    }
}
