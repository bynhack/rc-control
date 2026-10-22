//! MR-RC2 / OGESS-RC2 serial protocol (recovered from MR-RC2.exe).
//!
//! Every data byte travels as two ASCII nibble chars (`0x30 | nibble`, low
//! first) and every char is ACKed by the device with 0x00. One call:
//! `Q` [`R`] nibbles.. `^`(crc8 of the 16-byte param buffer) `V`(status)
//! then `@`+i to read back return byte i.

use std::io::{self, Read, Write};
use std::thread;
use std::time::Duration;

pub const BAUD: u32 = 460_800;

#[allow(dead_code)] // diagnostics; exercised by tests
pub const F_CAPS: i16 = -0x101;
pub const F_AP_COUNT: i16 = -0x200;
pub const F_AP_NAME: i16 = -0x201;
pub const F_AP_GET: i16 = -0x202;
pub const F_CP_COUNT: i16 = -0x300;
pub const F_CP_NAME: i16 = -0x301;
#[allow(dead_code)]
pub const F_CP_GET: i16 = -0x302;
pub const F_CP_SET: i16 = -0x303;

/// Chars sent before waiting for their ACKs. Measured on MR-RC2A3 fw 1.0.3.3:
/// 2 was 300/300 clean, 3 or more drops chars (~10% failed calls).
pub const PIPE: usize = 2;

/// Firmware reports this when a temperature/current sensor is not fitted.
pub const NOT_CONNECTED: f32 = -127.0;

/// CRC-8/NRSC-5: poly 0x31, init 0xFF, no reflection.
pub fn crc8(data: &[u8]) -> u8 {
    let mut c = 0xFFu8;
    for &b in data {
        c ^= b;
        for _ in 0..8 {
            c = if c & 0x80 != 0 { (c << 1) ^ 0x31 } else { c << 1 };
        }
    }
    c
}

pub fn nibbles(b: u8) -> [u8; 2] {
    [(b & 0x0F) | 0x30, (b >> 4) | 0x30]
}

#[derive(Debug)]
pub enum Error {
    Io(io::Error),
    Timeout(&'static str),
    Nack(u8),
    Crc { device: u8, host: u8 },
    Status(u8),
}

impl std::fmt::Display for Error {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Error::Io(e) => write!(f, "串口错误：{e}"),
            Error::Timeout(what) => write!(f, "等待{what}超时"),
            Error::Nack(b) => write!(f, "设备拒收 0x{b:02X}"),
            Error::Crc { device, host } => write!(f, "校验不一致 设备=0x{device:02X} 本机=0x{host:02X}"),
            Error::Status(b) => write!(f, "设备返回错误码 0x{b:02X}"),
        }
    }
}

impl std::error::Error for Error {}

impl From<io::Error> for Error {
    fn from(e: io::Error) -> Self {
        Error::Io(e)
    }
}

pub type Result<T> = std::result::Result<T, Error>;

/// What the protocol needs from a serial port.
pub trait Port: Read + Write {
    fn clear_input(&mut self) -> io::Result<()>;
}

impl Port for Box<dyn serialport::SerialPort> {
    fn clear_input(&mut self) -> io::Result<()> {
        self.clear(serialport::ClearBuffer::Input).map_err(io::Error::from)
    }
}

pub struct Rc2<P: Port> {
    port: P,
}

impl<P: Port> Rc2<P> {
    pub fn new(port: P) -> Self {
        Rc2 { port }
    }

    fn read_n(&mut self, n: usize, what: &'static str) -> Result<Vec<u8>> {
        let mut out = vec![0u8; n];
        let mut got = 0;
        while got < n {
            match self.port.read(&mut out[got..]) {
                Ok(0) => return Err(Error::Timeout(what)),
                Ok(k) => got += k,
                Err(e) if e.kind() == io::ErrorKind::TimedOut => return Err(Error::Timeout(what)),
                Err(e) if e.kind() == io::ErrorKind::Interrupted => {}
                Err(e) => return Err(e.into()),
            }
        }
        Ok(out)
    }

