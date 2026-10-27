// Dashboard for the Waveshare ESP32-P4 7B board: 1024x600 touch panel,
// driven through the board support package's LVGL adapter.
//
// Same palette and gauge language as the PC program (src/gui/theme.rs):
// forward throttle heats amber -> red, reverse cools cyan -> blue, the speed
// tier's ceiling is a thin ring with the unusable span in red.
//
// Touch: speed tier and emergency stop. Arming stays on the wheel's Start
// button only, so a stray touch can never arm the car.

#include "display.h"

#include "sdkconfig.h"

#if CONFIG_IDF_TARGET_ESP32P4

#include <math.h>
#include <stdio.h>
#include <string.h>

#include "bsp/display.h"
#include "bsp/esp-bsp.h"
#include "esp_log.h"
#include "lvgl.h"

static const char *TAG = "display";

// ---- palette (src/gui/theme.rs) ---------------------------------------------
#define C_BG 0x070a0f
#define C_PANEL 0x0d1219
#define C_EDGE 0x1d2633
#define C_TRACK 0x18202c
#define C_TEXT 0xe8eef6
#define C_DIM 0x7c899a
#define C_FAINT 0x424d5c
#define C_CYAN 0x00d4ff
#define C_BLUE 0x4c6cff
#define C_AMBER 0xffb224
#define C_RED 0xff3a34
#define C_GREEN 0x2ee88a

// ---- layout (1024 x 600) -----------------------------------------------------
#define TOP_H 64
#define M 16                     // outer margin and gap
#define DRIVE_W 600              // left panel
#define SIDE_X (M + DRIVE_W + M) // right column
#define SIDE_W (1024 - SIDE_X - M)
#define GAUGE_D 380 // throttle arc
#define LQ_SEGS 12

static lv_obj_t *s_pill, *s_pill_label, *s_hint;
static lv_obj_t *s_wheel_label, *s_button_label;
static lv_obj_t *s_arc, *s_lim_pos, *s_lim_neg, *s_value, *s_limit_label;
static lv_obj_t *s_steer_bar, *s_steer_label;
static lv_obj_t *s_speed_btn[3];
static lv_obj_t *s_gas_bar, *s_gas_label, *s_brake_bar, *s_brake_label;
static lv_obj_t *s_tx_label, *s_rssi_label, *s_lq_label, *s_ch_label;
static lv_obj_t *s_lq_seg[LQ_SEGS];

static lv_color_t hex(uint32_t c) {
    return lv_color_hex(c);
}

static void set_text(lv_obj_t *l, const char *t) {
    if (strcmp(lv_label_get_text(l), t) != 0) {
        lv_label_set_text(l, t);
    }
}

static lv_obj_t *panel(lv_obj_t *parent, int x, int y, int w, int h) {
    lv_obj_t *o = lv_obj_create(parent);
    lv_obj_remove_style_all(o);
    lv_obj_set_pos(o, x, y);
    lv_obj_set_size(o, w, h);
    lv_obj_set_style_bg_color(o, hex(C_PANEL), 0);
    lv_obj_set_style_bg_opa(o, LV_OPA_COVER, 0);
    lv_obj_set_style_border_color(o, hex(C_EDGE), 0);
    lv_obj_set_style_border_width(o, 1, 0);
    lv_obj_set_style_radius(o, 12, 0);
    lv_obj_remove_flag(o, LV_OBJ_FLAG_SCROLLABLE);
    return o;
}

static lv_obj_t *label(lv_obj_t *parent, const lv_font_t *font, uint32_t color, const char *text) {
    lv_obj_t *l = lv_label_create(parent);
    lv_obj_set_style_text_font(l, font, 0);
    lv_obj_set_style_text_color(l, hex(color), 0);
    lv_label_set_text(l, text);
    return l;
}

// Uppercase section title with wide tracking, like the PC panels.
static void section_title(lv_obj_t *parent, const char *text) {
    lv_obj_t *l = label(parent, &lv_font_montserrat_12, C_DIM, text);
    lv_obj_set_style_text_letter_space(l, 3, 0);
    lv_obj_set_pos(l, 18, 14);
}

