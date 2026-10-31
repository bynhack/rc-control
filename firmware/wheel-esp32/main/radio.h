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
    // Steering trim, like the knob on a stock radio, for a car that doesn't
    // run straight with the wheel centred: thousandths of full lock, + = right.
    int16_t trim;
    // Handling, per car (the 操控 tab). The wheel turns WHEEL_DEG lock to
    // lock (Pit House); the car's full lock comes at steer_deg of it.
    uint16_t steer_deg;
    // Steering end points, thousandths of full lock: [0] left, [1] right,
    // so the servo stops where the car's steering does.
    uint16_t steer_max[2];
    // Where the ESC starts to move the car, thousandths of full throttle:
    // [0] forward, [1] reverse. The pedal's travel starts there.
    uint16_t thr_start[2];
    // Softer steering around the centre, percent (0 = linear).
    uint8_t expo;
    uint8_t reserved[7];
} radio_config_t;

#define TRIM_MAX 300
#define WHEEL_DEG 900
#define STEER_DEG_MIN 90
#define STEER_MAX_MIN 300
#define THR_START_MAX 400
#define EXPO_MAX 80

// Loads the saved cars (or the defaults). Call before the radios start.
void radio_init(void);
// The active car's radio.
radio_config_t radio_config(void);
// Applies to the active car and saves.
void radio_set(const radio_config_t *c);
const char *radio_kind_name(radio_kind_t k);
// The wheel's -1..+1 (WHEEL_DEG) as the car's steering before trim and end
// points: scaled to steer_deg, then expo.
float radio_steer_shape(const radio_config_t *c, float wheel);
// The steering the car gets for the wheel: shaped, trimmed, held to the end
// points, then reversed if this output is wired that way.
float radio_steering(const radio_config_t *c, float wheel);
// The throttle the ESC gets for control_output(): forward and reverse start
// at thr_start, braking is passed as it is; reversed if wired that way.
float radio_throttle(const radio_config_t *c, float throttle, bool reverse);

// Setting a handling value with the wheel or pedals on the dashboard. While
// one is set, the step it sets is left out, so the driver finds the right
// spot and saves it: CAL_TRIM leaves out the trim, CAL_ENDS the end points,
// CAL_THROTTLE the start points (and control.c then sends the gas pedal
// straight, up to CAL_THROTTLE_MAX).
typedef enum { CAL_NONE, CAL_TRIM, CAL_ENDS, CAL_THROTTLE } radio_cal_t;
#define CAL_THROTTLE_MAX 0.5f
void radio_cal_set(radio_cal_t cal);
radio_cal_t radio_cal_get(void);

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
