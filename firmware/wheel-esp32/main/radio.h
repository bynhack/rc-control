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

// Loads the saved cars (or the defaults). Call before the radios start.
void radio_init(void);
// The active car's radio.
radio_config_t radio_config(void);
// Applies to the active car and saves.
void radio_set(const radio_config_t *c);
const char *radio_kind_name(radio_kind_t k);

// ---- cars --------------------------------------------------------------------
//
// Each car keeps its own radio, top speed and engine sound; one is active,
// and radio_config()/radio_set(), ui_topspeed_*() and ui_sound_*() work on
// that one. Everything else (language, volume, force feedback, screen,
// ELRS wiring) belongs to the controller, not the car.

#define CAR_COUNT 6
#define CAR_NAME_LEN 16

typedef struct {
    char name[CAR_NAME_LEN]; // "" = the default "Car N"
    radio_config_t radio;
    uint8_t top_kmh;
    uint8_t sound;
} car_t;

int car_active(void);
void car_select(int i);
car_t car_get(int i);
void car_rename(int i, const char *name);

// Screen language, saved next to the radio choice: 0 = Simplified Chinese
// (the default), 1 = Traditional.
int ui_lang_get(void);
void ui_lang_set(int lang);

// Which instrument cluster the main screen shows (dash_p4.c), saved.
int ui_dash_get(void);
void ui_dash_set(int dash);

// The active car's top speed in km/h, for turning the modelled speed into km/h on
// the dashboard (there is no speed sensor). Default 30.
int ui_topspeed_get(void);
void ui_topspeed_set(int kmh);

// Force feedback strength on the wheel base, 0..100 % (ffb.c). Default 40.
int ui_ffb_get(void);
void ui_ffb_set(int pct);

// Engine sound volume on the speaker, 0..100 % (sound.c). Default 80.
int ui_vol_get(void);
void ui_vol_set(int pct);

// The active car's engine sound (sound.h: SOUND_ROAD, SOUND_RALLY, SOUND_M4). Read every audio
// block, so cached.
int ui_sound_get(void);
void ui_sound_set(int voice);

// How the ELRS module is wired: false = one wire, half duplex (BETAFPV
// module, CRSF pin only); true = two wires, full duplex (a Nano receiver
// flashed as a TX). Read every frame by crsf.c, so cached.
bool ui_elrs_duplex_get(void);
void ui_elrs_duplex_set(bool full);

// The screen turned 180 degrees (for mounting the board upside down); takes
// effect at the next boot.
bool ui_flip_get(void);
void ui_flip_set(bool flip);
