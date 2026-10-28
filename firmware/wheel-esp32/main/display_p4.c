// Dashboard for the Waveshare ESP32-P4 7B board: 1024x600 touch panel,
// driven through the board support package's LVGL adapter.
//
// Same palette and gauge language as the PC program (src/gui/theme.rs):
// forward throttle heats amber -> red, reverse cools cyan -> blue, the speed
// tier's ceiling is a thin ring with the unusable span in red.
//
// Touch: speed tier, emergency stop and the RADIO setup page (which radio,
// MULTI protocol, bind, reversing). Arming stays on the wheel's Start
// button only, so a stray touch can never arm the car; opening the setup
// page disarms.

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

// Chinese subsets of Noto Sans SC (Simplified and Traditional), falling back to Montserrat
// for Latin, digits and symbols. Regenerate with fonts/gen_fonts.sh after
// changing any Chinese text here.
LV_FONT_DECLARE(cjk_14);
LV_FONT_DECLARE(cjk_16);
LV_FONT_DECLARE(cjk_20);
LV_FONT_DECLARE(cjk_24);
LV_FONT_DECLARE(cjk_32);

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
static lv_obj_t *s_sub;

// RADIO setup page.
static lv_obj_t *s_setup;
static lv_obj_t *s_kind_btn[RADIO_KINDS];
static lv_obj_t *s_proto_btn[16];
static lv_obj_t *s_rx_val, *s_opt_val, *s_rev_steer, *s_rev_thr, *s_bind_btn, *s_bind_label, *s_setup_hint;

// ---- text: Simplified (default) and Traditional Chinese -----------------------
typedef enum { LANG_SC, LANG_TC } lang_t;

enum {
    T_NO_WHEEL, T_ARMED, T_ESTOP, T_SAFE, T_DRIVE, T_THR_PCT, T_LEFT, T_RIGHT, T_STEER_FMT, T_STEER_ZERO,
    T_CONTROL, T_HINT, T_PEDALS, T_GAS, T_BRAKE, T_LINK, T_NO_TX, T_SETUP_BTN, T_SETUP_TITLE, T_DONE,
    T_OUTPUT, T_KIND_SERIAL, T_KIND_PPM, T_PROTO_TITLE, T_RX_NUM, T_FINE, T_REVERSE, T_REV_STEER, T_REV_THR,
    T_BIND, T_BINDING_FMT, T_UNKNOWN_FMT, T_PLUG, T_BUTTON_FMT, T_LIMIT_FMT, T_SUB_ELRS, T_SUB_MULTI_FMT,
    T_SUB_PPM, T_TX_SERIAL, T_TX_PPM, T_RX_FMT, T_DIAL, T_NO_TELEM, T_LINKED, T_CAR_OFF, T_CH_FMT,
    T_HINT_ELRS, T_HINT_SERIAL, T_HINT_PPM, T_LANG, T_COUNT
};

