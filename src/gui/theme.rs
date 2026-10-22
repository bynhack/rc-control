//! Palette, fonts and egui visuals for the dashboard.

use eframe::egui::{self, Color32, FontFamily, FontId};
use std::path::{Path, PathBuf};
use std::sync::Arc;

pub const BG: Color32 = Color32::from_rgb(7, 10, 15);
pub const PANEL: Color32 = Color32::from_rgb(13, 18, 25);
pub const PANEL_EDGE: Color32 = Color32::from_rgb(29, 38, 51);
pub const TRACK: Color32 = Color32::from_rgb(24, 32, 44);
pub const TEXT: Color32 = Color32::from_rgb(232, 238, 246);
pub const TEXT_DIM: Color32 = Color32::from_rgb(124, 137, 154);
pub const TEXT_FAINT: Color32 = Color32::from_rgb(66, 77, 92);

pub const CYAN: Color32 = Color32::from_rgb(0, 212, 255);
pub const BLUE: Color32 = Color32::from_rgb(76, 108, 255);
pub const AMBER: Color32 = Color32::from_rgb(255, 178, 36);
pub const ORANGE: Color32 = Color32::from_rgb(255, 110, 20);
pub const RED: Color32 = Color32::from_rgb(255, 58, 52);
pub const GREEN: Color32 = Color32::from_rgb(46, 232, 138);

/// Glow colors are additive (alpha 0): they brighten what is underneath.
pub fn glow(c: Color32, k: f32) -> Color32 {
    let s = |v: u8| (v as f32 * k).clamp(0.0, 255.0) as u8;
    Color32::from_rgb_additive(s(c.r()), s(c.g()), s(c.b()))
}

pub fn alpha(c: Color32, a: f32) -> Color32 {
    Color32::from_rgba_unmultiplied(c.r(), c.g(), c.b(), (a.clamp(0.0, 1.0) * 255.0) as u8)
}

/// Background tint for selected or active controls. egui blends in linear
/// space, so small alphas already read strong; keep these low.
pub fn tint(c: Color32) -> Color32 {
    alpha(c, 0.045)
}

/// Hover wash for unselected controls.
pub fn hover() -> Color32 {
    alpha(TEXT, 0.025)
}

/// Forward throttle heats from amber to red; reverse cools from cyan to blue.
/// Decided by the sign bit, so -0.0 (the start of a reverse arc) stays cyan.
pub fn throttle_color(v: f32) -> Color32 {
    let t = v.abs().clamp(0.0, 1.0);
    if v.is_sign_positive() { AMBER.lerp_to_gamma(RED, t) } else { CYAN.lerp_to_gamma(BLUE, t) }
}

pub fn bold_family() -> FontFamily {
    FontFamily::Name("bold".into())
}

pub fn display_family() -> FontFamily {
    FontFamily::Name("display".into())
}

/// Chinese body text.
pub fn body(size: f32) -> FontId {
    FontId::new(size, FontFamily::Proportional)
}

/// Chinese headings.
pub fn bold(size: f32) -> FontId {
    FontId::new(size, bold_family())
}

/// DIN-style numerals and Latin labels; CJK falls back to the bold face.
pub fn display(size: f32) -> FontId {
    FontId::new(size, display_family())
}

pub fn mono(size: f32) -> FontId {
    FontId::monospace(size)
}

pub fn apply(ctx: &egui::Context) {
    install_fonts(ctx);
    ctx.set_theme(egui::Theme::Dark);
    let mut v = egui::Visuals::dark();
    v.panel_fill = BG;
    v.window_fill = PANEL;
    v.extreme_bg_color = BG;
    v.override_text_color = Some(TEXT);
    v.selection.bg_fill = alpha(CYAN, 0.35);
    ctx.set_visuals_of(egui::Theme::Dark, v);
    ctx.style_mut_of(egui::Theme::Dark, |s| s.interaction.selectable_labels = false);
}

// ---------- fonts ----------

/// A system font file plus the full names of the faces to use from it.
struct SystemFont {
    path: PathBuf,
    regular: &'static str,
    bold: &'static str,
    bold_path: Option<&'static str>,
}

/// PingFang ships as a downloadable font asset whose directory name is a
/// hash, so it is searched for rather than hard-coded.
pub fn pingfang_path() -> Option<PathBuf> {
    let root = Path::new("/System/Library/AssetsV2");
    for dir in std::fs::read_dir(root).ok()?.flatten() {
        if !dir.file_name().to_string_lossy().starts_with("com_apple_MobileAsset_Font") {
            continue;
        }
        for asset in std::fs::read_dir(dir.path()).into_iter().flatten().flatten() {
            let p = asset.path().join("AssetData/PingFang.ttc");
            if p.exists() {
                return Some(p);
            }
        }
    }
    None
}

fn ui_fonts() -> Vec<SystemFont> {
    let mut v = Vec::new();
    if let Some(path) = pingfang_path() {
        v.push(SystemFont { path, regular: "PingFang SC Regular", bold: "PingFang SC Medium", bold_path: None });
    }
    v.push(SystemFont {
        path: "C:\\Windows\\Fonts\\msyh.ttc".into(),
        regular: "Microsoft YaHei",
        bold: "Microsoft YaHei Bold",
        bold_path: Some("C:\\Windows\\Fonts\\msyhbd.ttc"),
    });
    v.push(SystemFont {
        path: "/System/Library/Fonts/Hiragino Sans GB.ttc".into(),
        regular: "Hiragino Sans GB W3",
        bold: "Hiragino Sans GB W6",
        bold_path: None,
    });
    v
}

