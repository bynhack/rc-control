//! RTP → Annex-B access units for H.264 (RFC 6184) and H.265 (RFC 7798).
//!
//! FPV favours freshness over completeness: a fragment with a sequence gap is
//! dropped, and a new timestamp flushes whatever the previous frame had, so
//! one lost packet never holds up the next picture.

use serde::Deserialize;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Codec {
    H264,
    H265,
}

const START: [u8; 4] = [0, 0, 0, 1];

pub struct Depacketizer {
    codec: Codec,
    /// Access unit being assembled, Annex-B.
    au: Vec<u8>,
    ts: Option<u32>,
    /// Fragmented NAL being assembled, without start code.
    fu: Option<Vec<u8>>,
    last_seq: Option<u16>,
}

pub struct Rtp<'a> {
    pub payload_type: u8,
    pub seq: u16,
    pub ts: u32,
    pub marker: bool,
    pub payload: &'a [u8],
}

pub fn parse(pkt: &[u8]) -> Option<Rtp<'_>> {
    if pkt.len() < 12 || pkt[0] >> 6 != 2 {
        return None;
    }
    let cc = (pkt[0] & 0x0F) as usize;
    let mut off = 12 + 4 * cc;
    if pkt[0] & 0x10 != 0 {
        let len = u16::from_be_bytes([*pkt.get(off + 2)?, *pkt.get(off + 3)?]) as usize;
        off += 4 + 4 * len;
    }
    let mut end = pkt.len();
    if pkt[0] & 0x20 != 0 {
        end = end.checked_sub(*pkt.last()? as usize)?;
    }
    if off >= end {
        return None;
    }
    Some(Rtp {
        payload_type: pkt[1] & 0x7F,
        seq: u16::from_be_bytes([pkt[2], pkt[3]]),
        ts: u32::from_be_bytes([pkt[4], pkt[5], pkt[6], pkt[7]]),
        marker: pkt[1] & 0x80 != 0,
        payload: &pkt[off..end],
    })
}

impl Depacketizer {
    pub fn new(codec: Codec) -> Self {
        Depacketizer { codec, au: Vec::with_capacity(256 * 1024), ts: None, fu: None, last_seq: None }
    }

    /// Feeds one UDP datagram; returns a finished access unit when one completes.
    pub fn push(&mut self, pkt: &[u8]) -> Option<Vec<u8>> {
        let rtp = parse(pkt)?;
        let mut done = None;

        if let Some(last) = self.last_seq {
            if rtp.seq != last.wrapping_add(1) {
                self.fu = None; // a fragment lost its middle; it can't be repaired
            }
        }
        self.last_seq = Some(rtp.seq);

        if self.ts.is_some_and(|t| t != rtp.ts) {
            // Marker of the previous frame was lost: ship what we have.
            done = self.take();
        }
        self.ts = Some(rtp.ts);

        match self.codec {
            Codec::H264 => self.h264(rtp.payload),
            Codec::H265 => self.h265(rtp.payload),
        }

        if rtp.marker {
            done = self.take().or(done);
        }
        done
    }

    fn take(&mut self) -> Option<Vec<u8>> {
        self.fu = None;
        self.ts = None;
        if self.au.is_empty() {
            None
        } else {
            Some(std::mem::take(&mut self.au))
        }
    }

    fn nal(&mut self, nal: &[u8]) {
        if !nal.is_empty() {
            self.au.extend_from_slice(&START);
            self.au.extend_from_slice(nal);
        }
    }

    /// Aggregation packets: [u16 size][nal] repeated.
    fn aggregate(&mut self, mut p: &[u8]) {
        while p.len() >= 2 {
            let n = u16::from_be_bytes([p[0], p[1]]) as usize;
            if p.len() < 2 + n {
                return;
            }
            self.nal(&p[2..2 + n]);
            p = &p[2 + n..];
        }
    }

    fn fragment(&mut self, start: bool, end: bool, header: &[u8], data: &[u8]) {
        if start {
            let mut f = header.to_vec();
            f.extend_from_slice(data);
            self.fu = Some(f);
        } else if let Some(f) = &mut self.fu {
            f.extend_from_slice(data);
        }
        if end {
            if let Some(f) = self.fu.take() {
                self.nal(&f);
            }
        }
    }

    fn h264(&mut self, p: &[u8]) {
        match p[0] & 0x1F {
            1..=23 => self.nal(p),
            24 => self.aggregate(&p[1..]),
            28 if p.len() > 2 => {
                let fu = p[1];
                let header = [(p[0] & 0xE0) | (fu & 0x1F)];
                self.fragment(fu & 0x80 != 0, fu & 0x40 != 0, &header, &p[2..]);
            }
            _ => {}
        }
    }

    fn h265(&mut self, p: &[u8]) {
        if p.len() < 3 {
            return;
        }
        match (p[0] >> 1) & 0x3F {
            48 => self.aggregate(&p[2..]),
            49 => {
                let fu = p[2];
                let header = [(p[0] & 0x81) | ((fu & 0x3F) << 1), p[1]];
                self.fragment(fu & 0x80 != 0, fu & 0x40 != 0, &header, &p[3..]);
            }
            0..=47 => self.nal(p),
            _ => {}
        }
    }
}

