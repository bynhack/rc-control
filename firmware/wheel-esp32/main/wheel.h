// Wheel base input report parsing. Which base is plugged in comes from its
// USB VID:PID; which one to use is chosen on the screen (ui_wheel_get()).
//
// Thrustmaster T300RS (044f:b66e, PS3 / PC mode), report descriptor as
// hid-tmff2 rewrites it:
//   report id 0x07, little-endian 16-bit words
//   b1..b2  X steering: 0 .. 65535, centre 0x8000; full lock is the range
//           ffb.c sets (WHEEL_DEG)
//   b3..b4  brake    } only the low 10 bits count:
//   b5..b6  gas      } 1023 released, 0 floored
//   b7..b8  clutch
//   b11     13 buttons from bit 0, then the hat
// It first shows up as 044f:b65d ("Thrustmaster FFB Wheel") and has to be
// told to switch to b66e (wheel_t300_switch in main.c, as hid-thrustmaster).
//
// MOZA R5 (346e:0004), from its report descriptor and a capture:
//   report id 0x01, 42 bytes, little-endian
//   b1..b2   X  u16  steering: 0 .. 65535, centre 0x8000; full lock is the
//                   rotation angle set in Pit House
//   b3..b16  Y Z Rx Ry Rz Dial Slider, i16, -32768 released .. 32767
//            Z (b5) = gas (right pedal), Rz (b11) = brake (left pedal)
//            with the stock SR-P pedals
//   b17      hat (low nibble, 8 = centred), then 128 buttons from bit 4:
//            13 / 14 left / right paddle, 32 P, 36 Start, 19 N, 20 WIP
#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define T300_VID 0x044f
#define T300_PID_BASE 0xb66e
#define T300_PID_BOOT 0xb65d
#define MOZA_VID 0x346e

// WHEEL_NONE: not a known base. As the screen setting it means "any".
typedef enum { WHEEL_NONE, WHEEL_MOZA, WHEEL_T300, WHEEL_KINDS } wheel_kind_t;

typedef struct {
    float steering; // -1 (left) .. +1 (right)
    float gas;      // 0 released .. 1 floored
    float brake;    // 0 released .. 1 floored
    float throttle; // gas - brake, -1 .. +1
    uint64_t buttons; // bit n-1 = button n pressed
} wheel_axes_t;

#define WHEEL_BUTTON(n) (1ull << ((n) - 1))

wheel_kind_t wheel_kind(uint16_t vid, uint16_t pid);

// Short model name for the screen, or NULL for WHEEL_NONE.
const char *wheel_kind_name(wheel_kind_t k);

// Whether a base of kind k is used with the screen setting want.
static inline bool wheel_wanted(wheel_kind_t k, wheel_kind_t want) {
    return k != WHEEL_NONE && (want == WHEEL_NONE || want == k);
}

// Parses one input report. Returns false for anything that is not a
// steering/pedal report (other report ids, short reads, WHEEL_NONE).
bool wheel_parse(wheel_kind_t k, const uint8_t *data, size_t len, wheel_axes_t *out);
