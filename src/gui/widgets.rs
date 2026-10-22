//! Custom-painted dashboard pieces. Everything here is drawn with the egui
//! painter; interaction goes through `ui.interact` on explicit rects.

use super::theme::*;
use eframe::egui::text::{LayoutJob, TextFormat};
use eframe::egui::{
    pos2, vec2, Align2, Color32, CursorIcon, FontId, Mesh, Painter, Pos2, Rect, Response, Sense, Shape, Stroke,
    StrokeKind, Ui,
};
use std::f32::consts::{PI, TAU};

// ---------- primitives ----------

/// `Stroke::new` takes `impl Into<f32>`, which leaves bare float literals
/// untyped; this pins the width to f32.
pub fn stroke(width: f32, color: Color32) -> Stroke {
    Stroke::new(width, color)
}

pub fn polar(c: Pos2, r: f32, a: f32) -> Pos2 {
    c + vec2(a.cos(), a.sin()) * r
}

/// Text with extra tracking, for small uppercase HUD labels.
pub fn spaced(p: &Painter, pos: Pos2, anchor: Align2, s: &str, font: FontId, color: Color32, tracking: f32) -> Rect {
    let mut job = LayoutJob::default();
    job.append(s, 0.0, TextFormat { font_id: font, color, extra_letter_spacing: tracking, ..Default::default() });
    let galley = p.layout_job(job);
    let rect = anchor.anchor_size(pos, galley.size());
    p.galley(rect.min, galley, color);
    rect
}

/// Strip mesh across several radii of an arc; `color(t, ring)` with t in 0..=1
/// along the arc. Meshes are not anti-aliased, so callers fade edges to clear.
fn arc_mesh(p: &Painter, c: Pos2, a0: f32, a1: f32, radii: &[f32], color: impl Fn(f32, usize) -> Color32) {
    if (a1 - a0).abs() < 1e-4 {
        return;
    }
    let steps = (((a1 - a0).abs() / 0.025).ceil() as u32).max(2);
    let rings = radii.len() as u32;
    let mut m = Mesh::default();
    for i in 0..=steps {
        let t = i as f32 / steps as f32;
        let a = a0 + (a1 - a0) * t;
        for (j, &r) in radii.iter().enumerate() {
            m.colored_vertex(polar(c, r, a), color(t, j));
        }
        if i > 0 {
            let (prev, cur) = ((i - 1) * rings, i * rings);
            for j in 0..rings - 1 {
                m.add_triangle(prev + j, prev + j + 1, cur + j);
                m.add_triangle(prev + j + 1, cur + j + 1, cur + j);
            }
        }
    }
    p.add(Shape::mesh(m));
}

/// Solid arc band between radii r0 and r1, with soft 0.8 px edges.
pub fn arc_band(p: &Painter, c: Pos2, r0: f32, r1: f32, a0: f32, a1: f32, color: impl Fn(f32) -> Color32) {
    let f = 0.8;
    arc_mesh(p, c, a0, a1, &[r0 - f, r0, r1, r1 + f], |t, j| {
        if j == 0 || j == 3 { Color32::TRANSPARENT } else { color(t) }
    });
}

/// Additive glow centered on radius r, fading out over `width` both ways.
pub fn arc_glow(p: &Painter, c: Pos2, r: f32, width: f32, a0: f32, a1: f32, color: impl Fn(f32) -> Color32) {
    arc_mesh(p, c, a0, a1, &[r - width, r, r + width], |t, j| if j == 1 { color(t) } else { Color32::TRANSPARENT });
}

/// Additive disc fading from `color` at the center to nothing at `r`.
pub fn radial_glow(p: &Painter, c: Pos2, r: f32, color: Color32) {
    let n = 48u32;
    let mut m = Mesh::default();
    m.colored_vertex(c, color);
    for i in 0..=n {
        m.colored_vertex(polar(c, r, i as f32 / n as f32 * TAU), Color32::TRANSPARENT);
    }
    for i in 1..=n {
        m.add_triangle(0, i, i + 1);
    }
    p.add(Shape::mesh(m));
}

/// Horizontal gradient fill.
pub fn hgradient(p: &Painter, rect: Rect, left: Color32, right: Color32) {
    let mut m = Mesh::default();
    m.colored_vertex(rect.left_top(), left);
    m.colored_vertex(rect.right_top(), right);
    m.colored_vertex(rect.right_bottom(), right);
    m.colored_vertex(rect.left_bottom(), left);
    m.add_triangle(0, 1, 2);
    m.add_triangle(0, 2, 3);
    p.add(Shape::mesh(m));
}

