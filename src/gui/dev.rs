//! Development aids, both off unless their environment variable is set:
//!
//! - `RC_CONTROL_SNAPSHOT=out.bmp` saves one rendered frame after ~1.5 s
//!   (`RC_CONTROL_SNAPSHOT_FRAMES` overrides the 90-frame wait).
//! - `RC_CONTROL_DEMO=steer,throttle[,low|mid|high]` (each -1..1) fakes input
//!   for UI review.
//!   It refuses to act while a device is connected, so it can never move a
//!   real car; use it with ports that do not exist.

use crate::control::Speed;
use eframe::egui::{self, ViewportCommand};
use std::path::{Path, PathBuf};

const SNAPSHOT_AFTER_FRAMES: u32 = 90;
const DEMO_ARM_FRAME: u32 = 20;

#[derive(Default)]
pub struct Dev {
    snapshot: Option<PathBuf>,
    snapshot_after: u32,
    requested: bool,
    demo: Option<(f32, f32)>,
    demo_speed: Option<Speed>,
    frames: u32,
}

/// Demo input for this frame.
pub struct DemoInput {
    pub steering: f32,
    pub throttle: f32,
    pub arm: bool,
    pub speed: Option<Speed>,
}

impl Dev {
    pub fn from_env() -> Self {
        let snapshot = std::env::var_os("RC_CONTROL_SNAPSHOT").map(PathBuf::from);
        let spec = std::env::var("RC_CONTROL_DEMO").unwrap_or_default();
        let mut parts = spec.split(',').map(str::trim);
        let mut num = || parts.next()?.parse::<f32>().ok().map(|v| v.clamp(-1.0, 1.0));
        let demo = num().zip(num());
        let demo_speed = match parts.next() {
            Some("mid") => Some(Speed::Mid),
            Some("high") => Some(Speed::High),
            Some("low") => Some(Speed::Low),
            _ => None,
        };
        let snapshot_after = std::env::var("RC_CONTROL_SNAPSHOT_FRAMES")
            .ok()
            .and_then(|v| v.parse().ok())
            .unwrap_or(SNAPSHOT_AFTER_FRAMES);
        Dev { snapshot, snapshot_after, demo, demo_speed, ..Default::default() }
    }

    /// Neutral until the arm frame, armed with neutral input, then the demo values.
    pub fn demo_input(&mut self, device_connected: bool) -> Option<DemoInput> {
        if device_connected && self.demo.take().is_some() {
            eprintln!("有设备连接，已忽略 RC_CONTROL_DEMO");
        }
        let (steering, throttle) = self.demo?;
        let speed = self.demo_speed;
        Some(match self.frames {
            f if f < DEMO_ARM_FRAME => DemoInput { steering: 0.0, throttle: 0.0, arm: false, speed },
            DEMO_ARM_FRAME => DemoInput { steering: 0.0, throttle: 0.0, arm: true, speed },
            _ => DemoInput { steering, throttle, arm: false, speed },
        })
    }

    pub fn end_frame(&mut self, ctx: &egui::Context) {
        self.frames += 1;
        let Some(path) = &self.snapshot else { return };
        if !self.requested && self.frames >= self.snapshot_after {
            ctx.send_viewport_cmd(ViewportCommand::Screenshot(Default::default()));
            self.requested = true;
        }
        let image = ctx.input(|i| {
            i.raw.events.iter().find_map(|e| match e {
                egui::Event::Screenshot { image, .. } => Some(image.clone()),
                _ => None,
            })
        });
        if let Some(image) = image {
            match write_bmp(path, &image) {
                Ok(()) => println!("已保存截图 {}", path.display()),
                Err(e) => eprintln!("截图保存失败：{e}"),
            }
            self.snapshot = None;
        }
    }
}

/// 24-bit uncompressed BMP; readable everywhere without an image crate.
fn write_bmp(path: &Path, img: &egui::ColorImage) -> std::io::Result<()> {
    let [w, h] = img.size;
    let row = (w * 3 + 3) & !3;
    let size = 54 + row * h;
    let mut b = Vec::with_capacity(size);
    b.extend_from_slice(b"BM");
    b.extend_from_slice(&(size as u32).to_le_bytes());
    b.extend_from_slice(&[0; 4]);
    b.extend_from_slice(&54u32.to_le_bytes());
    b.extend_from_slice(&40u32.to_le_bytes());
    b.extend_from_slice(&(w as i32).to_le_bytes());
    b.extend_from_slice(&(h as i32).to_le_bytes());
    b.extend_from_slice(&1u16.to_le_bytes());
    b.extend_from_slice(&24u16.to_le_bytes());
    b.extend_from_slice(&[0; 24]);
    for y in (0..h).rev() {
        for c in &img.pixels[y * w..(y + 1) * w] {
            b.extend_from_slice(&[c.b(), c.g(), c.r()]);
        }
        b.resize(b.len() + row - w * 3, 0);
    }
    std::fs::write(path, b)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn demo_never_runs_with_a_device_connected() {
        let mut d = Dev { demo: Some((0.5, 0.8)), frames: 50, ..Default::default() };
        assert!(d.demo_input(true).is_none());
        // And it stays off even if the device goes away again.
        assert!(d.demo_input(false).is_none());
    }

    #[test]
    fn demo_arms_with_neutral_input_first() {
        let mut d = Dev { demo: Some((0.5, 0.8)), ..Default::default() };
        d.frames = DEMO_ARM_FRAME;
        let i = d.demo_input(false).unwrap();
        assert!(i.arm && i.throttle == 0.0);
        d.frames += 1;
        let i = d.demo_input(false).unwrap();
        assert!(!i.arm && i.throttle == 0.8);
    }
}
