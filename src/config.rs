use serde::Deserialize;
use std::path::Path;

#[derive(Debug, Clone, Deserialize)]
#[serde(default)]
pub struct Config {
    /// Input older than this counts as lost: output goes neutral and the
    /// throttle is disarmed until re-armed.
    pub heartbeat_timeout_ms: u64,
    pub elrs: ElrsConfig,
    pub video: VideoConfig,
    pub radio: RadioConfig,
    pub wheel: WheelConfig,
}

/// 方向盘硬件输入（Thrustmaster T300RS 等裸 HID 设备）。
#[derive(Debug, Clone, Deserialize)]
#[serde(default)]
pub struct WheelConfig {
    /// 窗口开着时后台读取并接管 steering/throttle。
    pub enabled: bool,
    /// 方向是否反相（不同人习惯不同）。
    pub steering_invert: bool,
    /// 油门/刹车按各自刻度归一后整体是否反相。
    pub throttle_invert: bool,
    /// 转向中位死区 0..0.1：细小抖动不算转向。
    pub steering_deadzone: f32,
    /// "auto" 用 VID 044f 自动找，或写死 "T300RS" 等名字片段（暂只支持 auto）。
    pub device: String,
}

impl Default for WheelConfig {
    fn default() -> Self {
        WheelConfig {
            enabled: true,
            steering_invert: false,
            throttle_invert: false,
            steering_deadzone: 0.02,
            device: "auto".into(),
        }
    }
}

/// Built-in video radio (Aviateur's receive path on an RTL8812AU-class
/// USB adapter). Received video goes to `video.port`.
#[derive(Debug, Clone, Deserialize)]
#[serde(default)]
pub struct RadioConfig {
    pub enabled: bool,
    /// "auto", or part of the adapter name as listed (e.g. "RTL8812AU").
    pub adapter: String,
    /// Wi-Fi channel the camera transmits on, e.g. 161 = 5805 MHz.
    pub channel: u8,
    /// 20 or 40.
    pub width_mhz: u16,
    /// gs.key path; empty uses the OpenIPC default key.
    pub key: Option<String>,
}

impl Default for RadioConfig {
    fn default() -> Self {
        RadioConfig { enabled: true, adapter: "auto".into(), channel: 161, width_mhz: 20, key: None }
    }
}

#[derive(Debug, Clone, Deserialize)]
#[serde(default)]
pub struct VideoConfig {
    pub enabled: bool,
    /// UDP port the RTP stream arrives on (Aviateur's forward port, or
    /// wfb-ng's usual 5600).
    pub port: u16,
    /// OpenIPC cameras default to H.265.
    pub codec: crate::video::rtp::Codec,
}

impl Default for VideoConfig {
    fn default() -> Self {
        VideoConfig { enabled: true, port: 5600, codec: crate::video::rtp::Codec::H265 }
    }
}

#[derive(Debug, Clone, Deserialize)]
#[serde(default)]
pub struct ElrsConfig {
    /// Serial device, or "auto" to pick the TX module by USB id.
    pub port: String,
    /// 115200 is the only rate the USB-patched AION Nano answers on.
    pub baud: u32,
    pub frame_interval_ms: u64,
    /// 1-based CRSF channels. Keep both within 1..=4: ELRS sends channels
    /// 5+ at reduced resolution (channel 5 is a 2-position switch).
    pub steering_channel: usize,
    pub throttle_channel: usize,
    pub steering_invert: bool,
    pub throttle_invert: bool,
}

impl Default for Config {
    fn default() -> Self {
        Config {
            heartbeat_timeout_ms: 300,
            elrs: ElrsConfig::default(),
            video: VideoConfig::default(),
            radio: RadioConfig::default(),
            wheel: WheelConfig::default(),
        }
    }
}

impl Default for ElrsConfig {
    fn default() -> Self {
        ElrsConfig {
            port: "auto".into(),
            baud: 115_200,
            frame_interval_ms: 20,
            steering_channel: 1,
            throttle_channel: 2,
            steering_invert: false,
            throttle_invert: false,
        }
    }
}

