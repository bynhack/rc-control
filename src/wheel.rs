//! 方向盘/踏板硬件输入（Windows 直接读裸 HID）。
//!
//! 这些基座是 DirectInput/HID 类设备，不是 XInput——XInput 只认 Xbox 形状的
//! 控制器。所以绕过 DirectInput，直接读 HID 输入报告，用系统自带的 HID 驱动。
//!
//! - Thrustmaster T300RS 基座：VID 044F PID B66E，报告 id 07
//! - MOZA R5 / R5 Pro 基座：VID 346E PID 0004（改款 0014），报告 id 01
//!   踏板从基座的同一份报告里读（油门 Z、刹车 Rz）

use anyhow::{anyhow, Result};
use hidapi::HidApi;
use std::collections::hash_map::Entry;
use std::collections::HashMap;
use std::ffi::CString;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant};

/// Thrustmaster.
pub const VID_TM: u16 = 0x044f;
/// T300RS 基座（方向盘 + 踏板都从基座走线）。
pub const PID_T300_BASE: u16 = 0xb66e;
/// Gudsen / MOZA.
pub const VID_MOZA: u16 = 0x346e;
/// R5 与 R5 Pro 基座。0014 是同一基座的改款 PID。
pub const PID_R5: u16 = 0x0004;
pub const PID_R5_V2: u16 = 0x0014;

/// 哪一种基座。决定输入报告怎么解析。
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum WheelKind {
    T300,
    MozaR5,
}

/// HID 输入报告一次读这么大就足够方向盘用。
pub const REPORT_BUF: usize = 128;

/// 枚举到的设备条目（device_list 的元素是借用 + 平台路径，拷成拥有类型好跨线程）。
#[derive(Debug, Clone)]
pub struct DeviceEntry {
    pub path: String,
    pub vendor_id: u16,
    pub product_id: u16,
    pub usage_page: u16,
    pub usage: u16,
    pub interface_number: i32,
    pub product: String,
}

impl DeviceEntry {
    pub fn label(&self) -> String {
        format!(
            "{:04x}:{:04x} iface {} 使用页 {:#06x} usage {:#04x}  {}",
            self.vendor_id, self.product_id, self.interface_number, self.usage_page, self.usage, self.product
        )
    }
}

/// 这个 HID 条目是不是我们认识的基座，以及是哪一种。
pub fn kind_of(d: &DeviceEntry) -> Option<WheelKind> {
    match (d.vendor_id, d.product_id) {
        (VID_TM, PID_T300_BASE) => Some(WheelKind::T300),
        (VID_MOZA, PID_R5 | PID_R5_V2) => Some(WheelKind::MozaR5),
        _ => None,
    }
}

/// 游戏摇杆那条接口。MOZA 基座只认 Generic Desktop / Joystick，
/// 免得打开力反馈或厂商接口。
fn is_input_iface(d: &DeviceEntry) -> bool {
    match kind_of(d) {
        Some(WheelKind::MozaR5) => d.usage_page == 0x01 && d.usage == 0x04,
        Some(WheelKind::T300) => true,
        None => false,
    }
}

/// 列出已知基座的 HID 条目（包含 FFB/厂商接口；调用者按 usage 挑）。
pub fn list_devices() -> Result<Vec<DeviceEntry>> {
    let api = HidApi::new()?;
    let mut out = Vec::new();
    for d in api.device_list() {
        if d.vendor_id() != VID_TM && d.vendor_id() != VID_MOZA {
            continue;
        }
        out.push(DeviceEntry {
            path: d.path().to_string_lossy().into_owned(),
            vendor_id: d.vendor_id(),
            product_id: d.product_id(),
            usage_page: d.usage_page(),
            usage: d.usage(),
            interface_number: d.interface_number(),
            product: d.product_string().unwrap_or("").to_string(),
        });
    }
    Ok(out)
}

/// 每字节 min/max 记账，键 = (设备序号, 字节偏移)，值 = (最小, 最大)。
pub type ByteStats = Arc<Mutex<HashMap<(usize, usize), (u8, u8)>>>;

/// 解析出的一帧输入：steering -1..=1（左为负），throttle -1..=1（刹车为负）。
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Axes {
    pub steering: f32,
    pub throttle: f32,
}

