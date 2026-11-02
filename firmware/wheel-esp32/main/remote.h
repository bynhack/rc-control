// A toy car's own 2.4G remote, driven through an MCP4728 I2C DAC: the DAC
// takes the place of the remote's steering and throttle pots.
//
// Wiring (P4 7B), bottom row: VCC <- 3V3 of the 12-pin header, GND, SCL, SDA
// <- the I2C terminal (GPIO8 / GPIO7, shared with the touch panel), LDAC ->
// GND. Not the I2C terminal's VCC: it is 5 V, and the board's 4.7k pull-ups
// would lift the bus to 5 V and hang it. Top row: VA -> the steering pot's
// wiper pad, VB -> the throttle pot's, with the pots' middle legs cut; VCC
// and GND -> the remote's battery contacts, batteries out, so the remote and
// the DAC share one 3V3 and scale alike.
//
// While the active car's radio is REMOTE (radio.h) the DAC follows
// control_output(); for any other car it holds the rest position. It also
// stores that position in the DAC's EEPROM, which the DAC puts out at
// power-up before the P4 has booted.
#pragma once

#include <stdbool.h>
#include <stdint.h>

void remote_start(void);

typedef struct {
    bool found;
    uint16_t steer, thr; // DAC codes last written, 0..4095
} remote_status_t;

remote_status_t remote_status(void);