/// NAL unit types in an Annex-B access unit, read with `codec`'s header layout.
pub fn nal_types(au: &[u8], codec: Codec) -> Vec<u8> {
    let mut out = Vec::new();
    let mut i = 0;
    while i + 4 < au.len() {
        if au[i..i + 4] == START {
            out.push(match codec {
                Codec::H264 => au[i + 4] & 0x1F,
                Codec::H265 => (au[i + 4] >> 1) & 0x3F,
            });
            i += 4;
        } else {
            i += 1;
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn rtp(seq: u16, ts: u32, marker: bool, payload: &[u8]) -> Vec<u8> {
        let mut v = vec![0x80, if marker { 0xE1 } else { 0x61 }];
        v.extend_from_slice(&seq.to_be_bytes());
        v.extend_from_slice(&ts.to_be_bytes());
        v.extend_from_slice(&[0, 0, 0, 1]);
        v.extend_from_slice(payload);
        v
    }

    #[test]
    fn h265_fragments_reassemble() {
        // NAL type 19 (IDR_W_RADL): header 0x26 0x01.
        let mut d = Depacketizer::new(Codec::H265);
        let fu_ind = [(49 << 1), 0x01];
        assert!(d.push(&rtp(1, 9, false, &[fu_ind[0], fu_ind[1], 0x80 | 19, 0xAA])).is_none());
        assert!(d.push(&rtp(2, 9, false, &[fu_ind[0], fu_ind[1], 19, 0xBB])).is_none());
        let au = d.push(&rtp(3, 9, true, &[fu_ind[0], fu_ind[1], 0x40 | 19, 0xCC])).unwrap();
        assert_eq!(au, [0, 0, 0, 1, 0x26, 0x01, 0xAA, 0xBB, 0xCC]);
    }

    #[test]
    fn h265_aggregation_and_single() {
        let mut d = Depacketizer::new(Codec::H265);
        // AP carrying VPS (32) and SPS (33), then a single slice in the same AU.
        let ap = [48 << 1, 1, 0, 3, 0x40, 0x01, 0x0C, 0, 3, 0x42, 0x01, 0x01];
        assert!(d.push(&rtp(10, 5, false, &ap)).is_none());
        let au = d.push(&rtp(11, 5, true, &[0x02, 0x01, 0xEE])).unwrap();
        assert_eq!(au, [0, 0, 0, 1, 0x40, 0x01, 0x0C, 0, 0, 0, 1, 0x42, 0x01, 0x01, 0, 0, 0, 1, 0x02, 0x01, 0xEE]);
    }

    #[test]
    fn gap_drops_broken_fragment_only() {
        let mut d = Depacketizer::new(Codec::H265);
        let fu_ind = [(49 << 1), 0x01];
        d.push(&rtp(1, 7, false, &[0x02, 0x01, 0x11])); // a complete small NAL
        d.push(&rtp(2, 7, false, &[fu_ind[0], fu_ind[1], 0x80 | 1, 0xAA]));
        // seq 3 lost
        let au = d.push(&rtp(4, 7, true, &[fu_ind[0], fu_ind[1], 0x40 | 1, 0xCC])).unwrap();
        assert_eq!(au, [0, 0, 0, 1, 0x02, 0x01, 0x11]);
    }

    #[test]
    fn lost_marker_flushes_on_new_timestamp() {
        let mut d = Depacketizer::new(Codec::H264);
        assert!(d.push(&rtp(1, 100, false, &[0x65, 0x01])).is_none());
        let au = d.push(&rtp(2, 200, false, &[0x41, 0x02])).unwrap();
        assert_eq!(au, [0, 0, 0, 1, 0x65, 0x01]);
        assert_eq!(d.push(&rtp(3, 200, true, &[0x41, 0x03])).unwrap(), [0, 0, 0, 1, 0x41, 0x02, 0, 0, 0, 1, 0x41, 0x03]);
    }

    #[test]
    fn h264_fu_a_and_stap_a() {
        let mut d = Depacketizer::new(Codec::H264);
        d.push(&rtp(1, 1, false, &[24, 0, 2, 0x67, 0x42, 0, 2, 0x68, 0xCE]));
        d.push(&rtp(2, 1, false, &[0x7C, 0x80 | 5, 0x01]));
        let au = d.push(&rtp(3, 1, true, &[0x7C, 0x40 | 5, 0x02])).unwrap();
        assert_eq!(au, [0, 0, 0, 1, 0x67, 0x42, 0, 0, 0, 1, 0x68, 0xCE, 0, 0, 0, 1, 0x65, 0x01, 0x02]);
    }

    #[test]
    fn rejects_non_rtp() {
        assert!(parse(&[0x00; 20]).is_none());
        assert!(parse(&[0x80, 0x60, 0, 1]).is_none());
    }
}