/// Display-only bipolar bar: fill from the center to `value` (-1..=1),
/// with amber ticks at the speed-tier `limit`.
pub fn hbar(p: &Painter, rect: Rect, value: f32, limit: f32, color: Color32) {
    p.rect_filled(rect, 3.0, alpha(TRACK, 0.9));
    let mid = rect.center().x;
    let half = rect.width() / 2.0;
    for s in [-limit, limit] {
        let x = mid + s.clamp(-1.0, 1.0) * half;
        p.line_segment([pos2(x, rect.top() - 4.0), pos2(x, rect.bottom() + 4.0)], stroke(1.5, AMBER));
    }
    p.line_segment([pos2(mid, rect.top() - 6.0), pos2(mid, rect.bottom() + 6.0)], stroke(1.0, TEXT_DIM));
    let x = mid + value.clamp(-1.0, 1.0) * half;
    if (x - mid).abs() > 0.5 {
        let fill = Rect::from_min_max(pos2(mid.min(x), rect.top()), pos2(mid.max(x), rect.bottom()));
        p.rect_filled(fill.expand(3.0), 4.0, glow(color, 0.25));
        p.rect_filled(fill, 3.0, color);
    }
}

/// Soft additive halo outside a rounded rect; the inside is left untouched
/// so text on the rect keeps its contrast.
pub fn rect_glow(p: &Painter, rect: Rect, radius: f32, color: Color32, strength: f32) {
    for (grow, width, k) in [(8.0, 6.0, 0.05), (5.0, 4.0, 0.09), (2.0, 3.0, 0.16)] {
        p.rect_stroke(rect.expand(grow), radius + grow, stroke(width, glow(color, k * strength)), StrokeKind::Middle);
    }
}

pub fn hit(ui: &Ui, rect: Rect, id: &str) -> Response {
    ui.interact(rect, ui.id().with(id), Sense::click()).on_hover_cursor(CursorIcon::PointingHand)
}

// ---------- surfaces ----------

pub fn backdrop(p: &Painter, rect: Rect) {
    p.rect_filled(rect, 0.0, BG);
    let step = 28.0;
    let line = stroke(1.0, Color32::from_rgba_unmultiplied(90, 130, 180, 8));
    let mut x = rect.left() + (rect.width() % step) / 2.0;
    while x < rect.right() {
        p.line_segment([pos2(x, rect.top()), pos2(x, rect.bottom())], line);
        x += step;
    }
    let mut y = rect.top() + (rect.height() % step) / 2.0;
    while y < rect.bottom() {
        p.line_segment([pos2(rect.left(), y), pos2(rect.right(), y)], line);
        y += step;
    }
}

/// Card with HUD tick marks on its top-left and bottom-right edges.
pub fn panel(p: &Painter, rect: Rect) {
    p.rect(rect, 12.0, PANEL, stroke(1.0, PANEL_EDGE), StrokeKind::Inside);
    let top = rect.top() + 0.5;
    p.line_segment([pos2(rect.left() + 18.0, top), pos2(rect.left() + 52.0, top)], stroke(2.0, alpha(CYAN, 0.85)));
    p.line_segment([pos2(rect.left() + 14.0, top), pos2(rect.left() + 56.0, top)], stroke(6.0, glow(CYAN, 0.12)));
    let bottom = rect.bottom() - 0.5;
    p.line_segment(
        [pos2(rect.right() - 40.0, bottom), pos2(rect.right() - 18.0, bottom)],
        stroke(2.0, alpha(CYAN, 0.35)),
    );
}

/// "链路  LINK" style heading; returns the y below it.
pub fn section_title(p: &Painter, pos: Pos2, zh: &str, en: &str) -> f32 {
    let r = p.text(pos, Align2::LEFT_TOP, zh, bold(15.0), TEXT);
    spaced(p, pos2(r.right() + 10.0, r.center().y + 1.0), Align2::LEFT_CENTER, en, display(11.0), TEXT_DIM, 1.8);
    r.bottom()
}

/// Label on the left, value on the right, on one row.
pub fn kv(p: &Painter, left: f32, right: f32, y: f32, k: &str, v: &str, v_font: FontId, v_color: Color32) {
    p.text(pos2(left, y), Align2::LEFT_CENTER, k, body(13.0), TEXT_DIM);
    p.text(pos2(right, y), Align2::RIGHT_CENTER, v, v_font, v_color);
}

