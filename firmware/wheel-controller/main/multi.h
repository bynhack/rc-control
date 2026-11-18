// A DIY-Multiprotocol (MULTI 4-in-1) TX module, e.g. the iRangeX IRX4+.
// Serial mode (dial at 0): the protocol comes from radio.h. PPM mode (dial
// 1-E): the module's own protocol table. radio.h picks which, or neither.
//
// Wiring (P4 7B): module PPM pin <- GPIO29 (terminal P3), GND -> GND,
// VCC -> 5 V (the module takes 5-14 V). One way only: the module's
// telemetry (S.Port pin) isn't read yet, so its red LED is the only sign of
// life: slow blink = no valid input, solid = transmitting, fast blink =
// binding.
//
// Channel 1 = steering, channel 2 = throttle, like crsf.c.
#pragma once

#include <stdbool.h>
#include <stdint.h>

// Starts the sender task. Reads control_output() for every frame.
void multi_start(void);

// Serial mode: puts the module into bind mode for 30 s. In PPM mode the
// module's own bind button does it.
void multi_bind(void);
void multi_bind_cancel(void);

typedef struct {
    bool binding;
    int bind_left_s;
    uint32_t frames; // frames sent while MULTI is the selected radio
} multi_status_t;

multi_status_t multi_status(void);