/// Writes the ELRS direction flips into the config file, touching only those
/// two keys so the rest of the file (comments included) is kept.
pub fn save_invert(path: &Path, steering: bool, throttle: bool) -> anyhow::Result<()> {
    let text = if path.exists() { std::fs::read_to_string(path)? } else { String::new() };
    let mut doc: toml_edit::DocumentMut = text.parse()?;
    let section = "elrs";
    if !doc.contains_table(section) {
        doc[section] = toml_edit::table();
    }
    doc[section]["steering_invert"] = toml_edit::value(steering);
    doc[section]["throttle_invert"] = toml_edit::value(throttle);
    std::fs::write(path, doc.to_string())?;
    Ok(())
}

impl Config {
    pub fn load(path: &Path) -> anyhow::Result<Config> {
        if !path.exists() {
            return Ok(Config::default());
        }
        let text = std::fs::read_to_string(path)?;
        let cfg: Config = toml::from_str(&text)?;
        cfg.validate()?;
        Ok(cfg)
    }

    fn validate(&self) -> anyhow::Result<()> {
        let e = &self.elrs;
        for (name, ch) in [("steering_channel", e.steering_channel), ("throttle_channel", e.throttle_channel)] {
            anyhow::ensure!((1..=16).contains(&ch), "elrs.{name} 必须在 1..16 之间");
        }
        anyhow::ensure!(e.steering_channel != e.throttle_channel, "转向和油门不能用同一个通道");
        anyhow::ensure!((4..=100).contains(&e.frame_interval_ms), "elrs.frame_interval_ms 必须在 4..100 之间");
        anyhow::ensure!(self.heartbeat_timeout_ms >= 100, "heartbeat_timeout_ms 至少 100");
        anyhow::ensure!(matches!(self.radio.width_mhz, 20 | 40), "radio.width_mhz 只能是 20 或 40");
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn example_file_parses() {
        let cfg: Config = toml::from_str(include_str!("../rc-control.example.toml")).unwrap();
        cfg.validate().unwrap();
        assert_eq!(cfg.elrs.baud, 115_200);
        assert_eq!(cfg.video.port, 5600);
        assert_eq!(cfg.video.codec, crate::video::rtp::Codec::H265);
        assert_eq!(cfg.radio.channel, 161);
    }

    #[test]
    fn save_invert_keeps_comments_and_other_keys() {
        let dir = std::env::temp_dir().join(format!("rc-control-test-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let path = dir.join("rc-control.toml");
        std::fs::write(&path, "# mine\n[elrs]\n# the adapter\nport = \"COM5\"\nbaud = 400000\n").unwrap();
        save_invert(&path, true, false).unwrap();
        let text = std::fs::read_to_string(&path).unwrap();
        assert!(text.contains("# mine") && text.contains("# the adapter") && text.contains("port = \"COM5\""));
        let cfg: Config = toml::from_str(&text).unwrap();
        assert!(cfg.elrs.steering_invert && !cfg.elrs.throttle_invert);
        assert_eq!(cfg.elrs.baud, 400_000);
        save_invert(&path, false, true).unwrap();
        let cfg: Config = toml::from_str(&std::fs::read_to_string(&path).unwrap()).unwrap();
        assert!(!cfg.elrs.steering_invert && cfg.elrs.throttle_invert);
        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn partial_file_keeps_defaults() {
        let cfg: Config = toml::from_str("[elrs]\nsteering_invert = true\n").unwrap();
        assert!(cfg.elrs.steering_invert);
        assert_eq!(cfg.elrs.throttle_channel, 2);
    }

    #[test]
    fn files_from_the_two_scheme_era_still_load() {
        // `backend` and [rc2] no longer exist; old local configs keep working.
        let old = "backend = \"rc2\"\n[elrs]\nbaud = 400000\n[rc2]\nport = \"COM3\"\nthrottle_rate = 3.0\n";
        let cfg: Config = toml::from_str(old).unwrap();
        cfg.validate().unwrap();
        assert_eq!(cfg.elrs.baud, 400_000);
    }
}
