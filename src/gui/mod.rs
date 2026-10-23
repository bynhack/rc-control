//! Native control window: a dark racing-dash style layout painted directly
//! with egui. Every frame feeds the current input into `Control`, which is
//! also the heartbeat: if the window stops updating (minimized, hung), the
//! watchdog centers and disarms the car.

mod dev;
mod theme;
mod widgets;

use crate::backend::{Invert, Shared, Status};
use crate::config::Config;
use crate::control::{ControlView, Speed};
use crate::{radio, video};
use eframe::egui::{
    self, pos2, vec2, Align2, Color32, Key, Modifiers, Painter, Rect, Sense, Stroke, StrokeKind, Ui, ViewportCommand,
};
use std::collections::VecDeque;
use std::sync::Arc;
use std::time::{Duration, Instant};
use theme::*;
use widgets::*;

const ARM_CONFIRM: Duration = Duration::from_secs(3);
const NOTE_TTL: Duration = Duration::from_secs(4);
const ESTOP_FLASH: f32 = 0.6;
/// Link history: one sample every 250 ms, 30 s kept.
const HISTORY_LEN: usize = 120;
const HISTORY_EVERY: Duration = Duration::from_millis(250);

/// 中位死区：|v| 在 dz 里归零，之外线性保持到 ±1。
fn deadzone(v: f32, dz: f32) -> f32 {
    let dz = dz.clamp(0.0, 0.5);
    if v.abs() <= dz {
        0.0
    } else {
        (v - v.signum() * dz) / (1.0 - dz)
    }
}

#[cfg(test)]
mod deadzone_tests {
    use super::deadzone;

    #[test]
    fn deadzone_zeroes_small_and_keeps_full_range() {
        assert_eq!(deadzone(0.01, 0.02), 0.0);
        assert_eq!(deadzone(-0.02, 0.02), 0.0);
        assert!((deadzone(1.0, 0.02) - 1.0).abs() < 1e-6);
        assert!((deadzone(-1.0, 0.02) + 1.0).abs() < 1e-6);
        assert!(deadzone(0.03, 0.02) > 0.0 && deadzone(0.03, 0.02) < 0.03);
    }
}


/// Display values eased toward their targets, so the dash moves smoothly.
/// Numeric readouts always show the exact values.
#[derive(Default)]
struct Anim {
    output: f32,
    demand: f32,
    steer: f32,
}

pub struct Gui {
    cfg: Config,
    /// Where direction changes are saved.
    config_path: std::path::PathBuf,
    shared: Arc<Shared>,
    /// Input positions, -1..=1.
    steering: f32,
    throttle: f32,
    arm_confirm_until: Option<Instant>,
    note: Option<(String, Instant)>,
    estop_flash: Option<Instant>,
    anim: Anim,
    /// (uplink, downlink) link quality, 0..=1.
    history: VecDeque<(f32, f32)>,
    last_sample: Instant,
    video: Arc<video::Shared>,
    video_tex: Option<egui::TextureHandle>,
    video_seen: u64,
    radio: Arc<radio::Shared>,
    dev: dev::Dev,
    /// 方向盘后台读取；None 表示没启用或启动失败（错误在 note 里）。
    wheel: Option<crate::wheel::Live>,
}

impl Gui {
    pub fn new(
        cfg: Config,
        config_path: std::path::PathBuf,
        shared: Arc<Shared>,
        video: Arc<video::Shared>,
        radio: Arc<radio::Shared>,
    ) -> Self {
        let (wheel, wheel_error) = if cfg.wheel.enabled {
            match crate::wheel::Live::start() {
                Ok(w) => (Some(w), None),
                Err(e) => (None, Some(format!("方向盘输入不可用：{e}"))),
            }
        } else {
            (None, None)
        };
        let now = Instant::now();
        Gui {
            cfg,
            config_path,
            shared,
            steering: 0.0,
            throttle: 0.0,
            arm_confirm_until: None,
            note: wheel_error.map(|e| (e, now)),
            estop_flash: None,
            anim: Anim::default(),
            history: VecDeque::with_capacity(HISTORY_LEN),
            last_sample: Instant::now(),
            video,
            video_tex: None,
            video_seen: 0,
            radio,
            dev: dev::Dev::from_env(),
            wheel,
        }
    }

    fn estop(&mut self) {
        self.steering = 0.0;
        self.throttle = 0.0;
        self.arm_confirm_until = None;
        self.estop_flash = Some(Instant::now());
        self.shared.control().estop();
    }

    /// Arming takes two clicks within `ARM_CONFIRM`; disarming takes one.
    fn arm_clicked(&mut self, armed: bool) {
        let now = Instant::now();
        if armed {
            self.shared.control().disarm("手动锁定");
            return;
        }
        match self.arm_confirm_until {
            Some(t) if now <= t => {
                self.arm_confirm_until = None;
                let res = self.shared.control().arm(now);
                if let Err(e) = res {
                    self.note = Some((e, now));
                }
            }
            _ => self.arm_confirm_until = Some(now + ARM_CONFIRM),
        }
    }
}

