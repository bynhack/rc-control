// Every safety rule and the driving model between the wheel and the radio,
// in one place. The radio senders only ever read control_output(), so
// nothing can bypass the ignition or the watchdog.
//
// Driving like a car:
//   - Start is the ignition. Engine off: nothing moves. It only starts in
//     neutral with both pedals released.
//   - Gears R N 1 2 3 on the paddles. Each forward gear caps the power; R is
//     the only way to reverse, and only from a standstill.
//   - The gas pedal sets a target speed. Lifting off coasts down slowly
//     instead of stopping dead; the brake pedal brakes (never reverses).
//
// "Speed" is a model, not a measurement: the car has no speed sensor.
#pragma once

#include <stdbool.h>
#include <stdint.h>

typedef enum { GEAR_R = -1, GEAR_N = 0, GEAR_1 = 1, GEAR_2 = 2, GEAR_3 = 3 } gear_t;
#define GEAR_TOP GEAR_3

typedef struct {
    float steering; // -1 .. +1
    float throttle; // -1 .. +1 to the ESC: + drive, - brake or reverse
} control_output_t;

typedef struct {
    float steering;
    float gas, brake; // pedals 0..1
    bool engine;
    bool fresh;
    gear_t gear;
    float speed;     // modelled speed -1..1, negative when reversing
    float gear_max;  // the current gear's power cap 0..1
    bool braking;
    const char *off_reason; // why the engine is off: "BOOT", "E-STOP", ...
    const char *notice;     // a refused action, shown for a moment, else NULL
    control_output_t output;
} control_view_t;

void control_init(int64_t timeout_us);

// A wheel sample; doubles as the heartbeat.
void control_input(float steering, float gas, float brake, int64_t now_us);

// Returns NULL on success, else why the engine won't start.
const char *control_ignition_on(int64_t now_us);
void control_ignition_off(const char *reason);
// Engine off and everything centred, regardless of input.
void control_estop(void);

// One gear up (+1) or down (-1). Returns NULL, or why it was refused.
const char *control_shift(int dir, int64_t now_us);

// Advances the driving model and latches an engine stop once input goes
// stale, so a wheel that comes back cannot drive off without a restart.
// Called by every radio sender; each call integrates the time since the
// last one.
void control_tick(int64_t now_us);

control_output_t control_output(int64_t now_us);
control_view_t control_view(int64_t now_us);
