// Dashboard for the Waveshare ESP32-P4 7B board: 1024x600 touch panel,
// driven through the board support package's LVGL adapter.
//
// The main screen is only an instrument cluster (dash_p4.c: several looks,
// swipe to switch); each shows the driver's notices its own way. Everything else (radio
// choice, link, pedals, wheel) sits behind the settings button, on the
// setup page's two tabs. Same palette as the PC program (src/gui/theme.rs).
//
// Ignition stays on the wheel's Start button only, so a stray touch can
// never start the car; opening setup stops it. Emergency stop: wheel P.

#include "display.h"

#include "sdkconfig.h"

#if CONFIG_IDF_TARGET_ESP32P4

#include <math.h>
#include <stdio.h>
#include <string.h>

#include "bsp/display.h"
#include "bsp/esp-bsp.h"
#include "esp_log.h"
#include "esp_system.h"
#include "lvgl.h"
#include "dash_p4.h"
#include "ui_p4.h"

static const char *TAG = "display";

// ---- layout (1024 x 600) -----------------------------------------------------
#define TOP_H 56
#define M 16
#define MID_CX 512
#define LQ_SEGS 10

// Status tab.
static lv_obj_t *s_sub, *s_wheel_label, *s_button_label, *s_steer_bar;
static lv_obj_t *s_gas_bar, *s_gas_label, *s_brake_bar, *s_brake_label;
static lv_obj_t *s_tx_label, *s_rssi_label, *s_lq_label, *s_ch_label;
static lv_obj_t *s_lq_seg[LQ_SEGS];

// RADIO setup page.
static lv_obj_t *s_setup;
static lv_obj_t *s_kind_btn[RADIO_KINDS];
static lv_obj_t *s_proto_btn[16];
static lv_obj_t *s_rx_val, *s_opt_val, *s_rev_steer, *s_rev_thr, *s_bind_btn, *s_bind_label, *s_setup_hint;

// ---- text: Simplified (default) and Traditional Chinese -----------------------
typedef enum { LANG_SC, LANG_TC } lang_t;


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
    [T_HINT] = {"Start 点火/熄火   拨片 换挡   P 急停   N 对频", "Start 點火/熄火   撥片 換擋   P 急停   N 對頻"},
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
    [T_HINT_ELRS] = {"单线接法（BETAFPV 高频头）：信号线接 GPIO28。左边按钮切换接法。",
                     "單線接法（BETAFPV 高頻頭）：信號線接 GPIO28。左邊按鈕切換接法。"},
    [T_HINT_ELRS2] = {"双线接法（Nano 刷成发射机）：Nano 的 RX 接 GPIO28，TX 接 GPIO29。左边按钮切换接法。",
                      "雙線接法（Nano 刷成發射機）：Nano 的 RX 接 GPIO28，TX 接 GPIO29。左邊按鈕切換接法。"},
    [T_HINT_SERIAL] = {"高频头旋钮拨到 0（转旋钮后要断电重开）。按“对频”或方向盘 N 键，再让接收机进入对频。"
                       "S-FHSS 不用按对频，接收机自己配。",
                       "高頻頭旋鈕撥到 0（轉旋鈕後要斷電重開）。按「對頻」或方向盤 N 鍵，再讓接收機進入對頻。"
                       "S-FHSS 不用按對頻，接收機自己配。"},
    [T_HINT_PPM] = {"用高频头旋钮选协议（1～E，F 选组别，转后要断电重开）。对频：按住高频头对频键上电 5 秒，"
                    "再让接收机进入对频。",
                    "用高頻頭旋鈕選協議（1～E，F 選組別，轉後要斷電重開）。對頻：按住高頻頭對頻鍵上電 5 秒，"
                    "再讓接收機進入對頻。"},
    [T_LANG] = {"语言", "語言"},
    [T_POWER] = {"动力 %", "動力 %"},
    [T_SPEED] = {"车速 %（估算）", "車速 %（估算）"},
    [T_ENGINE_ON] = {"已点火", "已點火"},
    [T_ENGINE_OFF] = {"已熄火", "已熄火"},
    [T_PRESS_START] = {"按 Start 点火", "按 Start 點火"},
    [T_N_STOP] = {"先停车再换方向", "先停車再換方向"},
    [T_N_PEDALS] = {"先松开踏板再点火", "先鬆開踏板再點火"},
    [T_N_ENGINE] = {"先按 Start 点火", "先按 Start 點火"},
    [T_STATUS] = {"状态信息", "狀態資訊"},
    [T_WHEEL] = {"方向盘", "方向盤"},
    [T_NO_LINK] = {"车未连线", "車未連線"},
    [T_DASH_A] = {"曜石", "曜石"},
    [T_DASH_B] = {"碳纤", "碳纖"},
    [T_CAP_SPEED] = {"km/h", "km/h"},
    [T_TAB_DRIVE] = {"驾驶设置", "駕駛設定"},
    [T_FFB] = {"方向盘力回馈", "方向盤力回饋"},
    [T_FLIP] = {"屏幕方向", "螢幕方向"},
    [T_FLIP_BTN] = {"翻转 180°", "翻轉 180°"},
    [T_WIRE_ONE] = {"接法：单线", "接法：單線"},
    [T_WIRE_TWO] = {"接法：双线 Nano", "接法：雙線 Nano"},
    [T_FLIP_HINT] = {"板子倒着装时用。点一下会重启屏幕，再点一下翻回来。", "板子倒著裝時用。點一下會重啟螢幕，再點一下翻回來。"},
    [T_FFB_HINT] = {"车速越快，方向盘回正越有力；停车时很轻。第一次试的时候手轻扶方向盘，从小往大调。0% 关闭。",
                    "車速越快，方向盤回正越有力；停車時很輕。第一次試的時候手輕扶方向盤，從小往大調。0% 關閉。"},
    [T_TOP_SPEED] = {"最高车速", "最高車速"},
    [T_TOP_HINT] = {"车上没有测速器：仪表的车速 = 估算的速度比例 × 最高车速。按这台车的实际极速填写。",
                    "車上沒有測速器：儀表的車速 = 估算的速度比例 × 最高車速。按這台車的實際極速填寫。"},
    [T_CAP_POWER] = {"动力", "動力"},
    [T_CAP_POWER10] = {"动力 ×10%", "動力 ×10%"},
};