static const char *const TEXT[T_COUNT][2] = {
    [T_NO_WHEEL] = {"未接方向盘", "未接方向盤"},
    [T_ARMED] = {"已解锁", "已解鎖"},
    [T_ESTOP] = {"紧急停止", "緊急停止"},
    [T_SAFE] = {"已上锁", "已上鎖"},
    [T_DRIVE] = {"驾驶", "駕駛"},
    [T_THR_PCT] = {"油门 %", "油門 %"},
    [T_LEFT] = {"左", "左"},
    [T_RIGHT] = {"右", "右"},
    [T_STEER_FMT] = {"转向  %+d", "轉向  %+d"},
    [T_STEER_ZERO] = {"转向  0", "轉向  0"},
    [T_CONTROL] = {"控制", "控制"},
    [T_HINT] = {"Start 解锁/上锁    拨片 换档    P 急停    N 对频", "Start 解鎖/上鎖    撥片 換檔    P 急停    N 對頻"},
    [T_PEDALS] = {"踏板", "踏板"},
    [T_GAS] = {"油门", "油門"},
    [T_BRAKE] = {"刹车", "剎車"},
    [T_LINK] = {"连线", "連線"},
    [T_NO_TX] = {"无发射机", "無發射機"},
    [T_SETUP_BTN] = {LV_SYMBOL_SETTINGS "  发射设置", LV_SYMBOL_SETTINGS "  發射設定"},
    [T_SETUP_TITLE] = {"发射设置", "發射設定"},
    [T_DONE] = {"完成", "完成"},
    [T_OUTPUT] = {"发射方式", "發射方式"},
    [T_KIND_SERIAL] = {"四合一  串口", "四合一  串口"},
    [T_KIND_PPM] = {"四合一  PPM（旋钮）", "四合一  PPM（旋鈕）"},
    [T_PROTO_TITLE] = {"协议（四合一串口模式用，高频头旋钮拨到 0）", "協議（四合一串口模式用，高頻頭旋鈕撥到 0）"},
    [T_RX_NUM] = {"接收机编号", "接收機編號"},
    [T_FINE] = {"频率微调", "頻率微調"},
    [T_REVERSE] = {"反转", "反轉"},
    [T_REV_STEER] = {"转向", "轉向"},
    [T_REV_THR] = {"油门", "油門"},
    [T_BIND] = {"对频", "對頻"},
    [T_BINDING_FMT] = {"对频中 %d 秒", "對頻中 %d 秒"},
    [T_UNKNOWN_FMT] = {"%04X:%04X  未知设备", "%04X:%04X  未知裝置"},
    [T_PLUG] = {"方向盘插到 USB-A 口", "方向盤插到 USB-A 口"},
    [T_BUTTON_FMT] = {"按键 %d", "按鍵 %d"},
    [T_LIMIT_FMT] = {"%s档   限速 %d%%", "%s檔   限速 %d%%"},
    [T_SUB_ELRS] = {"方向盘  >  ELRS  >  车", "方向盤  >  ELRS  >  車"},
    [T_SUB_MULTI_FMT] = {"方向盘  >  四合一 %s  >  车", "方向盤  >  四合一 %s  >  車"},
    [T_SUB_PPM] = {"方向盘  >  四合一 PPM（旋钮）  >  车", "方向盤  >  四合一 PPM（旋鈕）  >  車"},
    [T_TX_SERIAL] = {"四合一 串口", "四合一 串口"},
    [T_TX_PPM] = {"四合一 PPM", "四合一 PPM"},
    [T_RX_FMT] = {"%s  编号 %d", "%s  編號 %d"},
    [T_DIAL] = {"旋钮选协议", "旋鈕選協議"},
    [T_NO_TELEM] = {"无回传", "無回傳"},
    [T_LINKED] = {"已连线", "已連線"},
    [T_CAR_OFF] = {"车未连线", "車未連線"},
    [T_CH_FMT] = {"CH1 转向 %d us     CH2 油门 %d us", "CH1 轉向 %d us     CH2 油門 %d us"},
    [T_HINT_ELRS] = {"用 ELRS 高频头（GPIO28）发射，四合一不发射。", "用 ELRS 高頻頭（GPIO28）發射，四合一不發射。"},
    [T_HINT_SERIAL] = {"高频头旋钮拨到 0（转旋钮后要断电重开）。按“对频”或方向盘 N 键，再让接收机进入对频。"
                       "S-FHSS 不用按对频，接收机自己配。",
                       "高頻頭旋鈕撥到 0（轉旋鈕後要斷電重開）。按「對頻」或方向盤 N 鍵，再讓接收機進入對頻。"
                       "S-FHSS 不用按對頻，接收機自己配。"},
    [T_HINT_PPM] = {"用高频头旋钮选协议（1～E，F 选组别，转后要断电重开）。对频：按住高频头对频键上电 5 秒，"
                    "再让接收机进入对频。",
                    "用高頻頭旋鈕選協議（1～E，F 選組別，轉後要斷電重開）。對頻：按住高頻頭對頻鍵上電 5 秒，"
                    "再讓接收機進入對頻。"},
    [T_LANG] = {"语言", "語言"},
};

