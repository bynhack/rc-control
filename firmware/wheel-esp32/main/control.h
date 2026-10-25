// Every safety rule between the wheel and the radio, in one place.
// A port of src/control.rs: the CRSF sender only ever reads
// control_output(), so nothing can bypass arming or the watchdog.
#pragma once

#include <stdbool.h>
#include <stdint.h>

typedef enum { SPEED_LOW, SPEED_MID, SPEED_HIGH } speed_t;

typedef struct {
    float steering; // -1 .. +1
    float throttle; // -1 .. +1, already scaled by the speed tier
} control_output_t;

typedef struct {
    float steering;
    float throttle_demand;
    bool armed;
    bool fresh;
    speed_t speed;
    const char *disarm_reason; // short, ASCII (the screen font has no CJK)
    control_output_t output;
} control_view_t;

void control_init(int64_t timeout_us);

// A wheel sample; doubles as the heartbeat.
void control_input(float steering, float throttle, int64_t now_us);

// Returns NULL on success, else why arming was refused.
const char *control_arm(int64_t now_us);
void control_disarm(const char *reason);
// Disarm and centre everything, regardless of input.
void control_estop(void);
void control_set_speed(speed_t speed);
speed_t control_speed(void);

// Latches a disarm once input goes stale, so a wheel that comes back cannot
// resume driving without an explicit re-arm.
void control_tick(int64_t now_us);

control_output_t control_output(int64_t now_us);
control_view_t control_view(int64_t now_us);
