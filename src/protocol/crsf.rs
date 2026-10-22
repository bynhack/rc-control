//! CRSF framing as spoken between a handset and an ExpressLRS TX module.
//!
//! Frame: `[addr][len][type][payload..][crc8]`, where `len` counts type +
//! payload + crc and the CRC (poly 0xD5) covers type + payload.

pub const ADDR_TX_MODULE: u8 = 0xEE;
pub const ADDR_HANDSET: u8 = 0xEA;
pub const ADDR_FC: u8 = 0xC8;

pub const TYPE_LINK_STATS: u8 = 0x14;
pub const TYPE_RC_CHANNELS: u8 = 0x16;
pub const TYPE_DEVICE_PING: u8 = 0x28;
pub const TYPE_DEVICE_INFO: u8 = 0x29;

pub const CH_MIN: u16 = 172;
pub const CH_CENTER: u16 = 992;
pub const CH_MAX: u16 = 1811;
pub const CHANNELS: usize = 16;

pub fn crc8(data: &[u8]) -> u8 {
    let mut crc = 0u8;
    for &b in data {
        crc ^= b;
        for _ in 0..8 {
            crc = if crc & 0x80 != 0 { (crc << 1) ^ 0xD5 } else { crc << 1 };
        }
    }
    crc
}

/// Wraps `body` (type byte + payload) into a frame addressed to the TX module.
pub fn frame(body: &[u8]) -> Vec<u8> {
    let mut out = Vec::with_capacity(body.len() + 3);
    out.push(ADDR_TX_MODULE);
    out.push(body.len() as u8 + 1);
    out.extend_from_slice(body);
    out.push(crc8(body));
    out
}

/// Packs 16 channels of 11 bits each, LSB first, into 22 bytes.
pub fn pack_channels(channels: &[u16; CHANNELS]) -> [u8; 22] {
    let mut out = [0u8; 22];
    let mut acc: u32 = 0;
    let mut bits = 0;
    let mut i = 0;
    for &ch in channels {
        acc |= ((ch & 0x7FF) as u32) << bits;
        bits += 11;
        while bits >= 8 {
            out[i] = acc as u8;
            i += 1;
            acc >>= 8;
            bits -= 8;
        }
    }
    out
}

pub fn rc_frame(channels: &[u16; CHANNELS]) -> Vec<u8> {
    let mut body = Vec::with_capacity(23);
    body.push(TYPE_RC_CHANNELS);
    body.extend_from_slice(&pack_channels(channels));
    frame(&body)
}

/// Broadcast device ping; the module answers with a 0x29 device-info frame.
pub fn ping_frame() -> Vec<u8> {
    frame(&[TYPE_DEVICE_PING, ADDR_TX_MODULE, ADDR_HANDSET])
}

/// Maps -1.0..=1.0 onto the CRSF channel range, 0.0 being the 992 center.
pub fn to_channel(value: f32) -> u16 {
    let v = value.clamp(-1.0, 1.0);
    let span = if v < 0.0 { (CH_CENTER - CH_MIN) as f32 } else { (CH_MAX - CH_CENTER) as f32 };
    (CH_CENTER as f32 + v * span).round().clamp(CH_MIN as f32, CH_MAX as f32) as u16
}

/// Pulse width the receiver emits for a channel value (988..2012 µs).
pub fn channel_us(value: u16) -> u16 {
    (988.0 + (value as f32 - CH_MIN as f32) * (2012.0 - 988.0) / (CH_MAX - CH_MIN) as f32).round() as u16
}

#[derive(Debug, Clone, Copy, PartialEq, serde::Serialize)]
pub struct LinkStats {
    pub up_rssi: i16,
    pub up_lq: u8,
    pub down_rssi: i16,
    pub down_lq: u8,
}

#[derive(Debug, Clone, PartialEq)]
pub enum Event {
    LinkStats(LinkStats),
    DeviceName(String),
    /// The ESP32 boot banner showed up, i.e. the module rebooted.
    ModuleReset { brownout: bool },
}

/// ELRS sends RSSI as a signed byte (e.g. 0xD0 = -48 dBm); classic CRSF sends
/// the magnitude. Either way the result is negative dBm.
fn rssi(b: u8) -> i16 {
    let signed = b as i8 as i16;
    if signed > 0 { -signed } else { signed }
}

/// Incremental parser for whatever the TX module sends back over the wire.
#[derive(Default)]
pub struct Parser {
    buf: Vec<u8>,
}