/// T300RS 输入报告（报告 id 07）实测布局（都是小端 16 位，踏板其实只有
/// 低 10 位有意义：0..1023，松开=1023，踩下→0）：
///   b1..b2  转向：中位 ≈0x8000，左右极限 ≈0x4A00 / 0xB400
///   b3..b4  刹车
///   b5..b6  油门
///   b7..b8  离合
const STEER_HALF: f32 = 0x3800 as f32;

fn u16le(data: &[u8], i: usize) -> u16 {
    data[i] as u16 | ((data[i + 1] as u16) << 8)
}

/// 松开=1023、踩下=0 的踏板轴 -> 踩下比例 0..=1。
fn down_ratio(data: &[u8], i: usize) -> f32 {
    1.0 - (u16le(data, i) & 0x03ff) as f32 / 1023.0
}

/// T300 报告解析。正式路径走 `map_kind`；测试仍用这个入口。
#[cfg(test)]
pub fn map_report(data: &[u8]) -> Option<Axes> {
    map_kind(WheelKind::T300, data)
}

pub fn map_kind(kind: WheelKind, data: &[u8]) -> Option<Axes> {
    match kind {
        WheelKind::T300 => map_t300(data),
        WheelKind::MozaR5 => map_moza(data),
    }
}

/// T300RS 报告 id 07。
fn map_t300(data: &[u8]) -> Option<Axes> {
    if data.len() < 16 || data[0] != 0x07 {
        return None;
    }
    let steer = (u16le(data, 1) as f32 - 0x8000 as f32) / STEER_HALF;
    let gas = down_ratio(data, 5);
    let brake = down_ratio(data, 3);
    Some(Axes {
        steering: steer.clamp(-1.0, 1.0),
        throttle: (gas - brake).clamp(-1.0, 1.0),
    })
}

/// MOZA R5 报告 id 01（本机 R5 Pro 的报告描述符）：
///   b1..b2  X  转向，无符号 0..65535，中位 0x8000，向右增大
///   b5..b6  Z  油门，有符号，松开 = -32768，踩下 → +32767
///   b11..b12 Rz 刹车，刻度与油门相同
/// 离合器在 Dial（b13..b14），这里不用。
fn map_moza(data: &[u8]) -> Option<Axes> {
    if data.len() < 17 || data[0] != 0x01 {
        return None;
    }
    let steering = (u16le(data, 1) as f32 - 32768.0) / 32768.0;
    let gas = moza_pressed(i16le(data, 5));
    let brake = moza_pressed(i16le(data, 11));
    Some(Axes {
        steering: steering.clamp(-1.0, 1.0),
        throttle: (gas - brake).clamp(-1.0, 1.0),
    })
}

fn i16le(data: &[u8], i: usize) -> i16 {
    i16::from_le_bytes([data[i], data[i + 1]])
}

/// 松开 = -32768、踩下 = +32767 的轴 -> 踩下比例 0..=1。
fn moza_pressed(v: i16) -> f32 {
    (v as f32 + 32768.0) / 65535.0
}

/// GUI 用：后台滚动读 T300RS 并持续维护最新的解析值。
pub struct Live {
    latest: Arc<Mutex<Option<(Axes, Instant)>>>,
    stop: Arc<AtomicBool>,
    join: Option<thread::JoinHandle<()>>,
}

impl Live {
    /// 找基座并开始后台读。优先 MOZA R5，没有再找 T300RS。打不开就报错。
    pub fn start() -> Result<Live> {
        let devs = list_devices()?;
        let dev = devs
            .iter()
            .find(|d| kind_of(d) == Some(WheelKind::MozaR5) && is_input_iface(d))
            .or_else(|| devs.iter().find(|d| kind_of(d) == Some(WheelKind::T300) && is_input_iface(d)))
            .cloned()
            .ok_or_else(|| anyhow!("没找到方向盘（MOZA R5 346e:0004，或 Thrustmaster 044f:b66e）"))?;
        let kind = kind_of(&dev).expect("kind checked above");
        let reader = Reader::open(&dev, 0, Arc::new(Mutex::new(HashMap::new())))?;
        let latest = Arc::new(Mutex::new(None));
        let stop = Arc::new(AtomicBool::new(false));
        let (latest2, stop2) = (latest.clone(), stop.clone());
        let join = thread::Builder::new()
            .name("wheel-live".into())
            .spawn(move || {
                while !stop2.load(Ordering::Relaxed) {
                    if let Some(r) = reader.slot.lock().unwrap().as_ref() {
                        if let Some(axes) = map_kind(kind, r) {
                            *latest2.lock().unwrap() = Some((axes, Instant::now()));
                        }
                    }
                    thread::sleep(Duration::from_millis(2));
                }
            })?;
        Ok(Live { latest, stop, join: Some(join) })
    }