impl eframe::App for Gui {
    fn update(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        // Taken before any widget sees it, so Space can never "click" a
        // focused button such as the arm button.
        if ctx.input_mut(|i| i.consume_key(Modifiers::NONE, Key::Space)) {
            self.estop();
        }

        let now = Instant::now();
        let connected = self.shared.status().connected;
        let demo = self.dev.demo_input(connected);
        if let Some(d) = &demo {
            self.steering = d.steering;
            self.throttle = d.throttle;
        }
        // 方向盘有 250 ms 内的新输入就接管（盘上数值优先于调试页滑条，
        // 也压过 demo 值：方向盘是用来真开的）。
        if let Some(w) = &self.wheel {
            if let Some(a) = w.poll(Duration::from_millis(250)) {
                let s0 = if self.cfg.wheel.steering_invert { -a.steering } else { a.steering };
                self.steering = deadzone(s0, self.cfg.wheel.steering_deadzone);
                self.throttle = if self.cfg.wheel.throttle_invert { -a.throttle } else { a.throttle };
            }
        }
        {
            let mut c = self.shared.control();
            c.input(self.steering, self.throttle, now);
            if let Some(d) = demo.as_ref().filter(|d| d.arm) {
                if let Some(s) = d.speed {
                    c.set_speed(s);
                }
                let _ = c.arm(now);
            }
        }
        let view = self.shared.control().view(now);
        let status = self.shared.status().clone();
        if self.arm_confirm_until.is_some_and(|t| now > t) {
            self.arm_confirm_until = None;
        }
        if self.note.as_ref().is_some_and(|(_, t)| now.duration_since(*t) > NOTE_TTL) {
            self.note = None;
        }

        if now.duration_since(self.last_sample) >= HISTORY_EVERY {
            self.last_sample = now;
            let sample = status.link.map(|l| (l.up_lq as f32 / 100.0, l.down_lq as f32 / 100.0));
            if self.history.len() == HISTORY_LEN {
                self.history.pop_front();
            }
            self.history.push_back(sample.unwrap_or((0.0, 0.0)));
        }

        // Newest decoded picture into the texture, at most once per frame.
        if let Some(f) = self.video.take_newer(self.video_seen) {
            self.video_seen = f.id;
            let img = egui::ColorImage::from_rgba_unmultiplied([f.width, f.height], &f.rgba);
            match &mut self.video_tex {
                Some(t) => t.set(img, egui::TextureOptions::LINEAR),
                None => self.video_tex = Some(ctx.load_texture("video", img, egui::TextureOptions::LINEAR)),
            }
        }
        let vstats = self.video.stats().clone();
        let live = vstats.live(now) && self.video_tex.is_some();

        let (dt, time) = ctx.input(|i| (i.stable_dt.min(0.1), i.time));
        let k = 1.0 - (-dt * 14.0).exp();
        self.anim.output += (view.output.throttle - self.anim.output) * k;
        let demand = view.throttle_demand * view.speed.scale();
        self.anim.demand += (demand - self.anim.demand) * k;
        self.anim.steer += (view.output.steering - self.anim.steer) * k;

        egui::CentralPanel::default().frame(egui::Frame::NONE).show(ctx, |ui| {
            let full = ui.max_rect();
            let p = ui.painter().clone();
            backdrop(&p, full);

            let top = Rect::from_min_size(full.min, vec2(full.width(), 64.0));
            // The content runs under the macOS title bar, so the top bar moves
            // the window. Registered first so its buttons sit on top of it.
            let drag = ui.interact(top, ui.id().with("titlebar"), Sense::click_and_drag());
            if drag.drag_started() {
                ctx.send_viewport_cmd(ViewportCommand::StartDrag);
            }
            self.top_bar(ui, &p, top, &status, &view, time);

            let (pad, gap, input_h) = (16.0, 14.0, 150.0);
            let content = Rect::from_min_max(
                pos2(full.left() + pad, top.bottom() + gap),
                pos2(full.right() - pad, full.bottom() - pad),
            );
            let main = Rect::from_min_max(content.min, pos2(content.right(), content.bottom() - input_h - gap));
            let input = Rect::from_min_max(pos2(content.left(), main.bottom() + gap), content.max);
            let left = Rect::from_min_size(main.min, vec2(262.0, main.height()));
            let right = Rect::from_min_max(pos2(main.right() - 292.0, main.top()), main.max);
            let center = Rect::from_min_max(pos2(left.right() + gap, main.top()), pos2(right.left() - gap, main.bottom()));

            let radio = self.radio.status().clone();
            link_panel(&p, left, &status, &view, &radio, &self.history, time);
            // Video style while frames arrive, the gauge dashboard otherwise.
            match (&self.video_tex, live) {
                (Some(tex), true) => self.video_panel(&p, center, tex.id(), &vstats, &view, time),
                _ => self.drive_panel(&p, center, &view, time),
            }
            self.control_panel(ui, &p, right, &status, &view, time);
            self.input_panel(ui, &p, input);

            if let Some(t) = self.estop_flash {
                let e = now.duration_since(t).as_secs_f32();
                if e < ESTOP_FLASH {
                    let a = 1.0 - e / ESTOP_FLASH;
                    p.rect_stroke(full.shrink(2.0), 10.0, stroke(5.0, alpha(RED, a)), StrokeKind::Inside);
                    p.rect_filled(full, 0.0, glow(RED, 0.10 * a));
                } else {
                    self.estop_flash = None;
                }
            }
        });

        self.dev.end_frame(ctx);
        ctx.request_repaint_after(Duration::from_millis(16));
    }
}

// ---------- panels ----------

