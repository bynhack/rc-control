#include "dash_p4.h"

#include "sdkconfig.h"

#if CONFIG_IDF_TARGET_ESP32P4

#include <stdio.h>

#include "esp_log.h"
#include "esp_timer.h"
#include "radio.h"
#include "ui_p4.h"

static const char *TAG = "dash";

#define DASHES 3
#define TOAST_US 1500000

static const char *const GEAR_NAMES[5] = {"R", "N", "1", "2", "3"};

typedef struct {
    lv_obj_t *root;
    void (*show)(const dash_values_t *v);
} dash_t;

static dash_t s_dash[DASHES];
static int s_cur;
static lv_obj_t *s_dot[DASHES], *s_toast;
static int64_t s_toast_at = -1;

static uint32_t gear_color(const dash_values_t *v) {
    if (!v->on) {
        return C_FAINT;
    }
    return v->gear == GEAR_R ? C_AMBER : (v->gear == GEAR_N ? C_TEXT : C_GREEN);
}

static int pct(float v) {
    return (int)lroundf(fabsf(v) * 100.0f);
}

static lv_obj_t *root(lv_obj_t *scr) {
    lv_obj_t *r = lv_obj_create(scr);
    lv_obj_remove_style_all(r);
    lv_obj_set_size(r, 1024, 600);
    // Not clickable, so a swipe anywhere reaches the screen's gesture.
    lv_obj_remove_flag(r, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_remove_flag(r, LV_OBJ_FLAG_SCROLLABLE);
    return r;
}

static lv_obj_t *circle(lv_obj_t *par, int cx, int cy, int d, uint32_t top, uint32_t bottom) {
    lv_obj_t *c = lv_obj_create(par);
    lv_obj_remove_style_all(c);
    lv_obj_set_size(c, d, d);
    lv_obj_set_pos(c, cx - d / 2, cy - d / 2);
    lv_obj_set_style_radius(c, LV_RADIUS_CIRCLE, 0);
    lv_obj_set_style_bg_color(c, hex(top), 0);
    lv_obj_set_style_bg_grad_color(c, hex(bottom), 0);
    lv_obj_set_style_bg_grad_dir(c, LV_GRAD_DIR_VER, 0);
    lv_obj_set_style_bg_opa(c, LV_OPA_COVER, 0);
    lv_obj_remove_flag(c, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_remove_flag(c, LV_OBJ_FLAG_SCROLLABLE);
    return c;
}

// 0..100 over 270 degrees, starting bottom left.
static lv_obj_t *arc0(lv_obj_t *par, int cx, int cy, int d, int width) {
    lv_obj_t *a = lv_arc_create(par);
    lv_obj_set_size(a, d, d);
    lv_obj_set_pos(a, cx - d / 2, cy - d / 2);
    lv_arc_set_bg_angles(a, 135, 45);
    lv_arc_set_range(a, 0, 100);
    lv_arc_set_value(a, 0);
    lv_obj_remove_style(a, NULL, LV_PART_KNOB);
    lv_obj_remove_flag(a, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_set_style_arc_width(a, width, LV_PART_MAIN);
    lv_obj_set_style_arc_width(a, width, LV_PART_INDICATOR);
    lv_obj_set_style_arc_color(a, hex(C_TRACK), LV_PART_MAIN);
    lv_obj_set_style_arc_rounded(a, false, LV_PART_MAIN);
    lv_obj_set_style_arc_rounded(a, true, LV_PART_INDICATOR);
    return a;
}

static lv_obj_t *round_scale(lv_obj_t *par, int cx, int cy, int d, lv_scale_mode_t mode, int ticks, int major) {
    lv_obj_t *sc = lv_scale_create(par);
    lv_obj_set_size(sc, d, d);
    lv_obj_set_pos(sc, cx - d / 2, cy - d / 2);
    lv_scale_set_mode(sc, mode);
    lv_scale_set_range(sc, 0, 100);
    lv_scale_set_angle_range(sc, 270);
    lv_scale_set_rotation(sc, 135);
    lv_scale_set_total_tick_count(sc, ticks);
    lv_scale_set_major_tick_every(sc, major);
    lv_scale_set_label_show(sc, true);
    lv_obj_set_style_arc_width(sc, 0, LV_PART_MAIN);
    lv_obj_remove_flag(sc, LV_OBJ_FLAG_CLICKABLE);
    return sc;
}

static lv_obj_t *centered(lv_obj_t *par, const lv_font_t *font, uint32_t color, int cx, int y, int w) {
    lv_obj_t *l = label(par, font, color, "");
    lv_obj_set_width(l, w);
    lv_obj_set_style_text_align(l, LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_set_pos(l, cx - w / 2, y);
    return l;
}

static void set_number(lv_obj_t *l, int n) {
    char buf[12];
    snprintf(buf, sizeof(buf), "%d", n);
    set_text(l, buf);
}

// ---- 1. sport: glowing rings ------------------------------------------------

typedef struct {
    lv_obj_t *glow, *arc, *red, *value;
} ring_t;

static struct {
    ring_t power, speed;
    lv_obj_t *badge, *gear, *strip[5];
    uint32_t badge_color;
} s_sp;

static ring_t sport_ring(lv_obj_t *r, int cx, int cy, int caption, bool redline) {
    ring_t g = {0};
    const int d = 360;
    circle(r, cx, cy, d - 36, 0x141c28, 0x05080c);
    lv_obj_t *sc = round_scale(r, cx, cy, d + 40, LV_SCALE_MODE_ROUND_OUTER, 21, 2);
    lv_obj_set_style_length(sc, 6, LV_PART_ITEMS);
    lv_obj_set_style_length(sc, 12, LV_PART_INDICATOR);
    lv_obj_set_style_line_color(sc, hex(C_FAINT), LV_PART_ITEMS);
    lv_obj_set_style_line_color(sc, hex(C_DIM), LV_PART_INDICATOR);
    lv_obj_set_style_line_width(sc, 2, LV_PART_INDICATOR);
    lv_obj_set_style_text_color(sc, hex(C_DIM), LV_PART_INDICATOR);
    lv_obj_set_style_text_font(sc, &lv_font_montserrat_14, LV_PART_INDICATOR);
    if (redline) {
        g.red = arc0(r, cx, cy, d + 16, 5);
        lv_obj_set_style_arc_color(g.red, hex(C_RED), LV_PART_MAIN);
        lv_obj_set_style_arc_opa(g.red, LV_OPA_80, LV_PART_MAIN);
        lv_obj_remove_style(g.red, NULL, LV_PART_INDICATOR);
        lv_obj_set_style_arc_opa(g.red, LV_OPA_TRANSP, LV_PART_INDICATOR);
    }
    // A wide faint arc under the main one reads as a glow.
    g.glow = arc0(r, cx, cy, d, 34);
    lv_obj_set_style_arc_opa(g.glow, LV_OPA_TRANSP, LV_PART_MAIN);
    lv_obj_set_style_arc_opa(g.glow, LV_OPA_20, LV_PART_INDICATOR);
    g.arc = arc0(r, cx, cy, d, 12);
    lv_obj_set_style_arc_opa(g.arc, LV_OPA_TRANSP, LV_PART_MAIN);
    g.value = centered(r, &lv_font_montserrat_48, C_TEXT, cx, cy - 34, 160);
    ui_track(centered(r, &cjk_20, C_DIM, cx, cy + 30, 220), caption);
    return g;
}

static void sport_ring_show(const ring_t *g, float v, lv_color_t color, bool on) {
    int p = on ? pct(v) : 0;
    lv_arc_set_value(g->arc, p);
    lv_arc_set_value(g->glow, p);
    lv_obj_set_style_arc_color(g->arc, color, LV_PART_INDICATOR);
    lv_obj_set_style_arc_color(g->glow, color, LV_PART_INDICATOR);
    set_number(g->value, p);
    lv_obj_set_style_text_color(g->value, hex(on ? C_TEXT : C_FAINT), 0);
}

static void sport_show(const dash_values_t *v) {
    sport_ring_show(&s_sp.power, v->power, throttle_color(v->throttle), v->on);
    sport_ring_show(&s_sp.speed, v->speed, hex(v->speed < 0 ? C_BLUE : C_CYAN), v->on);
    if (!v->on || v->cap <= 0.0f || v->cap >= 0.999f) {
        lv_obj_add_flag(s_sp.power.red, LV_OBJ_FLAG_HIDDEN);
    } else {
        lv_obj_remove_flag(s_sp.power.red, LV_OBJ_FLAG_HIDDEN);
        lv_arc_set_bg_angles(s_sp.power.red, (135 + (int)lroundf(270.0f * v->cap)) % 360, 45);
    }
    uint32_t gc = gear_color(v);
    int gi = (int)v->gear - GEAR_R;
    set_text(s_sp.gear, GEAR_NAMES[gi]);
    lv_obj_set_style_text_color(s_sp.gear, hex(gc), 0);
    if (gc != s_sp.badge_color) { // the shadow is costly to redraw
        s_sp.badge_color = gc;
        lv_obj_set_style_border_color(s_sp.badge, hex(gc), 0);
        lv_obj_set_style_shadow_color(s_sp.badge, hex(gc), 0);
        lv_obj_set_style_shadow_opa(s_sp.badge, v->on ? LV_OPA_50 : LV_OPA_TRANSP, 0);
    }
    for (int i = 0; i < 5; i++) {
        lv_obj_set_style_text_color(s_sp.strip[i], hex(i == gi && v->on ? gc : C_FAINT), 0);
    }
}

static void sport_build(lv_obj_t *r) {
    s_sp.power = sport_ring(r, 216, 290, T_POWER, true);
    s_sp.speed = sport_ring(r, 808, 290, T_SPEED, false);
    lv_obj_t *b = lv_obj_create(r);
    lv_obj_remove_style_all(b);
    lv_obj_set_size(b, 176, 216);
    lv_obj_set_pos(b, 512 - 88, 150);
    lv_obj_set_style_radius(b, 28, 0);
    lv_obj_set_style_bg_color(b, hex(0x121a25), 0);
    lv_obj_set_style_bg_grad_color(b, hex(0x070a0f), 0);
    lv_obj_set_style_bg_grad_dir(b, LV_GRAD_DIR_VER, 0);
    lv_obj_set_style_bg_opa(b, LV_OPA_COVER, 0);
    lv_obj_set_style_border_width(b, 2, 0);
    lv_obj_set_style_shadow_width(b, 36, 0);
    lv_obj_remove_flag(b, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_remove_flag(b, LV_OBJ_FLAG_SCROLLABLE);
    s_sp.badge = b;
    s_sp.badge_color = 0xffffffff;
    s_sp.gear = label(b, &gear_160, C_TEXT, "N");
    lv_obj_center(s_sp.gear);
    for (int i = 0; i < 5; i++) {
        s_sp.strip[i] = label(r, &lv_font_montserrat_24, C_FAINT, GEAR_NAMES[i]);
        lv_obj_set_pos(s_sp.strip[i], 512 - 92 + i * 40, 388);
    }
}

// ---- 2. classic: silver bezels, needles ---------------------------------------

typedef struct {
    lv_obj_t *scale, *needle, *value;
    lv_scale_section_t *red;
} dial_t;

static struct {
    dial_t power, speed;
    lv_obj_t *gear;
} s_cl;

static lv_style_t s_red_major, s_red_minor;

static dial_t classic_dial(lv_obj_t *r, int cx, int cy, int caption, bool redline) {
    dial_t g = {0};
    circle(r, cx, cy, 392, 0xd5dbe2, 0x464c54); // bezel
    circle(r, cx, cy, 372, 0x1b1d21, 0x060607); // face
    lv_obj_t *sc = round_scale(r, cx, cy, 340, LV_SCALE_MODE_ROUND_INNER, 51, 5);
    lv_obj_set_style_length(sc, 9, LV_PART_ITEMS);
    lv_obj_set_style_length(sc, 20, LV_PART_INDICATOR);
    lv_obj_set_style_line_color(sc, hex(0x9aa3ad), LV_PART_ITEMS);
    lv_obj_set_style_line_color(sc, hex(0xf4f6f8), LV_PART_INDICATOR);
    lv_obj_set_style_line_width(sc, 2, LV_PART_ITEMS);
    lv_obj_set_style_line_width(sc, 4, LV_PART_INDICATOR);
    lv_obj_set_style_text_color(sc, hex(0xf4f6f8), LV_PART_INDICATOR);
    lv_obj_set_style_text_font(sc, &lv_font_montserrat_20, LV_PART_INDICATOR);
    lv_obj_set_style_pad_radial(sc, 8, LV_PART_INDICATOR);
    if (redline) {
        g.red = lv_scale_add_section(sc);
        lv_scale_set_section_style_indicator(sc, g.red, &s_red_major);
        lv_scale_set_section_style_items(sc, g.red, &s_red_minor);
        lv_scale_set_section_range(sc, g.red, 101, 101);
    }
    g.scale = sc;
    ui_track(centered(r, &cjk_16, 0x9aa3ad, cx, cy + 52, 200), caption);
    lv_obj_t *box = lv_obj_create(r);
    lv_obj_remove_style_all(box);
    lv_obj_set_size(box, 96, 40);
    lv_obj_set_pos(box, cx - 48, cy + 80);
    lv_obj_set_style_radius(box, 6, 0);
    lv_obj_set_style_bg_color(box, hex(0x0c1f17), 0);
    lv_obj_set_style_bg_opa(box, LV_OPA_COVER, 0);
    lv_obj_set_style_border_color(box, hex(0x2a3a33), 0);
    lv_obj_set_style_border_width(box, 1, 0);
    lv_obj_remove_flag(box, LV_OBJ_FLAG_CLICKABLE);
    g.value = label(box, &lv_font_montserrat_28, 0x7dffb2, "0");
    lv_obj_center(g.value);

    g.needle = lv_line_create(sc);
    lv_obj_set_style_line_width(g.needle, 6, 0);
    lv_obj_set_style_line_color(g.needle, hex(0xff3a34), 0);
    lv_obj_set_style_line_rounded(g.needle, true, 0);
    lv_scale_set_line_needle_value(sc, g.needle, 150, 0);
    lv_obj_t *hub = circle(r, cx, cy, 34, 0x3a3f46, 0x15171a);
    lv_obj_set_style_border_color(hub, hex(0x8a929b), 0);
    lv_obj_set_style_border_width(hub, 3, 0);
    return g;
}

static void classic_dial_show(const dial_t *g, float v, bool on) {
    int p = on ? pct(v) : 0;
    lv_scale_set_line_needle_value(g->scale, g->needle, 150, p);
    set_number(g->value, p);
}

static void classic_show(const dash_values_t *v) {
    classic_dial_show(&s_cl.power, v->power, v->on);
    classic_dial_show(&s_cl.speed, v->speed, v->on);
    int from = (!v->on || v->cap <= 0.0f || v->cap >= 0.999f) ? 101 : (int)lroundf(v->cap * 100.0f);
    lv_scale_set_section_range(s_cl.power.scale, s_cl.power.red, from, 100);
    set_text(s_cl.gear, GEAR_NAMES[(int)v->gear - GEAR_R]);
    lv_obj_set_style_text_color(s_cl.gear, hex(v->on ? (v->gear == GEAR_R ? 0xffb224 : 0x7dffb2) : 0x1f4a35), 0);
}

static void classic_build(lv_obj_t *r) {
    lv_style_init(&s_red_major);
    lv_style_set_line_color(&s_red_major, hex(C_RED));
    lv_style_set_line_width(&s_red_major, 4);
    lv_style_set_text_color(&s_red_major, hex(C_RED));
    lv_style_init(&s_red_minor);
    lv_style_set_line_color(&s_red_minor, hex(C_RED));
    lv_style_set_line_width(&s_red_minor, 2);
    s_cl.power = classic_dial(r, 210, 300, T_POWER, true);
    s_cl.speed = classic_dial(r, 814, 300, T_SPEED, false);
    lv_obj_t *lcd = lv_obj_create(r);
    lv_obj_remove_style_all(lcd);
    lv_obj_set_size(lcd, 180, 230);
    lv_obj_set_pos(lcd, 512 - 90, 170);
    lv_obj_set_style_radius(lcd, 16, 0);
    lv_obj_set_style_bg_color(lcd, hex(0x0f2a1f), 0);
    lv_obj_set_style_bg_grad_color(lcd, hex(0x050f0a), 0);
    lv_obj_set_style_bg_grad_dir(lcd, LV_GRAD_DIR_VER, 0);
    lv_obj_set_style_bg_opa(lcd, LV_OPA_COVER, 0);
    lv_obj_set_style_border_color(lcd, hex(0x8a929b), 0);
    lv_obj_set_style_border_width(lcd, 3, 0);
    lv_obj_remove_flag(lcd, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_remove_flag(lcd, LV_OBJ_FLAG_SCROLLABLE);
    s_cl.gear = label(lcd, &gear_160, 0x7dffb2, "N");
    lv_obj_center(s_cl.gear);
}

// ---- 3. race: shift lights, big digits ---------------------------------------

#define SHIFT_LEDS 16

static struct {
    lv_obj_t *led[SHIFT_LEDS], *speed, *power, *gear, *gear_box, *bar;
} s_rc;

static uint32_t led_color(int i) {
    return i < 8 ? C_GREEN : (i < 13 ? C_AMBER : C_RED);
}

static void race_show(const dash_values_t *v) {
    int lit = v->on ? (int)lroundf(v->power * SHIFT_LEDS) : 0;
    int cap = v->cap > 0.0f ? (int)lroundf(v->cap * SHIFT_LEDS) : 0;
    for (int i = 0; i < SHIFT_LEDS; i++) {
        bool on = i < lit;
        lv_obj_set_style_bg_color(s_rc.led[i], hex(on ? led_color(i) : C_TRACK), 0);
        // Beyond the gear's cap: outlined red, can't light.
        lv_obj_set_style_border_color(s_rc.led[i], hex(v->on && i >= cap ? 0x5a1a18 : C_EDGE), 0);
    }
    int sp = v->on ? pct(v->speed) : 0;
    set_number(s_rc.speed, sp);
    lv_obj_set_style_text_color(s_rc.speed, hex(!v->on ? C_FAINT : (v->speed < 0 ? C_CYAN : C_TEXT)), 0);
    set_number(s_rc.power, v->on ? pct(v->power) : 0);
    lv_bar_set_value(s_rc.bar, sp, LV_ANIM_OFF);
    uint32_t gc = gear_color(v);
    set_text(s_rc.gear, GEAR_NAMES[(int)v->gear - GEAR_R]);
    lv_obj_set_style_text_color(s_rc.gear, hex(gc), 0);
    lv_obj_set_style_border_color(s_rc.gear_box, hex(v->on ? gc : C_EDGE), 0);
}

static void race_build(lv_obj_t *r) {
    const int w = 54, gap = 6, x0 = (1024 - (SHIFT_LEDS * w + (SHIFT_LEDS - 1) * gap)) / 2;
    for (int i = 0; i < SHIFT_LEDS; i++) {
        lv_obj_t *l = lv_obj_create(r);
        lv_obj_remove_style_all(l);
        lv_obj_set_size(l, w, 26);
        lv_obj_set_pos(l, x0 + i * (w + gap), 76);
        lv_obj_set_style_radius(l, 6, 0);
        lv_obj_set_style_bg_opa(l, LV_OPA_COVER, 0);
        lv_obj_set_style_border_width(l, 2, 0);
        lv_obj_remove_flag(l, LV_OBJ_FLAG_CLICKABLE);
        s_rc.led[i] = l;
    }
    lv_obj_t *gb = lv_obj_create(r);
    lv_obj_remove_style_all(gb);
    lv_obj_set_size(gb, 200, 236);
    lv_obj_set_pos(gb, 56, 140);
    lv_obj_set_style_radius(gb, 20, 0);
    lv_obj_set_style_bg_color(gb, hex(C_PANEL), 0);
    lv_obj_set_style_bg_opa(gb, LV_OPA_COVER, 0);
    lv_obj_set_style_border_width(gb, 3, 0);
    lv_obj_remove_flag(gb, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_remove_flag(gb, LV_OBJ_FLAG_SCROLLABLE);
    s_rc.gear_box = gb;
    s_rc.gear = label(gb, &gear_160, C_TEXT, "N");
    lv_obj_center(s_rc.gear);

    s_rc.speed = centered(r, &big_120, C_TEXT, 512, 150, 420);
    ui_track(centered(r, &cjk_20, C_DIM, 512, 300, 300), T_SPEED);
    s_rc.power = centered(r, &lv_font_montserrat_48, C_TEXT, 868, 200, 200);
    ui_track(centered(r, &cjk_20, C_DIM, 868, 262, 200), T_POWER);

    s_rc.bar = lv_bar_create(r);
    lv_obj_set_size(s_rc.bar, 912, 22);
    lv_obj_set_pos(s_rc.bar, 56, 420);
    lv_bar_set_range(s_rc.bar, 0, 100);
    lv_obj_set_style_radius(s_rc.bar, 11, LV_PART_MAIN);
    lv_obj_set_style_radius(s_rc.bar, 11, LV_PART_INDICATOR);
    lv_obj_set_style_bg_color(s_rc.bar, hex(C_TRACK), LV_PART_MAIN);
    lv_obj_set_style_bg_opa(s_rc.bar, LV_OPA_COVER, LV_PART_MAIN);
    lv_obj_set_style_bg_color(s_rc.bar, hex(C_BLUE), LV_PART_INDICATOR);
    lv_obj_set_style_bg_grad_color(s_rc.bar, hex(C_CYAN), LV_PART_INDICATOR);
    lv_obj_set_style_bg_grad_dir(s_rc.bar, LV_GRAD_DIR_HOR, LV_PART_INDICATOR);
    lv_obj_remove_flag(s_rc.bar, LV_OBJ_FLAG_CLICKABLE);
}

// ---- switching ---------------------------------------------------------------

static const int DASH_NAMES[DASHES] = {T_DASH_SPORT, T_DASH_CLASSIC, T_DASH_RACE};

static void select_dash(int i, bool toast) {
    s_cur = (i + DASHES) % DASHES;
    for (int n = 0; n < DASHES; n++) {
        if (n == s_cur) {
            lv_obj_remove_flag(s_dash[n].root, LV_OBJ_FLAG_HIDDEN);
        } else {
            lv_obj_add_flag(s_dash[n].root, LV_OBJ_FLAG_HIDDEN);
        }
        lv_obj_set_style_bg_color(s_dot[n], hex(n == s_cur ? C_TEXT : C_FAINT), 0);
    }
    if (toast) {
        set_text(s_toast, ui_tr(DASH_NAMES[s_cur]));
        lv_obj_remove_flag(s_toast, LV_OBJ_FLAG_HIDDEN);
        s_toast_at = esp_timer_get_time();
    }
}

static void on_gesture(lv_event_t *e) {
    lv_dir_t dir = lv_indev_get_gesture_dir(lv_indev_active());
    if (dir == LV_DIR_LEFT || dir == LV_DIR_RIGHT) {
        select_dash(s_cur + (dir == LV_DIR_LEFT ? 1 : -1), true);
        ui_dash_set(s_cur);
        ESP_LOGI(TAG, "dashboard %d", s_cur);
    }
}

void dash_build(lv_obj_t *scr) {
    void (*builds[DASHES])(lv_obj_t *) = {sport_build, classic_build, race_build};
    void (*shows[DASHES])(const dash_values_t *) = {sport_show, classic_show, race_show};
    for (int i = 0; i < DASHES; i++) {
        s_dash[i].root = root(scr);
        s_dash[i].show = shows[i];
        builds[i](s_dash[i].root);
    }
    for (int i = 0; i < DASHES; i++) {
        lv_obj_t *d = lv_obj_create(scr);
        lv_obj_remove_style_all(d);
        lv_obj_set_size(d, 10, 10);
        lv_obj_set_pos(d, 512 - DASHES * 10 + i * 20, 584);
        lv_obj_set_style_radius(d, LV_RADIUS_CIRCLE, 0);
        lv_obj_set_style_bg_opa(d, LV_OPA_COVER, 0);
        lv_obj_remove_flag(d, LV_OBJ_FLAG_CLICKABLE);
        s_dot[i] = d;
    }
    s_toast = centered(scr, &cjk_32, C_TEXT, 512, 14, 300);
    lv_obj_add_flag(s_toast, LV_OBJ_FLAG_HIDDEN);
    lv_obj_add_event_cb(scr, on_gesture, LV_EVENT_GESTURE, NULL);
    select_dash(ui_dash_get(), false);
}

void dash_show(const dash_values_t *v) {
    s_dash[s_cur].show(v);
    if (s_toast_at >= 0 && esp_timer_get_time() - s_toast_at > TOAST_US) {
        lv_obj_add_flag(s_toast, LV_OBJ_FLAG_HIDDEN);
        s_toast_at = -1;
    }
}

#endif  // CONFIG_IDF_TARGET_ESP32P4
