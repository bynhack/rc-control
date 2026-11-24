// Per-car settings in NVS. Set from the console now; from the venue server later (docs/platform-plan.md).
#pragma once

#include <stdbool.h>
#include <stdint.h>

typedef struct {
    uint8_t car_no;        // IR car number, 1..15
    uint8_t speed_limit;   // max throttle, % (the venue's second line; the wheel is the first)
    uint8_t gyro_gain;     // steering assist, % (0 = off)
    bool gyro_rev;         // flip the gyro's sign (depends on how the board sits)
    bool motor_rev;        // swap the motor's direction
    bool steer_rev;        // reverse the servo
    bool ir_on;            // send the lap transponder frames
    bool vtx_on;           // power the VTX
    uint16_t cutoff_mv;    // battery cut-off, mV for the pack (2S)
} settings_t;

extern settings_t g_set;

void settings_init(void);
void settings_save(void);
