//! Video downlink: UDP RTP in, newest decoded picture out.
//!
//! Today the radio side is Aviateur (or wfb-ng) forwarding the stream to a
//! local UDP port; the receiver doesn't care who sends it.

pub mod decoder;
pub mod rtp;

use crate::config::VideoConfig;
use std::collections::VecDeque;
use std::net::UdpSocket;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex, MutexGuard};
use std::thread::JoinHandle;
use std::time::{Duration, Instant};

/// Video counts as live while frames keep arriving within this window.
pub const LIVE_WINDOW: Duration = Duration::from_secs(1);

pub struct Frame {
    pub id: u64,
    pub width: usize,
    pub height: usize,
    pub rgba: Vec<u8>,
}

#[derive(Debug, Clone, Default)]
pub struct Stats {
    pub port: u16,
    pub codec: String,
    pub width: usize,
    pub height: usize,
    pub fps: f32,
    pub kbps: f32,
    /// Time from the last packet of a frame to its decoded RGBA.
    pub decode_ms: f32,
    pub frames: u64,
    /// Datagrams that parsed as RTP, and access units reassembled from them.
    pub packets: u64,
    pub units: u64,
    /// RTP payload type of the stream (OpenIPC: 96 = H.264, 97 = H.265 by default).
    pub payload_type: Option<u8>,
    /// Which NAL unit types have been seen, by codec numbering.
    pub nal_types: std::collections::BTreeSet<u8>,
    pub last_frame: Option<Instant>,
    pub error: String,
}

impl Stats {
    pub fn live(&self, now: Instant) -> bool {
        self.last_frame.is_some_and(|t| now.duration_since(t) < LIVE_WINDOW)
    }
}

#[derive(Default)]
pub struct Shared {
    latest: Mutex<Option<Frame>>,
    stats: Mutex<Stats>,
}

impl Shared {
    pub fn stats(&self) -> MutexGuard<'_, Stats> {
        self.stats.lock().unwrap_or_else(|e| e.into_inner())
    }

    /// Hands the newest frame to the caller if it is newer than `seen`.
    pub fn take_newer(&self, seen: u64) -> Option<Frame> {
        let mut slot = self.latest.lock().unwrap_or_else(|e| e.into_inner());
        if slot.as_ref().is_some_and(|f| f.id > seen) { slot.take() } else { None }
    }
}

pub struct Receiver {
    stop: Arc<AtomicBool>,
    handle: Option<JoinHandle<()>>,
}

impl Receiver {
    pub fn start(cfg: VideoConfig, shared: Arc<Shared>) -> Receiver {
        let stop = Arc::new(AtomicBool::new(false));
        let flag = stop.clone();
        let handle = std::thread::Builder::new()
            .name("video".into())
            .spawn(move || run(cfg, shared, flag))
            .expect("spawn video thread");
        Receiver { stop, handle: Some(handle) }
    }
}

impl Drop for Receiver {
    fn drop(&mut self) {
        self.stop.store(true, Ordering::Relaxed);
        if let Some(h) = self.handle.take() {
            let _ = h.join();
        }
    }
}

/// Counts events within the last second.
#[derive(Default)]
struct Window(VecDeque<(Instant, usize)>);

impl Window {
    fn add(&mut self, now: Instant, n: usize) {
        self.0.push_back((now, n));
        while self.0.front().is_some_and(|(t, _)| now.duration_since(*t) > Duration::from_secs(1)) {
            self.0.pop_front();
        }
    }
    fn count(&self) -> usize {
        self.0.len()
    }
    fn sum(&self) -> usize {
        self.0.iter().map(|(_, n)| n).sum()
    }
}

fn run(cfg: VideoConfig, shared: Arc<Shared>, stop: Arc<AtomicBool>) {
    {
        let mut st = shared.stats();
        st.port = cfg.port;
        st.codec = format!("{:?}", cfg.codec).to_uppercase();
    }
    let socket = loop {
        match UdpSocket::bind(("0.0.0.0", cfg.port)) {
            Ok(s) => break s,
            Err(e) => {
                shared.stats().error = format!("无法监听 UDP {}：{e}", cfg.port);
                for _ in 0..50 {
                    if stop.load(Ordering::Relaxed) {
                        return;
                    }
                    std::thread::sleep(Duration::from_millis(20));
                }
            }
        }
    };
    let _ = socket.set_read_timeout(Some(Duration::from_millis(100)));
    shared.stats().error.clear();

    let mut depack = rtp::Depacketizer::new(cfg.codec);
    let mut decoder = match decoder::Decoder::new(cfg.codec) {
        Ok(d) => d,
        Err(e) => {
            shared.stats().error = format!("{e:#}");
            return;
        }
    };
    let mut buf = vec![0u8; 65536];
    let (mut frames_win, mut bytes_win) = (Window::default(), Window::default());
    let mut id = 0u64;

    while !stop.load(Ordering::Relaxed) {
        let n = match socket.recv(&mut buf) {
            Ok(n) => n,
            Err(_) => continue, // timeout: just re-check `stop`
        };
        let now = Instant::now();
        bytes_win.add(now, n);
        let pt = rtp::parse(&buf[..n]).map(|r| r.payload_type);
        let au = depack.push(&buf[..n]);
        {
            let mut st = shared.stats();
            st.kbps = bytes_win.sum() as f32 * 8.0 / 1000.0;
            st.packets += pt.is_some() as u64;
            st.units += au.is_some() as u64;
            if pt.is_some() {
                st.payload_type = pt;
            }
            if let Some(au) = &au {
                if st.nal_types.len() < 32 {
                    st.nal_types.extend(rtp::nal_types(au, cfg.codec));
                }
            }
        }
        let Some(au) = au else { continue };
        let Some(pic) = decoder.decode(&au) else { continue };
        let done = Instant::now();
        id += 1;
        frames_win.add(done, 1);
        {
            let mut st = shared.stats();
            st.width = pic.width;
            st.height = pic.height;
            st.fps = frames_win.count() as f32;
            st.kbps = bytes_win.sum() as f32 * 8.0 / 1000.0;
            st.decode_ms = done.duration_since(now).as_secs_f32() * 1000.0;
            st.frames = id;
            st.last_frame = Some(done);
        }
        *shared.latest.lock().unwrap_or_else(|e| e.into_inner()) =
            Some(Frame { id, width: pic.width, height: pic.height, rgba: pic.pixels });
    }
}