impl Gui {
    #[allow(clippy::too_many_arguments)]
    fn top_bar(&mut self, ui: &mut Ui, p: &Painter, rect: Rect, st: &Status, view: &ControlView, time: f64) {
        p.rect_filled(rect, 0.0, Color32::from_rgba_unmultiplied(11, 15, 22, 240));
        let cy = rect.center().y;
        // Leave room for the macOS traffic lights drawn over the content.
        let mut x = rect.left() + if cfg!(target_os = "macos") { 90.0 } else { 22.0 };

        for (i, col) in [CYAN, BLUE].into_iter().enumerate() {
            let ox = x + i as f32 * 9.0;
            p.add(egui::Shape::convex_polygon(
                vec![pos2(ox, cy + 13.0), pos2(ox + 8.0, cy - 13.0), pos2(ox + 14.0, cy - 13.0), pos2(ox + 6.0, cy + 13.0)],
                col,
                Stroke::NONE,
            ));
        }
        x += 34.0;
        let brand = spaced(p, pos2(x, cy - 7.0), Align2::LEFT_CENTER, "RC CONTROL", display(19.0), TEXT, 2.5);
        p.text(pos2(x, cy + 12.0), Align2::LEFT_CENTER, "遥控车控制台", body(11.0), TEXT_DIM);
        x = brand.right() + 34.0;

        // Scheme badge: ELRS over CRSF, and the configured line rate.
        let badge = Rect::from_min_size(pos2(x, cy - 15.0), vec2(78.0, 30.0));
        rect_glow(p, badge, 8.0, CYAN, 0.5);
        p.rect(badge, 8.0, tint(CYAN), stroke(1.0, CYAN), StrokeKind::Inside);
        spaced(p, badge.center(), Align2::CENTER_CENTER, "ELRS", display(14.0), CYAN, 1.2);
        p.text(
            pos2(badge.right() + 12.0, cy),
            Align2::LEFT_CENTER,
            format!("CRSF · {} bps", self.cfg.elrs.baud),
            display(13.0),
            TEXT_DIM,
        );

        // Emergency stop.
        let es = Rect::from_min_size(pos2(rect.right() - 22.0 - 204.0, cy - 21.0), vec2(204.0, 42.0));
        let resp = hit(ui, es, "estop");
        rect_glow(p, es, 10.0, RED, if resp.hovered() { 1.5 } else { 0.9 });
        let fill = if resp.is_pointer_button_down_on() {
            Color32::from_rgb(160, 28, 26)
        } else if resp.hovered() {
            Color32::from_rgb(238, 54, 48)
        } else {
            Color32::from_rgb(212, 40, 36)
        };
        p.rect_filled(es, 10.0, fill);
        p.text(pos2(es.left() + 18.0, es.center().y), Align2::LEFT_CENTER, "急停", bold(19.0), Color32::WHITE);
        spaced(p, pos2(es.left() + 66.0, es.center().y), Align2::LEFT_CENTER, "E-STOP", display(13.0), Color32::WHITE, 1.5);
        let kc = Rect::from_min_size(pos2(es.right() - 64.0, es.center().y - 11.0), vec2(52.0, 22.0));
        p.rect(kc, 5.0, Color32::from_black_alpha(50), stroke(1.0, alpha(Color32::WHITE, 0.6)), StrokeKind::Inside);
        spaced(p, kc.center(), Align2::CENTER_CENTER, "SPACE", display(10.0), Color32::WHITE, 1.0);
        if resp.clicked() {
            self.estop();
        }

        // Connection chip, right-aligned against the e-stop.
        let chip_right = es.left() - 22.0;
        let (label, col) = if st.connected { ("已连接", GREEN) } else { ("未连接", RED) };
        let a = p.text(pos2(chip_right, cy - 8.0), Align2::RIGHT_CENTER, label, bold(13.0), col);
        let port = if st.port.is_empty() { "—" } else { st.port.as_str() };
        let b = p.text(pos2(chip_right, cy + 10.0), Align2::RIGHT_CENTER, port, mono(11.0), TEXT_DIM);
        let dot = pos2(a.left().min(b.left()) - 14.0, cy);
        if st.connected {
            let pulse = 0.5 + 0.5 * (time * 2.5).sin() as f32;
            radial_glow(p, dot, 14.0, glow(GREEN, 0.3 + 0.4 * pulse));
        }
        p.circle_filled(dot, 4.5, col);

        let speed = if view.armed { 0.4 + self.anim.output.abs() * 1.6 } else { 0.0 };
        flow_line(p, rect.bottom() - 0.5, rect.left(), rect.right(), if view.armed { ORANGE } else { CYAN }, time, speed);
    }

    fn drive_panel(&self, p: &Painter, rect: Rect, view: &ControlView, time: f64) {
        panel(p, rect);
        section_title(p, pos2(rect.left() + 18.0, rect.top() + 16.0), "驾驶", "DRIVE");

        let steer = Rect::from_min_max(pos2(rect.left() + 14.0, rect.bottom() - 86.0), pos2(rect.right() - 14.0, rect.bottom() - 8.0));
        let region = Rect::from_min_max(pos2(rect.left(), rect.top() + 40.0), pos2(rect.right(), steer.top() - 4.0));
        let r = ((region.height() - 60.0) / 1.75).min(region.width() / 2.0 - 64.0).clamp(80.0, 230.0);
        let c = pos2(region.center().x, region.top() + r + 56.0);
        gauge(
            p,
            c,
            r,
            &GaugeData {
                output: self.anim.output,
                output_exact: view.output.throttle,
                demand: self.anim.demand,
                limit: view.speed.scale(),
                armed: view.armed,
                tier: tier_letter(view.speed),
            },
            time,
        );

        p.line_segment(
            [pos2(rect.left() + 18.0, steer.top()), pos2(rect.right() - 18.0, steer.top())],
            stroke(1.0, PANEL_EDGE),
        );
        steering_strip(p, steer, self.anim.steer, view.output.steering);
    }

