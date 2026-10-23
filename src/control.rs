//! Backend-neutral control state and every safety rule, in one place.
//!
//! Inputs (the debug page today, a wheel later) write demands here; backends
//! only ever read `output()`, so no backend can bypass arming or the watchdog.

use serde::{Deserialize, Serialize};
use std::time::{Duration, Instant};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Speed {
    Low,
    Mid,
    High,
}

impl Speed {
    pub fn scale(self) -> f32 {
        match self {
            Speed::Low => 1.0 / 3.0,
            Speed::Mid => 2.0 / 3.0,
            Speed::High => 1.0,
        }
    }
}

/// Throttle demand below this counts as "stick at center" for arming.
const ARM_THROTTLE_TOLERANCE: f32 = 0.02;

/// What a backend should transmit right now. Both values are -1.0..=1.0.
#[derive(Debug, Clone, Copy, PartialEq, Serialize)]
pub struct Output {
    pub steering: f32,
    pub throttle: f32,
}

impl Output {
    pub const NEUTRAL: Output = Output { steering: 0.0, throttle: 0.0 };
}

#[derive(Debug)]
pub struct Control {
    steering: f32,
    throttle_demand: f32,
    armed: bool,
    speed: Speed,
    last_input: Option<Instant>,
    timeout: Duration,
    disarm_reason: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct ControlView {
    pub steering: f32,
    pub throttle_demand: f32,
    pub armed: bool,
    pub speed: Speed,
    pub input_age_ms: Option<u64>,
    pub input_fresh: bool,
    pub disarm_reason: String,
    pub output: Output,
}

impl Control {
    pub fn new(timeout: Duration) -> Self {
        Control {
            steering: 0.0,
            throttle_demand: 0.0,
            armed: false,
            speed: Speed::Low,
            last_input: None,
            timeout,
            disarm_reason: "启动时默认锁定".into(),
        }
    }

    fn fresh(&self, now: Instant) -> bool {
        self.last_input.is_some_and(|t| now.duration_since(t) <= self.timeout)
    }

    /// An input sample; doubles as the heartbeat.
    pub fn input(&mut self, steering: f32, throttle: f32, now: Instant) {
        self.steering = clean(steering);
        self.throttle_demand = clean(throttle);
        self.last_input = Some(now);
    }

    pub fn arm(&mut self, now: Instant) -> Result<(), String> {
        if !self.fresh(now) {
            return Err("没有收到输入心跳，不能解锁".into());
        }
        if self.throttle_demand.abs() > ARM_THROTTLE_TOLERANCE {
            return Err("油门不在中位，不能解锁".into());
        }
        self.armed = true;
        self.disarm_reason.clear();
        Ok(())
    }

    pub fn disarm(&mut self, reason: &str) {
        if self.armed {
            self.armed = false;
            self.disarm_reason = reason.into();
        }
    }

    /// Emergency stop: disarm and center everything, regardless of input.
    pub fn estop(&mut self) {
        self.armed = true; // so disarm() records the reason
        self.disarm("急停");
        self.steering = 0.0;
        self.throttle_demand = 0.0;
    }

    pub fn set_speed(&mut self, speed: Speed) {
        self.speed = speed;
    }

    /// Latches a disarm once input goes stale, so a page that comes back
    /// cannot resume driving without an explicit re-arm.
    pub fn tick(&mut self, now: Instant) {
        if self.armed && !self.fresh(now) {
            self.disarm("输入心跳超时");
        }
    }

    pub fn output(&self, now: Instant) -> Output {
        if !self.fresh(now) {
            return Output::NEUTRAL;
        }
        let throttle = if self.armed { self.throttle_demand * self.speed.scale() } else { 0.0 };
        Output { steering: self.steering, throttle }
    }

    pub fn view(&self, now: Instant) -> ControlView {
        ControlView {
            steering: self.steering,
            throttle_demand: self.throttle_demand,
            armed: self.armed,
            speed: self.speed,
            input_age_ms: self.last_input.map(|t| now.duration_since(t).as_millis() as u64),
            input_fresh: self.fresh(now),
            disarm_reason: self.disarm_reason.clone(),
            output: self.output(now),
        }
    }
}

fn clean(v: f32) -> f32 {
    if v.is_finite() { v.clamp(-1.0, 1.0) } else { 0.0 }
}

#[cfg(test)]
mod tests {
    use super::*;

    const T: Duration = Duration::from_millis(300);

    #[test]
    fn starts_locked_and_neutral() {
        let now = Instant::now();
        let mut c = Control::new(T);
        c.input(0.5, 0.8, now);
        assert_eq!(c.output(now), Output { steering: 0.5, throttle: 0.0 });
    }

    #[test]
    fn refuses_to_arm_with_throttle_or_without_heartbeat() {
        let now = Instant::now();
        let mut c = Control::new(T);
        assert!(c.arm(now).is_err());
        c.input(0.0, 0.3, now);
        assert!(c.arm(now).is_err());
        c.input(0.0, 0.0, now);
        assert!(c.arm(now).is_ok());
    }

    #[test]
    fn speed_tier_scales_throttle() {
        let now = Instant::now();
        let mut c = Control::new(T);
        c.input(0.0, 0.0, now);
        c.arm(now).unwrap();
        c.input(0.0, -0.9, now);
        assert!((c.output(now).throttle + 0.3).abs() < 1e-6);
        c.set_speed(Speed::High);
        assert!((c.output(now).throttle + 0.9).abs() < 1e-6);
    }

    #[test]
    fn stale_input_goes_neutral_and_stays_disarmed() {
        let t0 = Instant::now();
        let mut c = Control::new(T);
        c.input(0.0, 0.0, t0);
        c.arm(t0).unwrap();
        c.input(0.4, 1.0, t0);
        let later = t0 + Duration::from_millis(400);
        assert_eq!(c.output(later), Output::NEUTRAL);
        c.tick(later);
        // Input resumes with the throttle still held: must not drive again.
        c.input(0.4, 1.0, later);
        assert_eq!(c.output(later).throttle, 0.0);
        assert_eq!(c.view(later).disarm_reason, "输入心跳超时");
    }

    #[test]
    fn estop_centers_and_disarms() {
        let now = Instant::now();
        let mut c = Control::new(T);
        c.input(0.0, 0.0, now);
        c.arm(now).unwrap();
        c.input(-0.7, 0.6, now);
        c.estop();
        let v = c.view(now);
        assert!(!v.armed);
        assert_eq!(v.output, Output::NEUTRAL);
    }

    #[test]
    fn rejects_nan() {
        let now = Instant::now();
        let mut c = Control::new(T);
        c.input(f32::NAN, f32::INFINITY, now);
        assert_eq!(c.output(now), Output::NEUTRAL);
    }
}