impl Parser {
    pub fn push(&mut self, data: &[u8]) -> Vec<Event> {
        let mut events = Vec::new();
        self.buf.extend_from_slice(data);

        while let Some(at) = find(&self.buf, b"ets Jun") {
            let window = &self.buf[at..self.buf.len().min(at + 180)];
            let brownout = find(window, b"Brownout").is_some() || find(window, b"RTCWDT").is_some();
            events.push(Event::ModuleReset { brownout });
            self.buf.drain(..at + 7);
        }

        let mut i = 0;
        while i + 4 <= self.buf.len() {
            if ![ADDR_HANDSET, ADDR_TX_MODULE, ADDR_FC].contains(&self.buf[i]) {
                i += 1;
                continue;
            }
            let len = self.buf[i + 1] as usize;
            if !(2..=64).contains(&len) {
                i += 1;
                continue;
            }
            if i + 2 + len > self.buf.len() {
                break; // wait for the rest of this frame
            }
            let body = &self.buf[i + 2..i + 1 + len];
            if crc8(body) != self.buf[i + 1 + len] {
                i += 1;
                continue;
            }
            if let Some(ev) = decode(body) {
                events.push(ev);
            }
            i += 2 + len;
        }
        self.buf.drain(..i);
        if self.buf.len() > 512 {
            let cut = self.buf.len() - 256;
            self.buf.drain(..cut);
        }
        events
    }
}

fn decode(body: &[u8]) -> Option<Event> {
    match body[0] {
        TYPE_LINK_STATS if body.len() >= 11 => Some(Event::LinkStats(LinkStats {
            up_rssi: rssi(body[1]),
            up_lq: body[3],
            down_rssi: rssi(body[8]),
            down_lq: body[9],
        })),
        // Extended frame: type, dest, origin, then a NUL-terminated name.
        TYPE_DEVICE_INFO if body.len() > 3 => {
            let name: Vec<u8> = body[3..].iter().take_while(|&&b| b != 0).copied().collect();
            Some(Event::DeviceName(String::from_utf8_lossy(&name).into_owned()))
        }
        _ => None,
    }
}

fn find(hay: &[u8], needle: &[u8]) -> Option<usize> {
    hay.windows(needle.len()).position(|w| w == needle)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn hex(v: &[u8]) -> String {
        v.iter().map(|b| format!("{b:02x}")).collect()
    }

    // Vectors carried over from the elrs-handset prototype, which drove the
    // AION Nano successfully.
    #[test]
    fn ping_matches_prototype() {
        assert_eq!(hex(&ping_frame()), "ee0428eeea97");
    }

    #[test]
    fn rc_frame_matches_prototype() {
        assert_eq!(
            hex(&rc_frame(&[CH_MIN; CHANNELS])),
            "ee1816ac60052b58c10a56b08215ac60052b58c10a56b082155b"
        );
    }

    #[test]
    fn channel_mapping() {
        assert_eq!(to_channel(0.0), CH_CENTER);
        assert_eq!(to_channel(-1.0), CH_MIN);
        assert_eq!(to_channel(1.0), CH_MAX);
        assert_eq!(to_channel(5.0), CH_MAX);
        assert_eq!(channel_us(CH_CENTER), 1500);
        assert_eq!(channel_us(CH_MIN), 988);
        assert_eq!(channel_us(CH_MAX), 2012);
    }

    #[test]
    fn parses_device_info_split_across_reads() {
        let mut body = vec![TYPE_DEVICE_INFO, ADDR_HANDSET, ADDR_TX_MODULE];
        body.extend_from_slice(b"AION 2G4NANO TX\0extra");
        let f = frame(&body);
        let mut p = Parser::default();
        assert!(p.push(&f[..5]).is_empty());
        assert_eq!(p.push(&f[5..]), vec![Event::DeviceName("AION 2G4NANO TX".into())]);
    }

    #[test]
    fn link_stats_rssi_is_signed() {
        // Raw bytes seen from the AION: 208 and 194 are -48 / -62 dBm.
        let body = [TYPE_LINK_STATS, 208, 0, 100, 0, 0, 0, 0, 194, 92, 0];
        let mut p = Parser::default();
        let ev = p.push(&frame(&body));
        assert_eq!(
            ev,
            vec![Event::LinkStats(LinkStats { up_rssi: -48, up_lq: 100, down_rssi: -62, down_lq: 92 })]
        );
    }

    #[test]
    fn detects_reboot_banner_and_skips_noise() {
        let mut p = Parser::default();
        let ev = p.push(b"junk\xEE\xFFets Jun  8 2016 00:22:57\r\nrst:0x1 (POWERON_RESET)");
        assert_eq!(ev, vec![Event::ModuleReset { brownout: false }]);
    }
}
