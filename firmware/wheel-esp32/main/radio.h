// Which transmitter drives the car, chosen on the screen and kept in NVS.
//
// ELRS: the CRSF module (crsf.c). MULTI: the 4-in-1 module (multi.c), either
// over its serial protocol (the protocol is picked here) or as plain PPM
// (the protocol is picked on the module's own dial). REMOTE: a toy car's own
// remote, its pots replaced by a DAC (remote.c). Only the selected one
// transmits.
#pragma once

#include <stdbool.h>
#include <stdint.h>

typedef enum { RADIO_ELRS, RADIO_MULTI_SERIAL, RADIO_MULTI_PPM, RADIO_REMOTE, RADIO_KINDS } radio_kind_t;
// The kinds with a slot in rev_steer/rev_thr; REMOTE came later and keeps
// its own in rev_remote, so the saved layout stays as it was.
#define RADIO_REV_KINDS 3

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
    // Per kind: the ELRS car and the MULTI cars are wired differently. Read
    // and flip them with radio_rev() / radio_rev_flip().
    bool rev_steer[RADIO_REV_KINDS];
    bool rev_thr[RADIO_REV_KINDS];
    // Steering trim, like the knob on a stock radio, for a car that doesn't
    // run straight with the wheel centred: thousandths of full lock, + = right.
    int16_t trim;
    // Handling, per car (the 操控 tab). The wheel turns WHEEL_DEG lock to
    // lock (Pit House); the car's full lock comes at steer_deg of it.
    uint16_t steer_deg;
    // Steering end points, thousandths of full lock: [0] left, [1] right,
    // so the servo stops where the car's steering does.
    uint16_t steer_max[2];
    // The throttle's dead band: where the ESC starts to move the car,
    // thousandths of full throttle, [0] forward, [1] reverse. The pedal's
    // travel starts there.
    uint16_t thr_start[2];
    // Softer steering around the centre, percent (0 = linear).
    uint8_t expo;
    bool rev_remote[2]; // REMOTE's reverse: [0] steering, [1] throttle
    // The steering's dead band: where the wheels start to turn, thousandths
    // of full lock, [0] left, [1] right. The wheel's travel starts there.
    uint16_t steer_start[2];
    uint8_t reserved[2];
} radio_config_t;

// Whether the selected kind's steering (thr false) or throttle is reversed.
bool radio_rev(const radio_config_t *c, bool thr);
void radio_rev_flip(radio_config_t *c, bool thr);

#define TRIM_MAX 300
#define WHEEL_DEG 900
#define STEER_DEG_MIN 90
#define STEER_MAX_MIN 300
#define THR_START_MAX 800
#define STEER_START_MAX 500
#define EXPO_MAX 80

// Loads the saved cars (or the defaults). Call before the radios start.
void radio_init(void);
// The active car's radio.
radio_config_t radio_config(void);
// Applies to the active car and saves.
void radio_set(const radio_config_t *c);
const char *radio_kind_name(radio_kind_t k);
// The handling, the same for every radio kind: each kind only turns the -1..1
// these return into its own signal (CRSF channels, PPM, MULTI channels, DAC
// codes), so every way of driving a car goes through it.
//
// Steering: range (steer_deg) -> expo -> dead band -> trim -> end points ->
// reverse. Throttle: dead band -> reverse; braking is passed as it is.
//
// The wheel's -1..+1 (WHEEL_DEG) scaled to steer_deg, then expo.
float radio_steer_shape(const radio_config_t *c, float wheel);
// Shaped, then past the dead band: the steering before trim and end points.
float radio_steer_base(const radio_config_t *c, float wheel);
// The steering the car gets for the wheel.
float radio_steering(const radio_config_t *c, float wheel);
// The throttle the car gets for control_output().
float radio_throttle(const radio_config_t *c, float throttle, bool reverse);

// Setting a handling value with the wheel or pedals on the dashboard. While
// one is set, the step it sets is left out, so the driver finds the right
// spot and saves it: CAL_TRIM leaves out the trim, CAL_ENDS the end points,
// CAL_THROTTLE the throttle's dead band (and control.c then sends the gas
// pedal straight, up to CAL_THROTTLE_MAX), CAL_STEER_START the steering's.
typedef enum { CAL_NONE, CAL_TRIM, CAL_ENDS, CAL_THROTTLE, CAL_STEER_START } radio_cal_t;
#define CAL_THROTTLE_MAX 0.9f
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

// Which wheel base to use (wheel.h wheel_kind_t; WHEEL_NONE = whichever is
// plugged in, the default). Read with every input report, so cached.
int ui_wheel_get(void);
void ui_wheel_set(int kind);

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