    /// Center panel while video is live: a status strip on top, the picture
    /// in its own aspect ratio, and the drive HUD in a strip underneath, so
    /// nothing is drawn over the image.
    #[allow(clippy::too_many_arguments)]
    fn video_panel(&self, p: &Painter, rect: Rect, tex: egui::TextureId, vs: &video::Stats, view: &ControlView, time: f64) {
        panel(p, rect);
        let (top_h, hud_h) = (48.0, 104.0);
        let strip = Rect::from_min_max(pos2(rect.left() + 18.0, rect.top() + 8.0), pos2(rect.right() - 18.0, rect.top() + top_h));
        let area = Rect::from_min_max(pos2(rect.left() + 10.0, strip.bottom() + 4.0), pos2(rect.right() - 10.0, rect.bottom() - hud_h));
        let hud = Rect::from_min_max(pos2(rect.left() + 14.0, area.bottom() + 4.0), pos2(rect.right() - 14.0, rect.bottom() - 8.0));

        // Picture, letterboxed in its native aspect ratio.
        let aspect = vs.width as f32 / vs.height.max(1) as f32;
        let size = if area.width() / area.height() > aspect {
            vec2(area.height() * aspect, area.height())
        } else {
            vec2(area.width(), area.width() / aspect)
        };
        let v = Rect::from_center_size(area.center(), size);
        p.rect_filled(area, 8.0, Color32::BLACK);
        p.image(tex, v, Rect::from_min_max(pos2(0.0, 0.0), pos2(1.0, 1.0)), Color32::WHITE);

        // Status strip: live tag, stream numbers, armed state.
        let cy = strip.center().y;
        let blink = 0.6 + 0.4 * (0.5 + 0.5 * (time * 3.0).sin() as f32);
        let tag = Rect::from_min_size(pos2(strip.left(), cy - 12.0), vec2(58.0, 24.0));
        p.rect_filled(tag, 5.0, alpha(RED, 0.9));
        p.circle_filled(pos2(tag.left() + 12.0, cy), 3.5, alpha(Color32::WHITE, blink));
        spaced(p, pos2(tag.left() + 21.0, cy), Align2::LEFT_CENTER, "LIVE", display(12.0), Color32::WHITE, 1.2);
        let title = section_title(p, pos2(tag.right() + 14.0, cy - 10.0), "图传", "VIDEO");
        let _ = title;
        let (col, label) = if view.armed { (GREEN, "已解锁 · ARMED") } else { (RED, "已锁定 · LOCKED") };
        let badge = Rect::from_min_size(pos2(strip.right() - 140.0, cy - 14.0), vec2(140.0, 28.0));
        // Stream numbers right-aligned before the badge; shortened if tight.
        let room = badge.left() - 16.0 - (tag.right() + 130.0);
        let long = format!(
            "{}×{}  ·  {:.0} FPS  ·  {:.1} Mbps  ·  {}  ·  解码 {:.1} ms",
            vs.width, vs.height, vs.fps, vs.kbps / 1000.0, vs.codec, vs.decode_ms
        );
        let short = format!("{}×{} · {:.0} FPS · {:.1} Mbps", vs.width, vs.height, vs.fps, vs.kbps / 1000.0);
        let info = if p.layout_no_wrap(long.clone(), display(13.0), TEXT_DIM).size().x <= room { long } else { short };
        if p.layout_no_wrap(info.clone(), display(13.0), TEXT_DIM).size().x <= room {
            p.text(pos2(badge.left() - 16.0, cy), Align2::RIGHT_CENTER, info, display(13.0), TEXT_DIM);
        }
        p.rect(badge, 14.0, tint(col), stroke(1.0, col), StrokeKind::Inside);
        p.text(badge.center(), Align2::CENTER_CENTER, label, bold(12.0), col);

        // HUD strip: throttle on the left, steering on the right.
        let out = view.output.throttle;
        let x0 = hud.left() + 6.0;
        let gear = if out > 0.005 { ("D", AMBER) } else if out < -0.005 { ("R", CYAN) } else { ("N", TEXT) };
        let g = Rect::from_min_size(pos2(x0, hud.top() + 14.0), vec2(30.0, 30.0));
        p.rect(g, 6.0, tint(gear.1), stroke(1.0, gear.1), StrokeKind::Inside);
        p.text(g.center(), Align2::CENTER_CENTER, gear.0, display(18.0), gear.1);
        let n = p.text(
            pos2(g.right() + 12.0, g.center().y + 2.0),
            Align2::LEFT_CENTER,
            format!("{}", (out.abs() * 100.0).round()),
            display(40.0),
            if view.armed { TEXT } else { TEXT_DIM },
        );
        p.text(pos2(n.right() + 3.0, n.bottom() - 9.0), Align2::LEFT_BOTTOM, "%", display(15.0), TEXT_DIM);
        p.text(pos2(n.right() + 26.0, n.center().y - 8.0), Align2::LEFT_CENTER, "油门输出", body(12.0), TEXT_DIM);
        p.text(
            pos2(n.right() + 26.0, n.center().y + 10.0),
            Align2::LEFT_CENTER,
            format!("档位 {} · 上限 {:.0}%", tier_letter(view.speed), view.speed.scale() * 100.0),
            body(12.0),
            TEXT_FAINT,
        );
        let split = hud.left() + (hud.width() * 0.38).max(300.0);
        let bar = Rect::from_min_max(pos2(x0, hud.bottom() - 22.0), pos2(split - 24.0, hud.bottom() - 16.0));
        hbar(p, bar, self.anim.output, view.speed.scale(), throttle_color(out));
        p.line_segment([pos2(split, hud.top() + 12.0), pos2(split, hud.bottom() - 8.0)], stroke(1.0, PANEL_EDGE));
        let steer = Rect::from_min_max(pos2(split + 10.0, hud.top() + 6.0), hud.max);
        steering_strip(p, steer, self.anim.steer, view.output.steering);
    }

