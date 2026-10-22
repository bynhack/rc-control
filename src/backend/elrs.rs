//! ExpressLRS TX module over CRSF. Streams a full 16-channel frame at a fixed
//! interval: the steady stream is what tells the module a handset is present,
//! and every frame carries the complete state, so a lost frame self-heals.

use super::{supervise, Shared};
use anyhow::Context;
use crate::config::ElrsConfig;
use crate::protocol::crsf::{self, Event, CHANNELS, CH_CENTER};
use std::io::{ErrorKind, Read, Write};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant};

/// WCH CH9102, the USB-serial chip on the Jumper AION Nano.
const USB_VID: u16 = 0x1a86;
const USB_PID: u16 = 0x55d4;

pub fn run(cfg: ElrsConfig, shared: Arc<Shared>, stop: Arc<AtomicBool>) {
    supervise(&shared, &stop, || session(&cfg, &shared, &stop));
}

pub fn channels(cfg: &ElrsConfig, steering: f32, throttle: f32) -> [u16; CHANNELS] {
    let mut ch = [CH_CENTER; CHANNELS];
    let sign = |inv: bool| if inv { -1.0 } else { 1.0 };
    ch[cfg.steering_channel - 1] = crsf::to_channel(steering * sign(cfg.steering_invert));
    ch[cfg.throttle_channel - 1] = crsf::to_channel(throttle * sign(cfg.throttle_invert));
    ch
}

fn session(cfg: &ElrsConfig, shared: &Shared, stop: &AtomicBool) -> anyhow::Result<()> {
    let name = super::find_port(&cfg.port, USB_VID, USB_PID)?;
    let mut port = serialport::new(&name, cfg.baud)
        .timeout(Duration::from_millis(1))
        .open()
        .with_context(|| format!("打开高频头串口 {name} 失败"))?;
    // Keep EN/IO0 released; the module still reboots once when the port opens.
    port.write_data_terminal_ready(false)?;
    port.write_request_to_send(false)?;
    {
        let mut st = shared.status();
        st.connected = true;
        st.port = name;
        st.device.clear();
        st.error.clear();
    }

    let interval = Duration::from_millis(cfg.frame_interval_ms);
    let mut next_frame = Instant::now();
    let mut next_ping = Instant::now() + Duration::from_millis(450);
    let mut parser = crsf::Parser::default();
    let mut buf = [0u8; 512];

    loop {
        if stop.load(Ordering::Relaxed) {
            // A few neutral frames, then silence: the receiver drops to failsafe.
            let neutral = crsf::rc_frame(&[CH_CENTER; CHANNELS]);
            for _ in 0..3 {
                let _ = port.write_all(&neutral);
                std::thread::sleep(interval);
            }
            return Ok(());
        }

        let now = Instant::now();
        if now >= next_frame {
            let out = shared.output();
            let ch = channels(cfg, out.steering, out.throttle);
            port.write_all(&crsf::rc_frame(&ch))?;
            next_frame += interval;
            if next_frame < now {
                next_frame = now + interval; // we fell behind; don't burst
            }
            let mut st = shared.status();
            st.sent.clear();
            for (label, idx) in [("转向", cfg.steering_channel), ("油门", cfg.throttle_channel)] {
                st.sent.insert(format!("{label} ch{idx}"), ch[idx - 1] as f32);
                st.sent.insert(format!("{label} µs"), crsf::channel_us(ch[idx - 1]) as f32);
            }
        }
        if now >= next_ping {
            port.write_all(&crsf::ping_frame())?;
            next_ping = now + Duration::from_secs(1);
        }

        match port.read(&mut buf) {
            Ok(n) if n > 0 => apply(shared, parser.push(&buf[..n])),
            Ok(_) => {}
            Err(e) if e.kind() == ErrorKind::TimedOut => {}
            Err(e) => return Err(e.into()),
        }
    }
}

fn apply(shared: &Shared, events: Vec<Event>) {
    if events.is_empty() {
        return;
    }
    let mut st = shared.status();
    for ev in events {
        match ev {
            Event::LinkStats(l) => st.link = Some(l),
            Event::DeviceName(n) => st.device = n,
            Event::ModuleReset { brownout } => {
                st.resets += 1;
                st.link = None;
                if brownout {
                    st.error = "高频头复位，可能是供电不足（换短线或换 USB 口）".into();
                }
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn maps_onto_configured_channels() {
        let cfg = ElrsConfig { steering_channel: 1, throttle_channel: 2, ..Default::default() };
        let ch = channels(&cfg, 1.0, -1.0);
        assert_eq!((ch[0], ch[1], ch[2]), (1811, 172, 992));
    }

    #[test]
    fn invert_flips_direction() {
        let cfg = ElrsConfig { steering_invert: true, throttle_channel: 3, ..Default::default() };
        let ch = channels(&cfg, 1.0, 0.5);
        assert_eq!(ch[0], 172);
        assert_eq!(ch[1], 992);
        assert_eq!(ch[2], crsf::to_channel(0.5));
    }
}