    fn send_acked(&mut self, chars: &[u8]) -> Result<()> {
        for part in chars.chunks(PIPE) {
            self.port.write_all(part)?;
            let acks = self.read_n(part.len(), "确认")?;
            if let Some(&bad) = acks.iter().find(|&&a| a != 0) {
                return Err(Error::Nack(bad));
            }
        }
        Ok(())
    }

    fn resync(&mut self) {
        thread::sleep(Duration::from_millis(30));
        let _ = self.port.clear_input();
    }

    /// Runs one device function. `Q` clears the device's parameter buffer, so
    /// a failed call is repeated once after draining late bytes.
    pub fn funexec(&mut self, code: i16, payload: &[u8], retlen: usize) -> Result<Vec<u8>> {
        match self.funexec_once(code, payload, retlen) {
            Ok(v) => Ok(v),
            Err(Error::Status(s)) => Err(Error::Status(s)),
            Err(_) => {
                self.resync();
                self.funexec_once(code, payload, retlen)
            }
        }
    }

    fn funexec_once(&mut self, code: i16, payload: &[u8], retlen: usize) -> Result<Vec<u8>> {
        assert!(payload.len() <= 14 && retlen <= 16);
        let mut frame = code.to_le_bytes().to_vec();
        frame.extend_from_slice(payload);
        let mut padded = frame.clone();
        padded.resize(16, 0);

        let mut chars: Vec<u8> = if retlen > 0 { b"QR".to_vec() } else { b"Q".to_vec() };
        for &b in &frame {
            chars.extend_from_slice(&nibbles(b));
        }
        self.port.clear_input()?;
        self.send_acked(&chars)?;

        self.port.write_all(b"^")?;
        let device = self.read_n(1, "校验")?[0];
        let host = crc8(&padded);
        if device != host {
            return Err(Error::Crc { device, host });
        }

        self.port.write_all(b"V")?;
        let status = self.read_n(1, "提交")?[0];
        if status != 0 {
            return Err(Error::Status(status));
        }

        let mut out = Vec::with_capacity(retlen);
        let mut i = 0;
        while i < retlen {
            let req: Vec<u8> = (i..retlen.min(i + PIPE)).map(|j| 0x40 + j as u8).collect();
            self.port.write_all(&req)?;
            out.extend(self.read_n(req.len(), "返回数据")?);
            i += req.len();
        }
        Ok(out)
    }

    fn ident(&mut self, cmd: u8) -> Result<String> {
        self.port.clear_input()?;
        self.port.write_all(&[cmd])?;
        let st = self.read_n(1, "身份")?[0];
        if st != 0 {
            return Err(Error::Status(st));
        }
        let mut raw = Vec::with_capacity(16);
        for i in 0..16u8 {
            self.port.write_all(&[0x40 + i])?;
            raw.extend(self.read_n(1, "身份")?);
        }
        Ok(cstr(&raw))
    }

    pub fn model(&mut self) -> Result<String> {
        self.ident(0x01)
    }

    pub fn serial(&mut self) -> Result<String> {
        self.ident(0x02)
    }

    pub fn firmware(&mut self) -> Result<String> {
        self.ident(0x03)
    }

    #[allow(dead_code)]
    pub fn caps(&mut self) -> Result<u32> {
        Ok(u32::from_le_bytes(arr4(&self.funexec(F_CAPS, &[], 4)?)))
    }

    fn names(&mut self, count: i16, name: i16) -> Result<Vec<String>> {
        let n = i32::from_le_bytes(arr4(&self.funexec(count, &[], 4)?)).clamp(0, 64);
        (0..n as i16)
            .map(|i| self.funexec(name, &i.to_le_bytes(), 16).map(|r| cstr(&r)))
            .collect()
    }

    pub fn cp_names(&mut self) -> Result<Vec<String>> {
        self.names(F_CP_COUNT, F_CP_NAME)
    }

    pub fn ap_names(&mut self) -> Result<Vec<String>> {
        self.names(F_AP_COUNT, F_AP_NAME)
    }

    pub fn get_ap(&mut self, idx: usize) -> Result<f32> {
        Ok(f32::from_le_bytes(arr4(&self.funexec(F_AP_GET, &(idx as i16).to_le_bytes(), 4)?)))
    }