static lang_t s_lang = LANG_SC;

static const char *tr(int id) {
    return TEXT[id][s_lang];
}

// Labels with fixed text, re-set when the language changes.
#define MAX_TLABELS 64
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

const char *ui_tr(int id) {
    return tr(id);
}

lv_obj_t *ui_track(lv_obj_t *l, int id) {
    return track(l, id);
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


// Uppercase section title with wide tracking, like the PC panels.
static void section_title(lv_obj_t *parent, int id) {
    lv_obj_t *l = track(label(parent, &cjk_14, C_DIM, ""), id);
    lv_obj_set_style_text_letter_space(l, 2, 0);
    lv_obj_set_pos(l, 18, 12);
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


static uint32_t lq_color(int lq) {
    return lq >= 70 ? C_GREEN : (lq >= 40 ? C_AMBER : C_RED);
}

// ---- touch -------------------------------------------------------------------

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
    // The same button picks the wiring when ELRS is selected.
    if (radio_config().kind == RADIO_ELRS) {
        ui_elrs_duplex_set(!ui_elrs_duplex_get());
    } else if (multi_status().binding) {
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

#define TABS 3
static lv_obj_t *s_tab_page[TABS], *s_tab_btn[TABS];
static lv_obj_t *s_kmh_val;
static int s_kmh;
static int s_tab;

static void on_tab(lv_event_t *e) {
    s_tab = (int)(intptr_t)lv_event_get_user_data(e);
    for (int i = 0; i < TABS; i++) {
        if (i == s_tab) {
            lv_obj_remove_flag(s_tab_page[i], LV_OBJ_FLAG_HIDDEN);
        } else {
            lv_obj_add_flag(s_tab_page[i], LV_OBJ_FLAG_HIDDEN);
        }
    }
}

static void on_setup_open(lv_event_t *e) {
    control_ignition_off("SETUP");
    lv_obj_remove_flag(s_setup, LV_OBJ_FLAG_HIDDEN);
}

static void on_setup_close(lv_event_t *e) {
    lv_obj_add_flag(s_setup, LV_OBJ_FLAG_HIDDEN);
}

// ---- build -------------------------------------------------------------------

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

static void build_top(lv_obj_t *scr) {
    lv_obj_t *setup = button(scr, 1024 - M - 64, 10, 64, 48, C_DIM, &lv_font_montserrat_24, LV_SYMBOL_SETTINGS);
    lv_obj_set_style_border_color(setup, hex(C_EDGE), 0);
    lv_obj_set_style_bg_opa(setup, LV_OPA_10, 0);
    lv_obj_add_event_cb(setup, on_setup_open, LV_EVENT_CLICKED, NULL);
}

// Status tab: the wheel, pedals and the radio link, for checking things.
static void build_status(lv_obj_t *t) {
    const int x0 = M + 8, w = 1024 - 2 * (M + 8);
    lv_obj_t *p = panel(t, x0, 80, w, 170);
    section_title(p, T_WHEEL);
    s_wheel_label = label(p, &cjk_20, C_TEXT, "");
    lv_obj_set_pos(s_wheel_label, 18, 40);
    s_button_label = label(p, &cjk_16, C_DIM, "");
    lv_obj_align(s_button_label, LV_ALIGN_TOP_RIGHT, -18, 44);
    static const int rows[3] = {T_REV_STEER, T_GAS, T_BRAKE};
    static const uint32_t colors[3] = {C_CYAN, C_GREEN, C_RED};
    const int bx = 90, bw = w - bx - 80;
    for (int i = 0; i < 3; i++) {
        int y = 82 + i * 28;
        lv_obj_t *name = track(label(p, &cjk_16, C_DIM, ""), rows[i]);
        lv_obj_set_pos(name, 18, y - 4);
        lv_obj_t *bar = hbar(p, bx, y, bw, 12, i ? 0 : -100, colors[i]);
        lv_obj_t *val = label(p, &lv_font_montserrat_16, C_TEXT, "0");
        lv_obj_align(val, LV_ALIGN_TOP_RIGHT, -18, y - 3);
        if (i == 0) {
            s_steer_bar = bar;
        } else if (i == 1) {
            s_gas_bar = bar, s_gas_label = val;
        } else {
            s_brake_bar = bar, s_brake_label = val;
        }
    }

    p = panel(t, x0, 266, w, 170);
    section_title(p, T_LINK);
    s_sub = label(p, &cjk_16, C_DIM, "");
    lv_obj_align(s_sub, LV_ALIGN_TOP_RIGHT, -18, 12);
    s_tx_label = label(p, &cjk_24, C_RED, "");
    lv_obj_set_pos(s_tx_label, 18, 42);
    s_rssi_label = label(p, &cjk_16, C_DIM, "-- dBm");
    lv_obj_align(s_rssi_label, LV_ALIGN_TOP_RIGHT, -18, 48);
    const int sw = (w - 36 - 110 - (LQ_SEGS - 1) * 4) / LQ_SEGS;
    for (int i = 0; i < LQ_SEGS; i++) {
        lv_obj_t *sg = lv_obj_create(p);
        lv_obj_remove_style_all(sg);
        lv_obj_set_size(sg, sw, 12);
        lv_obj_set_pos(sg, 18 + i * (sw + 4), 92);
        lv_obj_set_style_radius(sg, 2, 0);
        lv_obj_set_style_bg_color(sg, hex(C_TRACK), 0);
        lv_obj_set_style_bg_opa(sg, LV_OPA_COVER, 0);
        s_lq_seg[i] = sg;
    }
    s_lq_label = label(p, &cjk_16, C_DIM, "LQ --");
    lv_obj_align(s_lq_label, LV_ALIGN_TOP_RIGHT, -18, 88);
    s_ch_label = label(p, &cjk_16, C_FAINT, "");
    lv_obj_set_pos(s_ch_label, 18, 126);

    lv_obj_t *hint = track(label(t, &cjk_16, C_FAINT, ""), T_HINT);
    lv_obj_set_pos(hint, x0, 456);
}

static lv_obj_t *setup_label(lv_obj_t *p, int x, int y, int id) {
    lv_obj_t *l = track(label(p, &cjk_14, C_DIM, ""), id);
    lv_obj_set_style_text_letter_space(l, 2, 0);
    lv_obj_set_pos(l, x, y);
    return l;
}

static lv_obj_t *s_ffb_val;

static void on_ffb(lv_event_t *e) {
    int v = ui_ffb_get() + (int)(intptr_t)lv_event_get_user_data(e);
    ui_ffb_set(v < 0 ? 0 : (v > 100 ? 100 : v));
}

// The display's rotation is fixed when it starts, so flipping restarts.
static void on_flip(lv_event_t *e) {
    ui_flip_set(!ui_flip_get());
    ESP_LOGI(TAG, "screen flip -> restart");
    esp_restart();
}

static void on_kmh(lv_event_t *e) {
    int v = s_kmh + (int)(intptr_t)lv_event_get_user_data(e);
    s_kmh = v < 5 ? 5 : (v > 150 ? 150 : v);
    ui_topspeed_set(s_kmh);
}

// Driving tab: what the dashboard needs to know about the car.
static void build_drive_tab(lv_obj_t *t) {
    setup_label(t, M + 8, 88, T_TOP_SPEED);
    static const int steps[4] = {-10, -1, 1, 10};
    static const char *names[4] = {"-10", "-1", "+1", "+10"};
    for (int i = 0; i < 4; i++) {
        int x = M + 8 + i * 76 + (i >= 2 ? 200 : 0);
        lv_obj_t *b = button(t, x, 112, 68, 56, C_DIM, &lv_font_montserrat_20, names[i]);
        lv_obj_add_event_cb(b, on_kmh, LV_EVENT_CLICKED, (void *)(intptr_t)steps[i]);
    }
    s_kmh_val = label(t, &lv_font_montserrat_32, C_TEXT, "");
    lv_obj_set_width(s_kmh_val, 190);
    lv_obj_set_style_text_align(s_kmh_val, LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_set_pos(s_kmh_val, M + 8 + 2 * 76, 122);
    lv_obj_t *hint = track(label(t, &cjk_16, C_DIM, ""), T_TOP_HINT);
    lv_obj_set_width(hint, 1024 - 2 * (M + 8));
    lv_label_set_long_mode(hint, LV_LABEL_LONG_WRAP);
    lv_obj_set_pos(hint, M + 8, 190);

    setup_label(t, M + 8, 270, T_FFB);
    static const int fsteps[4] = {-10, -5, 5, 10};
    static const char *fnames[4] = {"-10", "-5", "+5", "+10"};
    for (int i = 0; i < 4; i++) {
        int x = M + 8 + i * 76 + (i >= 2 ? 200 : 0);
        lv_obj_t *b = button(t, x, 294, 68, 56, C_DIM, &lv_font_montserrat_20, fnames[i]);
        lv_obj_add_event_cb(b, on_ffb, LV_EVENT_CLICKED, (void *)(intptr_t)fsteps[i]);
    }
    s_ffb_val = label(t, &lv_font_montserrat_32, C_TEXT, "");
    lv_obj_set_width(s_ffb_val, 190);
    lv_obj_set_style_text_align(s_ffb_val, LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_set_pos(s_ffb_val, M + 8 + 2 * 76, 304);
    lv_obj_t *fh = track(label(t, &cjk_16, C_DIM, ""), T_FFB_HINT);
    lv_obj_set_width(fh, 1024 - 2 * (M + 8));
    lv_label_set_long_mode(fh, LV_LABEL_LONG_WRAP);
    lv_obj_set_pos(fh, M + 8, 372);

    setup_label(t, M + 8, 440, T_FLIP);
    lv_obj_t *fb = button(t, M + 8, 464, 260, 56, C_CYAN, &cjk_20, "");
    track(lv_obj_get_child(fb, 0), T_FLIP_BTN);
    lv_obj_add_event_cb(fb, on_flip, LV_EVENT_CLICKED, NULL);
    lv_obj_t *flh = track(label(t, &cjk_16, C_DIM, ""), T_FLIP_HINT);
    lv_obj_set_pos(flh, M + 8 + 280, 482);
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

    // Two tabs: radio settings and status. Pages first, so the header
    // buttons sit on top of them.
    for (int i = 0; i < TABS; i++) {
        lv_obj_t *t = lv_obj_create(p);
        lv_obj_remove_style_all(t);
        lv_obj_set_size(t, 1024, 600);
        lv_obj_remove_flag(t, LV_OBJ_FLAG_SCROLLABLE);
        lv_obj_remove_flag(t, LV_OBJ_FLAG_CLICKABLE);
        s_tab_page[i] = t;
    }
    lv_obj_add_flag(s_tab_page[1], LV_OBJ_FLAG_HIDDEN);
    lv_obj_add_flag(s_tab_page[2], LV_OBJ_FLAG_HIDDEN);
    static const int tabs[TABS] = {T_SETUP_TITLE, T_TAB_DRIVE, T_STATUS};
    for (int i = 0; i < TABS; i++) {
        s_tab_btn[i] = button(p, M + 8 + i * 156, 12, 146, 48, C_CYAN, &cjk_20, "");
        track(lv_obj_get_child(s_tab_btn[i], 0), tabs[i]);
        lv_obj_add_event_cb(s_tab_btn[i], on_tab, LV_EVENT_CLICKED, (void *)(intptr_t)i);
    }
    build_drive_tab(s_tab_page[1]);
    build_status(s_tab_page[2]);
    lv_obj_t *done = button(p, 1024 - M - 160, 12, 160, 48, C_GREEN, &cjk_20, "");
    track(lv_obj_get_child(done, 0), T_DONE);
    lv_obj_add_event_cb(done, on_setup_close, LV_EVENT_CLICKED, NULL);
    static const char *langs[2] = {"简体", "繁體"};
    for (int i = 0; i < 2; i++) {
        s_lang_btn[i] = button(p, 1024 - M - 160 - 16 - (2 - i) * 104, 12, 96, 48, C_DIM, &cjk_20, langs[i]);
        lv_obj_add_event_cb(s_lang_btn[i], on_lang, LV_EVENT_CLICKED, (void *)(intptr_t)i);
    }

    lv_obj_t *r = s_tab_page[0];
    // Which radio transmits.
    setup_label(r, M + 8, 78, T_OUTPUT);
    static const int kinds[RADIO_KINDS] = {-1, T_KIND_SERIAL, T_KIND_PPM};
    const int kw = (1024 - 2 * M - 16 - 2 * 12) / 3;
    for (int i = 0; i < RADIO_KINDS; i++) {
        s_kind_btn[i] = button(r, M + 8 + i * (kw + 12), 100, kw, 60, C_CYAN, &cjk_20, "ELRS");
        if (kinds[i] >= 0) {
            track(lv_obj_get_child(s_kind_btn[i], 0), kinds[i]);
        }
        lv_obj_add_event_cb(s_kind_btn[i], on_kind, LV_EVENT_CLICKED, (void *)(intptr_t)i);
    }

    // MULTI serial protocol.
    setup_label(r, M + 8, 178, T_PROTO_TITLE);
    const int cols = 4, pw = (1024 - 2 * M - 16 - (cols - 1) * 12) / cols;
    for (int i = 0; i < MULTI_PROTO_COUNT && i < 16; i++) {
        int x = M + 8 + (i % cols) * (pw + 12), y = 200 + (i / cols) * 62;
        s_proto_btn[i] = button(r, x, y, pw, 52, C_AMBER, &cjk_20, MULTI_PROTOS[i].name);
        lv_obj_add_event_cb(s_proto_btn[i], on_proto, LV_EVENT_CLICKED, (void *)(intptr_t)i);
    }

    // RX number and fine tune.
    const int ry = 410;
    setup_label(r, M + 8, ry - 2, T_RX_NUM);
    lv_obj_t *b = button(r, M + 8, ry + 20, 56, 52, C_DIM, &lv_font_montserrat_24, "-");
    lv_obj_add_event_cb(b, on_rx, LV_EVENT_CLICKED, (void *)(intptr_t)-1);
    s_rx_val = label(r, &lv_font_montserrat_28, C_TEXT, "0");
    lv_obj_set_pos(s_rx_val, M + 8 + 72, ry + 30);
    b = button(r, M + 8 + 120, ry + 20, 56, 52, C_DIM, &lv_font_montserrat_24, "+");
    lv_obj_add_event_cb(b, on_rx, LV_EVENT_CLICKED, (void *)(intptr_t)1);

    const int ox = 230;
    setup_label(r, ox, ry - 2, T_FINE);
    static const int steps[4] = {-10, -1, 1, 10};
    static const char *step_names[4] = {"-10", "-1", "+1", "+10"};
    for (int i = 0; i < 4; i++) {
        int x = ox + i * 66 + (i >= 2 ? 90 : 0);
        b = button(r, x, ry + 20, 58, 52, C_DIM, &lv_font_montserrat_16, step_names[i]);
        lv_obj_add_event_cb(b, on_option, LV_EVENT_CLICKED, (void *)(intptr_t)steps[i]);
    }
    s_opt_val = label(r, &lv_font_montserrat_28, C_TEXT, "0");
    lv_obj_set_pos(s_opt_val, ox + 2 * 66 + 8, ry + 30);

    // Reversing for the selected output.
    const int vx = 680;
    setup_label(r, vx, ry - 2, T_REVERSE);
    s_rev_steer = button(r, vx, ry + 20, 150, 52, C_CYAN, &cjk_20, "");
    track(lv_obj_get_child(s_rev_steer, 0), T_REV_STEER);
    lv_obj_add_event_cb(s_rev_steer, on_rev_steer, LV_EVENT_CLICKED, NULL);
    s_rev_thr = button(r, vx + 162, ry + 20, 150, 52, C_CYAN, &cjk_20, "");
    track(lv_obj_get_child(s_rev_thr, 0), T_REV_THR);
    lv_obj_add_event_cb(s_rev_thr, on_rev_thr, LV_EVENT_CLICKED, NULL);

    // Bind (MULTI serial) and what to do for the selected output.
    s_bind_btn = button(r, M + 8, 510, 300, 64, C_AMBER, &cjk_24, "");
    s_bind_label = lv_obj_get_child(s_bind_btn, 0);
    lv_obj_add_event_cb(s_bind_btn, on_bind, LV_EVENT_CLICKED, NULL);
    s_setup_hint = label(r, &cjk_16, C_DIM, "");
    lv_obj_set_width(s_setup_hint, 1024 - 2 * M - 340);
    lv_label_set_long_mode(s_setup_hint, LV_LABEL_LONG_WRAP);
    lv_obj_set_pos(s_setup_hint, M + 8 + 320, 514);
}

void display_init(void) {
    bool flip = ui_flip_get();
    bsp_display_cfg_t cfg = {
        .lv_adapter_cfg = ESP_LV_ADAPTER_DEFAULT_CONFIG(),
        .rotation = flip ? ESP_LV_ADAPTER_ROTATE_180 : ESP_LV_ADAPTER_ROTATE_0,
        .tear_avoid_mode = ESP_LV_ADAPTER_TEAR_AVOID_MODE_TRIPLE_PARTIAL,
        // The adapter turns the picture but not the touch panel: flip that too.
        .touch_flags = {.swap_xy = 0, .mirror_x = !flip, .mirror_y = !flip},
    };
    if (bsp_display_start_with_config(&cfg) == NULL) {
        ESP_LOGE(TAG, "display start failed");
        return;
    }
    bsp_display_backlight_on();

    s_lang = ui_lang_get() ? LANG_TC : LANG_SC;
    s_kmh = ui_topspeed_get();
    bsp_display_lock(-1);
    lv_obj_t *scr = lv_screen_active();
    lv_obj_set_style_bg_color(scr, hex(C_BG), 0);
    lv_obj_set_style_bg_opa(scr, LV_OPA_COVER, 0);
    lv_obj_remove_flag(scr, LV_OBJ_FLAG_SCROLLABLE);
    dash_build(scr);
    build_top(scr);
    build_setup();
    bsp_display_unlock();
    ESP_LOGI(TAG, "7\" dashboard up");
}

// ---- update ------------------------------------------------------------------

static void show_status(const display_state_t *s) {
    const control_view_t *c = &s->ctl;
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

    int st = s->wheel ? (int)lroundf(c->steering * 100.0f) : 0;
    int g = s->wheel ? (int)lroundf(c->gas * 100.0f) : 0;
    int b = s->wheel ? (int)lroundf(c->brake * 100.0f) : 0;
    lv_bar_set_value(s_steer_bar, st, LV_ANIM_OFF);
    lv_bar_set_value(s_gas_bar, g, LV_ANIM_OFF);
    lv_bar_set_value(s_brake_bar, b, LV_ANIM_OFF);
    snprintf(buf, sizeof(buf), "%d", g);
    set_text(s_gas_label, buf);
    snprintf(buf, sizeof(buf), "%d", b);
    set_text(s_brake_label, buf);
}

static int notice_id(const char *n) {
    if (n == NULL) {
        return -1;
    }
    if (strcmp(n, "STOP FIRST") == 0) {
        return T_N_STOP;
    }
    if (strcmp(n, "RELEASE PEDALS") == 0) {
        return T_N_PEDALS;
    }
    if (strcmp(n, "ENGINE OFF") == 0) {
        return T_N_ENGINE;
    }
    if (strcmp(n, "NO WHEEL") == 0) {
        return T_NO_WHEEL;
    }
    return -1;
}

static void show_drive(const display_state_t *s) {
    const control_view_t *c = &s->ctl;
    // Whatever needs the driver's attention, most urgent first; each
    // dashboard decides where to show it.
    int n = notice_id(c->notice);
    uint32_t nc = C_AMBER;
    if (n < 0) {
        if (!s->wheel) {
            n = T_NO_WHEEL;
        } else if (!c->engine && strcmp(c->off_reason, "E-STOP") == 0) {
            n = T_ESTOP, nc = C_RED;
        } else if (!c->engine) {
            n = T_PRESS_START, nc = C_DIM;
        } else if (s->cfg.kind == RADIO_ELRS && !s->radio.link) {
            n = T_NO_LINK, nc = C_RED;
        }
    }
    float thr = c->output.throttle;
    const dash_values_t v = {
        .on = c->engine && s->wheel,
        .gear = c->gear,
        // Power: what drives the wheels; braking doesn't count.
        .power = (c->braking || thr * c->speed < 0) ? 0.0f : fabsf(thr),
        .throttle = thr,
        .speed = c->speed,
        .cap = c->gear == GEAR_N ? 0.0f : c->gear_max,
        .steer = s->wheel ? c->steering : 0.0f,
        .notice = n >= 0 ? tr(n) : NULL,
        .top_kmh = s_kmh,
        .notice_color = nc,
    };
    dash_show(&v);
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
    for (int i = 0; i < TABS; i++) {
        highlight(s_tab_btn[i], s_tab == i, C_CYAN);
    }
    snprintf(buf, sizeof(buf), "%d km/h", s_kmh);
    set_text(s_kmh_val, buf);
    snprintf(buf, sizeof(buf), "%d%%", ui_ffb_get());
    set_text(s_ffb_val, buf);
    for (int i = 0; i < MULTI_PROTO_COUNT && i < 16; i++) {
        highlight(s_proto_btn[i], c->proto == i, c->kind == RADIO_MULTI_SERIAL ? C_AMBER : C_DIM);
    }
    snprintf(buf, sizeof(buf), "%d", c->rx_num);
    set_text(s_rx_val, buf);
    snprintf(buf, sizeof(buf), "%d", c->option);
    set_text(s_opt_val, buf);
    highlight(s_rev_steer, c->rev_steer[c->kind], C_CYAN);
    highlight(s_rev_thr, c->rev_thr[c->kind], C_CYAN);

    bool serial = c->kind == RADIO_MULTI_SERIAL, elrs = c->kind == RADIO_ELRS;
    if (serial || elrs) {
        lv_obj_remove_state(s_bind_btn, LV_STATE_DISABLED);
        lv_obj_remove_flag(s_bind_btn, LV_OBJ_FLAG_HIDDEN);
    } else {
        lv_obj_add_flag(s_bind_btn, LV_OBJ_FLAG_HIDDEN);
    }
    if (elrs) {
        set_text(s_bind_label, tr(ui_elrs_duplex_get() ? T_WIRE_TWO : T_WIRE_ONE));
        highlight(s_bind_btn, ui_elrs_duplex_get(), C_CYAN);
    } else if (s->multi.binding) {
        snprintf(buf, sizeof(buf), tr(T_BINDING_FMT), s->multi.bind_left_s);
        set_text(s_bind_label, buf);
        highlight(s_bind_btn, true, C_AMBER);
    } else {
        set_text(s_bind_label, tr(T_BIND));
        highlight(s_bind_btn, false, C_AMBER);
    }
    const char *hint;
    if (elrs) {
        hint = tr(ui_elrs_duplex_get() ? T_HINT_ELRS2 : T_HINT_ELRS);
    } else if (serial) {
        hint = tr(T_HINT_SERIAL);
    } else {
        hint = tr(T_HINT_PPM);
    }
    set_text(s_setup_hint, hint);
}

void display_show(const display_state_t *s) {
    if (s_tab_page[0] == NULL || !bsp_display_lock(20)) {
        return;
    }
    show_drive(s);
    show_status(s);
    show_link(s);
    show_setup(s);
    bsp_display_unlock();
}

#endif  // CONFIG_IDF_TARGET_ESP32P4
