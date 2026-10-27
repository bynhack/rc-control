// Status screen, per target:
//   ESP32-S3: 1.28" round GC9A01 (240x240, SPI), display.c
//     RST -> GPIO8   CS  -> GPIO10   DC -> GPIO9
//     SDA -> GPIO11  SCL -> GPIO12   (SPI MOSI / clock, not I2C)
//     VCC -> 3V3     GND -> GND      (no backlight pin; always on)
//   ESP32-P4 (Waveshare 7B): the board's 7" 1024x600 touch panel, display_p4.c
#pragma once

#include <stdbool.h>
#include <stdint.h>

#include "control.h"
#include "crsf.h"
#include "wheel.h"

typedef struct {
    bool wheel;        // a parsed wheel report arrived recently
    uint16_t vid, pid; // attached HID device, 0 when none
    float rate;        // reports per second
    wheel_axes_t axes; // raw pedals and steering, valid when wheel is true
    control_view_t ctl;
    crsf_status_t radio;
    int button; // last pressed button number while it is shown, else 0
} display_state_t;

void display_init(void);

// Safe to call from any task; draws on the next LVGL refresh.
void display_show(const display_state_t *s);
