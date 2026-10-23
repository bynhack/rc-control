use serde::{Deserialize, Serialize};
use std::path::Path;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum BackendKind {
    Elrs,
    Rc2,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(default)]
pub struct Config {
    /// Backend started at launch; the window can switch at runtime.
    pub backend: BackendKind,
    /// Input older than this counts as lost: output goes neutral and the
    /// throttle is disarmed until re-armed.
    pub heartbeat_timeout_ms: u64,
    pub elrs: ElrsConfig,
    pub rc2: Rc2Config,
    pub video: VideoConfig,
    pub radio: RadioConfig,
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

#[derive(Debug, Clone, Deserialize)]
#[serde(default)]
pub struct Rc2Config {
    pub port: String,
    pub baud: u32,
    pub steering_invert: bool,
    pub throttle_invert: bool,
    /// Device-side slew limit for Switch; protects the drivetrain.
    pub throttle_rate: f32,
    /// Rewrite unchanged values this often so a reconnected device catches up.
    pub refresh_ms: u64,
}

impl Default for Config {
    fn default() -> Self {
        Config {
            backend: BackendKind::Elrs,
            heartbeat_timeout_ms: 300,
            elrs: ElrsConfig::default(),
            rc2: Rc2Config::default(),
            video: VideoConfig::default(),
            radio: RadioConfig::default(),
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

impl Default for Rc2Config {
    fn default() -> Self {
        Rc2Config {
            port: "auto".into(),
            baud: crate::protocol::rc2::BAUD,
            steering_invert: false,
            throttle_invert: false,
            throttle_rate: 3.0,
            refresh_ms: 250,
        }
    }
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
        assert_eq!(cfg.rc2.baud, 460_800);
        assert_eq!(cfg.video.port, 5600);
        assert_eq!(cfg.video.codec, crate::video::rtp::Codec::H265);
        assert_eq!(cfg.radio.channel, 161);
    }

    #[test]
    fn partial_file_keeps_defaults() {
        let cfg: Config = toml::from_str("backend = \"rc2\"\n[elrs]\nsteering_invert = true\n").unwrap();
        assert_eq!(cfg.backend, BackendKind::Rc2);
        assert!(cfg.elrs.steering_invert);
        assert_eq!(cfg.elrs.throttle_channel, 2);
    }
}
