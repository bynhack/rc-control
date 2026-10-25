#include "control.h"

#include <math.h>
#include <stddef.h>

#include "freertos/FreeRTOS.h"

// Throttle demand below this counts as "pedals released" for arming.
#define ARM_THROTTLE_TOLERANCE 0.02f

static portMUX_TYPE s_lock = portMUX_INITIALIZER_UNLOCKED;
static float s_steering;
static float s_throttle_demand;
static bool s_armed;
static speed_t s_speed = SPEED_LOW;
static int64_t s_last_input_us = -1;
static int64_t s_timeout_us;
static const char *s_disarm_reason = "BOOT";

static float clean(float v) {
    if (!isfinite(v)) {
        return 0.0f;
    }
    return v < -1.0f ? -1.0f : (v > 1.0f ? 1.0f : v);
}

static float scale(speed_t s) {
    switch (s) {
        case SPEED_MID:
            return 2.0f / 3.0f;
        case SPEED_HIGH:
            return 1.0f;
        default:
            return 1.0f / 3.0f;
    }
}

// Callers hold s_lock.
static bool fresh(int64_t now_us) {
    return s_last_input_us >= 0 && now_us - s_last_input_us <= s_timeout_us;
}

static void disarm_locked(const char *reason) {
    if (s_armed) {
        s_armed = false;
        s_disarm_reason = reason;
    }
}

static control_output_t output_locked(int64_t now_us) {
    if (!fresh(now_us)) {
        return (control_output_t){0};
    }
    float throttle = s_armed ? s_throttle_demand * scale(s_speed) : 0.0f;
    return (control_output_t){.steering = s_steering, .throttle = throttle};
}

void control_init(int64_t timeout_us) {
    s_timeout_us = timeout_us;
}

void control_input(float steering, float throttle, int64_t now_us) {
    portENTER_CRITICAL(&s_lock);
    s_steering = clean(steering);
    s_throttle_demand = clean(throttle);
    s_last_input_us = now_us;
    portEXIT_CRITICAL(&s_lock);
}

const char *control_arm(int64_t now_us) {
    const char *why = NULL;
    portENTER_CRITICAL(&s_lock);
    if (!fresh(now_us)) {
        why = "NO WHEEL";
    } else if (fabsf(s_throttle_demand) > ARM_THROTTLE_TOLERANCE) {
        why = "RELEASE PEDALS";
    } else {
        s_armed = true;
        s_disarm_reason = "";
    }
    portEXIT_CRITICAL(&s_lock);
    return why;
}

void control_disarm(const char *reason) {
    portENTER_CRITICAL(&s_lock);
    disarm_locked(reason);
    portEXIT_CRITICAL(&s_lock);
}

void control_estop(void) {
    portENTER_CRITICAL(&s_lock);
    s_armed = true; // so disarm_locked() records the reason
    disarm_locked("E-STOP");
    s_steering = 0.0f;
    s_throttle_demand = 0.0f;
    portEXIT_CRITICAL(&s_lock);
}

void control_set_speed(speed_t speed) {
    portENTER_CRITICAL(&s_lock);
    s_speed = speed;
    portEXIT_CRITICAL(&s_lock);
}

speed_t control_speed(void) {
    portENTER_CRITICAL(&s_lock);
    speed_t s = s_speed;
    portEXIT_CRITICAL(&s_lock);
    return s;
}

void control_tick(int64_t now_us) {
    portENTER_CRITICAL(&s_lock);
    if (s_armed && !fresh(now_us)) {
        disarm_locked("WHEEL LOST");
    }
    portEXIT_CRITICAL(&s_lock);
}

control_output_t control_output(int64_t now_us) {
    portENTER_CRITICAL(&s_lock);
    control_output_t out = output_locked(now_us);
    portEXIT_CRITICAL(&s_lock);
    return out;
}

control_view_t control_view(int64_t now_us) {
    portENTER_CRITICAL(&s_lock);
    control_view_t v = {
        .steering = s_steering,
        .throttle_demand = s_throttle_demand,
        .armed = s_armed,
        .fresh = fresh(now_us),
        .speed = s_speed,
        .disarm_reason = s_disarm_reason,
        .output = output_locked(now_us),
    };
    portEXIT_CRITICAL(&s_lock);
    return v;
}
