#include "dash_p4.h"

#include "sdkconfig.h"

#if CONFIG_IDF_TARGET_ESP32P4

#include <stdio.h>

#include "esp_log.h"
#include "esp_timer.h"
#include "radio.h"
#include "ui_p4.h"

static const char *TAG = "dash";

#define DASHES 2
#define TOAST_US 1500000
#define PI_F 3.14159265f

static const char *const GEAR_NAMES[5] = {"R", "N", "1", "2", "3"};

// ---- images (design/render/build_assets.py) ---------------------------------

#define EMBED(name) \
    extern const uint8_t _binary_##name##_bin_start[]; \
    extern const uint8_t _binary_##name##_bin_end[]
EMBED(a_bg);
EMBED(a_arc);
EMBED(a_tip);
EMBED(b_bg);
EMBED(b_needle);
EMBED(b_wheel);

static lv_image_dsc_t image(const uint8_t *start, const uint8_t *end, int w, int h, lv_color_format_t cf) {
    int bpp = cf == LV_COLOR_FORMAT_RGB565 ? 2 : 4;
    return (lv_image_dsc_t){
        .header = {.magic = LV_IMAGE_HEADER_MAGIC, .cf = cf, .w = w, .h = h, .stride = w * bpp},
        .data_size = (uint32_t)(end - start),
        .data = start,
    };
}

#define IMAGE(name, w, h, cf) image(_binary_##name##_bin_start, _binary_##name##_bin_end, w, h, cf)

static lv_image_dsc_t s_a_bg, s_a_arc, s_a_tip, s_b_bg, s_b_needle, s_b_wheel;

// ---- helpers -----------------------------------------------------------------

typedef struct {
    lv_obj_t *root;
    void (*show)(const dash_values_t *v);
    int notice_y;
} dash_t;

static dash_t s_dash[DASHES];
static int s_cur;
static lv_obj_t *s_dot[DASHES], *s_toast;
static int64_t s_toast_at = -1;

static int pct(float v) {
    return (int)lroundf(fabsf(v) * 100.0f);
}

// Concept angles: degrees clockwise from 12 o'clock.
static void polar(int cx, int cy, float r, float deg, float *x, float *y) {
    float a = (deg - 90.0f) * PI_F / 180.0f;
    *x = cx + r * cosf(a);
    *y = cy + r * sinf(a);
}

