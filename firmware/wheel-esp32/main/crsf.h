// CRSF to an ExpressLRS TX module over one wire (half duplex).
//
// Wiring: module CRSF/S.Port pin -> GPIO17, GND -> GND. Same settings as the
// PC program: 400000 baud, BETAFPV DIP switches 3 and 4 ON.
//
// Channel 1 = steering, channel 2 = throttle, the rest centred.
#pragma once

#include <stdbool.h>
#include <stdint.h>

typedef struct {
    bool module;     // the module answered recently (TX alive)
    bool link;       // link statistics recently, i.e. a receiver is bound
    int rssi;        // uplink RSSI in dBm, valid when link
    int lq;          // uplink link quality 0..100, valid when link
    uint32_t frames; // RC frames sent
} crsf_status_t;

// Starts the 250 Hz sender task. Reads control_output() for every frame.
void crsf_start(void);

crsf_status_t crsf_status(void);
