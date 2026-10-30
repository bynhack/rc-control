#include "ffb.h"

#include <math.h>
#include <string.h>

#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "radio.h"
#include "usb/hid.h"

static const char *TAG = "ffb";

// PID report ids, from the R5's report descriptor.
#define RID_SET_EFFECT 0x01
#define RID_SET_CONDITION 0x03
#define RID_EFFECT_OP 0x0a
#define RID_DEVICE_CONTROL 0x0c
#define RID_DEVICE_GAIN 0x0d
#define RID_CREATE_EFFECT 0x11
#define RID_BLOCK_LOAD 0x12

// Effect type: 1-based index into the descriptor's list.
#define ET_SPRING 8
#define ET_DAMPER 9
#define OP_START 1
#define CTRL_ENABLE_ACTUATORS 0x01
#define CTRL_RESET 0x08
#define DURATION_INFINITE 0xffff
#define NO_TRIGGER 0xff
#define AXIS_X 0x01
#define DIRECTION_ENABLE 0x04
#define DIRECTION_X 9000 // hundredths of a degree
#define LOAD_SUCCESS 1

#define PERIOD_MS 20
// Resend a coefficient or the spring centre only when it moves at least this
// much (of 32767).
#define MIN_CHANGE 300
#define MIN_CENTRE_CHANGE 60

typedef struct {
    uint8_t block; // 0 = not created
    int last;      // last coefficient sent, -1 = none
} effect_t;

static portMUX_TYPE s_lock = portMUX_INITIALIZER_UNLOCKED;
static hid_host_device_handle_t s_dev;
static bool s_attach_pending;
static float s_spring, s_damper, s_centre;
static effect_t s_fx[2];
static int s_centre_sent; // spring centre last sent
static int s_gain = -1;

// Output reports go on the interrupt OUT endpoint: the R5 acknowledges a
// SET_REPORT on the control pipe but ignores it. Devices without one get the
// control pipe.
static esp_err_t out(uint8_t *r, size_t len) {
    esp_err_t e = hid_host_device_send_output_report(s_dev, r, len);
    if (e == ESP_ERR_NOT_SUPPORTED) {
        e = hid_class_request_set_report(s_dev, HID_REPORT_TYPE_OUTPUT, r[0], r, len);
    }
    return e;
}

static void put16(uint8_t *p, int v) {
    p[0] = (uint8_t)v;
    p[1] = (uint8_t)(v >> 8);
}

// Create New Effect, then read the block index the base gave it.
static uint8_t create(uint8_t type) {
    uint8_t c[4] = {RID_CREATE_EFFECT, type, 0, 0};
    if (hid_class_request_set_report(s_dev, HID_REPORT_TYPE_FEATURE, c[0], c, sizeof(c)) != ESP_OK) {
        return 0;
    }
    uint8_t r[5] = {0};
    size_t len = sizeof(r);
    if (hid_class_request_get_report(s_dev, HID_REPORT_TYPE_FEATURE, RID_BLOCK_LOAD, r, &len) != ESP_OK) {
        return 0;
    }
    // r: id, block index, load status, RAM pool available
    if (r[2] != LOAD_SUCCESS) {
        ESP_LOGW(TAG, "effect %d not loaded (status %d)", type, r[2]);
        return 0;
    }
    return r[1];
}

static esp_err_t set_effect(uint8_t block, uint8_t type) {
    uint8_t r[22] = {RID_SET_EFFECT, block, type};
    put16(r + 3, DURATION_INFINITE); // duration
    // trigger repeat, sample period, start delay: 0
    r[11] = 255;        // gain
    r[12] = NO_TRIGGER; // no trigger button
    // The R5 needs the direction: with it disabled (or 0, which points along
    // Y) a condition effect does nothing on the wheel.
    r[13] = AXIS_X | DIRECTION_ENABLE;
    put16(r + 14, DIRECTION_X);
    return out(r, sizeof(r));
}

// Symmetric condition on X around a centre, full saturation.
static esp_err_t set_condition(uint8_t block, int coef, int centre) {
    uint8_t r[15] = {RID_SET_CONDITION, block, 0};
    put16(r + 3, centre); // centre
    put16(r + 5, coef);   // positive coefficient
    put16(r + 7, coef);   // negative coefficient
    put16(r + 9, 32767);  // positive saturation
    put16(r + 11, 32767); // negative saturation
    put16(r + 13, 0);     // dead band
    return out(r, sizeof(r));
}

static esp_err_t start(uint8_t block) {
    uint8_t r[4] = {RID_EFFECT_OP, block, OP_START, 1};
    return out(r, sizeof(r));
}