    #[allow(dead_code)]
    pub fn get_cp(&mut self, idx: usize) -> Result<f32> {
        Ok(f32::from_le_bytes(arr4(&self.funexec(F_CP_GET, &(idx as i16).to_le_bytes(), 4)?)))
    }

    /// `rate` asks the device to slew toward `value` instead of jumping.
    pub fn set_cp(&mut self, idx: usize, value: f32, rate: Option<f32>) -> Result<()> {
        let mut p = (idx as i32).to_le_bytes().to_vec();
        p.extend_from_slice(&value.to_le_bytes());
        if let Some(r) = rate {
            p.extend_from_slice(&r.to_le_bytes());
        }
        self.funexec(F_CP_SET, &p, 0).map(|_| ())
    }
}

fn arr4(v: &[u8]) -> [u8; 4] {
    let mut a = [0u8; 4];
    for (d, s) in a.iter_mut().zip(v) {
        *d = *s;
    }
    a
}

fn cstr(raw: &[u8]) -> String {
    let end = raw.iter().position(|&b| b == 0).unwrap_or(raw.len());
    String::from_utf8_lossy(&raw[..end]).trim().to_string()
}

#[cfg(test)]
pub mod sim {
    //! A software MR-RC2 that follows the wire protocol, for tests.
    use super::*;
    use std::collections::VecDeque;

    pub struct SimDevice {
        pub cps: Vec<(String, f32)>,
        pub aps: Vec<(String, f32)>,
        pub writes: Vec<(usize, f32, Option<f32>)>,
        /// Corrupt the ACK of the Nth data char once, to exercise the retry.
        pub glitch_at: Option<usize>,
        param: Vec<u8>,
        half: Option<u8>,
        ret: Vec<u8>,
        out: VecDeque<u8>,
        chars_seen: usize,
    }

    impl SimDevice {
        pub fn new() -> Self {
            SimDevice {
                cps: ["Direction", "Switch", "Status", "Sync"].iter().map(|n| (n.to_string(), 0.0)).collect(),
                aps: vec![("Signal".into(), 4.0), ("TmpC".into(), NOT_CONNECTED)],
                writes: Vec::new(),
                glitch_at: None,
                param: Vec::new(),
                half: None,
                ret: Vec::new(),
                out: VecDeque::new(),
                chars_seen: 0,
            }
        }

        fn ident(&mut self, s: &str) {
            let mut r = s.as_bytes().to_vec();
            r.resize(16, 0);
            self.ret = r;
            self.out.push_back(0);
        }

        fn execute(&mut self) -> u8 {
            let code = i16::from_le_bytes([self.param[0], self.param[1]]);
            let p = &self.param[2..];
            let idx16 = || i16::from_le_bytes([p[0], p[1]]) as usize;
            let name = |list: &Vec<(String, f32)>, i: usize| {
                let mut r = list[i].0.as_bytes().to_vec();
                r.resize(16, 0);
                r
            };
            self.ret = match code {
                F_CAPS => 0x2Du32.to_le_bytes().to_vec(),
                F_CP_COUNT => (self.cps.len() as i32).to_le_bytes().to_vec(),
                F_AP_COUNT => (self.aps.len() as i32).to_le_bytes().to_vec(),
                F_CP_NAME => name(&self.cps, idx16()),
                F_AP_NAME => name(&self.aps, idx16()),
                F_CP_GET if self.cps[idx16()].0 == "Sync" => return 0x0A,
                F_CP_GET => self.cps[idx16()].1.to_le_bytes().to_vec(),
                F_AP_GET => self.aps[idx16()].1.to_le_bytes().to_vec(),
                F_CP_SET => {
                    let i = i32::from_le_bytes(p[0..4].try_into().unwrap()) as usize;
                    let v = f32::from_le_bytes(p[4..8].try_into().unwrap());
                    let rate = (p.len() >= 12).then(|| f32::from_le_bytes(p[8..12].try_into().unwrap()));
                    self.cps[i].1 = v;
                    self.writes.push((i, v, rate));
                    Vec::new()
                }
                _ => return 0x01,
            };
            0
        }
    }