static lv_obj_t *root(lv_obj_t *scr, const lv_image_dsc_t *bg) {
    lv_obj_t *r = lv_image_create(scr);
    lv_image_set_src(r, bg);
    lv_obj_set_pos(r, 0, 0);
    // Not clickable, so a swipe anywhere reaches the screen's gesture.
    lv_obj_remove_flag(r, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_remove_flag(r, LV_OBJ_FLAG_SCROLLABLE);
    return r;
}

static lv_obj_t *box(lv_obj_t *par, int x, int y, int w, int h, int radius, uint32_t color) {
    lv_obj_t *o = lv_obj_create(par);
    lv_obj_remove_style_all(o);
    lv_obj_set_pos(o, x, y);
    lv_obj_set_size(o, w, h);
    lv_obj_set_style_radius(o, radius, 0);
    lv_obj_set_style_bg_color(o, hex(color), 0);
    lv_obj_set_style_bg_opa(o, LV_OPA_COVER, 0);
    lv_obj_remove_flag(o, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_remove_flag(o, LV_OBJ_FLAG_SCROLLABLE);
    return o;
}

// A label whose text baseline sits at y, like SVG text: centred on cx, or
// left-aligned from x when align is LV_TEXT_ALIGN_LEFT.
static lv_obj_t *text_at(lv_obj_t *par, const lv_font_t *font, uint32_t color, int x, int baseline, int w,
                         lv_text_align_t align) {
    lv_obj_t *l = label(par, font, color, "");
    lv_obj_set_width(l, w);
    lv_obj_set_style_text_align(l, align, 0);
    int top = baseline - (font->line_height - font->base_line);
    lv_obj_set_pos(l, align == LV_TEXT_ALIGN_CENTER ? x - w / 2 : x, top);
    return l;
}

static void set_number(lv_obj_t *l, int n) {
    char buf[12];
    snprintf(buf, sizeof(buf), "%d", n);
    set_text(l, buf);
}

static lv_obj_t *line(lv_obj_t *par, int width, uint32_t color, lv_opa_t opa) {
    lv_obj_t *l = lv_line_create(par);
    lv_obj_set_pos(l, 0, 0);
    lv_obj_set_style_line_width(l, width, 0);
    lv_obj_set_style_line_color(l, hex(color), 0);
    lv_obj_set_style_line_opa(l, opa, 0);
    lv_obj_set_style_line_rounded(l, true, 0);
    lv_obj_remove_flag(l, LV_OBJ_FLAG_CLICKABLE);
    return l;
}

static void visible(lv_obj_t *o, bool on) {
    if (on) {
        lv_obj_remove_flag(o, LV_OBJ_FLAG_HIDDEN);
    } else {
        lv_obj_add_flag(o, LV_OBJ_FLAG_HIDDEN);
    }
}

// ---- A: obsidian -------------------------------------------------------------
// One speed dial, a slim power bar, a gear column and a top-down car whose
// front wheels and predicted path follow the steering.

#define A_CX 512
#define A_CY 318
#define A_R 222
#define A_GX 920
#define A_GY0 170
#define A_GSTEP 64
#define A_CAR_Y 532
#define A_PATH_PTS 9
#define A_PATH_SEGS 4

static struct {
    lv_obj_t *arc, *tip, *speed, *bar, *cap, *power, *pill, *gear[5], *wheel[2];
    lv_obj_t *path[2][A_PATH_SEGS];
    lv_point_precise_t pts[2][A_PATH_PTS];
    int gi;
    bool rev;
} s_a = {.gi = -1};

static void a_build(lv_obj_t *r) {
    // The lit arc: the pre-rendered gradient and glow as the indicator's
    // texture, revealed up to the speed. The track is in the background.
    lv_obj_t *a = lv_arc_create(r);
    lv_obj_set_size(a, 476, 476);
    lv_obj_set_pos(a, A_CX - 238, A_CY - 238);
    lv_arc_set_bg_angles(a, 135, 45);
    lv_arc_set_range(a, 0, 1000);
    lv_arc_set_value(a, 0);
    lv_obj_remove_style(a, NULL, LV_PART_KNOB);
    lv_obj_remove_flag(a, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_set_style_arc_opa(a, LV_OPA_TRANSP, LV_PART_MAIN);
    lv_obj_set_style_arc_width(a, 32, LV_PART_INDICATOR);
    lv_obj_set_style_arc_rounded(a, false, LV_PART_INDICATOR);
    lv_obj_set_style_arc_image_src(a, &s_a_arc, LV_PART_INDICATOR);
    s_a.arc = a;
    s_a.tip = lv_image_create(r);
    lv_image_set_src(s_a.tip, &s_a_tip);

    s_a.speed = text_at(r, &saira_thin_132, 0xf2f6fa, A_CX, A_CY + 38, 420, LV_TEXT_ALIGN_CENTER);
    lv_obj_t *cap = ui_track(text_at(r, &cjk_16, 0x56697d, A_CX, A_CY + 78, 200, LV_TEXT_ALIGN_CENTER), T_CAP_SPEED);
    lv_obj_set_style_text_letter_space(cap, 6, 0);

    lv_obj_t *pc = ui_track(text_at(r, &cjk_14, 0x56697d, 92, 140, 80, LV_TEXT_ALIGN_LEFT), T_CAP_POWER);
    lv_obj_set_style_text_letter_space(pc, 4, 0);
    s_a.bar = lv_bar_create(r);
    lv_obj_set_pos(s_a.bar, 96, 160);
    lv_obj_set_size(s_a.bar, 8, 300);
    lv_bar_set_range(s_a.bar, 0, 100);
    lv_obj_set_style_bg_opa(s_a.bar, LV_OPA_TRANSP, LV_PART_MAIN);
    lv_obj_set_style_radius(s_a.bar, 4, LV_PART_INDICATOR);
    lv_obj_set_style_bg_color(s_a.bar, hex(0xff3d5a), LV_PART_INDICATOR);
    lv_obj_set_style_bg_grad_color(s_a.bar, hex(0xff9a3c), LV_PART_INDICATOR);
    lv_obj_set_style_bg_grad_dir(s_a.bar, LV_GRAD_DIR_VER, LV_PART_INDICATOR);
    lv_obj_set_style_shadow_width(s_a.bar, 14, LV_PART_INDICATOR);
    lv_obj_set_style_shadow_color(s_a.bar, hex(0xff5a4a), LV_PART_INDICATOR);
    lv_obj_set_style_shadow_opa(s_a.bar, LV_OPA_50, LV_PART_INDICATOR);
    lv_obj_remove_flag(s_a.bar, LV_OBJ_FLAG_CLICKABLE);
    s_a.cap = box(r, 88, 0, 24, 2, 0, 0xff3d5a);
    s_a.power = text_at(r, &saira_xl_30, 0xe8edf2, 100, 500, 100, LV_TEXT_ALIGN_CENTER);

    s_a.pill = box(r, A_GX - 34, A_GY0 - 26, 68, 52, 26, 0x0f2233);
    lv_obj_set_style_border_width(s_a.pill, 2, 0);
    lv_obj_set_style_shadow_width(s_a.pill, 18, 0);
    lv_obj_set_style_shadow_opa(s_a.pill, LV_OPA_50, 0);
    for (int i = 0; i < 5; i++) {
        s_a.gear[i] = text_at(r, &saira_l_30, 0x2f3c4a, A_GX, A_GY0 + i * A_GSTEP + 12, 60, LV_TEXT_ALIGN_CENTER);
        lv_label_set_text(s_a.gear[i], GEAR_NAMES[i]);
    }

    // The path: each side a few segments fading out ahead of the car.
    static const lv_opa_t fade[A_PATH_SEGS] = {230, 160, 100, 45};
    for (int side = 0; side < 2; side++) {
        for (int k = 0; k < A_PATH_SEGS; k++) {
            s_a.path[side][k] = line(r, 3, 0x29d3ff, fade[k]);
        }
    }
    for (int side = 0; side < 2; side++) {
        lv_obj_t *w = box(r, A_CX + (side ? 21 : -21) - 3, A_CAR_Y - 18 - 8, 7, 16, 3, 0x9fb4c8);
        lv_obj_set_style_transform_pivot_x(w, 3, 0);
        lv_obj_set_style_transform_pivot_y(w, 8, 0);
        s_a.wheel[side] = w;
    }
}

static void a_show(const dash_values_t *v) {
    int sp = v->on ? pct(v->speed) : 0;
    float sf = v->on ? fminf(fabsf(v->speed), 1.0f) : 0.0f;
    lv_arc_set_value(s_a.arc, (int)lroundf(sf * 1000.0f));
    visible(s_a.arc, sf > 0.003f);
    float tx, ty;
    polar(A_CX, A_CY, A_R, -135.0f + 270.0f * sf, &tx, &ty);
    lv_obj_set_pos(s_a.tip, (int)lroundf(tx) - 24, (int)lroundf(ty) - 24);
    visible(s_a.tip, v->on);
    set_number(s_a.speed, sp);
    lv_obj_set_style_text_color(s_a.speed, hex(!v->on ? 0x2a3644 : (v->speed < 0 ? 0x7fdcff : 0xf2f6fa)), 0);

    int pw = v->on ? pct(v->power) : 0;
    lv_bar_set_value(s_a.bar, pw, LV_ANIM_OFF);
    set_number(s_a.power, pw);
    bool cap_on = v->on && v->cap > 0.0f && v->cap < 0.999f;
    visible(s_a.cap, cap_on);
    lv_obj_set_y(s_a.cap, 460 - (int)lroundf(300.0f * v->cap) - 1);

    int gi = (int)v->gear - GEAR_R;
    bool rev = v->gear == GEAR_R;
    if (gi != s_a.gi || rev != s_a.rev) { // the pill's glow is costly to redraw
        s_a.gi = gi;
        s_a.rev = rev;
        lv_obj_set_y(s_a.pill, A_GY0 + gi * A_GSTEP - 26);
        uint32_t c = rev ? 0xffb23c : 0x29d3ff;
        lv_obj_set_style_border_color(s_a.pill, hex(c), 0);
        lv_obj_set_style_shadow_color(s_a.pill, hex(c), 0);
        for (int i = 0; i < 5; i++) {
            lv_obj_set_style_text_color(s_a.gear[i], hex(i == gi ? (rev ? 0xffd08a : 0xeafcff) : 0x2f3c4a), 0);
        }
    }

    float st = v->steer;
    for (int side = 0; side < 2; side++) {
        lv_obj_set_style_transform_rotation(s_a.wheel[side], (int)lroundf(st * 320.0f), 0);
        lv_obj_set_style_opa(s_a.wheel[side], v->on ? LV_OPA_COVER : LV_OPA_40, 0);
        // Quadratic curve from the car's front corner, bending with steering.
        float x0 = A_CX + (side ? 17 : -17), y0 = A_CAR_Y - 32, len = 74;
        float ex = x0 + st * 58.0f, ey = y0 - len + fabsf(st) * 14.0f, qy = y0 - len * 0.6f;
        for (int i = 0; i < A_PATH_PTS; i++) {
            float t = (float)i / (A_PATH_PTS - 1), u = 1.0f - t;
            s_a.pts[side][i].x = u * u * x0 + 2 * u * t * x0 + t * t * ex;
            s_a.pts[side][i].y = u * u * y0 + 2 * u * t * qy + t * t * ey;
        }
        for (int k = 0; k < A_PATH_SEGS; k++) {
            int n = (A_PATH_PTS - 1) / A_PATH_SEGS;
            lv_line_set_points(s_a.path[side][k], &s_a.pts[side][k * n], n + 1);
            visible(s_a.path[side][k], v->on);
        }
    }
}

// ---- B: carbon ---------------------------------------------------------------
// A big power dial with a needle and the gear's red zone, speed in digits,
// shift lights, and steering on the two wings plus a turning wheel icon.

#define B_CX 512
#define B_CY 280
#define B_R 236
#define B_LEDS 12
#define B_WHEEL_X 120
#define B_WHEEL_Y 530

static struct {
    lv_obj_t *red, *needle, *gear, *speed, *led[B_LEDS], *wing[2][2], *wheel, *angle;
    lv_point_precise_t wing_pts[2][3];
    int lit;
} s_b = {.lit = -1};

// The wings from the middle outward: (290,430) (250,470) (0,470) and mirrored.
static const float WING[3][2] = {{290, 430}, {250, 470}, {0, 470}};
#define WING_LEN (56.57f + 250.0f)

static uint32_t led_color(int i) {
    return i < 6 ? 0x2ee86b : (i < 10 ? 0xffcc1e : 0xff1e2d);
}

static void b_build(lv_obj_t *r) {
    // The gear's unusable span: a red band just inside the ticks.
    lv_obj_t *a = lv_arc_create(r);
    lv_obj_set_size(a, 2 * (B_R - 9), 2 * (B_R - 9));
    lv_obj_set_pos(a, B_CX - (B_R - 9), B_CY - (B_R - 9));
    lv_obj_remove_style(a, NULL, LV_PART_KNOB);
    lv_obj_remove_flag(a, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_set_style_arc_width(a, 18, LV_PART_MAIN);
    lv_obj_set_style_arc_color(a, hex(0xff1e2d), LV_PART_MAIN);
    lv_obj_set_style_arc_opa(a, 217, LV_PART_MAIN);
    lv_obj_set_style_arc_rounded(a, false, LV_PART_MAIN);
    lv_obj_set_style_arc_opa(a, LV_OPA_TRANSP, LV_PART_INDICATOR);
    s_b.red = a;

    ui_track(text_at(r, &cjk_14, 0x7b7f86, B_CX, B_CY - 92, 200, LV_TEXT_ALIGN_CENTER), T_CAP_POWER10);
    s_b.needle = lv_image_create(r);
    lv_image_set_src(s_b.needle, &s_b_needle);
    lv_obj_set_pos(s_b.needle, B_CX - 20, B_CY - 221);
    lv_image_set_pivot(s_b.needle, 20, 221);
    lv_obj_t *hub = box(r, B_CX - 44, B_CY - 44, 88, 88, LV_RADIUS_CIRCLE, 0x0b0b0c);
    lv_obj_set_style_border_color(hub, hex(0x2c2f34), 0);
    lv_obj_set_style_border_width(hub, 3, 0);
    s_b.gear = text_at(r, &barlow_58, 0xffffff, B_CX, B_CY + 20, 120, LV_TEXT_ALIGN_CENTER);
    s_b.speed = text_at(r, &barlow_64, 0xffffff, B_CX, B_CY + 140, 200, LV_TEXT_ALIGN_CENTER);
    lv_obj_t *cap = ui_track(text_at(r, &cjk_14, 0x7b7f86, B_CX, B_CY + 166, 200, LV_TEXT_ALIGN_CENTER), T_CAP_SPEED);
    lv_obj_set_style_text_letter_space(cap, 4, 0);

    for (int i = 0; i < B_LEDS; i++) {
        lv_obj_t *l = box(r, B_CX - 6 * 34 + i * 34 + 17 - 9, 22 - 9, 18, 18, LV_RADIUS_CIRCLE, led_color(i));
        lv_obj_set_style_shadow_width(l, 14, 0);
        lv_obj_set_style_shadow_color(l, hex(led_color(i)), 0);
        lv_obj_set_style_shadow_opa(l, LV_OPA_70, 0);
        lv_obj_add_flag(l, LV_OBJ_FLAG_HIDDEN);
        s_b.led[i] = l;
    }
    for (int side = 0; side < 2; side++) {
        s_b.wing[side][0] = line(r, 10, 0xff1e2d, LV_OPA_30); // glow
        s_b.wing[side][1] = line(r, 4, 0xff1e2d, LV_OPA_COVER);
        lv_obj_set_style_line_rounded(s_b.wing[side][0], false, 0);
        lv_obj_set_style_line_rounded(s_b.wing[side][1], false, 0);
    }
    s_b.wheel = lv_image_create(r);
    lv_image_set_src(s_b.wheel, &s_b_wheel);
    lv_obj_set_pos(s_b.wheel, B_WHEEL_X - 40, B_WHEEL_Y - 40);
    lv_image_set_pivot(s_b.wheel, 40, 40);
    s_b.angle = text_at(r, &barlow_28, 0xd8d9db, B_WHEEL_X + 48, B_WHEEL_Y + 10, 120, LV_TEXT_ALIGN_LEFT);
}

// The first len pixels of a wing as a polyline; returns the point count.
static int wing_points(int side, float len, lv_point_precise_t *out) {
    float seg1 = 56.57f;
    int n = 0;
    for (int i = 0; i < 3; i++) {
        float x = WING[i][0], y = WING[i][1];
        if (i == 1 && len < seg1) {
            float t = len / seg1;
            x = WING[0][0] + (WING[1][0] - WING[0][0]) * t;
            y = WING[0][1] + (WING[1][1] - WING[0][1]) * t;
        } else if (i == 2) {
            if (len <= seg1) {
                break;
            }
            x = WING[1][0] - (len - seg1);
        }
        out[n].x = side ? 1024.0f - x : x;
        out[n].y = y;
        n++;
        if (i == 1 && len < seg1) {
            break;
        }
    }
    return n;
}

static void b_show(const dash_values_t *v) {
    float pw = v->on ? fminf(v->power, 1.0f) : 0.0f;
    lv_image_set_rotation(s_b.needle, (int)lroundf((-120.0f + 240.0f * pw) * 10.0f));
    bool cap_on = v->on && v->cap > 0.0f && v->cap < 0.999f;
    visible(s_b.red, cap_on);
    if (cap_on) {
        int start = (int)lroundf(-210.0f + 240.0f * v->cap);
        lv_arc_set_bg_angles(s_b.red, (start + 360) % 360, 30);
    }
    set_text(s_b.gear, GEAR_NAMES[(int)v->gear - GEAR_R]);
    lv_obj_set_style_text_color(s_b.gear, hex(!v->on ? 0x3a3c40 : (v->gear == GEAR_R ? 0xffb23c : 0xffffff)), 0);
    set_number(s_b.speed, v->on ? pct(v->speed) : 0);
    lv_obj_set_style_text_color(s_b.speed, hex(v->on ? 0xffffff : 0x3a3c40), 0);

    int lit = (int)lroundf(pw * B_LEDS);
    if (lit != s_b.lit) {
        s_b.lit = lit;
        for (int i = 0; i < B_LEDS; i++) {
            visible(s_b.led[i], i < lit);
        }
    }

    float st = v->on ? v->steer : 0.0f;
    for (int side = 0; side < 2; side++) {
        bool active = side ? st > 0.0f : st < 0.0f;
        float len = active ? fabsf(st) * WING_LEN : 0.0f;
        int n = len > 1.0f ? wing_points(side, len, s_b.wing_pts[side]) : 0;
        for (int k = 0; k < 2; k++) {
            lv_line_set_points(s_b.wing[side][k], s_b.wing_pts[side], n);
            visible(s_b.wing[side][k], n >= 2);
        }
    }
    lv_image_set_rotation(s_b.wheel, (int)lroundf(v->steer * 1350.0f));
    char buf[24];
    int deg = (int)lroundf(v->steer * 135.0f);
    if (deg == 0) {
        snprintf(buf, sizeof(buf), "0°");
    } else {
        snprintf(buf, sizeof(buf), "%s %d°", deg < 0 ? "L" : "R", deg < 0 ? -deg : deg);
    }
    set_text(s_b.angle, buf);
}

// ---- switching ---------------------------------------------------------------

static const int DASH_NAMES[DASHES] = {T_DASH_A, T_DASH_B};

static void select_dash(int i, bool toast) {
    s_cur = (i % DASHES + DASHES) % DASHES;
    for (int n = 0; n < DASHES; n++) {
        visible(s_dash[n].root, n == s_cur);
        lv_obj_set_style_bg_color(s_dot[n], hex(n == s_cur ? C_TEXT : C_FAINT), 0);
    }
    if (toast) {
        set_text(s_toast, ui_tr(DASH_NAMES[s_cur]));
        visible(s_toast, true);
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
    s_a_bg = IMAGE(a_bg, 1024, 600, LV_COLOR_FORMAT_RGB565);
    s_a_arc = IMAGE(a_arc, 476, 476, LV_COLOR_FORMAT_ARGB8888);
    s_a_tip = IMAGE(a_tip, 48, 48, LV_COLOR_FORMAT_ARGB8888);
    s_b_bg = IMAGE(b_bg, 1024, 600, LV_COLOR_FORMAT_RGB565);
    s_b_needle = IMAGE(b_needle, 40, 262, LV_COLOR_FORMAT_ARGB8888);
    s_b_wheel = IMAGE(b_wheel, 80, 80, LV_COLOR_FORMAT_ARGB8888);

    s_dash[0] = (dash_t){.root = root(scr, &s_a_bg), .show = a_show, .notice_y = 30};
    a_build(s_dash[0].root);
    s_dash[1] = (dash_t){.root = root(scr, &s_b_bg), .show = b_show, .notice_y = 540};
    b_build(s_dash[1].root);

    for (int i = 0; i < DASHES; i++) {
        lv_obj_t *d = box(scr, 512 - DASHES * 10 + i * 20 + 5, 586, 8, 8, LV_RADIUS_CIRCLE, C_FAINT);
        s_dot[i] = d;
    }
    s_toast = text_at(scr, &cjk_32, C_TEXT, 512, 120, 300, LV_TEXT_ALIGN_CENTER);
    visible(s_toast, false);
    lv_obj_add_event_cb(scr, on_gesture, LV_EVENT_GESTURE, NULL);
    select_dash(ui_dash_get(), false);
}

void dash_show(const dash_values_t *v) {
    s_dash[s_cur].show(v);
    if (s_toast_at >= 0 && esp_timer_get_time() - s_toast_at > TOAST_US) {
        visible(s_toast, false);
        s_toast_at = -1;
    }
}

int dash_notice_y(void) {
    return s_dash[s_cur].notice_y;
}

#endif  // CONFIG_IDF_TARGET_ESP32P4
