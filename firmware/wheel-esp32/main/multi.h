// A DIY-Multiprotocol (MULTI 4-in-1) TX module, e.g. the iRangeX IRX4+, in
// serial mode: dial at 0, green LED off.
//
// Wiring (P4 7B): module PPM pin <- GPIO30 (terminal P3), GND -> GND,
// VCC -> 5 V (the module takes 5-14 V). One way only: the module's
// telemetry (S.Port pin) isn't read yet, so its red LED is the only sign of
// life: slow blink = no valid serial input, solid = transmitting, fast
// blink = binding.
//
// Channel 1 = steering, channel 2 = throttle, like crsf.c.
#pragma once

#include <stdbool.h>
#include <stdint.h>

// Starts the sender task. Reads control_output() for every frame.
void multi_start(void);

// Puts the module into bind mode for a few seconds. Put the receiver into
// bind mode first.
void multi_bind(void);

typedef struct {
    bool binding;
    uint32_t frames; // serial frames sent
} multi_status_t;

multi_status_t multi_status(void);
