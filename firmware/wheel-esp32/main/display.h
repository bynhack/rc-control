// 1.28" round GC9A01 status screen (240x240, SPI).
//
// Wiring (module pin -> ESP32-S3):
//   RST -> GPIO8   CS  -> GPIO10   DC -> GPIO9
//   SDA -> GPIO11  SCL -> GPIO12   (SPI MOSI / clock, not I2C)
//   VCC -> 3V3     GND -> GND      (no backlight pin; always on)
#pragma once

#include <stdbool.h>
#include <stdint.h>

#include "control.h"
#include "crsf.h"

typedef struct {
    bool wheel;        // a parsed wheel report arrived recently
    uint16_t vid, pid; // attached HID device, 0 when none
    float rate;        // reports per second
    control_view_t ctl;
    crsf_status_t radio;
    int button; // last pressed button number while it is shown, else 0
} display_state_t;

void display_init(void);

// Safe to call from any task; draws on the next LVGL refresh.
void display_show(const display_state_t *s);