    #[allow(clippy::too_many_arguments)]
    fn control_panel(&mut self, ui: &mut Ui, p: &Painter, rect: Rect, st: &Status, view: &ControlView, time: f64) {
        panel(p, rect);
        let (l, r) = (rect.left() + 18.0, rect.right() - 18.0);
        let mut y = section_title(p, pos2(l, rect.top() + 16.0), "控制", "CONTROL") + 16.0;

        // Arm / disarm.
        let arm = Rect::from_min_max(pos2(l, y), pos2(r, y + 64.0));
        let resp = hit(ui, arm, "arm");
        let (title, sub, col) = if view.armed {
            let pulse = 0.6 + 0.4 * (0.5 + 0.5 * (time * 3.0).sin() as f32);
            rect_glow(p, arm, 12.0, GREEN, pulse);
            p.rect(arm, 12.0, tint(GREEN), stroke(1.5, GREEN), StrokeKind::Inside);
            ("已解锁 · 点击锁定", "ARMED", GREEN)
        } else if let Some(until) = self.arm_confirm_until {
            rect_glow(p, arm, 12.0, RED, 1.2);
            p.rect_filled(arm, 12.0, Color32::from_rgb(200, 40, 36));
            let left = until.saturating_duration_since(Instant::now()).as_secs_f32() / ARM_CONFIRM.as_secs_f32();
            let bar = Rect::from_min_size(pos2(arm.left() + 14.0, arm.bottom() - 9.0), vec2((arm.width() - 28.0) * left, 3.0));
            p.rect_filled(bar, 1.5, alpha(Color32::WHITE, 0.85));
            ("再点一次确认解锁", "CONFIRM", Color32::WHITE)
        } else {
            let k = if resp.hovered() { 1.0 } else { 0.0 };
            p.rect(arm, 12.0, alpha(GREEN, 0.02 + 0.03 * k), stroke(1.5, alpha(GREEN, 0.6 + 0.3 * k)), StrokeKind::Inside);
            ("解锁油门", "ARM THROTTLE", GREEN)
        };
        p.text(arm.center() + vec2(0.0, -8.0), Align2::CENTER_CENTER, title, bold(17.0), col);
        spaced(p, arm.center() + vec2(0.0, 14.0), Align2::CENTER_CENTER, sub, display(11.0), alpha(col, 0.8), 3.0);
        if resp.clicked() {
            self.arm_clicked(view.armed);
        }
        y = arm.bottom() + 10.0;
        // One line of context under the button: a refusal, the confirm
        // prompt, or why the throttle is locked.
        let message = if let Some((n, _)) = &self.note {
            Some((n.clone(), RED))
        } else if self.arm_confirm_until.is_some() {
            Some(("车轮离地或周围清空后，3 秒内再点一次".to_string(), AMBER))
        } else if !view.armed && !view.disarm_reason.is_empty() {
            Some((format!("锁定原因：{}", view.disarm_reason), AMBER))
        } else {
            None
        };
        if let Some((text, col)) = message {
            let g = p.layout(text, body(12.0), col, r - l);
            let h = g.size().y;
            p.galley(pos2(l, y), g, col);
            y += h.max(18.0) + 12.0;
        } else {
            y += 30.0;
        }

        // Speed tiers.
        y = small_label(p, l, y, "速度档", "SPEED");
        let (gap, th) = (8.0, 66.0);
        let tw = (r - l - 2.0 * gap) / 3.0;
        for (i, (s, letter, zh)) in [(Speed::Low, "L", "低速"), (Speed::Mid, "M", "中速"), (Speed::High, "H", "高速")].into_iter().enumerate() {
            let tr = Rect::from_min_size(pos2(l + i as f32 * (tw + gap), y), vec2(tw, th));
            let resp = hit(ui, tr, letter);
            let on = view.speed == s;
            if on {
                rect_glow(p, tr, 10.0, ORANGE, 0.7);
                p.rect(tr, 10.0, tint(ORANGE), stroke(1.5, ORANGE), StrokeKind::Inside);
            } else {
                let fill = if resp.hovered() { hover() } else { Color32::TRANSPARENT };
                p.rect(tr, 10.0, fill, stroke(1.0, PANEL_EDGE), StrokeKind::Inside);
            }
            let col = if on { ORANGE } else if resp.hovered() { TEXT } else { TEXT_DIM };
            p.text(pos2(tr.left() + 12.0, tr.top() + 10.0), Align2::LEFT_TOP, letter, display(26.0), col);
            p.text(pos2(tr.left() + 12.0, tr.bottom() - 10.0), Align2::LEFT_BOTTOM, zh, body(12.0), if on { TEXT } else { TEXT_DIM });
            for b in 0..3 {
                let bh = 8.0 + b as f32 * 6.0;
                let bx = tr.right() - 12.0 - (2 - b) as f32 * 7.0 - 5.0;
                let br = Rect::from_min_size(pos2(bx, tr.top() + 34.0 - bh), vec2(5.0, bh));
                p.rect_filled(br, 1.0, if b <= i { col } else { TRACK });
            }
            if resp.clicked() {
                self.shared.control().set_speed(s);
            }
        }
        y += th + 8.0;
        p.text(pos2(l, y), Align2::LEFT_TOP, format!("油门上限 {:.0}%", view.speed.scale() * 100.0), body(12.0), TEXT_DIM);
        y += 28.0;

        // Direction flips: applied live, saved to the config.
        y = small_label(p, l, y, "方向", "DIRECTION");
        let inv = self.shared.invert();
        let cw = (r - l - gap) / 2.0;
        for (i, (name, on)) in [("转向反向", inv.steering), ("油门反向", inv.throttle)].into_iter().enumerate() {
            let cr = Rect::from_min_size(pos2(l + i as f32 * (cw + gap), y), vec2(cw, 32.0));
            let resp = hit(ui, cr, name);
            if on {
                rect_glow(p, cr, 8.0, CYAN, 0.5);
                p.rect(cr, 8.0, tint(CYAN), stroke(1.0, CYAN), StrokeKind::Inside);
            } else {
                p.rect(cr, 8.0, if resp.hovered() { hover() } else { Color32::TRANSPARENT }, stroke(1.0, PANEL_EDGE), StrokeKind::Inside);
            }
            p.text(cr.center(), Align2::CENTER_CENTER, name, body(13.0), if on { CYAN } else { TEXT_DIM });
            if resp.clicked() {
                let new = if i == 0 { Invert { steering: !on, ..inv } } else { Invert { throttle: !on, ..inv } };
                self.shared.set_invert(new);
                if let Err(e) = crate::config::save_invert(&self.config_path, new.steering, new.throttle) {
                    self.note = Some((format!("已生效，但保存配置失败：{e:#}"), Instant::now()));
                }
            }
        }
        y += 32.0 + 12.0;

        // What actually went out on the wire.
        y = small_label(p, l, y, "线上发送", "WIRE");
        if st.sent.is_empty() {
            p.text(pos2(l, y + 9.0), Align2::LEFT_CENTER, "未连接，无数据", body(13.0), TEXT_FAINT);
        }
        for (k, v) in &st.sent {
            kv(p, l, r, y + 9.0, k, &format!("{v}"), mono(13.0), TEXT);
            y += 24.0;
        }
    }