/// DIN on macOS; Bahnschrift (Microsoft's DIN) on Windows.
const DISPLAY_FONTS: [&str; 3] = [
    "/System/Library/Fonts/Supplemental/DIN Alternate Bold.ttf",
    "C:\\Windows\\Fonts\\bahnschrift.ttf",
    "/System/Library/Fonts/Supplemental/DIN Condensed Bold.ttf",
];

/// Index of the face called `full_name` inside a .ttc, by its name table.
/// A plain .ttf is face 0.
pub fn face_index(data: &[u8], full_name: &str) -> Option<u32> {
    let u16_at = |o: usize| data.get(o..o + 2).map(|b| u16::from_be_bytes([b[0], b[1]]) as usize);
    let u32_at = |o: usize| data.get(o..o + 4).map(|b| u32::from_be_bytes([b[0], b[1], b[2], b[3]]) as usize);
    if data.get(0..4) != Some(b"ttcf") {
        return Some(0);
    }
    let want: Vec<u8> = full_name.encode_utf16().flat_map(|c| c.to_be_bytes()).collect();
    for i in 0..u32_at(8)? {
        let face = u32_at(12 + 4 * i)?;
        for t in 0..u16_at(face + 4)? {
            let rec = face + 12 + 16 * t;
            if data.get(rec..rec + 4) != Some(b"name") {
                continue;
            }
            let table = u32_at(rec + 8)?;
            let strings = table + u16_at(table + 4)?;
            for r in 0..u16_at(table + 2)? {
                let n = table + 6 + 12 * r;
                // Windows platform, US English, full font name (id 4).
                if (u16_at(n)?, u16_at(n + 4)?, u16_at(n + 6)?) != (3, 0x409, 4) {
                    continue;
                }
                let (len, off) = (u16_at(n + 8)?, u16_at(n + 10)?);
                if data.get(strings + off..strings + off + len) == Some(&want[..]) {
                    return Some(i as u32);
                }
            }
        }
    }
    None
}

/// Font files are read once and live for the whole process.
fn leak_file(path: &Path) -> Option<&'static [u8]> {
    std::fs::read(path).ok().map(|b| &*Box::leak(b.into_boxed_slice()))
}

fn face(data: &'static [u8], name: &str) -> Option<egui::FontData> {
    let mut f = egui::FontData::from_static(data);
    f.index = face_index(data, name)?;
    Some(f)
}

fn install_fonts(ctx: &egui::Context) {
    let mut fonts = egui::FontDefinitions::default();
    let mut bold_chain: Vec<String> = Vec::new();

    let ui = ui_fonts().into_iter().find_map(|sf| leak_file(&sf.path).map(|d| (sf, d)));
    match ui {
        Some((sf, data)) => {
            // Regular text must render even if a face name differs on some OS build.
            let regular = face(data, sf.regular).unwrap_or_else(|| egui::FontData::from_static(data));
            let bold_face = match sf.bold_path {
                Some(p) => leak_file(Path::new(p)).and_then(|d| face(d, sf.bold)),
                None => face(data, sf.bold),
            };
            fonts.font_data.insert("ui".into(), Arc::new(regular.clone()));
            fonts.font_data.insert("ui-bold".into(), Arc::new(bold_face.unwrap_or(regular)));
            fonts.families.get_mut(&FontFamily::Proportional).unwrap().insert(0, "ui".into());
            fonts.families.get_mut(&FontFamily::Monospace).unwrap().push("ui".into());
            bold_chain.push("ui-bold".into());
        }
        None => eprintln!("没找到系统中文字体，界面文字可能显示为方块"),
    }
    bold_chain.extend(fonts.families[&FontFamily::Proportional].iter().cloned());

    let mut display_chain = Vec::new();
    if let Some(data) = DISPLAY_FONTS.iter().find_map(|p| leak_file(Path::new(p))) {
        fonts.font_data.insert("display".into(), Arc::new(egui::FontData::from_static(data)));
        display_chain.push("display".to_string());
    }
    display_chain.extend(bold_chain.iter().cloned());

    fonts.families.insert(bold_family(), bold_chain);
    fonts.families.insert(display_family(), display_chain);
    ctx.set_fonts(fonts);
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn plain_ttf_is_face_zero() {
        assert_eq!(face_index(b"\0\x01\0\0rest", "anything"), Some(0));
    }

    #[test]
    fn finds_pingfang_faces_by_name() {
        let Some(path) = pingfang_path() else { return }; // not macOS
        let data = std::fs::read(path).unwrap();
        assert_eq!(face_index(&data, "PingFang SC Regular"), Some(3));
        assert_eq!(face_index(&data, "PingFang SC Medium"), Some(7));
        assert_eq!(face_index(&data, "No Such Face"), None);
    }

    #[test]
    fn throttle_colors_by_direction() {
        assert_eq!(throttle_color(1.0), RED);
        assert_eq!(throttle_color(-1.0), BLUE);
        assert_eq!(throttle_color(0.0), AMBER);
        assert_eq!(throttle_color(-0.0), CYAN);
    }
}