    /// 有新鲜输入就返回；`fresh` 超时算失效（模拟盘被拔/停发）。
    pub fn poll(&self, fresh: Duration) -> Option<Axes> {
        let (axes, at) = (*self.latest.lock().unwrap())?;
        (at.elapsed() <= fresh).then_some(axes)
    }

    fn stop(&mut self) {
        self.stop.store(true, Ordering::Relaxed);
        if let Some(j) = self.join.take() {
            let _ = j.join();
        }
    }
}

impl Drop for Live {
    fn drop(&mut self) {
        self.stop();
    }
}


/// 后台滚动读一个 HID 设备，最新一份完整输入报告放在共享槽里。
/// GUI 每帧来取即可；线程遇读错误（拔线）自己退出，槽里不再有新报告。
pub struct Reader {
    /// 最新报告；None 表示还没读到过（也用作初始化错误通道）。
    pub slot: Arc<Mutex<Option<Vec<u8>>>>,
    stop: Arc<AtomicBool>,
    join: Option<thread::JoinHandle<()>>,
}

impl Reader {
    pub fn open(entry: &DeviceEntry, dev_index: usize, stats: ByteStats) -> Result<Reader> {
        let slot = Arc::new(Mutex::new(None));
        let stop = Arc::new(AtomicBool::new(false));
        let (slot2, stop2) = (slot.clone(), stop.clone());
        let path = entry.path.clone();
        let product = entry.product.clone();

        let join = thread::Builder::new()
            .name("wheel-read".into())
            .spawn(move || {
                let fail = |msg: String, slot: &Arc<Mutex<Option<Vec<u8>>>>| {
                    *slot.lock().unwrap() = Some(msg.into_bytes());
                };
                let Ok(api) = HidApi::new() else {
                    fail("HidApi 初始化失败".into(), &slot2);
                    return;
                };
                let Ok(cstr) = CString::new(path) else { return };
                let handle = match api.open_path(&cstr) {
                    Ok(h) => h,
                    Err(e) => {
                        fail(format!("打开失败（{product}）：{e}"), &slot2);
                        return;
                    }
                };
                let mut buf = vec![0u8; REPORT_BUF];
                loop {
                    if stop2.load(Ordering::Relaxed) {
                        return;
                    }
                    match handle.read_timeout(&mut buf, 20) {
                        Ok(n) if n > 0 => {
                            *slot2.lock().unwrap() = Some(buf[..n].to_vec());
                            let mut st = stats.lock().unwrap();
                            for (k, v) in buf[..n].iter().enumerate() {
                                match st.entry((dev_index, k)) {
                                    Entry::Occupied(mut e) => {
                                        let (lo, hi) = e.get_mut();
                                        *lo = (*lo).min(*v);
                                        *hi = (*hi).max(*v);
                                    }
                                    Entry::Vacant(e) => {
                                        e.insert((*v, *v));
                                    }
                                }
                            }
                        }
                        Ok(_) => {}
                        Err(_) => {
                            fail("读取中断（拔线/驱动占用？）".into(), &slot2);
                            return;
                        }
                    }
                }
            })?;
        Ok(Reader { slot, stop, join: Some(join) })
    }

    fn stop(&mut self) {
        self.stop.store(true, Ordering::Relaxed);
        if let Some(j) = self.join.take() {
            let _ = j.join();
        }
    }
}

impl Drop for Reader {
    fn drop(&mut self) {
        self.stop();
    }
}

