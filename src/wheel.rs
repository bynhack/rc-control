//! 方向盘/踏板硬件输入（Windows 直接读裸 HID）。
//!
//! Thrustmaster T300RS（基座 VID 044F PID B66E）是 DirectInput/HID 类设备，
//! 不是 XInput——XInput 只认 Xbox 形状的控制器。所以正确的做法是绕过
//! DirectInput API，直接用 HID 读输入报告：系统自带的 HID 驱动就够，
//! 装不装 Thrustmaster 官方驱动都无影响。

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

/// 列出 Thrustmaster 的所有 HID 条目（包含 FFB/厂商接口；调用者按 usage 挑）。
pub fn list_devices() -> Result<Vec<DeviceEntry>> {
    let api = HidApi::new()?;
    let mut out = Vec::new();
    for d in api.device_list() {
        if d.vendor_id() != VID_TM {
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

/// 从一份输入报告解析轴值。不是 07 报告（FFB 状态、中断帧等）就返回 None。
pub fn map_report(data: &[u8]) -> Option<Axes> {
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

/// GUI 用：后台滚动读 T300RS 并持续维护最新的解析值。
pub struct Live {
    latest: Arc<Mutex<Option<(Axes, Instant)>>>,
    stop: Arc<AtomicBool>,
    join: Option<thread::JoinHandle<()>>,
}

impl Live {
    /// 找 T300RS 基座（B66E）并开始后台读。没有设备或打不开就报错。
    pub fn start() -> Result<Live> {
        let dev = list_devices()?
            .into_iter()
            .find(|d| d.product_id == PID_T300_BASE)
            .ok_or_else(|| anyhow!("没找到 Thrustmaster 基座 (044f:b66e)"))?;
        let reader = Reader::open(&dev, 0, Arc::new(Mutex::new(HashMap::new())))?;
        let latest = Arc::new(Mutex::new(None));
        let stop = Arc::new(AtomicBool::new(false));
        let (latest2, stop2) = (latest.clone(), stop.clone());
        let join = thread::Builder::new()
            .name("wheel-live".into())
            .spawn(move || {
                while !stop2.load(Ordering::Relaxed) {
                    if let Some(r) = reader.slot.lock().unwrap().as_ref() {
                        if let Some(axes) = map_report(r) {
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
        return Err(anyhow!("没找到 Thrustmaster (044f) 的 HID 设备"));
    }
    println!("找到 {} 个 Thrustmaster HID 条目：", devs.len());
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
}