    fn input_panel(&mut self, ui: &mut Ui, p: &Painter, rect: Rect) {
        panel(p, rect);
        let (l, r) = (rect.left() + 18.0, rect.right() - 18.0);
        let top = section_title(p, pos2(l, rect.top() + 14.0), "输入", "INPUT");
        p.text(pos2(r, rect.top() + 23.0), Align2::RIGHT_CENTER, "调试输入 · 接方向盘后由方向盘控制 · 空格键急停", body(12.0), TEXT_FAINT);
        let rows_top = top + 8.0;
        let row_h = (rect.bottom() - 10.0 - rows_top) / 2.0;

        let row = |i: f32| Rect::from_min_size(pos2(l, rows_top + i * row_h), vec2(r - l, row_h));
        let label = |rr: Rect, zh: &str, en: &str| {
            p.text(pos2(rr.left(), rr.center().y - 7.0), Align2::LEFT_CENTER, zh, bold(15.0), TEXT);
            spaced(p, pos2(rr.left(), rr.center().y + 11.0), Align2::LEFT_CENTER, en, display(10.0), TEXT_DIM, 1.8);
        };
        let value = |rr: Rect, v: f32, col: Color32| {
            let txt = format!("{:+.0}", v * 100.0);
            p.text(pos2(rr.right() - 92.0, rr.center().y), Align2::RIGHT_CENTER, if v.abs() < 0.005 { "0".into() } else { txt }, display(22.0), col);
        };

        let sr = row(0.0);
        label(sr, "转向", "STEERING");
        let slider = Rect::from_min_max(pos2(sr.left() + 104.0, sr.top()), pos2(sr.right() - 160.0, sr.bottom()));
        bipolar_slider(ui, slider, "steer", &mut self.steering, CYAN, CYAN);
        value(sr, self.steering, if self.steering.abs() > 0.005 { CYAN } else { TEXT_DIM });
        let btn = Rect::from_min_size(pos2(sr.right() - 76.0, sr.center().y - 15.0), vec2(76.0, 30.0));
        let resp = hit(ui, btn, "steer-center");
        p.rect(btn, 8.0, if resp.hovered() { tint(CYAN) } else { Color32::TRANSPARENT }, stroke(1.0, alpha(CYAN, 0.6)), StrokeKind::Inside);
        p.text(btn.center(), Align2::CENTER_CENTER, "回中", body(13.0), CYAN);
        if resp.clicked() {
            self.steering = 0.0;
        }

        let tr = row(1.0);
        label(tr, "油门", "THROTTLE");
        let slider = Rect::from_min_max(pos2(tr.left() + 104.0, tr.top()), pos2(tr.right() - 160.0, tr.bottom()));
        let resp = bipolar_slider(ui, slider, "throttle", &mut self.throttle, AMBER, CYAN);
        value(tr, self.throttle, if self.throttle.abs() > 0.005 { throttle_color(self.throttle) } else { TEXT_DIM });
        // Dead-man: the throttle only holds while the mouse is holding it.
        if !resp.is_pointer_button_down_on() {
            self.throttle = 0.0;
        }
        p.text(pos2(tr.right(), tr.center().y), Align2::RIGHT_CENTER, "按住拖动\n松开回零", body(11.0), TEXT_FAINT);
    }
}

