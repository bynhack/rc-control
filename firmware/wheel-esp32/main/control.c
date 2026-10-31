#include "control.h"

#include <math.h>
#include <stddef.h>

#include "freertos/FreeRTOS.h"
#include "radio.h"

// Pedal travel below this counts as released.
#define PEDAL_DEAD 0.03f
// Power cap per gear. R is capped low: reversing is done half blind.
#define GEAR_R_MAX 0.40f
#define GEAR_1_MAX (1.0f / 3.0f)
#define GEAR_2_MAX (2.0f / 3.0f)
#define GEAR_3_MAX 1.0f
// Model rates, full scale per second. ACCEL: how fast the gas pedal's
// target is reached. COAST: lift-off slowdown (100 % -> 0 in ~2.5 s).
// BRAKE: slowdown with the brake floored. Downshifting above the new
// gear's cap slows at COAST too, like engine braking.
#define ACCEL_RATE 3.0f
#define COAST_RATE 0.4f
#define BRAKE_RATE 2.5f
// Below this modelled speed the car counts as stopped (shift into R).
#define STOPPED 0.03f
// Typical ESCs (forward / brake / reverse): the first reverse command
// brakes, and reverse only engages after a return to neutral. Going into
// reverse sends that handshake: brake, neutral, then reverse.
#define REV_BRAKE_US 120000
#define REV_GAP_US 120000
#define NOTICE_US 2000000

typedef enum { REV_IDLE, REV_BRAKE, REV_GAP, REV_ON } rev_state_t;

static portMUX_TYPE s_lock = portMUX_INITIALIZER_UNLOCKED;
static float s_steering, s_gas, s_brake;
static bool s_engine;
static gear_t s_gear = GEAR_N;
static float s_speed;
static control_output_t s_out;
static rev_state_t s_rev = REV_IDLE;
static int64_t s_rev_at;
static int64_t s_last_input_us = -1;
static int64_t s_last_tick_us = -1;
static int64_t s_timeout_us;
static const char *s_off_reason = "BOOT";
static const char *s_notice;
static int64_t s_notice_at;

static float clamp(float v, float lo, float hi) {
    if (!isfinite(v)) {
        return 0.0f;
    }
    return v < lo ? lo : (v > hi ? hi : v);
}

static float gear_max(gear_t g) {
    switch (g) {
        case GEAR_R:
            return GEAR_R_MAX;
        case GEAR_1:
            return GEAR_1_MAX;
        case GEAR_2:
            return GEAR_2_MAX;
        case GEAR_3:
            return GEAR_3_MAX;
        default:
            return 0.0f;
    }
}

// Moves v toward target by at most step.
static float approach(float v, float target, float step) {
    if (v < target) {
        return v + step < target ? v + step : target;
    }
    return v - step > target ? v - step : target;
}

// Callers hold s_lock.
static bool fresh(int64_t now_us) {
    return s_last_input_us >= 0 && now_us - s_last_input_us <= s_timeout_us;
}

static void stop_locked(const char *reason) {
    if (s_engine) {
        s_engine = false;
        s_off_reason = reason;
    }
    s_speed = 0.0f;
    s_gear = GEAR_N;
    s_rev = REV_IDLE;
    s_out = (control_output_t){0};
}

static void notice_locked(const char *n, int64_t now_us) {
    s_notice = n;
    s_notice_at = now_us;
}

static bool braking_locked(void) {
    return s_brake > PEDAL_DEAD;
}

static void model_locked(float dt) {
    float max = gear_max(s_gear);
    float target = 0.0f;
    // Setting the throttle start: the pedal goes out as it is (up to
    // CAL_THROTTLE_MAX, in any forward gear or R), so the driver can find
    // where the car starts to move.
    bool cal = radio_cal_get() == CAL_THROTTLE;
    if (cal) {
        max = s_gear == GEAR_N ? 0.0f : CAL_THROTTLE_MAX;
    }
    if (!braking_locked() && s_gas > PEDAL_DEAD) {
        target = s_gas * max * (s_gear == GEAR_R ? -1.0f : 1.0f);
    }
    if (cal && !braking_locked() && target * s_speed >= 0.0f) {
        s_speed = target;
        return;
    }
    if (braking_locked()) {
        s_speed = approach(s_speed, 0.0f, BRAKE_RATE * s_brake * dt);
    } else if (fabsf(target) > fabsf(s_speed) && target * s_speed >= 0.0f) {
        s_speed = approach(s_speed, target, ACCEL_RATE * dt);
    } else {
        s_speed = approach(s_speed, target, COAST_RATE * dt);
    }
}

