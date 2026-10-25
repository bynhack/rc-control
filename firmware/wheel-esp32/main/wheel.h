// Wheel base input report parsing, chosen by USB VID:PID.
//
// Thrustmaster T300RS (044f:b66e, PC mode), same layout as src/wheel.rs:
//   report id 0x07, little-endian 16-bit words
//   b1..b2  steering: centre ~0x8000, full lock ~0x4A00 / 0xB400
//   b3..b4  brake    } only the low 10 bits count:
//   b5..b6  gas      } 1023 released, 0 floored
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
#define MOZA_VID 0x346e

typedef struct {
    float steering; // -1 (left) .. +1 (right)
    float gas;      // 0 released .. 1 floored
    float brake;    // 0 released .. 1 floored
    float throttle; // gas - brake, -1 .. +1
    uint64_t buttons; // bit n-1 = button n pressed (MOZA only so far)
} wheel_axes_t;

#define WHEEL_BUTTON(n) (1ull << ((n) - 1))

// True when this VID:PID has a known layout.
bool wheel_known(uint16_t vid, uint16_t pid);

// Short model name for the screen, or NULL when unknown.
const char *wheel_name(uint16_t vid, uint16_t pid);

// Parses one input report. Returns false for anything that is not a
// steering/pedal report (other report ids, short reads, unknown devices).
bool wheel_parse(uint16_t vid, uint16_t pid, const uint8_t *data, size_t len, wheel_axes_t *out);
