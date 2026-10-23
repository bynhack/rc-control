//! MR-RC2 controller. Its protocol is request/response with an ACK per char
//! (~40 ms per write), so instead of streaming we write only what changed,
//! refresh periodically, and read one telemetry point at a time in between so
//! control writes never queue behind a full telemetry sweep.

use super::{supervise, Invert, Shared};
use crate::config::BackendKind;
use crate::config::Rc2Config;
use crate::protocol::rc2::{Rc2, NOT_CONNECTED};
use anyhow::Context;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant};

/// WCH CH340.
pub const USB_VID: u16 = 0x1a86;
pub const USB_PID: u16 = 0x7523;

pub const DIRECTION_MAX: f32 = 39.0;
pub const SWITCH_MAX: f32 = 50.0;
const TELEMETRY_SWEEP: Duration = Duration::from_millis(350);

pub fn run(cfg: Rc2Config, shared: Arc<Shared>, stop: Arc<AtomicBool>) {
    supervise(&shared, &stop, || session(&cfg, &shared, &stop));
}

/// Device units: Direction -39..39, Switch -50..50 (signed drive).
pub fn targets(invert: Invert, steering: f32, throttle: f32) -> (i32, i32) {
    let (steering, throttle) = invert.apply(steering, throttle);
    ((steering * DIRECTION_MAX).round() as i32, (throttle * SWITCH_MAX).round() as i32)
}

fn index_of(names: &[String], want: &str) -> anyhow::Result<usize> {
    names
        .iter()
        .position(|n| n.eq_ignore_ascii_case(want))
        .with_context(|| format!("设备没有控制点 {want}（设备上报 {names:?}）"))
}

fn session(cfg: &Rc2Config, shared: &Shared, stop: &AtomicBool) -> anyhow::Result<()> {
    let name = super::find_port(&cfg.port, USB_VID, USB_PID)?;
    let port = serialport::new(&name, cfg.baud)
        .timeout(Duration::from_millis(400))
        .open()
        .with_context(|| format!("打开 RC2 串口 {name} 失败"))?;
    let mut dev = Rc2::new(port);

    let model = dev.model().context("读取型号失败（端口或波特率不对？）")?;
    let upper = model.to_uppercase();
    anyhow::ensure!(upper.starts_with("OGESS") || upper.starts_with("MR-"), "{name} 上不是 RC2 控制器（型号 {model:?}）");
    let fw = dev.firmware()?;
    let sn = dev.serial()?;
    let cps = dev.cp_names()?;
    let (i_dir, i_sw, i_st) = (index_of(&cps, "Direction")?, index_of(&cps, "Switch")?, index_of(&cps, "Status")?);
    let aps = dev.ap_names().unwrap_or_default();
    {
        let mut st = shared.status();
        st.connected = true;
        st.port = name;
        st.device = format!("{model} · 固件 {fw}\nSN {sn}");
        st.error.clear();
    }

    let refresh = Duration::from_millis(cfg.refresh_ms);
    let mut written: Option<(i32, i32, u8)> = None;
    let mut last_write = Instant::now();
    let mut ap_cursor = 0;
    let mut next_sweep = Instant::now();

    loop {
        if stop.load(Ordering::Relaxed) {
            // Drive first, then steering, then lights; no slew on the way to 0.
            let _ = dev.set_cp(i_sw, 0.0, None);
            let _ = dev.set_cp(i_dir, 0.0, None);
            let _ = dev.set_cp(i_st, 0.0, None);
            return Ok(());
        }

        let out = shared.output();
        let (dir, sw) = targets(shared.invert(BackendKind::Rc2), out.steering, out.throttle);
        let target = (dir, sw, out.lights);
        let due = last_write.elapsed() >= refresh;

        if written != Some(target) || due {
            let prev = if due { None } else { written };
            if prev.map(|p| p.1) != Some(sw) {
                // Stopping is never slewed.
                let rate = (sw != 0).then_some(cfg.throttle_rate);
                dev.set_cp(i_sw, sw as f32, rate)?;
            }
            if prev.map(|p| p.0) != Some(dir) {
                dev.set_cp(i_dir, dir as f32, None)?;
            }
            if prev.map(|p| p.2) != Some(out.lights) {
                dev.set_cp(i_st, out.lights as f32, None)?;
            }
            written = Some(target);
            last_write = Instant::now();
            let mut st = shared.status();
            st.sent.clear();
            st.sent.insert("Direction".into(), dir as f32);
            st.sent.insert("Switch".into(), sw as f32);
            st.sent.insert("Status".into(), out.lights as f32);
            continue;
        }

        if !aps.is_empty() && Instant::now() >= next_sweep {
            let v = dev.get_ap(ap_cursor).ok().filter(|&v| v != NOT_CONNECTED);
            shared.status().telemetry.insert(aps[ap_cursor].clone(), v);
            ap_cursor += 1;
            if ap_cursor == aps.len() {
                ap_cursor = 0;
                next_sweep = Instant::now() + TELEMETRY_SWEEP;
            }
            continue;
        }

        std::thread::sleep(Duration::from_millis(2));
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn scales_to_device_units() {
        assert_eq!(targets(Invert::default(), 1.0, -1.0), (39, -50));
        assert_eq!(targets(Invert::default(), 0.5, 0.34), (20, 17));
        assert_eq!(targets(Invert { steering: true, throttle: false }, 1.0, 0.0), (-39, 0));
        assert_eq!(targets(Invert { steering: false, throttle: true }, 0.0, 0.5), (0, -25));
    }
}
