// Which transmitter drives the car, chosen on the screen and kept in NVS.
//
// ELRS: the CRSF module (crsf.c). MULTI: the 4-in-1 module (multi.c), either
// over its serial protocol (the protocol is picked here) or as plain PPM
// (the protocol is picked on the module's own dial). Only the selected one
// transmits.
#pragma once

#include <stdbool.h>
#include <stdint.h>

typedef enum { RADIO_ELRS, RADIO_MULTI_SERIAL, RADIO_MULTI_PPM, RADIO_KINDS } radio_kind_t;

// A MULTI protocol as the serial frame names it (Multiprotocol.h).
typedef struct {
    const char *name;
    uint8_t protocol;
    uint8_t sub;
    int8_t option; // default; CC2500 protocols: fine frequency tune
} multi_proto_t;

extern const multi_proto_t MULTI_PROTOS[];
extern const int MULTI_PROTO_COUNT;

typedef struct {
    radio_kind_t kind;
    uint8_t proto;  // index into MULTI_PROTOS
    uint8_t rx_num; // 0..15, one per bound model
    int8_t option;
    // Per kind: the ELRS car and the MULTI cars are wired differently.
    bool rev_steer[RADIO_KINDS];
    bool rev_thr[RADIO_KINDS];
} radio_config_t;

// Loads the saved choice (or the defaults). Call before the radios start.
void radio_init(void);
radio_config_t radio_config(void);
// Applies and saves.
void radio_set(const radio_config_t *c);
const char *radio_kind_name(radio_kind_t k);