/// Like `kv`, but a value too wide to sit beside its label goes on wrapped
/// line(s) underneath instead of running into the label. Returns the advance.
#[allow(clippy::too_many_arguments)]
pub fn kv_fit(p: &Painter, left: f32, right: f32, y: f32, k: &str, v: &str, v_font: FontId, v_color: Color32) -> f32 {
    let label_w = p.layout_no_wrap(k.to_string(), body(13.0), TEXT_DIM).size().x;
    let value_w = p.layout_no_wrap(v.to_string(), v_font.clone(), v_color).size().x;
    if label_w + 16.0 + value_w <= right - left {
        kv(p, left, right, y, k, v, v_font, v_color);
        return 28.0;
    }
    p.text(pos2(left, y), Align2::LEFT_CENTER, k, body(13.0), TEXT_DIM);
    let g = p.layout(v.to_string(), v_font, v_color, right - left);
    let h = g.size().y;
    p.galley(pos2(left, y + 12.0), g, v_color);
    h + 28.0
}

/// Signal-strength style bar: `n` segments, lit up to `frac`.
pub fn seg_bar(p: &Painter, rect: Rect, frac: f32, color: Color32, n: usize) {
    let gap = 3.0;
    let w = (rect.width() - gap * (n as f32 - 1.0)) / n as f32;
    for i in 0..n {
        let r = Rect::from_min_size(pos2(rect.left() + i as f32 * (w + gap), rect.top()), vec2(w, rect.height()));
        if (i as f32 + 0.5) / n as f32 <= frac {
            p.rect_filled(r.expand(2.0), 3.0, glow(color, 0.12));
            p.rect_filled(r, 1.5, color);
        } else {
            p.rect_filled(r, 1.5, TRACK);
        }
    }
}

/// Thin line with a highlight streaking along it; faster when `speed` is up.
pub fn flow_line(p: &Painter, y: f32, x0: f32, x1: f32, color: Color32, time: f64, speed: f32) {
    p.line_segment([pos2(x0, y), pos2(x1, y)], stroke(1.0, alpha(color, 0.30)));
    let len = (x1 - x0) * 0.28;
    let rate = 0.12 + 0.9 * speed as f64;
    let head = x0 + ((time * rate).fract() as f32) * (x1 - x0 + len);
    let tail = (head - len).max(x0);
    let head = head.min(x1);
    if head > tail {
        let r = Rect::from_min_max(pos2(tail, y - 1.0), pos2(head, y + 1.0));
        hgradient(p, r, Color32::TRANSPARENT, glow(color, 1.0));
        let halo = Rect::from_min_max(pos2(tail, y - 5.0), pos2(head, y + 5.0));
        hgradient(p, halo, Color32::TRANSPARENT, glow(color, 0.25));
    }
}

/// Line chart of 0..=1 samples, newest on the right, with a fading fill.
pub fn sparkline(p: &Painter, rect: Rect, samples: &[f32], capacity: usize, color: Color32) {
    if samples.len() < 2 {
        return;
    }
    let dx = rect.width() / (capacity.max(2) - 1) as f32;
    let x0 = rect.right() - dx * (samples.len() - 1) as f32;
    let pts: Vec<Pos2> = samples
        .iter()
        .enumerate()
        .map(|(i, v)| pos2(x0 + dx * i as f32, rect.bottom() - v.clamp(0.0, 1.0) * rect.height()))
        .collect();
    let mut m = Mesh::default();
    for (i, pt) in pts.iter().enumerate() {
        m.colored_vertex(*pt, alpha(color, 0.22));
        m.colored_vertex(pos2(pt.x, rect.bottom()), Color32::TRANSPARENT);
        if i > 0 {
            let k = 2 * i as u32;
            m.add_triangle(k - 2, k - 1, k);
            m.add_triangle(k - 1, k + 1, k);
        }
    }
    p.add(Shape::mesh(m));
    p.add(Shape::line(pts, stroke(1.6, color)));
}

// ---------- throttle gauge ----------

pub struct GaugeData {
    /// Smoothed output, -1..=1, drives the arc.
    pub output: f32,
    /// Exact output for the numeric readout.
    pub output_exact: f32,
    /// Smoothed input demand already scaled by the speed tier.
    pub demand: f32,
    /// Speed-tier ceiling, 0..=1.
    pub limit: f32,
    pub armed: bool,
    pub tier: &'static str,
}

