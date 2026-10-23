// Release builds on Windows open no console window next to the GUI.
#![cfg_attr(all(windows, not(debug_assertions)), windows_subsystem = "windows")]

mod backend;
mod config;
mod control;
mod gui;
mod protocol;
mod radio;
mod video;

use anyhow::Context;
use backend::{Runner, Shared};
use config::{BackendKind, Config};
use control::Control;
use std::path::PathBuf;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

const USAGE: &str = "\
用法: rc-control [--config 路径] [--backend elrs|rc2] [--list-ports] [--probe-video]

  --config      配置文件，默认依次找当前目录、程序所在目录下的 rc-control.toml
  --backend     覆盖配置里的启动方案
  --list-ports  列出串口及 USB 编号后退出
  --probe-video 只接收图传 10 秒并打印统计，用来检查图传链路";

fn default_config_path() -> PathBuf {
    let name = "rc-control.toml";
    let here = PathBuf::from(name);
    if here.exists() {
        return here;
    }
    std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(|d| d.join(name)))
        .filter(|p| p.exists())
        .unwrap_or(here)
}

fn main() -> anyhow::Result<()> {
    let mut args = std::env::args().skip(1);
    let mut config_path = None;
    let mut backend = None;
    let mut probe_video = false;
    while let Some(a) = args.next() {
        match a.as_str() {
            "--config" => config_path = Some(PathBuf::from(args.next().context("--config 后面要跟路径")?)),
            "--backend" => {
                backend = Some(match args.next().as_deref() {
                    Some("elrs") => BackendKind::Elrs,
                    Some("rc2") => BackendKind::Rc2,
                    _ => anyhow::bail!("--backend 只能是 elrs 或 rc2"),
                })
            }
            "--probe-video" => probe_video = true,
            "--list-ports" => {
                for p in backend::describe_ports() {
                    println!("{p}");
                }
                return Ok(());
            }
            "-h" | "--help" => {
                println!("{USAGE}");
                return Ok(());
            }
            other => anyhow::bail!("不认识的参数 {other}\n\n{USAGE}"),
        }
    }

    let path = config_path.unwrap_or_else(default_config_path);
    let mut cfg = Config::load(&path).with_context(|| format!("读取配置 {}", path.display()))?;
    if path.exists() {
        println!("配置: {}", path.display());
    } else {
        println!("配置: 未找到 {}，使用默认值", path.display());
    }
    if let Some(b) = backend {
        cfg.backend = b;
    }
    if probe_video {
        return probe(cfg.video, cfg.radio);
    }

    let shared = Arc::new(Shared::new(Control::new(Duration::from_millis(cfg.heartbeat_timeout_ms))));

    // Watchdog independent of any backend or the web server.
    let wd = shared.clone();
    std::thread::Builder::new().name("watchdog".into()).spawn(move || loop {
        wd.control().tick(Instant::now());
        std::thread::sleep(Duration::from_millis(20));
    })?;

    let runner = Arc::new(Mutex::new(Runner::start(cfg.backend, &cfg, shared.clone())));
    println!("方案: {:?}", cfg.backend);

    // RC2 holds its last value until told otherwise, so every way out must
    // zero the outputs: Ctrl+C in a terminal, or closing the window.
    let shutdown = {
        let (shared, runner) = (shared.clone(), runner.clone());
        move || {
            shared.control().estop();
            runner.lock().unwrap_or_else(|e| e.into_inner()).stop();
        }
    };
    let video = Arc::new(video::Shared::default());
    let _receiver = cfg.video.enabled.then(|| video::Receiver::start(cfg.video.clone(), video.clone()));
    let radio = Arc::new(radio::Radio::start(cfg.radio.clone(), cfg.video.port));

    let on_signal = shutdown.clone();
    let on_signal_radio = radio.clone();
    ctrlc::set_handler(move || {
        on_signal();
        on_signal_radio.shutdown();
        println!("已归零并关闭串口和图传网卡");
        std::process::exit(0);
    })?;

    let result = gui::run(gui::Gui::new(cfg, shared, runner, video, radio.shared.clone()));
    radio.shutdown();
    shutdown();
    result
}

/// Receives video without opening any serial port and prints what arrives.
fn probe(cfg: config::VideoConfig, radio_cfg: config::RadioConfig) -> anyhow::Result<()> {
    let shared = Arc::new(video::Shared::default());
    let _rx = video::Receiver::start(cfg.clone(), shared.clone());
    let radio = radio::Radio::start(radio_cfg, cfg.port);
    println!("监听 UDP {}，编码 {:?}，10 秒……", cfg.port, cfg.codec);
    for _ in 0..10 {
        std::thread::sleep(Duration::from_secs(1));
        let r = radio.shared.status().clone();
        println!(
            "图传网卡 {:?}  {}  信道 {} / {} MHz  wifi 帧 {}  wfb 帧 {}  RTP {}  链路 {:?}  丢包 {}",
            r.state, r.adapter, r.channel, r.width_mhz, r.wifi_frames, r.wfb_frames, r.rtp_packets, r.link_score, r.packet_loss
        );
        let s = shared.stats().clone();
        println!(
            "收包 {:>6.0} kbps  RTP {:>5}  PT {}  帧组 {:>4}  NAL {:?}  解出 {:>5} 帧  {:>3.0} fps  {}x{}  解码 {:.1} ms  {}",
            s.kbps,
            s.packets,
            s.payload_type.map(|p| p.to_string()).unwrap_or_else(|| "-".into()),
            s.units,
            s.nal_types,
            s.frames,
            s.fps,
            s.width,
            s.height,
            s.decode_ms,
            s.error
        );
    }
    Ok(())
}
