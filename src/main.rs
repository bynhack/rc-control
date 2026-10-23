// Release builds on Windows open no console window next to the GUI.
#![cfg_attr(all(windows, not(debug_assertions)), windows_subsystem = "windows")]

mod backend;
mod config;
mod control;
mod gui;
mod protocol;
mod radio;
mod video;
mod wheel;

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
  --probe-video 只接收图传 10 秒并打印统计，用来检查图传链路
  --probe-rc2   只做 RC2 连接握手并打印每一步结果，用来检查串口
  --probe-elrs  开高频头串口发 250 帧 CRSF 后退出，检查 ELRS 链路
  --probe-wheel 记录 20 秒方向盘/踏板的 HID 输入，用来定轴偏移";

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
    let mut probe_rc2 = false;
    let mut probe_elrs = false;
    let mut probe_wheel = false;
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
            "--probe-rc2" => probe_rc2 = true,
            "--probe-elrs" => probe_elrs = true,
            "--probe-wheel" => probe_wheel = true,
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
    if probe_wheel {
        return wheel::probe(28);
    }
    if probe_elrs {
        return probe_elrs_cmd(cfg.elrs.clone());
    }
    if probe_rc2 {
        return probe_rc2_cmd(cfg.rc2.clone());
    }
    if probe_video {
        return probe(cfg.video, cfg.radio);
    }

    let shared = Arc::new(Shared::new(Control::new(Duration::from_millis(cfg.heartbeat_timeout_ms)), &cfg));

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

    let result = gui::run(gui::Gui::new(cfg, path, shared, runner, video, radio.shared.clone()));
    radio.shutdown();
    shutdown();
    result
}

/// 开 ELRS 串口，流式发出 CRSF RC 帧（BETAFPV 模块无需应答也能工作），
/// 顺便收设备应答并打印。RXD 没接线时收不到任何东西，属预期。
fn probe_elrs_cmd(cfg: config::ElrsConfig) -> anyhow::Result<()> {
    println!("串口清单：");
    for p in backend::describe_ports() {
        println!("  {p}");
    }
    let name = backend::find_port(&cfg.port, backend::elrs::USB_VID, backend::elrs::USB_PID)
        .with_context(|| format!("找 ELRS 串口（port = {}）", cfg.port))?;
    println!("选定串口 {name}，波特率 {}，帧间隔 {} ms", cfg.baud, cfg.frame_interval_ms);

    let mut port = serialport::new(&name, cfg.baud)
        .timeout(Duration::from_millis(1))
        .open()
        .with_context(|| format!("打开 {name} 失败"))?;
    port.write_data_terminal_ready(false)?;
    port.write_request_to_send(false)?;
    println!("open ok，DTR/RTS 已释放。发送 250 帧（约 {} 秒）……", 250 * cfg.frame_interval_ms / 1000);

    let interval = Duration::from_millis(cfg.frame_interval_ms);
    let neutral = protocol::crsf::rc_frame(&[protocol::crsf::CH_CENTER; protocol::crsf::CHANNELS]);
    let ping = protocol::crsf::ping_frame();
    let mut parser = protocol::crsf::Parser::default();
    let mut buf = [0u8; 512];
    // 打开串口时模块可能复位，先等它缓过劲来。
    std::thread::sleep(Duration::from_millis(450));
    let mut reads = 0usize;
    port.write_all(&ping)?;
    for i in 0..250 {
        port.write_all(&if i == 125 { &ping } else { &neutral })?;
        match port.read(&mut buf) {
            Ok(n) if n > 0 => {
                reads += n;
                for ev in parser.push(&buf[..n]) {
                    println!("收到 {ev:?}");
                }
            }
            Err(e) if e.kind() == std::io::ErrorKind::TimedOut => {}
            Err(e) => anyhow::bail!("读串口失败：{e}"),
            _ => {}
        }
        std::thread::sleep(interval);
    }
    println!("250 帧全部写入成功；RX 回数据 {reads} 字节（RXD 未接线时为 0，属预期）");
    // 退出前发 3 帧中值，让接收机落地。没有接收机时这步是无害的。
    for _ in 0..3 {
        let _ = port.write_all(&neutral);
        std::thread::sleep(interval);
    }
    Ok(())
}

/// 在真实设备上逐段执行 RC2 握手，每步计时并打印，便于诊断 Windows 串口问题。
fn probe_rc2_cmd(cfg: config::Rc2Config) -> anyhow::Result<()> {
    println!("串口清单：");
    for p in backend::describe_ports() {
        println!("  {p}");
    }
    let name = backend::find_port(&cfg.port, backend::rc2::USB_VID, backend::rc2::USB_PID)
        .with_context(|| format!("找 RC2 串口（ Wanted {}）", cfg.port))?;
    println!("选定串口 {name}，波特率 {}", cfg.baud);

    let t = Instant::now();
    let port = serialport::new(&name, cfg.baud)
        .timeout(Duration::from_millis(400))
        .open()
        .with_context(|| format!("打开 {name} 失败"))?;
    println!("open            {:>7.0} ms", t.elapsed().as_secs_f64() * 1000.0);

    let mut dev = protocol::rc2::Rc2::new(port);
    let step = |t0: &mut Instant, ok: bool, label: &str, detail: String| {
        println!("{:<14} {}: {:>7.0} ms  {detail}", label, if ok { "ok " } else { "ERR" }, t0.elapsed().as_secs_f64() * 1000.0);
        *t0 = Instant::now();
    };

    let mut t = Instant::now();
    match dev.model() {
        Ok(m) => step(&mut t, true, "model", format!("{m:?}")),
        Err(e) => {
            step(&mut t, false, "model", e.to_string());
            anyhow::bail!("型号读取失败（如上）；后续流程不继续");
        }
    }
    let fw = dev.firmware();
    step(&mut t, fw.is_ok(), "firmware", fw.as_ref().map(|v| v.to_owned()).unwrap_or_else(|e| e.to_string()));
    let sn = dev.serial();
    step(&mut t, sn.is_ok(), "serial", sn.as_ref().map(|v| v.to_owned()).unwrap_or_else(|e| e.to_string()));
    let cps = dev.cp_names();
    step(&mut t, cps.is_ok(), "cp_names", cps.as_ref().map(|v| v.join(", ")).unwrap_or_else(|e| e.to_string()));
    let aps = dev.ap_names();
    step(&mut t, aps.is_ok(), "ap_names", aps.as_ref().map(|v| v.join(", ")).unwrap_or_else(|e| e.to_string()));
    // 读一个遥测点，模拟正常运行中最频繁的操作。
    if let (Ok(c), Ok(a)) = (&cps, &aps) {
        if !a.is_empty() {
            let v = dev.get_ap(0);
            step(&mut t, v.is_ok(), "get_ap[0]", v.map_or_else(|e| e.to_string(), |x| x.to_string()));
        }
        let _ = c;
    }
    println!("离开时再清零输出一次");
    Ok(())
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