const SWEEP: f32 = 2.0 * PI / 3.0; // 120° each side of top

fn gauge_angle(v: f32) -> f32 {
    -PI / 2.0 + v.clamp(-1.0, 1.0) * SWEEP
}

pub fn gauge(p: &Painter, c: Pos2, r: f32, d: &GaugeData, time: f64) {
    let out = d.output;
    let hot = if d.armed && out.abs() > 0.01 { throttle_color(out) } else { CYAN };

    radial_glow(p, c, r * 1.35, glow(hot, 0.07 + 0.10 * out.abs()));

    // Outer hairline and the track.
    arc_band(p, c, r + 33.0, r + 34.0, gauge_angle(-1.0), gauge_angle(1.0), |_| alpha(TEXT_FAINT, 0.25));
    arc_band(p, c, r - 9.0, r + 9.0, gauge_angle(-1.0), gauge_angle(1.0), |_| TRACK);

    // Speed-tier ceiling: a thin ring, usable span light, beyond it red.
    let lim = d.limit.clamp(0.05, 1.0);
    arc_band(p, c, r + 12.0, r + 14.0, gauge_angle(-lim), gauge_angle(lim), |_| alpha(TEXT_DIM, 0.5));
    if lim < 0.999 {
        for (a0, a1) in [(gauge_angle(lim), gauge_angle(1.0)), (gauge_angle(-1.0), gauge_angle(-lim))] {
            arc_band(p, c, r + 12.0, r + 14.0, a0, a1, |_| alpha(RED, 0.45));
        }
    }
    for s in [-lim, lim] {
        let a = gauge_angle(s);
        p.line_segment([polar(c, r - 13.0, a), polar(c, r + 18.0, a)], stroke(2.0, AMBER));
    }

    // Ticks every 10 %, labels every 50 %.
    for i in -10..=10 {
        let v = i as f32 / 10.0;
        let a = gauge_angle(v);
        let major = i % 5 == 0;
        let beyond = v.abs() > lim + 1e-3;
        let color = if beyond { alpha(RED, 0.45) } else if major { TEXT_DIM } else { TEXT_FAINT };
        let outer = if major { r + 30.0 } else { r + 25.0 };
        p.line_segment([polar(c, r + 20.0, a), polar(c, outer, a)], stroke(if major { 2.0 } else { 1.0 }, color));
        if major {
            let label = format!("{}", (v.abs() * 100.0).round());
            p.text(polar(c, r + 48.0, a), Align2::CENTER_CENTER, label, display(13.0), TEXT_DIM);
        }
    }
    let end_label = |v: f32, s: &str, col: Color32| {
        let at = polar(c, r, gauge_angle(v)) + vec2(0.0, 30.0);
        spaced(p, at, Align2::CENTER_CENTER, s, display(12.0), col, 1.5);
    };
    end_label(-1.0, "REV", CYAN);
    end_label(1.0, "FWD", AMBER);

    // What the input asks for (ghost) vs what is actually sent (band); the
    // ghost only shows when they differ, e.g. throttle input while locked.
    if d.demand.abs() > 0.004 && (d.demand - out).abs() > 0.01 {
        arc_band(p, c, r - 16.0, r - 13.0, gauge_angle(0.0), gauge_angle(d.demand), |_| alpha(TEXT, 0.35));
    }
    if out.abs() > 0.004 {
        let (a0, a1) = (gauge_angle(0.0), gauge_angle(out));
        arc_glow(p, c, r, 26.0, a0, a1, |t| glow(throttle_color(out * t), 0.22 + 0.3 * t));
        arc_band(p, c, r - 9.0, r + 9.0, a0, a1, |t| throttle_color(out * t));
        let tip = polar(c, r, a1);
        radial_glow(p, tip, 30.0, glow(throttle_color(out), 0.9));
        p.circle_filled(tip, 5.5, Color32::WHITE);
    }

    // Zero marker.
    let top = polar(c, r - 22.0, gauge_angle(0.0));
    p.add(Shape::convex_polygon(
        vec![top + vec2(-6.0, -7.0), top + vec2(6.0, -7.0), top + vec2(0.0, 2.0)],
        TEXT_DIM,
        Stroke::NONE,
    ));

    // Gear strip: R N D.
    let exact = d.output_exact;
    let active = if exact > 0.005 { 2 } else if exact < -0.005 { 0 } else { 1 };
    for (i, (g, col)) in [("R", CYAN), ("N", TEXT), ("D", AMBER)].into_iter().enumerate() {
        let at = c + vec2((i as f32 - 1.0) * 30.0, -0.47 * r);
        if i == active {
            p.rect_filled(Rect::from_center_size(at, vec2(26.0, 26.0)), 6.0, tint(col));
            p.rect_stroke(Rect::from_center_size(at, vec2(26.0, 26.0)), 6.0, stroke(1.0, alpha(col, 0.8)), StrokeKind::Inside);
            p.text(at, Align2::CENTER_CENTER, g, display(17.0), col);
        } else {
            p.text(at, Align2::CENTER_CENTER, g, display(17.0), TEXT_FAINT);
        }
    }

    // Big readout.
    let pct = (exact.abs() * 100.0).round();
    let num_color = if d.armed { TEXT } else { TEXT_DIM };
    let num = p.text(c + vec2(-0.04 * r, -0.04 * r), Align2::CENTER_CENTER, format!("{pct}"), display(0.52 * r), num_color);
    p.text(
        pos2(num.right() + 4.0, num.bottom() - 0.14 * r),
        Align2::LEFT_BOTTOM,
        "%",
        display(0.17 * r),
        TEXT_DIM,
    );
    spaced(p, c + vec2(0.0, 0.25 * r), Align2::CENTER_CENTER, "油门输出  THROTTLE", body(12.0), TEXT_DIM, 1.2);

    // Armed / locked badge.
    let badge = Rect::from_center_size(c + vec2(0.0, 0.44 * r), vec2(156.0, 30.0));
    let (col, label) = if d.armed { (GREEN, "已解锁 · ARMED") } else { (RED, "已锁定 · LOCKED") };
    if d.armed {
        let pulse = 0.6 + 0.4 * ((time * 3.0).sin() as f32 * 0.5 + 0.5);
        rect_glow(p, badge, 15.0, col, pulse);
    }
    p.rect(badge, 15.0, tint(col), stroke(1.0, col), StrokeKind::Inside);
    p.text(badge.center(), Align2::CENTER_CENTER, label, bold(13.0), col);

    p.text(
        c + vec2(0.0, 0.66 * r),
        Align2::CENTER_CENTER,
        format!("档位 {}  ·  上限 {:.0}%", d.tier, d.limit * 100.0),
        body(12.0),
        TEXT_DIM,
    );
}