    impl Read for SimDevice {
        fn read(&mut self, buf: &mut [u8]) -> io::Result<usize> {
            let n = buf.len().min(self.out.len());
            if n == 0 {
                return Err(io::Error::new(io::ErrorKind::TimedOut, "sim timeout"));
            }
            for b in buf.iter_mut().take(n) {
                *b = self.out.pop_front().unwrap();
            }
            Ok(n)
        }
    }

    impl Write for SimDevice {
        fn write(&mut self, buf: &[u8]) -> io::Result<usize> {
            for &c in buf {
                match c {
                    0x01 => self.ident("MR-RC2A3"),
                    0x02 => self.ident("ID2511129C60D8C2"),
                    0x03 => self.ident("1.0.3.3"),
                    b'Q' => {
                        self.param.clear();
                        self.half = None;
                        self.out.push_back(0);
                    }
                    b'R' => self.out.push_back(0),
                    0x30..=0x3F => {
                        let nib = c & 0x0F;
                        match self.half.take() {
                            None => self.half = Some(nib),
                            Some(lo) => self.param.push(lo | (nib << 4)),
                        }
                        self.chars_seen += 1;
                        let bad = self.glitch_at == Some(self.chars_seen);
                        if bad {
                            self.glitch_at = None;
                        }
                        self.out.push_back(if bad { 0x73 } else { 0 });
                    }
                    b'^' => {
                        let mut p = self.param.clone();
                        p.resize(16, 0);
                        self.out.push_back(crc8(&p));
                    }
                    b'V' => {
                        let st = self.execute();
                        self.out.push_back(st);
                    }
                    0x40..=0x4F => {
                        let i = (c - 0x40) as usize;
                        self.out.push_back(*self.ret.get(i).unwrap_or(&0));
                    }
                    _ => {}
                }
            }
            Ok(buf.len())
        }

        fn flush(&mut self) -> io::Result<()> {
            Ok(())
        }
    }

    impl Port for SimDevice {
        fn clear_input(&mut self) -> io::Result<()> {
            self.out.clear();
            Ok(())
        }
    }
}

#[cfg(test)]
mod tests {
    use super::sim::SimDevice;
    use super::*;

    #[test]
    fn crc_check_value() {
        // CRC-8/NRSC-5 catalogue check value.
        assert_eq!(crc8(b"123456789"), 0xF7);
    }

    #[test]
    fn nibble_order_low_first() {
        assert_eq!(nibbles(0xA5), [0x35, 0x3A]);
    }

    #[test]
    fn identity_and_tables() {
        let mut d = Rc2::new(SimDevice::new());
        assert_eq!(d.model().unwrap(), "MR-RC2A3");
        assert_eq!(d.firmware().unwrap(), "1.0.3.3");
        assert_eq!(d.caps().unwrap(), 0x2D);
        assert_eq!(d.cp_names().unwrap(), ["Direction", "Switch", "Status", "Sync"]);
        assert_eq!(d.ap_names().unwrap(), ["Signal", "TmpC"]);
        assert_eq!(d.get_ap(0).unwrap(), 4.0);
        assert_eq!(d.get_ap(1).unwrap(), NOT_CONNECTED);
    }

    #[test]
    fn set_with_and_without_rate() {
        let mut d = Rc2::new(SimDevice::new());
        d.set_cp(0, -12.0, None).unwrap();
        d.set_cp(1, 25.0, Some(3.0)).unwrap();
        assert_eq!(d.get_cp(0).unwrap(), -12.0);
        assert_eq!(d.port.writes, vec![(0, -12.0, None), (1, 25.0, Some(3.0))]);
    }

    #[test]
    fn write_only_cp_reports_status() {
        let mut d = Rc2::new(SimDevice::new());
        assert!(matches!(d.get_cp(3), Err(Error::Status(0x0A))));
    }

    #[test]
    fn retries_once_after_a_bad_ack() {
        let mut sim = SimDevice::new();
        sim.glitch_at = Some(5);
        let mut d = Rc2::new(sim);
        d.set_cp(1, 10.0, None).unwrap();
        assert_eq!(d.port.writes, vec![(1, 10.0, None)]);
    }
}