static void setup(void) {
    uint8_t ctrl[2] = {RID_DEVICE_CONTROL, CTRL_RESET};
    out(ctrl, sizeof(ctrl));
    vTaskDelay(pdMS_TO_TICKS(50));
    ctrl[1] = CTRL_ENABLE_ACTUATORS;
    out(ctrl, sizeof(ctrl));
    s_gain = -1;
    static const uint8_t types[2] = {ET_SPRING, ET_DAMPER};
    for (int i = 0; i < 2; i++) {
        s_fx[i] = (effect_t){.block = create(types[i]), .last = -1};
        if (s_fx[i].block == 0) {
            continue;
        }
        if (set_effect(s_fx[i].block, types[i]) != ESP_OK || set_condition(s_fx[i].block, 0, 0) != ESP_OK ||
            start(s_fx[i].block) != ESP_OK) {
            ESP_LOGW(TAG, "effect %d setup failed", types[i]);
            s_fx[i].block = 0;
            continue;
        }
        s_fx[i].last = 0;
    }
    s_centre_sent = 0;
    ESP_LOGI(TAG, "spring block %d, damper block %d", s_fx[0].block, s_fx[1].block);
}

static void task(void *arg) {
    for (;;) {
        vTaskDelay(pdMS_TO_TICKS(PERIOD_MS));
        portENTER_CRITICAL(&s_lock);
        bool attach = s_attach_pending;
        s_attach_pending = false;
        bool have = s_dev != NULL;
        float want[2] = {s_spring, s_damper};
        float centre_f = s_centre;
        portEXIT_CRITICAL(&s_lock);
        if (!have) {
            continue;
        }
        if (attach) {
            vTaskDelay(pdMS_TO_TICKS(200)); // let the base settle after enumeration
            setup();
        }
        int gain = ui_ffb_get() * 255 / 100;
        if (gain != s_gain) {
            uint8_t g[2] = {RID_DEVICE_GAIN, (uint8_t)gain};
            if (out(g, sizeof(g)) == ESP_OK) {
                s_gain = gain;
            }
        }
        centre_f = centre_f < -1.0f ? -1.0f : (centre_f > 1.0f ? 1.0f : centre_f);
        int centre = (int)lroundf(centre_f * 32767.0f);
        for (int i = 0; i < 2; i++) {
            if (s_fx[i].block == 0) {
                continue;
            }
            float w = want[i] < 0.0f ? 0.0f : (want[i] > 1.0f ? 1.0f : want[i]);
            int coef = (int)lroundf(w * 32767.0f);
            int c = i == 0 ? centre : 0; // only the spring has a centre
            bool moved = i == 0 && (abs(c - s_centre_sent) >= MIN_CENTRE_CHANGE || (c == 0 && s_centre_sent != 0));
            if (s_fx[i].last < 0 || abs(coef - s_fx[i].last) >= MIN_CHANGE || (coef == 0 && s_fx[i].last != 0) ||
                moved) {
                if (set_condition(s_fx[i].block, coef, c) == ESP_OK) {
                    s_fx[i].last = coef;
                    if (i == 0) {
                        s_centre_sent = c;
                    }
                }
            }
        }
    }
}

void ffb_attach(hid_host_device_handle_t dev) {
    static bool started;
    if (!started) {
        started = true;
        xTaskCreatePinnedToCore(task, "ffb", 4096, NULL, 4, NULL, 0);
    }
    portENTER_CRITICAL(&s_lock);
    s_dev = dev;
    s_attach_pending = true;
    portEXIT_CRITICAL(&s_lock);
}

void ffb_detach(void) {
    portENTER_CRITICAL(&s_lock);
    s_dev = NULL;
    portEXIT_CRITICAL(&s_lock);
    memset(s_fx, 0, sizeof(s_fx));
}

#define RECENTRE_US 4000000

static volatile int64_t s_recentre_until = -1;

void ffb_recentre(void) {
    s_recentre_until = esp_timer_get_time() + RECENTRE_US;
}

void ffb_recentre_stop(void) {
    s_recentre_until = -1;
}

void ffb_set_centre(float centre) {
    portENTER_CRITICAL(&s_lock);
    s_centre = centre;
    portEXIT_CRITICAL(&s_lock);
}

bool ffb_recentring(void) {
    return esp_timer_get_time() < s_recentre_until;
}

void ffb_set(float spring, float damper) {
    portENTER_CRITICAL(&s_lock);
    s_spring = spring;
    s_damper = damper;
    portEXIT_CRITICAL(&s_lock);
}