fn tier_letter(s: Speed) -> &'static str {
    match s {
        Speed::Low => "L",
        Speed::Mid => "M",
        Speed::High => "H",
    }
}

fn small_label(p: &Painter, l: f32, y: f32, zh: &str, en: &str) -> f32 {
    let a = p.text(pos2(l, y), Align2::LEFT_TOP, zh, body(12.0), TEXT_DIM);
    spaced(p, pos2(a.right() + 8.0, a.center().y + 1.0), Align2::LEFT_CENTER, en, display(10.0), TEXT_FAINT, 1.6);
    a.bottom() + 10.0
}

fn lq_color(lq: u8) -> Color32 {
    match lq {
        80.. => GREEN,
        50..=79 => AMBER,
        _ => RED,
    }
}

/// Built-in video radio: adapter, channel and link quality.
fn radio_section(p: &Painter, l: f32, r: f32, mut y: f32, rs: &radio::Status) -> f32 {
    p.line_segment([pos2(l, y), pos2(r, y)], stroke(1.0, PANEL_EDGE));
    y = small_label(p, l, y + 12.0, "图传", "RADIO") + 8.0;
    let (state, col) = match &rs.state {
        radio::State::Receiving => (rs.adapter.clone(), GREEN),
        radio::State::Starting => (format!("{} 启动中", rs.adapter), AMBER),
        radio::State::NoAdapter => ("未插入图传网卡".to_string(), TEXT_FAINT),
        radio::State::Error(e) => (e.clone(), RED),
        radio::State::Disabled => ("未启用".to_string(), TEXT_FAINT),
    };
    y += kv_fit(p, l, r, y, "网卡", &state, bold(12.0), col);
    let ch = format!("{} · {} MHz · {} MHz", rs.channel, radio::channel_mhz(rs.channel), rs.width_mhz);
    kv(p, l, r, y, "信道", &ch, display(14.0), TEXT);
    y += 28.0;
    if rs.state == radio::State::Receiving {
        let best = rs.link_score[0].max(rs.link_score[1]);
        let frac = radio::score_frac(best);
        let txt = if rs.wfb_frames == 0 { "等待信号".to_string() } else { format!("{:.0}%  丢包 {}", frac * 100.0, rs.packet_loss) };
        let c = if rs.wfb_frames == 0 { AMBER } else { lq_color((frac * 100.0) as u8) };
        kv(p, l, r, y, "链路", &txt, display(15.0), c);
        y += 28.0;
    }
    y
}

/// Top of the link panel once the module is connected: uplink/downlink LQ.
fn link_quality(p: &Painter, l: f32, r: f32, mut y: f32, st: &Status, time: f64) -> f32 {
    let big_block = |y: f32, zh: &str, en: &str, value: Option<f32>, right: String, frac: f32, col: Color32| -> f32 {
        let a = p.text(pos2(l, y), Align2::LEFT_TOP, zh, body(12.0), TEXT_DIM);
        spaced(p, pos2(a.right() + 8.0, a.center().y + 1.0), Align2::LEFT_CENTER, en, display(10.0), TEXT_FAINT, 1.6);
        p.text(pos2(r, a.center().y), Align2::RIGHT_CENTER, right, mono(11.0), TEXT_DIM);
        let txt = value.map(|v| format!("{v}")).unwrap_or_else(|| "--".into());
        let n = p.text(pos2(l, a.bottom() + 2.0), Align2::LEFT_TOP, txt, display(36.0), if value.is_some() { col } else { TEXT_FAINT });
        let bar = Rect::from_min_max(pos2(l + 92.0, n.center().y - 5.0), pos2(r, n.center().y + 5.0));
        seg_bar(p, bar, frac, col, 12);
        n.bottom() + 12.0
    };

    match st.link {
        Some(link) => {
            for (zh, en, lq, rssi) in [("上行", "UPLINK", link.up_lq, link.up_rssi), ("下行", "DOWNLINK", link.down_lq, link.down_rssi)] {
                y = big_block(y, zh, en, Some(lq as f32), format!("{rssi} dBm"), lq as f32 / 100.0, lq_color(lq));
            }
            y
        }
        None if st.tx_only() => {
            // Control works one-way; there is just no wire to hear back on.
            let t = spaced(p, pos2(l, y + 2.0), Align2::LEFT_TOP, "TX ONLY", display(32.0), AMBER, 2.0);
            p.text(pos2(l, t.bottom() + 8.0), Align2::LEFT_TOP, "只发送，读不到回传", bold(13.0), TEXT);
            let g = p.layout(
                "控制信号照常发出。高频头的 CRSF 只接了 TXD，链路质量要接上 RXD（经 1kΩ 电阻）才能读到。".to_string(),
                body(12.0),
                TEXT_DIM,
                r - l,
            );
            let h = g.size().y;
            p.galley(pos2(l, t.bottom() + 30.0), g, TEXT_DIM);
            t.bottom() + 30.0 + h + 14.0
        }
        None => {
            let blink = 0.55 + 0.45 * (0.5 + 0.5 * (time * 2.0).sin() as f32);
            let t = spaced(p, pos2(l, y + 2.0), Align2::LEFT_TOP, "NO LINK", display(32.0), alpha(RED, blink), 2.0);
            p.text(pos2(l, t.bottom() + 8.0), Align2::LEFT_TOP, "接收机未连上", bold(13.0), TEXT);
            p.text(pos2(l, t.bottom() + 28.0), Align2::LEFT_TOP, "检查车上电源和对频", body(12.0), TEXT_DIM);
            seg_bar(p, Rect::from_min_size(pos2(l, t.bottom() + 54.0), vec2(r - l, 8.0)), 0.0, RED, 12);
            t.bottom() + 78.0
        }
    }
}