static lang_t s_lang = LANG_SC;

static const char *tr(int id) {
    return TEXT[id][s_lang];
}

// Labels with fixed text, re-set when the language changes.
#define MAX_TLABELS 48
static struct {
    lv_obj_t *obj;
    int id;
} s_tlabels[MAX_TLABELS];
static int s_tlabel_count;

static lv_obj_t *track(lv_obj_t *l, int id) {
    if (s_tlabel_count < MAX_TLABELS) {
        s_tlabels[s_tlabel_count].obj = l;
        s_tlabels[s_tlabel_count].id = id;
        s_tlabel_count++;
    }
    lv_label_set_text(l, tr(id));
    return l;
}

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
static void section_title(lv_obj_t *parent, int id) {
    lv_obj_t *l = track(label(parent, &cjk_14, C_DIM, ""), id);
    lv_obj_set_style_text_letter_space(l, 2, 0);
    lv_obj_set_pos(l, 18, 12);
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

// Every setup change applies (and is saved) at once.
static void edit(void (*fn)(radio_config_t *c, intptr_t arg), intptr_t arg) {
    radio_config_t c = radio_config();
    fn(&c, arg);
    radio_set(&c);
}

static void set_kind(radio_config_t *c, intptr_t k) {
    c->kind = (radio_kind_t)k;
    multi_bind_cancel();
}

static void set_proto(radio_config_t *c, intptr_t i) {
    if (c->proto != i) {
        c->proto = (uint8_t)i;
        c->option = MULTI_PROTOS[i].option;
    }
}

static void add_rx(radio_config_t *c, intptr_t d) {
    c->rx_num = (uint8_t)((c->rx_num + 16 + d) % 16);
}

static void add_option(radio_config_t *c, intptr_t d) {
    int v = c->option + (int)d;
    c->option = (int8_t)(v < -127 ? -127 : (v > 127 ? 127 : v));
}

static void flip_steer(radio_config_t *c, intptr_t unused) {
    c->rev_steer[c->kind] = !c->rev_steer[c->kind];
}

static void flip_thr(radio_config_t *c, intptr_t unused) {
    c->rev_thr[c->kind] = !c->rev_thr[c->kind];
}

static void on_kind(lv_event_t *e) {
    edit(set_kind, (intptr_t)lv_event_get_user_data(e));
}

static void on_proto(lv_event_t *e) {
    edit(set_proto, (intptr_t)lv_event_get_user_data(e));
}

static void on_rx(lv_event_t *e) {
    edit(add_rx, (intptr_t)lv_event_get_user_data(e));
}

static void on_option(lv_event_t *e) {
    edit(add_option, (intptr_t)lv_event_get_user_data(e));
}

static void on_rev_steer(lv_event_t *e) {
    edit(flip_steer, 0);
}

static void on_rev_thr(lv_event_t *e) {
    edit(flip_thr, 0);
}

static void on_bind(lv_event_t *e) {
    if (multi_status().binding) {
        multi_bind_cancel();
    } else {
        multi_bind();
    }
}

static lv_obj_t *s_lang_btn[2];

static void on_lang(lv_event_t *e) {
    s_lang = (lang_t)(intptr_t)lv_event_get_user_data(e);
    ui_lang_set(s_lang);
    for (int i = 0; i < s_tlabel_count; i++) {
        lv_label_set_text(s_tlabels[i].obj, tr(s_tlabels[i].id));
    }
}

static void on_setup_open(lv_event_t *e) {
    control_disarm("RADIO");
    lv_obj_remove_flag(s_setup, LV_OBJ_FLAG_HIDDEN);
}

static void on_setup_close(lv_event_t *e) {
    lv_obj_add_flag(s_setup, LV_OBJ_FLAG_HIDDEN);
}

// ---- build -------------------------------------------------------------------

static void build_top(lv_obj_t *scr) {
    lv_obj_t *title = label(scr, &lv_font_montserrat_24, C_TEXT, "RC CONTROL");
    lv_obj_set_style_text_letter_space(title, 2, 0);
    lv_obj_set_pos(title, M + 8, 10);
    s_sub = label(scr, &cjk_14, C_DIM, "");
    lv_obj_set_style_text_letter_space(s_sub, 2, 0);
    lv_obj_set_pos(s_sub, M + 8, 40);

    s_pill = lv_obj_create(scr);
    lv_obj_remove_style_all(s_pill);
    lv_obj_set_size(s_pill, 260, 44);
    lv_obj_align(s_pill, LV_ALIGN_TOP_MID, 0, 10);
    lv_obj_set_style_radius(s_pill, 22, 0);
    lv_obj_set_style_bg_opa(s_pill, LV_OPA_20, 0);
    lv_obj_set_style_border_width(s_pill, 2, 0);
    lv_obj_remove_flag(s_pill, LV_OBJ_FLAG_SCROLLABLE);
    s_pill_label = label(s_pill, &cjk_24, C_TEXT, tr(T_NO_WHEEL));
    lv_obj_set_style_text_letter_space(s_pill_label, 3, 0);
    lv_obj_center(s_pill_label);

    s_wheel_label = label(scr, &cjk_16, C_DIM, "");
    lv_obj_align(s_wheel_label, LV_ALIGN_TOP_RIGHT, -M - 8, 12);
    s_button_label = label(scr, &cjk_14, C_FAINT, "");
    lv_obj_align(s_button_label, LV_ALIGN_TOP_RIGHT, -M - 8, 40);
}

static void build_drive(lv_obj_t *scr) {
    lv_obj_t *p = panel(scr, M, TOP_H + 8, DRIVE_W, 600 - TOP_H - 8 - M);
    section_title(p, T_DRIVE);
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
    lv_obj_t *cap = track(label(p, &cjk_14, C_DIM, ""), T_THR_PCT);
    lv_obj_set_style_text_letter_space(cap, 3, 0);
    lv_obj_align(cap, LV_ALIGN_TOP_MID, 0, cy + 22);
    s_limit_label = label(p, &cjk_16, C_AMBER, "");
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
    lv_obj_t *l = track(label(p, &cjk_14, C_FAINT, ""), T_LEFT);
    lv_obj_set_pos(l, (DRIVE_W - sw) / 2 - 18, sy - 1);
    lv_obj_t *r = track(label(p, &cjk_14, C_FAINT, ""), T_RIGHT);
    lv_obj_set_pos(r, (DRIVE_W + sw) / 2 + 8, sy - 1);
    s_steer_label = label(p, &cjk_16, C_DIM, "");
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
    section_title(p, T_CONTROL);

    static const char *names[3] = {"低速", "中速", "高速"};
    const int bw = (SIDE_W - 36 - 16) / 3;
    for (int i = 0; i < 3; i++) {
        s_speed_btn[i] = button(p, 18 + i * (bw + 8), 40, bw, 56, C_DIM, &cjk_24, names[i]);
        lv_obj_add_event_cb(s_speed_btn[i], on_speed, LV_EVENT_CLICKED, (void *)(intptr_t)i);
    }

    lv_obj_t *stop = button(p, 18, 108, SIDE_W - 36, 72, C_RED, &cjk_32, "");
    track(lv_obj_get_child(stop, 0), T_ESTOP);
    lv_obj_set_style_bg_opa(stop, LV_OPA_40, 0);
    // Pressed, not clicked: stop on touch-down, without waiting for release.
    lv_obj_add_event_cb(stop, on_estop, LV_EVENT_PRESSED, NULL);

    s_hint = track(label(p, &cjk_14, C_DIM, ""), T_HINT);
    lv_obj_set_pos(s_hint, 18, 196);
}

static void build_pedals(lv_obj_t *scr) {
    const int y0 = TOP_H + 8 + 236 + M, h = 112;
    lv_obj_t *p = panel(scr, SIDE_X, y0, SIDE_W, h);
    section_title(p, T_PEDALS);
    const int bx = 86, bw = SIDE_W - bx - 70;
    for (int i = 0; i < 2; i++) {
        int y = 44 + i * 32;
        lv_obj_t *name = track(label(p, &cjk_14, C_DIM, ""), i ? T_BRAKE : T_GAS);
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
    section_title(p, T_LINK);

    s_tx_label = label(p, &cjk_24, C_RED, "");
    lv_obj_set_style_text_letter_space(s_tx_label, 2, 0);
    lv_obj_set_pos(s_tx_label, 18, 36);
    s_rssi_label = label(p, &cjk_16, C_DIM, "-- dBm");
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
    s_lq_label = label(p, &cjk_16, C_DIM, "LQ --");
    lv_obj_align(s_lq_label, LV_ALIGN_TOP_RIGHT, -18, 77);

    s_ch_label = label(p, &cjk_14, C_FAINT, "");
    lv_obj_set_pos(s_ch_label, 18, 106);

    lv_obj_t *radio = button(p, SIDE_W - 18 - 150, 6, 150, 30, C_CYAN, &cjk_16, "");
    track(lv_obj_get_child(radio, 0), T_SETUP_BTN);
    lv_obj_add_event_cb(radio, on_setup_open, LV_EVENT_CLICKED, NULL);
}

static lv_obj_t *setup_label(lv_obj_t *p, int x, int y, int id) {
    lv_obj_t *l = track(label(p, &cjk_14, C_DIM, ""), id);
    lv_obj_set_style_text_letter_space(l, 2, 0);
    lv_obj_set_pos(l, x, y);
    return l;
}

// Full-screen page over the dashboard, hidden until RADIO is tapped.
static void build_setup(void) {
    lv_obj_t *p = lv_obj_create(lv_layer_top());
    lv_obj_remove_style_all(p);
    lv_obj_set_size(p, 1024, 600);
    lv_obj_set_style_bg_color(p, hex(C_BG), 0);
    lv_obj_set_style_bg_opa(p, LV_OPA_COVER, 0);
    lv_obj_remove_flag(p, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_add_flag(p, LV_OBJ_FLAG_HIDDEN);
    s_setup = p;

    lv_obj_t *title = track(label(p, &cjk_24, C_TEXT, ""), T_SETUP_TITLE);
    lv_obj_set_style_text_letter_space(title, 2, 0);
    lv_obj_set_pos(title, M + 8, 18);
    lv_obj_t *done = button(p, 1024 - M - 160, 12, 160, 48, C_GREEN, &cjk_20, "");
    track(lv_obj_get_child(done, 0), T_DONE);
    lv_obj_add_event_cb(done, on_setup_close, LV_EVENT_CLICKED, NULL);
    static const char *langs[2] = {"简体", "繁體"};
    for (int i = 0; i < 2; i++) {
        s_lang_btn[i] = button(p, 1024 - M - 160 - 16 - (2 - i) * 120, 12, 112, 48, C_DIM, &cjk_20, langs[i]);
        lv_obj_add_event_cb(s_lang_btn[i], on_lang, LV_EVENT_CLICKED, (void *)(intptr_t)i);
    }

    // Which radio transmits.
    setup_label(p, M + 8, 78, T_OUTPUT);
    static const int kinds[RADIO_KINDS] = {-1, T_KIND_SERIAL, T_KIND_PPM};
    const int kw = (1024 - 2 * M - 16 - 2 * 12) / 3;
    for (int i = 0; i < RADIO_KINDS; i++) {
        s_kind_btn[i] = button(p, M + 8 + i * (kw + 12), 100, kw, 60, C_CYAN, &cjk_20, "ELRS");
        if (kinds[i] >= 0) {
            track(lv_obj_get_child(s_kind_btn[i], 0), kinds[i]);
        }
        lv_obj_add_event_cb(s_kind_btn[i], on_kind, LV_EVENT_CLICKED, (void *)(intptr_t)i);
    }

    // MULTI serial protocol.
    setup_label(p, M + 8, 178, T_PROTO_TITLE);
    const int cols = 4, pw = (1024 - 2 * M - 16 - (cols - 1) * 12) / cols;
    for (int i = 0; i < MULTI_PROTO_COUNT && i < 16; i++) {
        int x = M + 8 + (i % cols) * (pw + 12), y = 200 + (i / cols) * 62;
        s_proto_btn[i] = button(p, x, y, pw, 52, C_AMBER, &cjk_20, MULTI_PROTOS[i].name);
        lv_obj_add_event_cb(s_proto_btn[i], on_proto, LV_EVENT_CLICKED, (void *)(intptr_t)i);
    }

    // RX number and fine tune.
    const int ry = 410;
    setup_label(p, M + 8, ry - 2, T_RX_NUM);
    lv_obj_t *b = button(p, M + 8, ry + 20, 56, 52, C_DIM, &lv_font_montserrat_24, "-");
    lv_obj_add_event_cb(b, on_rx, LV_EVENT_CLICKED, (void *)(intptr_t)-1);
    s_rx_val = label(p, &lv_font_montserrat_28, C_TEXT, "0");
    lv_obj_set_pos(s_rx_val, M + 8 + 72, ry + 30);
    b = button(p, M + 8 + 120, ry + 20, 56, 52, C_DIM, &lv_font_montserrat_24, "+");
    lv_obj_add_event_cb(b, on_rx, LV_EVENT_CLICKED, (void *)(intptr_t)1);

    const int ox = 230;
    setup_label(p, ox, ry - 2, T_FINE);
    static const int steps[4] = {-10, -1, 1, 10};
    static const char *step_names[4] = {"-10", "-1", "+1", "+10"};
    for (int i = 0; i < 4; i++) {
        int x = ox + i * 66 + (i >= 2 ? 90 : 0);
        b = button(p, x, ry + 20, 58, 52, C_DIM, &lv_font_montserrat_16, step_names[i]);
        lv_obj_add_event_cb(b, on_option, LV_EVENT_CLICKED, (void *)(intptr_t)steps[i]);
    }
    s_opt_val = label(p, &lv_font_montserrat_28, C_TEXT, "0");
    lv_obj_set_pos(s_opt_val, ox + 2 * 66 + 8, ry + 30);

    // Reversing for the selected output.
    const int vx = 680;
    setup_label(p, vx, ry - 2, T_REVERSE);
    s_rev_steer = button(p, vx, ry + 20, 150, 52, C_CYAN, &cjk_20, "");
    track(lv_obj_get_child(s_rev_steer, 0), T_REV_STEER);
    lv_obj_add_event_cb(s_rev_steer, on_rev_steer, LV_EVENT_CLICKED, NULL);
    s_rev_thr = button(p, vx + 162, ry + 20, 150, 52, C_CYAN, &cjk_20, "");
    track(lv_obj_get_child(s_rev_thr, 0), T_REV_THR);
    lv_obj_add_event_cb(s_rev_thr, on_rev_thr, LV_EVENT_CLICKED, NULL);

    // Bind (MULTI serial) and what to do for the selected output.
    s_bind_btn = button(p, M + 8, 510, 300, 64, C_AMBER, &cjk_24, "");
    s_bind_label = lv_obj_get_child(s_bind_btn, 0);
    lv_obj_add_event_cb(s_bind_btn, on_bind, LV_EVENT_CLICKED, NULL);
    s_setup_hint = label(p, &cjk_16, C_DIM, "");
    lv_obj_set_width(s_setup_hint, 1024 - 2 * M - 340);
    lv_label_set_long_mode(s_setup_hint, LV_LABEL_LONG_WRAP);
    lv_obj_set_pos(s_setup_hint, M + 8 + 320, 514);
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

    s_lang = ui_lang_get() ? LANG_TC : LANG_SC;
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
    build_setup();
    bsp_display_unlock();
    ESP_LOGI(TAG, "7\" dashboard up");
}

// ---- update ------------------------------------------------------------------

static void show_state(const display_state_t *s) {
    const control_view_t *c = &s->ctl;
    const char *text;
    uint32_t color;
    if (!s->wheel) {
        text = tr(T_NO_WHEEL), color = C_FAINT;
    } else if (c->armed) {
        text = tr(T_ARMED), color = C_GREEN;
    } else if (strcmp(c->disarm_reason, "E-STOP") == 0) {
        text = tr(T_ESTOP), color = C_RED;
    } else {
        text = tr(T_SAFE), color = C_AMBER;
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
            snprintf(buf, sizeof(buf), tr(T_UNKNOWN_FMT), s->vid, s->pid);
        }
    } else {
        snprintf(buf, sizeof(buf), "%s", tr(T_PLUG));
    }
    set_text(s_wheel_label, buf);
    lv_obj_set_style_text_color(s_wheel_label, hex(s->wheel ? C_TEXT : C_DIM), 0);
    if (s->button) {
        snprintf(buf, sizeof(buf), tr(T_BUTTON_FMT), s->button);
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
    static const char *tier[3] = {"低速", "中速", "高速"};
    snprintf(buf, sizeof(buf), tr(T_LIMIT_FMT), tier[c->speed], lp);
    set_text(s_limit_label, buf);

    int st = s->wheel ? (int)lroundf(c->steering * 100.0f) : 0;
    lv_bar_set_value(s_steer_bar, st, LV_ANIM_OFF);
    snprintf(buf, sizeof(buf), tr(T_STEER_FMT), st);
    set_text(s_steer_label, st == 0 ? tr(T_STEER_ZERO) : buf);

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
    const radio_config_t *cfg = &s->cfg;
    char buf[64];
    const char *proto = MULTI_PROTOS[cfg->proto].name;
    if (cfg->kind == RADIO_ELRS) {
        set_text(s_sub, tr(T_SUB_ELRS));
    } else if (cfg->kind == RADIO_MULTI_SERIAL) {
        snprintf(buf, sizeof(buf), tr(T_SUB_MULTI_FMT), proto);
        set_text(s_sub, buf);
    } else {
        set_text(s_sub, tr(T_SUB_PPM));
    }
    if (cfg->kind != RADIO_ELRS) {
        // MULTI: one way, no telemetry; show what is being sent.
        if (s->multi.binding) {
            snprintf(buf, sizeof(buf), tr(T_BINDING_FMT), s->multi.bind_left_s);
            set_text(s_tx_label, buf);
            lv_obj_set_style_text_color(s_tx_label, hex(C_AMBER), 0);
        } else {
            set_text(s_tx_label, tr(cfg->kind == RADIO_MULTI_SERIAL ? T_TX_SERIAL : T_TX_PPM));
            lv_obj_set_style_text_color(s_tx_label, hex(C_CYAN), 0);
        }
        if (cfg->kind == RADIO_MULTI_SERIAL) {
            snprintf(buf, sizeof(buf), tr(T_RX_FMT), proto, cfg->rx_num);
            set_text(s_rssi_label, buf);
        } else {
            set_text(s_rssi_label, tr(T_DIAL));
        }
        set_text(s_lq_label, tr(T_NO_TELEM));
        for (int i = 0; i < LQ_SEGS; i++) {
            lv_obj_set_style_bg_color(s_lq_seg[i], hex(C_TRACK), 0);
        }
    } else if (r->link) {
        set_text(s_tx_label, tr(T_LINKED));
        lv_obj_set_style_text_color(s_tx_label, hex(C_GREEN), 0);
        snprintf(buf, sizeof(buf), "%d dBm", r->rssi);
        set_text(s_rssi_label, buf);
        snprintf(buf, sizeof(buf), "LQ %d", r->lq);
        set_text(s_lq_label, buf);
    } else {
        set_text(s_tx_label, tr(r->module ? T_CAR_OFF : T_NO_TX));
        lv_obj_set_style_text_color(s_tx_label, hex(r->module ? C_AMBER : C_RED), 0);
        set_text(s_rssi_label, "-- dBm");
        set_text(s_lq_label, "LQ --");
    }
    if (cfg->kind == RADIO_ELRS) {
        int lit = r->link ? (r->lq * LQ_SEGS + 50) / 100 : 0;
        uint32_t col = lq_color(r->lq);
        for (int i = 0; i < LQ_SEGS; i++) {
            lv_obj_set_style_bg_color(s_lq_seg[i], hex(i < lit ? col : C_TRACK), 0);
        }
    }
    // Pulse widths the receiver puts out (988..2012 us around 1500).
    const control_output_t *o = &s->ctl.output;
    snprintf(buf, sizeof(buf), tr(T_CH_FMT), (int)lroundf(1500 + o->steering * 512),
             (int)lroundf(1500 + o->throttle * 512));
    set_text(s_ch_label, buf);
}

static void highlight(lv_obj_t *b, bool on, uint32_t color) {
    lv_obj_set_style_border_color(b, hex(on ? color : C_EDGE), 0);
    lv_obj_set_style_bg_color(b, hex(on ? color : C_DIM), 0);
    lv_obj_set_style_bg_opa(b, on ? LV_OPA_40 : LV_OPA_10, 0);
}

static void show_setup(const display_state_t *s) {
    if (lv_obj_has_flag(s_setup, LV_OBJ_FLAG_HIDDEN)) {
        return;
    }
    const radio_config_t *c = &s->cfg;
    char buf[160];
    for (int i = 0; i < RADIO_KINDS; i++) {
        highlight(s_kind_btn[i], c->kind == i, C_CYAN);
    }
    for (int i = 0; i < 2; i++) {
        highlight(s_lang_btn[i], (int)s_lang == i, C_GREEN);
    }
    for (int i = 0; i < MULTI_PROTO_COUNT && i < 16; i++) {
        highlight(s_proto_btn[i], c->proto == i, c->kind == RADIO_MULTI_SERIAL ? C_AMBER : C_DIM);
    }
    snprintf(buf, sizeof(buf), "%d", c->rx_num);
    set_text(s_rx_val, buf);
    snprintf(buf, sizeof(buf), "%d", c->option);
    set_text(s_opt_val, buf);
    highlight(s_rev_steer, c->rev_steer[c->kind], C_CYAN);
    highlight(s_rev_thr, c->rev_thr[c->kind], C_CYAN);

    bool serial = c->kind == RADIO_MULTI_SERIAL;
    if (serial) {
        lv_obj_remove_state(s_bind_btn, LV_STATE_DISABLED);
        lv_obj_remove_flag(s_bind_btn, LV_OBJ_FLAG_HIDDEN);
    } else {
        lv_obj_add_flag(s_bind_btn, LV_OBJ_FLAG_HIDDEN);
    }
    if (s->multi.binding) {
        snprintf(buf, sizeof(buf), tr(T_BINDING_FMT), s->multi.bind_left_s);
        set_text(s_bind_label, buf);
        highlight(s_bind_btn, true, C_AMBER);
    } else {
        set_text(s_bind_label, tr(T_BIND));
        highlight(s_bind_btn, false, C_AMBER);
    }
    const char *hint;
    if (c->kind == RADIO_ELRS) {
        hint = tr(T_HINT_ELRS);
    } else if (serial) {
        hint = tr(T_HINT_SERIAL);
    } else {
        hint = tr(T_HINT_PPM);
    }
    set_text(s_setup_hint, hint);
}

void display_show(const display_state_t *s) {
    if (s_pill == NULL || !bsp_display_lock(20)) {
        return;
    }
    show_state(s);
    show_drive(s);
    show_pedals(s);
    show_link(s);
    show_setup(s);
    bsp_display_unlock();
}

#endif  // CONFIG_IDF_TARGET_ESP32P4
