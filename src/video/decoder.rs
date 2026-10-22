//! FFmpeg decoding tuned for latency: LOW_DELAY, and slice threading only.
//! Frame threading would buffer one frame per thread before output.

use super::rtp::Codec;
use anyhow::Context;
use ffmpeg_next as ff;

/// A decoded picture as tightly packed RGBA.
pub struct Rgba {
    pub width: usize,
    pub height: usize,
    pub pixels: Vec<u8>,
}

pub struct Decoder {
    dec: ff::decoder::Video,
    scaler: Option<(ff::software::scaling::Context, ff::format::Pixel, u32, u32)>,
    /// Newest picture received.
    frame: ff::frame::Video,
    /// receive_frame target: a failed call (EAGAIN) unrefs the frame it was
    /// given, so pictures are received here and swapped into `frame`.
    scratch: ff::frame::Video,
    rgba: ff::frame::Video,
}

impl Decoder {
    pub fn new(codec: Codec) -> anyhow::Result<Self> {
        ff::init().context("FFmpeg 初始化失败")?;
        // Corrupt input is expected on a lossy radio link; don't spam stderr.
        unsafe { ff::ffi::av_log_set_level(ff::ffi::AV_LOG_FATAL) };
        let id = match codec {
            Codec::H264 => ff::codec::Id::H264,
            Codec::H265 => ff::codec::Id::HEVC,
        };
        let found = ff::decoder::find(id).with_context(|| format!("这份 FFmpeg 不带 {codec:?} 解码器"))?;
        let mut ctx = ff::codec::context::Context::new_with_codec(found);
        ctx.set_flags(ff::codec::Flags::LOW_DELAY);
        ctx.set_threading(ff::threading::Config { kind: ff::threading::Type::Slice, count: 4, ..Default::default() });
        let dec = ctx.decoder().video().context("打开解码器失败")?;
        Ok(Decoder {
            dec,
            scaler: None,
            frame: ff::frame::Video::empty(),
            scratch: ff::frame::Video::empty(),
            rgba: ff::frame::Video::empty(),
        })
    }

    /// Decodes one Annex-B access unit. Returns the newest picture it yields;
    /// broken input (missing references, lost slices) just yields nothing.
    pub fn decode(&mut self, au: &[u8]) -> Option<Rgba> {
        let pkt = ff::Packet::copy(au);
        if self.dec.send_packet(&pkt).is_err() {
            return None;
        }
        let mut got = false;
        while self.dec.receive_frame(&mut self.scratch).is_ok() {
            std::mem::swap(&mut self.frame, &mut self.scratch);
            got = true;
        }
        if got { self.convert() } else { None }
    }

    fn convert(&mut self) -> Option<Rgba> {
        let (fmt, w, h) = (self.frame.format(), self.frame.width(), self.frame.height());
        if w == 0 || h == 0 {
            return None;
        }
        let stale = !matches!(&self.scaler, Some((_, f, sw, sh)) if *f == fmt && *sw == w && *sh == h);
        if stale {
            let ctx = ff::software::scaling::Context::get(fmt, w, h, ff::format::Pixel::RGBA, w, h, ff::software::scaling::Flags::FAST_BILINEAR)
                .ok()?;
            self.scaler = Some((ctx, fmt, w, h));
        }
        let (scaler, ..) = self.scaler.as_mut()?;
        scaler.run(&self.frame, &mut self.rgba).ok()?;

        let (w, h) = (w as usize, h as usize);
        let stride = self.rgba.stride(0);
        let data = self.rgba.data(0);
        let mut pixels = Vec::with_capacity(w * h * 4);
        for row in 0..h {
            pixels.extend_from_slice(&data[row * stride..row * stride + w * 4]);
        }
        Some(Rgba { width: w, height: h, pixels })
    }
}