// ---------- steering ----------

pub fn wheel_icon(p: &Painter, c: Pos2, r: f32, rot: f32, color: Color32) {
    radial_glow(p, c, r * 1.8, glow(color, 0.10));
    p.circle_stroke(c, r, stroke(3.5, color));
    for base in [0.0, PI, PI / 2.0] {
        p.line_segment([polar(c, r * 0.25, base + rot), polar(c, r * 0.95, base + rot)], stroke(3.0, color));
    }
    p.circle_filled(c, r * 0.25, color);
    let a = -PI / 2.0 + rot;
    p.line_segment([polar(c, r - 5.0, a), polar(c, r + 4.0, a)], stroke(4.0, Color32::WHITE));
}

/// Steering readout: rotating wheel, centered bar, and a numeric value.
pub fn steering_strip(p: &Painter, rect: Rect, value: f32, exact: f32) {
    let wheel_c = pos2(rect.left() + 34.0, rect.center().y);
    let active = exact.abs() > 0.005;
    wheel_icon(p, wheel_c, 24.0, value * PI / 2.0, if active { CYAN } else { TEXT_DIM });

    // Narrow: the value moves up beside the label and the bar takes the width.
    let compact = rect.width() < 440.0;
    let x0 = rect.left() + 84.0;
    let x1 = rect.right() - if compact { 14.0 } else { 120.0 };
    let y = rect.center().y + 6.0;
    let label = if compact { "转向输出" } else { "转向输出  STEERING" };
    spaced(p, pos2(x0, rect.top() + 8.0), Align2::LEFT_TOP, label, body(12.0), TEXT_DIM, 1.2);
    let track = Rect::from_min_max(pos2(x0, y - 3.0), pos2(x1, y + 3.0));
    p.rect_filled(track, 3.0, TRACK);
    let mid = track.center().x;
    for i in -4..=4 {
        let x = mid + track.width() / 2.0 * i as f32 / 4.0;
        let h = if i == 0 { 16.0 } else { 7.0 };
        p.line_segment([pos2(x, y - 6.0 - h), pos2(x, y - 6.0)], stroke(1.0, if i == 0 { TEXT_DIM } else { TEXT_FAINT }));
    }
    p.text(pos2(x0, y + 16.0), Align2::LEFT_CENTER, "左", body(11.0), TEXT_FAINT);
    p.text(pos2(x1, y + 16.0), Align2::RIGHT_CENTER, "右", body(11.0), TEXT_FAINT);

    let xv = mid + value.clamp(-1.0, 1.0) * track.width() / 2.0;
    if (xv - mid).abs() > 0.5 {
        let (l, r) = if xv > mid { (mid, xv) } else { (xv, mid) };
        let fill = Rect::from_min_max(pos2(l, track.top()), pos2(r, track.bottom()));
        let (cl, cr) = if xv > mid { (alpha(CYAN, 0.2), CYAN) } else { (CYAN, alpha(CYAN, 0.2)) };
        hgradient(p, fill.expand2(vec2(0.0, 5.0)), glow(cl, 0.15), glow(cr, 0.35));
        hgradient(p, fill, cl, cr);
    }
    let marker = Rect::from_center_size(pos2(xv, y), vec2(4.0, 22.0));
    radial_glow(p, marker.center(), 22.0, glow(CYAN, 0.5));
    p.rect_filled(marker, 2.0, Color32::WHITE);

    let pct = (exact.abs() * 100.0).round();
    let text = if pct == 0.0 { "居中".to_string() } else if exact < 0.0 { format!("左 {pct}%") } else { format!("右 {pct}%") };
    let color = if active { CYAN } else { TEXT_DIM };
    if compact {
        p.text(pos2(x1, rect.top() + 6.0), Align2::RIGHT_TOP, text, display(20.0), color);
    } else {
        p.text(pos2(rect.right() - 12.0, y - 2.0), Align2::RIGHT_CENTER, text, display(24.0), color);
    }
}

