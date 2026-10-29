// Shared by the P4 dashboard files: palette, fonts, text ids and small
// LVGL helpers.
#pragma once

#include <math.h>
#include <string.h>

#include "lvgl.h"

// Chinese subsets of Noto Sans SC (Simplified and Traditional), falling back to Montserrat
// for Latin, digits and symbols. Regenerate with fonts/gen_fonts.sh after
// changing any Chinese text in display_p4.c or dash_p4.c.
LV_FONT_DECLARE(cjk_14);
LV_FONT_DECLARE(cjk_16);
LV_FONT_DECLARE(cjk_20);
LV_FONT_DECLARE(cjk_24);
LV_FONT_DECLARE(cjk_32);
LV_FONT_DECLARE(saira_thin_132);
LV_FONT_DECLARE(saira_xl_30);
LV_FONT_DECLARE(saira_l_30);
LV_FONT_DECLARE(saira_l_15);
LV_FONT_DECLARE(barlow_58);
LV_FONT_DECLARE(barlow_64);
LV_FONT_DECLARE(barlow_28);

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

// ---- text ids (strings in display_p4.c, both scripts) -----------------------
enum {
    T_NO_WHEEL, T_ARMED, T_ESTOP, T_SAFE, T_DRIVE, T_THR_PCT, T_LEFT, T_RIGHT, T_STEER_FMT, T_STEER_ZERO,
    T_CONTROL, T_HINT, T_PEDALS, T_GAS, T_BRAKE, T_LINK, T_NO_TX, T_SETUP_BTN, T_SETUP_TITLE, T_DONE,
    T_OUTPUT, T_KIND_SERIAL, T_KIND_PPM, T_PROTO_TITLE, T_RX_NUM, T_FINE, T_REVERSE, T_REV_STEER, T_REV_THR,
    T_BIND, T_BINDING_FMT, T_UNKNOWN_FMT, T_PLUG, T_BUTTON_FMT, T_LIMIT_FMT, T_SUB_ELRS, T_SUB_MULTI_FMT,
    T_SUB_PPM, T_TX_SERIAL, T_TX_PPM, T_RX_FMT, T_DIAL, T_NO_TELEM, T_LINKED, T_CAR_OFF, T_CH_FMT,
    T_HINT_ELRS, T_HINT_SERIAL, T_HINT_PPM, T_LANG, T_POWER, T_SPEED, T_ENGINE_ON, T_ENGINE_OFF, T_PRESS_START,
    T_N_STOP, T_N_PEDALS, T_N_ENGINE, T_STATUS, T_WHEEL, T_NO_LINK, T_DASH_A, T_DASH_B, T_CAP_SPEED, T_CAP_POWER, T_CAP_POWER10, T_TAB_DRIVE, T_TOP_SPEED, T_TOP_HINT, T_FFB, T_FFB_HINT, T_FLIP, T_FLIP_BTN, T_FLIP_HINT, T_WIRE_ONE, T_WIRE_TWO, T_HINT_ELRS2, T_COUNT
};

// The current language's string.
const char *ui_tr(int id);
// Sets a label to a text id and re-sets it when the language changes.
lv_obj_t *ui_track(lv_obj_t *l, int id);

// ---- helpers ---------------------------------------------------------------
static inline lv_color_t hex(uint32_t c) {
    return lv_color_hex(c);
}

static inline void set_text(lv_obj_t *l, const char *t) {
    if (strcmp(lv_label_get_text(l), t) != 0) {
        lv_label_set_text(l, t);
    }
}

static inline lv_obj_t *label(lv_obj_t *parent, const lv_font_t *font, uint32_t color, const char *text) {
    lv_obj_t *l = lv_label_create(parent);
    lv_obj_set_style_text_font(l, font, 0);
    lv_obj_set_style_text_color(l, hex(color), 0);
    lv_label_set_text(l, text);
    return l;
}

// Forward amber -> red, reverse cyan -> blue (theme::throttle_color).
static inline lv_color_t throttle_color(float v) {
    float t = fabsf(v);
    if (t > 1.0f) {
        t = 1.0f;
    }
    lv_opa_t mix = (lv_opa_t)(t * 255.0f);
    return v >= 0 ? lv_color_mix(hex(C_RED), hex(C_AMBER), mix) : lv_color_mix(hex(C_BLUE), hex(C_CYAN), mix);
}