#[allow(clippy::too_many_arguments)]
fn link_panel(
    p: &Painter,
    rect: Rect,
    st: &Status,
    view: &ControlView,
    radio: &radio::Status,
    history: &VecDeque<(f32, f32)>,
    time: f64,
) {
    panel(p, rect);
    let (l, r) = (rect.left() + 18.0, rect.right() - 18.0);
    let mut y = section_title(p, pos2(l, rect.top() + 16.0), "链路", "LINK") + 18.0;

    if !st.connected {
        let blink = 0.55 + 0.45 * (0.5 + 0.5 * (time * 2.0).sin() as f32);
        let t = spaced(p, pos2(l, y + 2.0), Align2::LEFT_TOP, "OFFLINE", display(32.0), alpha(RED, blink), 2.0);
        p.text(pos2(l, t.bottom() + 8.0), Align2::LEFT_TOP, "高频头未连接", bold(13.0), TEXT);
        y = t.bottom() + 34.0;
        if !st.error.is_empty() {
            let g = p.layout(st.error.clone(), body(12.0), RED, r - l - 20.0);
            let box_rect = Rect::from_min_size(pos2(l, y), vec2(r - l, g.size().y + 14.0));
            p.rect(box_rect, 8.0, tint(RED), stroke(1.0, alpha(RED, 0.5)), StrokeKind::Inside);
            p.galley(box_rect.min + vec2(10.0, 7.0), g, RED);
            y = box_rect.bottom() + 16.0;
        }
    } else {
        y = link_quality(p, l, r, y, st, time);
    }

    p.line_segment([pos2(l, y), pos2(r, y)], stroke(1.0, PANEL_EDGE));
    y += 20.0;
    let (hb, hb_col) = if view.input_fresh {
        (format!("{} ms", view.input_age_ms.unwrap_or(0)), GREEN)
    } else {
        ("已断".to_string(), RED)
    };
    kv(p, l, r, y, "输入心跳", &hb, display(16.0), hb_col);
    y += 28.0;
    let col = if st.resets > 1 { AMBER } else { TEXT };
    kv(p, l, r, y, "高频头复位", &st.resets.to_string(), display(16.0), col);
    y += 28.0;
    y += kv_fit(p, l, r, y, "设备", if st.device.is_empty() { "—" } else { &st.device }, bold(12.0), TEXT);
    y += kv_fit(p, l, r, y, "串口", if st.port.is_empty() { "—" } else { &st.port }, mono(10.5), TEXT_DIM);

    if radio.state != radio::State::Disabled {
        y = radio_section(p, l, r, y + 6.0, radio);
    }

    // Link history chart along the bottom, when there is room for it.
    let chart = Rect::from_min_max(pos2(l, rect.bottom() - 112.0), pos2(r, rect.bottom() - 20.0));
    let title_y = chart.top() - 30.0;
    if y + 8.0 > title_y {
        return;
    }
    small_label(p, l, title_y, "链路历史", "30 S");
    let legend: &[(&str, Color32)] = &[("上行", GREEN), ("下行", CYAN)];
    let mut lx = r;
    for (name, col) in legend.iter().rev() {
        let t = p.text(pos2(lx, title_y + 8.0), Align2::RIGHT_CENTER, *name, body(11.0), TEXT_DIM);
        p.circle_filled(pos2(t.left() - 7.0, t.center().y), 3.0, *col);
        lx = t.left() - 18.0;
    }
    for frac in [0.0, 0.5, 1.0] {
        let gy = chart.bottom() - frac * chart.height();
        p.line_segment([pos2(chart.left(), gy), pos2(chart.right(), gy)], stroke(1.0, alpha(TEXT_FAINT, 0.35)));
    }
    let up: Vec<f32> = history.iter().map(|s| s.0).collect();
    sparkline(p, chart, &up, HISTORY_LEN, GREEN);
    let down: Vec<f32> = history.iter().map(|s| s.1).collect();
    sparkline(p, chart, &down, HISTORY_LEN, CYAN);
}

pub fn run(gui: Gui) -> anyhow::Result<()> {
    let options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_title("RC 控制台")
            .with_inner_size([1200.0, 780.0])
            .with_min_inner_size([1060.0, 720.0])
            // macOS: draw under a transparent title bar; ignored elsewhere.
            .with_fullsize_content_view(true)
            .with_title_shown(false)
            .with_titlebar_shown(false),
        ..Default::default()
    };
    eframe::run_native(
        "rc-control",
        options,
        Box::new(|cc| {
            theme::apply(&cc.egui_ctx);
            Ok(Box::new(gui))
        }),
    )
    .map_err(|e| anyhow::anyhow!("无法打开窗口: {e}"))
}