// ---------- input slider ----------

/// Centered -1..=1 slider. Returns the response so callers can tell whether
/// the pointer is holding it (the throttle springs back when released).
pub fn bipolar_slider(ui: &Ui, rect: Rect, id: &str, value: &mut f32, pos: Color32, neg: Color32) -> Response {
    let resp = ui.interact(rect, ui.id().with(id), Sense::click_and_drag()).on_hover_cursor(CursorIcon::Grab);
    let track = Rect::from_center_size(rect.center(), vec2(rect.width() - 28.0, 8.0));
    if resp.is_pointer_button_down_on() {
        if let Some(pt) = resp.interact_pointer_pos() {
            *value = ((pt.x - track.left()) / track.width() * 2.0 - 1.0).clamp(-1.0, 1.0);
        }
    }
    let p = ui.painter();
    p.rect_filled(track, 4.0, TRACK);
    let mid = track.center().x;
    for i in -10..=10 {
        let x = mid + track.width() / 2.0 * i as f32 / 10.0;
        let (h, col) = match i {
            0 => (10.0, TEXT_DIM),
            _ if i % 5 == 0 => (7.0, TEXT_FAINT),
            _ => (4.0, alpha(TEXT_FAINT, 0.6)),
        };
        p.line_segment([pos2(x, track.bottom() + 5.0), pos2(x, track.bottom() + 5.0 + h)], stroke(1.0, col));
    }

    let col = if *value >= 0.0 { pos } else { neg };
    let xv = mid + *value * track.width() / 2.0;
    if (xv - mid).abs() > 0.5 {
        let (l, r) = if xv > mid { (mid, xv) } else { (xv, mid) };
        let fill = Rect::from_min_max(pos2(l, track.top()), pos2(r, track.bottom()));
        let (cl, cr) = if xv > mid { (alpha(col, 0.25), col) } else { (col, alpha(col, 0.25)) };
        hgradient(p, fill.expand2(vec2(0.0, 6.0)), glow(cl, 0.12), glow(cr, 0.3));
        hgradient(p, fill, cl, cr);
    }
    let held = resp.is_pointer_button_down_on();
    let hc = pos2(xv, track.center().y);
    radial_glow(p, hc, 30.0, glow(col, if held { 0.6 } else if resp.hovered() { 0.35 } else { 0.18 }));
    p.circle_filled(hc, 12.0, PANEL);
    p.circle_stroke(hc, 12.0, stroke(2.0, col));
    p.circle_filled(hc, 4.5, col);
    resp
}
