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

// ---- MOZA R5: USB PID ------------------------------------------------------

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

// The effects: centring spring, damper, and the end stop (a second spring
// with a dead band, so it only pushes once the wheel is past the car's lock).
enum { FX_SPRING, FX_DAMPER, FX_STOP, FX_COUNT };
#define STOP_COEF 32767

static portMUX_TYPE s_lock = portMUX_INITIALIZER_UNLOCKED;
static hid_host_device_handle_t s_dev;
static wheel_kind_t s_kind;
static bool s_attach_pending;
static float s_spring, s_damper, s_centre, s_stop = 1.0f;
static effect_t s_fx[FX_COUNT];
static int s_centre_sent; // spring centre last sent
static int s_stop_sent;   // end stop dead band last sent
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

static esp_err_t pid_set_effect(uint8_t block, uint8_t type) {
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
static esp_err_t pid_condition(uint8_t block, int coef, int centre, int dead_band) {
    uint8_t r[15] = {RID_SET_CONDITION, block, 0};
    put16(r + 3, centre); // centre
    put16(r + 5, coef);   // positive coefficient
    put16(r + 7, coef);   // negative coefficient
    put16(r + 9, 32767);  // positive saturation
    put16(r + 11, 32767); // negative saturation
    put16(r + 13, dead_band);
    return out(r, sizeof(r));
}

static esp_err_t pid_start(uint8_t block) {
    uint8_t r[4] = {RID_EFFECT_OP, block, OP_START, 1};
    return out(r, sizeof(r));
}

static void pid_setup(void) {
    uint8_t ctrl[2] = {RID_DEVICE_CONTROL, CTRL_RESET};
    out(ctrl, sizeof(ctrl));
    vTaskDelay(pdMS_TO_TICKS(50));
    ctrl[1] = CTRL_ENABLE_ACTUATORS;
    out(ctrl, sizeof(ctrl));
    static const uint8_t types[FX_COUNT] = {ET_SPRING, ET_DAMPER, ET_SPRING};
    for (int i = 0; i < FX_COUNT; i++) {
        s_fx[i] = (effect_t){.block = create(types[i]), .last = -1};
        if (s_fx[i].block == 0) {
            continue;
        }
        if (pid_set_effect(s_fx[i].block, types[i]) != ESP_OK || pid_condition(s_fx[i].block, 0, 0, 0) != ESP_OK ||
            pid_start(s_fx[i].block) != ESP_OK) {
            ESP_LOGW(TAG, "effect %d setup failed", types[i]);
            s_fx[i].block = 0;
            continue;
        }
        s_fx[i].last = 0;
    }
}

static esp_err_t pid_gain(int gain) {
    uint8_t g[2] = {RID_DEVICE_GAIN, (uint8_t)gain};
    return out(g, sizeof(g));
}

// ---- T300RS: Thrustmaster's protocol ----------------------------------------
//
// Every command is output report 0x60 with 63 bytes after the id, zero
// padded. Effects are numbered by us: effect i has id i + 1. Where the spring
// pulls to and its dead band are one thing on this base: the band runs from
// left_band to right_band, around the centre.

#define T300_RID 0x60
#define T300_LEN 63
#define T300_SPRING 0x06
#define T300_DAMPER 0x07
#define T300_SAT_SPRING 0x6aa6
#define T300_SAT_DAMPER 0x7ffc

static esp_err_t t300_send(const uint8_t *cmd, size_t len) {
    uint8_t r[1 + T300_LEN] = {T300_RID};
    memcpy(r + 1, cmd, len);
    return out(r, sizeof(r));
}

static int clamp7fff(int v) {
    return v < -0x7fff ? -0x7fff : (v > 0x7fff ? 0x7fff : v);
}

static uint8_t t300_type(int fx) {
    return fx == FX_DAMPER ? T300_DAMPER : T300_SPRING;
}

static int t300_sat(int fx) {
    return fx == FX_DAMPER ? T300_SAT_DAMPER : T300_SAT_SPRING;
}

// Creates condition effect fx, endless, at strength 0.
static esp_err_t t300_upload(int fx) {
    uint8_t c[38] = {0, (uint8_t)(fx + 1), 0x64};
    // c[3..10]: coefficients and band edges, 0 for now
    put16(c + 11, t300_sat(fx)); // right / left saturation
    put16(c + 13, t300_sat(fx));
    static const uint8_t fixed[8] = {0xfe, 0xff, 0xfe, 0xff, 0xfe, 0xff, 0xfe, 0xff};
    memcpy(c + 15, fixed, sizeof(fixed));
    put16(c + 23, t300_sat(fx)); // max right / left saturation
    put16(c + 25, t300_sat(fx));
    c[27] = t300_type(fx);
    c[28] = 0x4f; // timing: start marker, duration, offset, end marker
    put16(c + 29, DURATION_INFINITE);
    put16(c + 36, 0xffff);
    return t300_send(c, sizeof(c));
}

static esp_err_t t300_play(int fx) {
    uint8_t c[6] = {0, (uint8_t)(fx + 1), 0x89, 0x41, 0, 0}; // count 0 = endless
    return t300_send(c, sizeof(c));
}

static esp_err_t t300_condition(int fx, int coef, int centre, int band) {
    uint8_t c[21] = {0, (uint8_t)(fx + 1), 0x4c};
    put16(c + 3, coef); // right / left coefficient
    put16(c + 5, coef);
    put16(c + 7, clamp7fff(centre + band)); // right / left band edge
    put16(c + 9, clamp7fff(centre - band));
    put16(c + 11, t300_sat(fx)); // right / left saturation
    put16(c + 13, t300_sat(fx));
    c[15] = 0x06; // as hid-tmff2 sends it, damper or not
    c[16] = 0x45;
    put16(c + 17, DURATION_INFINITE);
    return t300_send(c, sizeof(c));
}

static esp_err_t t300_gain(int gain) {
    uint8_t c[2] = {0x02, (uint8_t)gain};
    return t300_send(c, sizeof(c));
}

static void t300_setup(void) {
    static const uint8_t open[2] = {0x01, 0x05};
    // The base's own centring spring off: ours does that.
    static const uint8_t autocentre_mode[4] = {0x08, 0x04, 0x01, 0x00};
    static const uint8_t autocentre_off[4] = {0x08, 0x03, 0x00, 0x00};
    // Lock to lock: WHEEL_DEG, like Pit House sets it on the MOZA.
    const unsigned range = WHEEL_DEG * 0x3c;
    const uint8_t lock[4] = {0x08, 0x11, (uint8_t)range, (uint8_t)(range >> 8)};
    if (t300_send(open, sizeof(open)) != ESP_OK || t300_send(autocentre_mode, sizeof(autocentre_mode)) != ESP_OK ||
        t300_send(autocentre_off, sizeof(autocentre_off)) != ESP_OK || t300_send(lock, sizeof(lock)) != ESP_OK) {
        ESP_LOGW(TAG, "T300 setup failed");
    }
    for (int i = 0; i < FX_COUNT; i++) {
        s_fx[i] = (effect_t){0};
        if (t300_upload(i) != ESP_OK || t300_play(i) != ESP_OK) {
            ESP_LOGW(TAG, "T300 effect %d setup failed", i);
            continue;
        }
        s_fx[i] = (effect_t){.block = (uint8_t)(i + 1), .last = 0};
    }
}

// ---- either base -------------------------------------------------------------

static void setup(void) {
    if (s_kind == WHEEL_T300) {
        t300_setup();
    } else {
        pid_setup();
    }
    s_gain = -1;
    s_centre_sent = 0;
    s_stop_sent = -1;
    ESP_LOGI(TAG, "%s: spring %d, damper %d, end stop %d", wheel_kind_name(s_kind), s_fx[FX_SPRING].block,
             s_fx[FX_DAMPER].block, s_fx[FX_STOP].block);
}

static esp_err_t set_gain(int gain) {
    return s_kind == WHEEL_T300 ? t300_gain(gain) : pid_gain(gain);
}

static esp_err_t set_condition(int fx, int coef, int centre, int dead_band) {
    if (s_kind == WHEEL_T300) {
        return t300_condition(fx, coef, centre, dead_band);
    }
    return pid_condition(s_fx[fx].block, coef, centre, dead_band);
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
        float stop = s_stop;
        portEXIT_CRITICAL(&s_lock);
        if (!have) {
            continue;
        }
        if (attach) {
            vTaskDelay(pdMS_TO_TICKS(200)); // let the base settle after enumeration
            setup();
        }
        int gain = ui_ffb_get() * 255 / 100;
        if (gain != s_gain && set_gain(gain) == ESP_OK) {
            s_gain = gain;
        }
        centre_f = centre_f < -1.0f ? -1.0f : (centre_f > 1.0f ? 1.0f : centre_f);
        int centre = (int)lroundf(centre_f * 32767.0f);
        // End stop: off (coefficient 0) at full wheel lock.
        int band = stop >= 1.0f ? 32767 : (int)lroundf((stop < 0.0f ? 0.0f : stop) * 32767.0f);
        if (s_fx[FX_STOP].block && band != s_stop_sent &&
            set_condition(FX_STOP, band >= 32767 ? 0 : STOP_COEF, 0, band) == ESP_OK) {
            s_stop_sent = band;
        }
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
                if (set_condition(i, coef, c, 0) == ESP_OK) {
                    s_fx[i].last = coef;
                    if (i == 0) {
                        s_centre_sent = c;
                    }
                }
            }
        }
    }
}

void ffb_attach(hid_host_device_handle_t dev, wheel_kind_t kind) {
    static bool started;
    if (!started) {
        started = true;
        xTaskCreatePinnedToCore(task, "ffb", 4096, NULL, 4, NULL, 0);
    }
    portENTER_CRITICAL(&s_lock);
    s_dev = dev;
    s_kind = kind;
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

void ffb_set_stop(float edge) {
    portENTER_CRITICAL(&s_lock);
    s_stop = edge;
    portEXIT_CRITICAL(&s_lock);
}

void ffb_set(float spring, float damper) {
    portENTER_CRITICAL(&s_lock);
    s_spring = spring;
    s_damper = damper;
    portEXIT_CRITICAL(&s_lock);
}