// What goes to the ESC for the modelled state.
static void output_locked(int64_t now_us) {
    float thr;
    if (braking_locked() && s_speed > STOPPED) {
        thr = -s_brake; // the ESC's brake
    } else if (braking_locked()) {
        // Stopped, or reversing: neutral. Never a second brake command at a
        // standstill, which the ESC would take as reverse.
        thr = 0.0f;
    } else {
        thr = s_speed;
    }

    if (thr < 0.0f && !braking_locked()) {
        // Reverse wanted: run the ESC handshake first.
        if (s_rev == REV_IDLE) {
            s_rev = REV_BRAKE;
            s_rev_at = now_us;
        }
        if (s_rev == REV_BRAKE) {
            if (now_us - s_rev_at < REV_BRAKE_US) {
                thr = -0.3f;
            } else {
                s_rev = REV_GAP;
                s_rev_at = now_us;
            }
        }
        if (s_rev == REV_GAP) {
            if (now_us - s_rev_at < REV_GAP_US) {
                thr = 0.0f;
            } else {
                s_rev = REV_ON;
            }
        }
    } else if (thr > 0.0f) {
        s_rev = REV_IDLE; // driving forward again: the next reverse brakes first
    } else if (thr < 0.0f) {
        s_rev = REV_IDLE; // braking forward motion
    }
    s_out = (control_output_t){.steering = s_steering, .throttle = thr, .reverse = thr < 0.0f && s_rev == REV_ON};
}

void control_init(int64_t timeout_us) {
    s_timeout_us = timeout_us;
}

void control_input(float steering, float gas, float brake, int64_t now_us) {
    portENTER_CRITICAL(&s_lock);
    s_steering = clamp(steering, -1.0f, 1.0f);
    s_gas = clamp(gas, 0.0f, 1.0f);
    s_brake = clamp(brake, 0.0f, 1.0f);
    s_last_input_us = now_us;
    portEXIT_CRITICAL(&s_lock);
}

const char *control_ignition_on(int64_t now_us) {
    const char *why = NULL;
    portENTER_CRITICAL(&s_lock);
    if (!fresh(now_us)) {
        why = "NO WHEEL";
    } else if (s_gas > PEDAL_DEAD || s_brake > PEDAL_DEAD) {
        why = "RELEASE PEDALS";
    } else {
        s_engine = true;
        s_off_reason = "";
        s_gear = GEAR_N;
        s_speed = 0.0f;
        s_rev = REV_IDLE;
    }
    if (why) {
        notice_locked(why, now_us);
    }
    portEXIT_CRITICAL(&s_lock);
    return why;
}

void control_ignition_off(const char *reason) {
    portENTER_CRITICAL(&s_lock);
    stop_locked(reason);
    portEXIT_CRITICAL(&s_lock);
}

void control_estop(void) {
    portENTER_CRITICAL(&s_lock);
    s_engine = true; // so stop_locked() records the reason
    stop_locked("E-STOP");
    s_steering = 0.0f;
    s_gas = s_brake = 0.0f;
    portEXIT_CRITICAL(&s_lock);
}

const char *control_shift(int dir, int64_t now_us) {
    const char *why = NULL;
    portENTER_CRITICAL(&s_lock);
    int g = (int)s_gear + (dir > 0 ? 1 : -1);
    if (!s_engine) {
        why = "ENGINE OFF";
    } else if (g < GEAR_R || g > GEAR_TOP) {
        why = NULL; // already at the end: nothing to do
        g = s_gear;
    } else if ((g == GEAR_R && s_speed > STOPPED) || (g > GEAR_N && s_speed < -STOPPED)) {
        why = "STOP FIRST"; // no changing direction while still rolling
    }
    if (why) {
        notice_locked(why, now_us);
    } else {
        s_gear = (gear_t)g;
    }
    portEXIT_CRITICAL(&s_lock);
    return why;
}

void control_tick(int64_t now_us) {
    portENTER_CRITICAL(&s_lock);
    float dt = s_last_tick_us < 0 ? 0.0f : (float)(now_us - s_last_tick_us) * 1e-6f;
    s_last_tick_us = now_us;
    if (dt > 0.1f) {
        dt = 0.1f;
    }
    if (s_engine && !fresh(now_us)) {
        stop_locked("WHEEL LOST");
    }
    if (s_engine) {
        model_locked(dt);
        output_locked(now_us);
    } else {
        s_out = (control_output_t){0};
    }
    if (s_notice && now_us - s_notice_at > NOTICE_US) {
        s_notice = NULL;
    }
    portEXIT_CRITICAL(&s_lock);
}

control_output_t control_output(int64_t now_us) {
    portENTER_CRITICAL(&s_lock);
    control_output_t out = fresh(now_us) ? s_out : (control_output_t){0};
    portEXIT_CRITICAL(&s_lock);
    return out;
}

control_view_t control_view(int64_t now_us) {
    portENTER_CRITICAL(&s_lock);
    control_view_t v = {
        .steering = s_steering,
        .gas = s_gas,
        .brake = s_brake,
        .engine = s_engine,
        .fresh = fresh(now_us),
        .gear = s_gear,
        .speed = s_speed,
        .gear_max = gear_max(s_gear),
        .braking = braking_locked(),
        .off_reason = s_off_reason,
        .notice = s_notice,
        .output = fresh(now_us) ? s_out : (control_output_t){0},
    };
    portEXIT_CRITICAL(&s_lock);
    return v;
}