/// 交互探针 v2：把每份改变的输入报告按时间戳记成 CSV 轨迹，
/// 便于按时段定位每个字节对应的控制。运行时请按提示的动作顺序操作。
/// 时间线（全自动提示，跟随秒数）：
///   0-4s   静止（方向盘居中，踏板全松）
///   4-8s   只踩油门：踩到底，再完全松开
///   8-12s  只踩刹车：踩到底，再完全松开
///   12-16s 方向盘：最左到最右一个来回，回正
///   16-20s 按住方向盘上的任意按键 2 秒
///   20-24s 静止
pub fn probe(seconds: u64) -> Result<()> {
    let devs = list_devices()?;
    if devs.is_empty() {
        return Err(anyhow!("没找到方向盘 HID 设备（MOZA 346e 或 Thrustmaster 044f）"));
    }
    println!("找到 {} 个方向盘 HID 条目：", devs.len());
    for (i, d) in devs.iter().enumerate() {
        println!("  [{i}] {}", d.label());
    }

    let stats: ByteStats = Arc::new(Mutex::new(HashMap::new()));
    // 变化轨迹："<ms> < dev> <hex>"。
    let trace: Arc<Mutex<Vec<String>>> = Arc::new(Mutex::new(Vec::new()));
    let t_start = Instant::now();
    let mut readers: Vec<(usize, Reader)> = Vec::new();
    for (i, d) in devs.iter().enumerate() {
        match Reader::open(d, i, stats.clone()) {
            Ok(r) => readers.push((i, r)),
            Err(e) => println!("  [{i}] 打开失败：{e}"),
        }
    }
    {
        let trace2 = trace.clone();
        let slotc: Vec<Arc<Mutex<Option<Vec<u8>>>>> = readers.iter().map(|(_, r)| r.slot.clone()).collect();
        let last: Arc<Mutex<Vec<Option<Vec<u8>>>>> =
            Arc::new(Mutex::new(vec![None; slotc.len().max(1)]));
        let last2 = last.clone();
        thread::spawn(move || loop {
            thread::sleep(Duration::from_millis(2));
            for (i, slot) in slotc.iter().enumerate() {
                let cur = slot.lock().unwrap().clone();
                let mut last = last2.lock().unwrap();
                if i < last.len() && cur != last[i] {
                    if let Some(s) = &cur {
                        let ms = t_start.elapsed().as_millis();
                        let hex: String = s.iter().map(|b| format!("{b:02x}")).collect();
                        trace2.lock().unwrap().push(format!("{ms} {i} {hex}"));
                    }
                    if i < last.len() {
                        last[i] = cur;
                    }
                }
            }
            if t_start.elapsed() >= Duration::from_secs(seconds + 2) {
                return;
            }
        });
    }

    let phases = [
        ("静止：手离盘，踏板全部松开", 0u64),
        ("【油门】慢慢踩到底（8 秒内到脚底）", 3),
        ("【保持到底】", 12),
        ("【油门】慢慢松开回原位", 17),
        ("静止（收尾）", 24),
    ];
    println!("\n按口令操作！时间线：");
    for (f, t) in phases {
        println!("  {t:>2}-{}s  {f}", t + 4);
    }
    let phase_names: Vec<(u64, &str)> = phases.iter().map(|(f, t)| (*t, *f)).collect();
    let t0 = Instant::now();
    let mut next_phase = 0;
    while t0.elapsed() < Duration::from_secs(seconds) {
        let s = t0.elapsed().as_secs();
        if next_phase < phase_names.len() && s >= phase_names[next_phase].0 {
            println!(">>> {s}s：{}", phase_names[next_phase].1);
            next_phase += 1;
        }
        thread::sleep(Duration::from_millis(200));
    }

    println!("\n== 每字节 min..max ==（对照仅粗看）");
    let snapshot = stats.lock().unwrap().clone();
    let mut keys: Vec<(usize, usize)> = snapshot.keys().cloned().collect();
    keys.sort();
    let mut last_dev = usize::MAX;
    for (di, off) in &keys {
        let (lo, hi) = snapshot[&(*di, *off)];
        if *di != last_dev {
            println!("[设备 {di}]");
            last_dev = *di;
        }
        println!("  b{off:<3} min {lo:3} max {hi:3}");
    }

    std::thread::sleep(Duration::from_millis(1500));
    std::fs::write("wheel-trace.csv", trace.lock().unwrap().join("\n")).ok();
    let n = trace.lock().unwrap().len();
    println!("\n轨迹已写入 wheel-trace.csv（{n} 条）");
    drop(readers);
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    /// A report 07 with the given raw steering and pedal words.
    fn report(steer: u16, brake: u16, gas: u16) -> Vec<u8> {
        let mut r = vec![0u8; 16];
        r[0] = 0x07;
        r[1..3].copy_from_slice(&steer.to_le_bytes());
        r[3..5].copy_from_slice(&brake.to_le_bytes());
        r[5..7].copy_from_slice(&gas.to_le_bytes());
        r
    }

    #[test]
    fn centred_and_released_is_neutral() {
        let a = map_report(&report(0x8000, 1023, 1023)).unwrap();
        assert_eq!(a, Axes { steering: 0.0, throttle: 0.0 });
    }

    #[test]
    fn full_lock_and_pedals() {
        assert_eq!(map_report(&report(0x4800, 1023, 1023)).unwrap().steering, -1.0);
        assert_eq!(map_report(&report(0xB800, 1023, 1023)).unwrap().steering, 1.0);
        assert_eq!(map_report(&report(0x8000, 1023, 0)).unwrap().throttle, 1.0);
        assert_eq!(map_report(&report(0x8000, 0, 1023)).unwrap().throttle, -1.0);
        // Both pedals floored cancel out.
        assert_eq!(map_report(&report(0x8000, 0, 0)).unwrap().throttle, 0.0);
        // Only the low 10 bits of a pedal word count.
        assert_eq!(map_report(&report(0x8000, 0xFC00 | 1023, 0xFC00 | 1023)).unwrap().throttle, 0.0);
    }

    #[test]
    fn ignores_other_reports() {
        let mut r = report(0x8000, 1023, 1023);
        r[0] = 0x01;
        assert!(map_report(&r).is_none());
        assert!(map_report(&[0x07, 0, 0]).is_none());
    }

    /// 本机 R5 Pro 静止时抓到的报告：盘略偏右，踏板全松。
    fn moza_rest() -> Vec<u8> {
        vec![
            0x01, 0x6b, 0x81, 0x01, 0x80, 0x00, 0x80, 0x01, 0x80, 0x01, 0x80, 0x00, 0x80, 0x00, 0x80, 0x00, 0x80,
        ]
    }

    #[test]
    fn moza_rest_is_near_centre_with_pedals_up() {
        let a = map_kind(WheelKind::MozaR5, &moza_rest()).unwrap();
        assert!((a.steering - (0x816bu16 as f32 - 32768.0) / 32768.0).abs() < 1e-5);
        assert!(a.steering.abs() < 0.02);
        assert_eq!(a.throttle, 0.0);
    }

    #[test]
    fn moza_full_lock_and_pedals() {
        let mut r = moza_rest();
        r[1] = 0x00;
        r[2] = 0x00;
        assert_eq!(map_kind(WheelKind::MozaR5, &r).unwrap().steering, -1.0);
        r[1] = 0xff;
        r[2] = 0xff;
        assert!((map_kind(WheelKind::MozaR5, &r).unwrap().steering - 1.0).abs() < 1e-4);

        let mut gas = moza_rest();
        gas[5] = 0xff;
        gas[6] = 0x7f;
        assert_eq!(map_kind(WheelKind::MozaR5, &gas).unwrap().throttle, 1.0);
        let mut brake = moza_rest();
        brake[11] = 0xff;
        brake[12] = 0x7f;
        assert_eq!(map_kind(WheelKind::MozaR5, &brake).unwrap().throttle, -1.0);
        let mut both = gas;
        both[11] = 0xff;
        both[12] = 0x7f;
        assert_eq!(map_kind(WheelKind::MozaR5, &both).unwrap().throttle, 0.0);
    }

    #[test]
    fn moza_ignores_other_reports() {
        let mut r = moza_rest();
        r[0] = 0x02;
        assert!(map_kind(WheelKind::MozaR5, &r).is_none());
        assert!(map_kind(WheelKind::MozaR5, &[0x01, 0, 0]).is_none());
    }
}
