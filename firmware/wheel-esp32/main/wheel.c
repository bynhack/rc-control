#include "wheel.h"

// T300: half the measured lock-to-centre span.
#define T300_STEER_HALF ((float)0x3800)
#define T300_REPORT_ID 0x07
#define T300_REPORT_MIN_LEN 16

#define MOZA_REPORT_ID 0x01
#define MOZA_REPORT_MIN_LEN 13
#define MOZA_OFF_STEER 1
#define MOZA_OFF_GAS 5
#define MOZA_OFF_BRAKE 11
// Buttons start at bit 4 of byte 17, after the hat switch nibble.
#define MOZA_BUTTON_BIT0 (17 * 8 + 4)

static inline uint16_t u16le(const uint8_t *d, size_t i) {
    return (uint16_t)(d[i] | (d[i + 1] << 8));
}

static inline float clampf(float v, float lo, float hi) {
    return v < lo ? lo : (v > hi ? hi : v);
}

// T300 pedal word (1023 released, 0 floored) -> pressed ratio 0..1.
static inline float t300_pressed(const uint8_t *d, size_t i) {
    return 1.0f - (float)(u16le(d, i) & 0x03ff) / 1023.0f;
}

// MOZA pedal axis (i16, -32768 released, 32767 floored) -> 0..1.
static inline float moza_pressed(const uint8_t *d, size_t i) {
    return ((float)(int16_t)u16le(d, i) + 32768.0f) / 65535.0f;
}

static bool t300_parse(const uint8_t *data, size_t len, wheel_axes_t *out) {
    if (len < T300_REPORT_MIN_LEN || data[0] != T300_REPORT_ID) {
        return false;
    }
    out->steering = clampf(((float)u16le(data, 1) - (float)0x8000) / T300_STEER_HALF, -1.0f, 1.0f);
    out->brake = t300_pressed(data, 3);
    out->gas = t300_pressed(data, 5);
    out->buttons = 0;
    return true;
}

static bool moza_parse(const uint8_t *data, size_t len, wheel_axes_t *out) {
    if (len < MOZA_REPORT_MIN_LEN || data[0] != MOZA_REPORT_ID) {
        return false;
    }
    out->steering = clampf(((float)u16le(data, MOZA_OFF_STEER) - 32768.0f) / 32768.0f, -1.0f, 1.0f);
    out->brake = moza_pressed(data, MOZA_OFF_BRAKE);
    out->gas = moza_pressed(data, MOZA_OFF_GAS);
    out->buttons = 0;
    for (int k = 0; k < 64; k++) {
        size_t bit = MOZA_BUTTON_BIT0 + k;
        if (bit / 8 < len && (data[bit / 8] >> (bit % 8)) & 1) {
            out->buttons |= 1ull << k;
        }
    }
    return true;
}

bool wheel_known(uint16_t vid, uint16_t pid) {
    return wheel_name(vid, pid) != NULL;
}

const char *wheel_name(uint16_t vid, uint16_t pid) {
    if (vid == T300_VID && pid == T300_PID_BASE) {
        return "T300RS";
    }
    if (vid == MOZA_VID) {
        return "MOZA";
    }
    return NULL;
}

bool wheel_parse(uint16_t vid, uint16_t pid, const uint8_t *data, size_t len, wheel_axes_t *out) {
    bool ok;
    if (vid == T300_VID && pid == T300_PID_BASE) {
        ok = t300_parse(data, len, out);
    } else if (vid == MOZA_VID) {
        ok = moza_parse(data, len, out);
    } else {
        return false;
    }
    if (ok) {
        out->throttle = clampf(out->gas - out->brake, -1.0f, 1.0f);
    }
    return ok;
}