static lv_obj_t *arc(lv_obj_t *parent, int d, int width, uint32_t track, lv_opa_t track_opa) {
    lv_obj_t *a = lv_arc_create(parent);
    lv_obj_set_size(a, d, d);
    lv_arc_set_bg_angles(a, 135, 45);
    lv_arc_set_range(a, -100, 100);
    lv_arc_set_mode(a, LV_ARC_MODE_SYMMETRICAL);
    lv_arc_set_value(a, 0);
    lv_obj_remove_style(a, NULL, LV_PART_KNOB);
    lv_obj_remove_flag(a, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_set_style_arc_width(a, width, LV_PART_MAIN);
    lv_obj_set_style_arc_width(a, width, LV_PART_INDICATOR);
    lv_obj_set_style_arc_color(a, hex(track), LV_PART_MAIN);
    lv_obj_set_style_arc_opa(a, track_opa, LV_PART_MAIN);
    lv_obj_set_style_arc_rounded(a, false, LV_PART_MAIN);
    lv_obj_set_style_arc_rounded(a, false, LV_PART_INDICATOR);
    return a;
}

static lv_obj_t *hbar(lv_obj_t *parent, int x, int y, int w, int h, int min, uint32_t color) {
    lv_obj_t *b = lv_bar_create(parent);
    lv_obj_set_pos(b, x, y);
    lv_obj_set_size(b, w, h);
    lv_bar_set_range(b, min, 100);
    if (min < 0) {
        lv_bar_set_mode(b, LV_BAR_MODE_SYMMETRICAL);
    }
    lv_obj_set_style_bg_color(b, hex(C_TRACK), LV_PART_MAIN);
    lv_obj_set_style_bg_opa(b, LV_OPA_COVER, LV_PART_MAIN);
    lv_obj_set_style_bg_color(b, hex(color), LV_PART_INDICATOR);
    lv_obj_set_style_radius(b, 3, LV_PART_MAIN);
    lv_obj_set_style_radius(b, 3, LV_PART_INDICATOR);
    return b;
}

// Forward amber -> red, reverse cyan -> blue (theme::throttle_color).
static lv_color_t throttle_color(float v) {
    float t = fabsf(v);
    if (t > 1.0f) {
        t = 1.0f;
    }
    lv_opa_t mix = (lv_opa_t)(t * 255.0f);
    return v >= 0 ? lv_color_mix(hex(C_RED), hex(C_AMBER), mix) : lv_color_mix(hex(C_BLUE), hex(C_CYAN), mix);
}

static uint32_t lq_color(int lq) {
    return lq >= 70 ? C_GREEN : (lq >= 40 ? C_AMBER : C_RED);
}

static float speed_limit(speed_t s) {
    return s == SPEED_HIGH ? 1.0f : (s == SPEED_MID ? 2.0f / 3.0f : 1.0f / 3.0f);
}

// ---- touch -------------------------------------------------------------------

static void on_estop(lv_event_t *e) {
    control_estop();
    ESP_LOGW(TAG, "E-STOP (screen)");
}

static void on_speed(lv_event_t *e) {
    speed_t s = (speed_t)(intptr_t)lv_event_get_user_data(e);
    control_set_speed(s);
    ESP_LOGI(TAG, "speed %d (screen)", (int)s);
}

// ---- build -------------------------------------------------------------------

static void build_top(lv_obj_t *scr) {
    lv_obj_t *title = label(scr, &lv_font_montserrat_24, C_TEXT, "RC CONTROL");
    lv_obj_set_style_text_letter_space(title, 2, 0);
    lv_obj_set_pos(title, M + 8, 10);
    lv_obj_t *sub = label(scr, &lv_font_montserrat_12, C_DIM, "WHEEL  >  ELRS  >  CAR");
    lv_obj_set_style_text_letter_space(sub, 2, 0);
    lv_obj_set_pos(sub, M + 8, 40);

    s_pill = lv_obj_create(scr);
    lv_obj_remove_style_all(s_pill);
    lv_obj_set_size(s_pill, 260, 44);
    lv_obj_align(s_pill, LV_ALIGN_TOP_MID, 0, 10);
    lv_obj_set_style_radius(s_pill, 22, 0);
    lv_obj_set_style_bg_opa(s_pill, LV_OPA_20, 0);
    lv_obj_set_style_border_width(s_pill, 2, 0);
    lv_obj_remove_flag(s_pill, LV_OBJ_FLAG_SCROLLABLE);
    s_pill_label = label(s_pill, &lv_font_montserrat_24, C_TEXT, "NO WHEEL");
    lv_obj_set_style_text_letter_space(s_pill_label, 3, 0);
    lv_obj_center(s_pill_label);

    s_wheel_label = label(scr, &lv_font_montserrat_16, C_DIM, "");
    lv_obj_align(s_wheel_label, LV_ALIGN_TOP_RIGHT, -M - 8, 12);
    s_button_label = label(scr, &lv_font_montserrat_12, C_FAINT, "");
    lv_obj_align(s_button_label, LV_ALIGN_TOP_RIGHT, -M - 8, 40);
}

static void build_drive(lv_obj_t *scr) {
    lv_obj_t *p = panel(scr, M, TOP_H + 8, DRIVE_W, 600 - TOP_H - 8 - M);
    section_title(p, "DRIVE");
    const int cy = 230; // gauge centre in the panel

    // Ticks every 10 %, labels every 50 %.
    lv_obj_t *sc = lv_scale_create(p);
    lv_obj_set_size(sc, GAUGE_D + 40, GAUGE_D + 40);
    lv_obj_align(sc, LV_ALIGN_TOP_MID, 0, cy - (GAUGE_D + 40) / 2);
    lv_scale_set_mode(sc, LV_SCALE_MODE_ROUND_OUTER);
    lv_scale_set_range(sc, -100, 100);
    lv_scale_set_angle_range(sc, 270);
    lv_scale_set_rotation(sc, 135);
    lv_scale_set_total_tick_count(sc, 21);
    lv_scale_set_major_tick_every(sc, 5);
    lv_scale_set_label_show(sc, true);
    lv_obj_set_style_arc_width(sc, 0, LV_PART_MAIN);
    lv_obj_set_style_length(sc, 6, LV_PART_ITEMS);
    lv_obj_set_style_length(sc, 12, LV_PART_INDICATOR);
    lv_obj_set_style_line_color(sc, hex(C_FAINT), LV_PART_ITEMS);
    lv_obj_set_style_line_color(sc, hex(C_DIM), LV_PART_INDICATOR);
    lv_obj_set_style_line_width(sc, 1, LV_PART_ITEMS);
    lv_obj_set_style_line_width(sc, 2, LV_PART_INDICATOR);
    lv_obj_set_style_text_color(sc, hex(C_DIM), LV_PART_INDICATOR);
    lv_obj_set_style_text_font(sc, &lv_font_montserrat_12, LV_PART_INDICATOR);

    // Speed-tier ceiling: thin ring, usable span light, beyond it red.
    s_lim_pos = arc(p, GAUGE_D + 26, 3, C_RED, LV_OPA_50);
    s_lim_neg = arc(p, GAUGE_D + 26, 3, C_RED, LV_OPA_TRANSP);
    for (int i = 0; i < 2; i++) {
        lv_obj_t *a = i ? s_lim_neg : s_lim_pos;
        lv_obj_align(a, LV_ALIGN_TOP_MID, 0, cy - (GAUGE_D + 26) / 2);
        lv_obj_set_style_arc_color(a, hex(C_DIM), LV_PART_INDICATOR);
    }

    s_arc = arc(p, GAUGE_D, 22, C_TRACK, LV_OPA_COVER);
    lv_obj_align(s_arc, LV_ALIGN_TOP_MID, 0, cy - GAUGE_D / 2);

    s_value = label(p, &lv_font_montserrat_48, C_TEXT, "--");
    lv_obj_align(s_value, LV_ALIGN_TOP_MID, 0, cy - 34);
    lv_obj_t *cap = label(p, &lv_font_montserrat_12, C_DIM, "THROTTLE  %");
    lv_obj_set_style_text_letter_space(cap, 3, 0);
    lv_obj_align(cap, LV_ALIGN_TOP_MID, 0, cy + 22);
    s_limit_label = label(p, &lv_font_montserrat_16, C_AMBER, "");
    lv_obj_align(s_limit_label, LV_ALIGN_TOP_MID, 0, cy + 46);

    // Steering strip under the gauge.
    const int sy = 448, sw = 500;
    s_steer_bar = hbar(p, (DRIVE_W - sw) / 2, sy, sw, 14, -100, C_CYAN);
    lv_obj_t *mid = lv_obj_create(p);
    lv_obj_remove_style_all(mid);
    lv_obj_set_size(mid, 2, 24);
    lv_obj_set_pos(mid, DRIVE_W / 2 - 1, sy - 5);
    lv_obj_set_style_bg_color(mid, hex(C_DIM), 0);
    lv_obj_set_style_bg_opa(mid, LV_OPA_COVER, 0);
    lv_obj_t *l = label(p, &lv_font_montserrat_12, C_FAINT, "L");
    lv_obj_set_pos(l, (DRIVE_W - sw) / 2 - 18, sy - 1);
    lv_obj_t *r = label(p, &lv_font_montserrat_12, C_FAINT, "R");
    lv_obj_set_pos(r, (DRIVE_W + sw) / 2 + 8, sy - 1);
    s_steer_label = label(p, &lv_font_montserrat_16, C_DIM, "STEER  0");
    lv_obj_align(s_steer_label, LV_ALIGN_TOP_MID, 0, sy - 30);
}

static lv_obj_t *button(lv_obj_t *parent, int x, int y, int w, int h, uint32_t color, const lv_font_t *font,
                        const char *text) {
    lv_obj_t *b = lv_button_create(parent);
    lv_obj_set_pos(b, x, y);
    lv_obj_set_size(b, w, h);
    lv_obj_set_style_radius(b, 10, 0);
    lv_obj_set_style_shadow_width(b, 0, 0);
    lv_obj_set_style_bg_color(b, hex(color), 0);
    lv_obj_set_style_bg_opa(b, LV_OPA_20, 0);
    lv_obj_set_style_bg_opa(b, LV_OPA_60, LV_STATE_PRESSED);
    lv_obj_set_style_border_color(b, hex(color), 0);
    lv_obj_set_style_border_width(b, 2, 0);
    lv_obj_t *l = label(b, font, C_TEXT, text);
    lv_obj_set_style_text_letter_space(l, 3, 0);
    lv_obj_center(l);
    return b;
}

static void build_control(lv_obj_t *scr) {
    const int y0 = TOP_H + 8, h = 236;
    lv_obj_t *p = panel(scr, SIDE_X, y0, SIDE_W, h);
    section_title(p, "CONTROL");

    static const char *names[3] = {"L", "M", "H"};
    const int bw = (SIDE_W - 36 - 16) / 3;
    for (int i = 0; i < 3; i++) {
        s_speed_btn[i] = button(p, 18 + i * (bw + 8), 40, bw, 56, C_DIM, &lv_font_montserrat_28, names[i]);
        lv_obj_add_event_cb(s_speed_btn[i], on_speed, LV_EVENT_CLICKED, (void *)(intptr_t)i);
    }

    lv_obj_t *stop = button(p, 18, 108, SIDE_W - 36, 72, C_RED, &lv_font_montserrat_32, "E-STOP");
    lv_obj_set_style_bg_opa(stop, LV_OPA_40, 0);
    // Pressed, not clicked: stop on touch-down, without waiting for release.
    lv_obj_add_event_cb(stop, on_estop, LV_EVENT_PRESSED, NULL);

    s_hint = label(p, &lv_font_montserrat_12, C_DIM, "START  arm / disarm     PADDLES  speed     P  stop");
    lv_obj_set_pos(s_hint, 18, 196);
}

static void build_pedals(lv_obj_t *scr) {
    const int y0 = TOP_H + 8 + 236 + M, h = 112;
    lv_obj_t *p = panel(scr, SIDE_X, y0, SIDE_W, h);
    section_title(p, "PEDALS");
    const int bx = 86, bw = SIDE_W - bx - 70;
    for (int i = 0; i < 2; i++) {
        int y = 44 + i * 32;
        lv_obj_t *name = label(p, &lv_font_montserrat_12, C_DIM, i ? "BRAKE" : "GAS");
        lv_obj_set_style_text_letter_space(name, 2, 0);
        lv_obj_set_pos(name, 18, y);
        lv_obj_t *bar = hbar(p, bx, y + 1, bw, 12, 0, i ? C_CYAN : C_AMBER);
        lv_obj_t *val = label(p, &lv_font_montserrat_16, C_TEXT, "0");
        lv_obj_align(val, LV_ALIGN_TOP_RIGHT, -18, y - 3);
        if (i) {
            s_brake_bar = bar, s_brake_label = val;
        } else {
            s_gas_bar = bar, s_gas_label = val;
        }
    }
}

static void build_link(lv_obj_t *scr) {
    const int y0 = TOP_H + 8 + 236 + M + 112 + M;
    const int h = 600 - y0 - M;
    lv_obj_t *p = panel(scr, SIDE_X, y0, SIDE_W, h);
    section_title(p, "LINK");

    s_tx_label = label(p, &lv_font_montserrat_24, C_RED, "NO TX");
    lv_obj_set_style_text_letter_space(s_tx_label, 2, 0);
    lv_obj_set_pos(s_tx_label, 18, 36);
    s_rssi_label = label(p, &lv_font_montserrat_16, C_DIM, "-- dBm");
    lv_obj_align(s_rssi_label, LV_ALIGN_TOP_RIGHT, -18, 42);

    const int sw = (SIDE_W - 36 - 70 - (LQ_SEGS - 1) * 3) / LQ_SEGS;
    for (int i = 0; i < LQ_SEGS; i++) {
        lv_obj_t *s = lv_obj_create(p);
        lv_obj_remove_style_all(s);
        lv_obj_set_size(s, sw, 10);
        lv_obj_set_pos(s, 18 + i * (sw + 3), 82);
        lv_obj_set_style_radius(s, 2, 0);
        lv_obj_set_style_bg_color(s, hex(C_TRACK), 0);
        lv_obj_set_style_bg_opa(s, LV_OPA_COVER, 0);
        s_lq_seg[i] = s;
    }
    s_lq_label = label(p, &lv_font_montserrat_16, C_DIM, "LQ --");
    lv_obj_align(s_lq_label, LV_ALIGN_TOP_RIGHT, -18, 77);

    s_ch_label = label(p, &lv_font_montserrat_12, C_FAINT, "");
    lv_obj_set_pos(s_ch_label, 18, 106);
}

void display_init(void) {
    bsp_display_cfg_t cfg = {
        .lv_adapter_cfg = ESP_LV_ADAPTER_DEFAULT_CONFIG(),
        .rotation = ESP_LV_ADAPTER_ROTATE_0,
        .tear_avoid_mode = ESP_LV_ADAPTER_TEAR_AVOID_MODE_TRIPLE_PARTIAL,
        .touch_flags = {.swap_xy = 0, .mirror_x = 1, .mirror_y = 1},
    };
    if (bsp_display_start_with_config(&cfg) == NULL) {
        ESP_LOGE(TAG, "display start failed");
        return;
    }
    bsp_display_backlight_on();

    bsp_display_lock(-1);
    lv_obj_t *scr = lv_screen_active();
    lv_obj_set_style_bg_color(scr, hex(C_BG), 0);
    lv_obj_set_style_bg_opa(scr, LV_OPA_COVER, 0);
    lv_obj_remove_flag(scr, LV_OBJ_FLAG_SCROLLABLE);
    build_top(scr);
    build_drive(scr);
    build_control(scr);
    build_pedals(scr);
    build_link(scr);
    bsp_display_unlock();
    ESP_LOGI(TAG, "7\" dashboard up");
}

// ---- update ------------------------------------------------------------------

static void show_state(const display_state_t *s) {
    const control_view_t *c = &s->ctl;
    const char *text;
    uint32_t color;
    if (!s->wheel) {
        text = "NO WHEEL", color = C_FAINT;
    } else if (c->armed) {
        text = "ARMED", color = C_GREEN;
    } else if (strcmp(c->disarm_reason, "E-STOP") == 0) {
        text = "E-STOP", color = C_RED;
    } else {
        text = "SAFE", color = C_AMBER;
    }
    set_text(s_pill_label, text);
    lv_obj_set_style_bg_color(s_pill, hex(color), 0);
    lv_obj_set_style_border_color(s_pill, hex(color), 0);
    lv_obj_set_style_text_color(s_pill_label, hex(color), 0);

    char buf[48];
    if (s->vid != 0) {
        const char *name = wheel_name(s->vid, s->pid);
        if (name) {
            snprintf(buf, sizeof(buf), "%s  %.0f Hz", name, (double)s->rate);
        } else {
            snprintf(buf, sizeof(buf), "%04X:%04X  unknown", s->vid, s->pid);
        }
    } else {
        snprintf(buf, sizeof(buf), "plug the wheel into USB-A");
    }
    set_text(s_wheel_label, buf);
    lv_obj_set_style_text_color(s_wheel_label, hex(s->wheel ? C_TEXT : C_DIM), 0);
    if (s->button) {
        snprintf(buf, sizeof(buf), "BUTTON %d", s->button);
    } else {
        buf[0] = '\0';
    }
    set_text(s_button_label, buf);
}

static void show_drive(const display_state_t *s) {
    const control_view_t *c = &s->ctl;
    char buf[32];
    // Throttle actually sent when armed; otherwise the pedal demand, dimmed,
    // so the pedals can still be checked.
    float thr = c->armed ? c->output.throttle : c->throttle_demand;
    int pct = (int)lroundf(thr * 100.0f);
    lv_arc_set_value(s_arc, s->wheel ? pct : 0);
    lv_obj_set_style_arc_color(s_arc, c->armed ? throttle_color(thr) : hex(C_FAINT), LV_PART_INDICATOR);
    if (s->wheel) {
        snprintf(buf, sizeof(buf), "%+d", pct);
        set_text(s_value, pct == 0 ? "0" : buf);
    } else {
        set_text(s_value, "--");
    }
    lv_obj_set_style_text_color(s_value, hex(c->armed ? C_TEXT : C_DIM), 0);

    float lim = speed_limit(c->speed);
    int lp = (int)lroundf(lim * 100.0f);
    lv_arc_set_value(s_lim_pos, lp);
    lv_arc_set_value(s_lim_neg, -lp);
    static const char *tier[3] = {"L", "M", "H"};
    snprintf(buf, sizeof(buf), "SPEED %s   LIMIT %d%%", tier[c->speed], lp);
    set_text(s_limit_label, buf);

    int st = s->wheel ? (int)lroundf(c->steering * 100.0f) : 0;
    lv_bar_set_value(s_steer_bar, st, LV_ANIM_OFF);
    snprintf(buf, sizeof(buf), "STEER  %+d", st);
    set_text(s_steer_label, st == 0 ? "STEER  0" : buf);

    for (int i = 0; i < 3; i++) {
        bool on = (int)c->speed == i;
        lv_obj_set_style_border_color(s_speed_btn[i], hex(on ? C_AMBER : C_EDGE), 0);
        lv_obj_set_style_bg_color(s_speed_btn[i], hex(on ? C_AMBER : C_DIM), 0);
        lv_obj_set_style_bg_opa(s_speed_btn[i], on ? LV_OPA_30 : LV_OPA_10, 0);
    }
}

static void show_pedals(const display_state_t *s) {
    char buf[8];
    int g = s->wheel ? (int)lroundf(s->axes.gas * 100.0f) : 0;
    int b = s->wheel ? (int)lroundf(s->axes.brake * 100.0f) : 0;
    lv_bar_set_value(s_gas_bar, g, LV_ANIM_OFF);
    lv_bar_set_value(s_brake_bar, b, LV_ANIM_OFF);
    snprintf(buf, sizeof(buf), "%d", g);
    set_text(s_gas_label, buf);
    snprintf(buf, sizeof(buf), "%d", b);
    set_text(s_brake_label, buf);
}

static void show_link(const display_state_t *s) {
    const crsf_status_t *r = &s->radio;
    char buf[64];
    if (r->link) {
        set_text(s_tx_label, "LINKED");
        lv_obj_set_style_text_color(s_tx_label, hex(C_GREEN), 0);
        snprintf(buf, sizeof(buf), "%d dBm", r->rssi);
        set_text(s_rssi_label, buf);
        snprintf(buf, sizeof(buf), "LQ %d", r->lq);
        set_text(s_lq_label, buf);
    } else {
        set_text(s_tx_label, r->module ? "TX ONLY" : "NO TX");
        lv_obj_set_style_text_color(s_tx_label, hex(r->module ? C_AMBER : C_RED), 0);
        set_text(s_rssi_label, "-- dBm");
        set_text(s_lq_label, "LQ --");
    }
    int lit = r->link ? (r->lq * LQ_SEGS + 50) / 100 : 0;
    uint32_t col = lq_color(r->lq);
    for (int i = 0; i < LQ_SEGS; i++) {
        lv_obj_set_style_bg_color(s_lq_seg[i], hex(i < lit ? col : C_TRACK), 0);
    }
    // Pulse widths the receiver puts out (988..2012 us around 1500).
    const control_output_t *o = &s->ctl.output;
    snprintf(buf, sizeof(buf), "CH1 STEER %d us     CH2 THROTTLE %d us", (int)lroundf(1500 + o->steering * 512),
             (int)lroundf(1500 + o->throttle * 512));
    set_text(s_ch_label, buf);
}

void display_show(const display_state_t *s) {
    if (s_pill == NULL || !bsp_display_lock(20)) {
        return;
    }
    show_state(s);
    show_drive(s);
    show_pedals(s);
    show_link(s);
    bsp_display_unlock();
}

#endif  // CONFIG_IDF_TARGET_ESP32P4
