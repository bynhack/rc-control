//! Backends turn the shared `Control` output into bytes on a serial port.
//! Each runs on its own thread and reconnects on its own after errors.

pub mod elrs;
pub mod rc2;

use crate::config::{BackendKind, Config};
use crate::control::Control;
use crate::protocol::crsf::LinkStats;
use serde::Serialize;
use std::collections::BTreeMap;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex, MutexGuard};
use std::thread::{self, JoinHandle};
use std::time::{Duration, Instant};

#[derive(Debug, Default, Clone, Serialize)]
pub struct Status {
    pub connected: bool,
    pub port: String,
    pub device: String,
    pub error: String,
    /// ELRS link quality, present once the receiver is actually linked.
    pub link: Option<LinkStats>,
    /// RC2 telemetry points; `None` means the sensor is not fitted.
    pub telemetry: BTreeMap<String, Option<f32>>,
    /// Last values put on the wire, in the backend's own units.
    pub sent: BTreeMap<String, f32>,
    pub resets: u32,
    /// Any valid frame has come back from the device since connecting. An
    /// ELRS module wired TX-only (no RX return) never sets this.
    pub replies: bool,
    #[serde(skip)]
    pub connected_at: Option<std::time::Instant>,
}

/// How long a connected device may stay silent before we conclude there is
/// no return path (the ELRS backend pings once a second).
pub const REPLY_GRACE: std::time::Duration = std::time::Duration::from_secs(3);

impl Status {
    /// Connected, but nothing has ever come back: wired transmit-only.
    pub fn tx_only(&self) -> bool {
        self.connected && !self.replies && self.connected_at.is_some_and(|t| t.elapsed() > REPLY_GRACE)
    }
}

pub struct Shared {
    pub control: Mutex<Control>,
    pub status: Mutex<Status>,
}

impl Shared {
    pub fn new(control: Control) -> Self {
        Shared { control: Mutex::new(control), status: Mutex::new(Status::default()) }
    }

    pub fn control(&self) -> MutexGuard<'_, Control> {
        self.control.lock().unwrap_or_else(|e| e.into_inner())
    }

    pub fn status(&self) -> MutexGuard<'_, Status> {
        self.status.lock().unwrap_or_else(|e| e.into_inner())
    }

    pub fn output(&self) -> crate::control::Output {
        self.control().output(Instant::now())
    }
}

pub struct Runner {
    pub kind: BackendKind,
    stop: Arc<AtomicBool>,
    handle: Option<JoinHandle<()>>,
}

impl Runner {
    pub fn start(kind: BackendKind, cfg: &Config, shared: Arc<Shared>) -> Runner {
        *shared.status() = Status::default();
        let stop = Arc::new(AtomicBool::new(false));
        let flag = stop.clone();
        let handle = match kind {
            BackendKind::Elrs => {
                let c = cfg.elrs.clone();
                thread::Builder::new().name("elrs".into()).spawn(move || elrs::run(c, shared, flag))
            }
            BackendKind::Rc2 => {
                let c = cfg.rc2.clone();
                thread::Builder::new().name("rc2".into()).spawn(move || rc2::run(c, shared, flag))
            }
        }
        .expect("spawn backend thread");
        Runner { kind, stop, handle: Some(handle) }
    }

    /// Asks the backend to send neutral, close its port, and waits for it.
    pub fn stop(&mut self) {
        self.stop.store(true, Ordering::Relaxed);
        if let Some(h) = self.handle.take() {
            let _ = h.join();
        }
    }
}

impl Drop for Runner {
    fn drop(&mut self) {
        self.stop();
    }
}

/// Retries `session` until stopped, surfacing each failure in the status.
fn supervise(shared: &Shared, stop: &AtomicBool, mut session: impl FnMut() -> anyhow::Result<()>) {
    while !stop.load(Ordering::Relaxed) {
        if let Err(e) = session() {
            let mut st = shared.status();
            st.connected = false;
            st.link = None;
            st.error = format!("{e:#}");
            drop(st);
            sleep_unless(stop, Duration::from_secs(1));
        }
    }
    shared.status().connected = false;
}

fn sleep_unless(stop: &AtomicBool, total: Duration) {
    let until = Instant::now() + total;
    while Instant::now() < until && !stop.load(Ordering::Relaxed) {
        thread::sleep(Duration::from_millis(20));
    }
}

/// Resolves "auto" to the first serial port with the given USB vendor/product.
/// On macOS the call-out device (/dev/cu.*) is preferred over /dev/tty.*,
/// which blocks waiting for carrier detect.
pub fn find_port(wanted: &str, vid: u16, pid: u16) -> anyhow::Result<String> {
    if wanted != "auto" {
        return Ok(wanted.to_string());
    }
    let mut hits: Vec<String> = serialport::available_ports()?
        .into_iter()
        .filter(|p| matches!(&p.port_type, serialport::SerialPortType::UsbPort(u) if u.vid == vid && u.pid == pid))
        .map(|p| p.port_name)
        .filter(|n| !n.starts_with("/dev/tty."))
        .collect();
    hits.sort();
    hits.into_iter()
        .next()
        .ok_or_else(|| anyhow::anyhow!("没找到 USB 设备 {vid:04x}:{pid:04x}，确认已插上，或在配置里写明端口"))
}

/// Lists serial ports with their USB ids, for `--list-ports`.
pub fn describe_ports() -> Vec<String> {
    serialport::available_ports()
        .unwrap_or_default()
        .into_iter()
        .map(|p| match p.port_type {
            serialport::SerialPortType::UsbPort(u) => format!(
                "{}  usb {:04x}:{:04x}  {}{}",
                p.port_name,
                u.vid,
                u.pid,
                u.product.unwrap_or_default(),
                u.serial_number.map(|s| format!("  sn {s}")).unwrap_or_default()
            ),
            _ => p.port_name,
        })
        .collect()
}
