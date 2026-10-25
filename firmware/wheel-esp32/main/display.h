// 1.28" round GC9A01 status screen (240x240, SPI).
//
// Wiring (module pin -> ESP32-S3):
//   RST -> GPIO8   CS  -> GPIO10   DC -> GPIO9
//   SDA -> GPIO11  SCL -> GPIO12   (SPI MOSI / clock, not I2C)
//   VCC -> 3V3     GND -> GND      (no backlight pin; always on)
#pragma once

#include <stdbool.h>
#include <stdint.h>

#include "wheel.h"

typedef struct {
    bool wheel;       // a parsed wheel report arrived recently
    wheel_axes_t axes; // valid when wheel is true
    float rate;       // reports per second
    uint16_t vid, pid; // attached HID device, 0 when none
} display_state_t;

void display_init(void);

// Safe to call from any task; draws on the next LVGL refresh.
void display_show(const display_state_t *s);
