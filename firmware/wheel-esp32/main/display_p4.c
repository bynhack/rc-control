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


#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "bsp/display.h"
#include "bsp/esp-bsp.h"
#include "esp_log.h"
#include "esp_system.h"
#include "ffb.h"
#include "remote.h"
#include "lvgl.h"
#include "dash_p4.h"
#include "ui_p4.h"
#include "sound.h"

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
    [T_HINT_ELRS2] = {"双线接法（Nano 刷成发射机）：Nano 的 RX 接 GPIO28，TX 接 GPIO30。左边按钮切换接法。",
                      "雙線接法（Nano 刷成發射機）：Nano 的 RX 接 GPIO28，TX 接 GPIO30。左邊按鈕切換接法。"},
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
    [T_VOL] = {"引擎声音量", "引擎聲音量"},
    [T_SOUND] = {"引擎声浪", "引擎聲浪"},
    [T_SOUND_ROAD] = {"普通轿车", "普通轎車"},
    [T_SOUND_RALLY] = {"拉力赛车", "拉力賽車"},
    [T_SOUND_M4] = {"宝马 M4", "寶馬 M4"},
    [T_TAB_CAR] = {"车辆", "車輛"},
    [T_CAR_PICK] = {"选择车辆", "選擇車輛"},
    [T_CAR_FMT] = {"车 %d", "車 %d"},
    [T_RENAME] = {"改名", "改名"},
    [T_CAR_HINT] = {"点一下就换成这台车。“发射设置”“驾驶设置”“操控”里改的（发射方式、协议、对频编号、反转、最高车速、声浪、转角、舵量、油门起步点、方向回正）都只存进选中的这台车。",
                    "點一下就換成這台車。「發射設定」「駕駛設定」「操控」裡改的（發射方式、協議、對頻編號、反轉、最高車速、聲浪、轉角、舵量、油門起步點、方向回正）都只存進選中的這台車。"},
    [T_TRIM] = {"方向回正", "方向回正"},
    [T_TRIM_ZERO] = {"居中", "居中"},
    [T_TRIM_L_FMT] = {"偏左 %.1f%%", "偏左 %.1f%%"},
    [T_TRIM_R_FMT] = {"偏右 %.1f%%", "偏右 %.1f%%"},
    [T_TRIM_RESET] = {"归零", "歸零"},
    [T_TRIM_SET] = {"用方向盘调", "用方向盤調"},
    [T_TRIM_SAVE] = {"保存", "保存"},
    [T_TRIM_CANCEL] = {"取消", "取消"},
    [T_TRIM_HINT] = {"方向盘回中时车还往一边跑就用这个。每台车单独保存。",
                     "方向盤回中時車還往一邊跑就用這個。每台車單獨保存。"},
    [T_TRIM_HOW] = {"点火慢慢开，把方向盘转到车刚好走直线的位置，扶住，按“保存”。",
                    "點火慢慢開，把方向盤轉到車剛好走直線的位置，扶住，按「保存」。"},
    [T_FLIP_HINT] = {"板子倒着装时用。点一下会重启屏幕，再点一下翻回来。", "板子倒著裝時用。點一下會重啟螢幕，再點一下翻回來。"},
    [T_FFB_HINT] = {"车速越快，方向盘回正越有力；停车时很轻。第一次试的时候手轻扶方向盘，从小往大调。0% 关闭。",
                    "車速越快，方向盤回正越有力；停車時很輕。第一次試的時候手輕扶方向盤，從小往大調。0% 關閉。"},
    [T_TAB_HANDLE] = {"操控", "操控"},
    [T_RANGE] = {"方向盘转角", "方向盤轉角"},
    [T_RANGE_HINT] = {"方向盘转到这个角度车轮就打死，再往外方向盘会顶住。越大转向越稳，越小越灵敏。Pit House 保持 900°。",
                      "方向盤轉到這個角度車輪就打死，再往外方向盤會頂住。越大轉向越穩，越小越靈敏。Pit House 保持 900°。"},
    [T_EXPO] = {"中心柔和", "中心柔和"},
    [T_EXPO_HINT] = {"越大，方向盘中间一段转向越细，打得越多才转得越快，直线更稳。0% 为线性。",
                     "越大，方向盤中間一段轉向越細，打得越多才轉得越快，直線更穩。0% 為線性。"},
    [T_ENDS] = {"舵量", "舵量"},
    [T_ENDS_FMT] = {"左 %d%%  右 %d%%", "左 %d%%  右 %d%%"},
    [T_ENDS_HINT] = {"打到底时舵机还在响（顶死），或者左右打死的角度不一样时用。",
                     "打到底時舵機還在響（頂死），或者左右打死的角度不一樣時用。"},
    [T_ENDS_HOW] = {"点火，方向盘慢慢往左打，车轮刚好打到底时按“存左”；往右打，按“存右”。调的时候舵机会打到最大。",
                    "點火，方向盤慢慢往左打，車輪剛好打到底時按「存左」；往右打，按「存右」。調的時候舵機會打到最大。"},
    [T_ENDS_RESET] = {"恢复", "恢復"},
    [T_ENDS_SAVE_L] = {"存左", "存左"},
    [T_ENDS_SAVE_R] = {"存右", "存右"},
    [T_SIDE_L_FMT] = {"向左 %.1f%%", "向左 %.1f%%"},
    [T_SIDE_R_FMT] = {"向右 %.1f%%", "向右 %.1f%%"},
    [T_THR] = {"油门死区", "油門死區"},
    [T_THR_FMT] = {"前进 %.1f%%  倒车 %.1f%%", "前進 %.1f%%  倒車 %.1f%%"},
    [T_THR_SET] = {"用油门调", "用油門調"},
    [T_THR_HINT] = {"油门要踩一段车才动，就是电调的死区。设好以后一踩车就走，每个档位都一样。",
                    "油門要踩一段車才動，就是電調的死區。設好以後一踩車就走，每個檔位都一樣。"},
    [T_THR_HOW] = {"点火挂 1 档（倒车挂 R），慢慢踩油门，车刚开始动时按“保存”。前进、倒车各存一次。车会动，先架起来或放在空地上。",
                   "點火掛 1 檔（倒車掛 R），慢慢踩油門，車剛開始動時按「保存」。前進、倒車各存一次。車會動，先架起來或放在空地上。"},
    [T_THR_LIVE_F] = {"前进 %.1f%%", "前進 %.1f%%"},
    [T_THR_LIVE_R] = {"倒车 %.1f%%", "倒車 %.1f%%"},
    [T_THR_LIVE_N] = {"挂 1 档或 R 档", "掛 1 檔或 R 檔"},
    [T_SAVED_FMT] = {"已存：%s", "已存：%s"},
    [T_STEER_DB] = {"方向死区", "方向死區"},
    [T_STEER_DB_FMT] = {"左 %.1f%%  右 %.1f%%", "左 %.1f%%  右 %.1f%%"},
    [T_STEER_DB_SET] = {"用方向盘调", "用方向盤調"},
    [T_STEER_DB_HINT] = {"方向盘离开中间要转一段车轮才动时用（舵机或转向的死区）。设好以后方向盘一动车轮就跟着动。",
                         "方向盤離開中間要轉一段車輪才動時用（舵機或轉向的死區）。設好以後方向盤一動車輪就跟著動。"},
    [T_STEER_DB_HOW] = {"点火，方向盘从中间慢慢往左转，车轮刚开始动时按“存左”；再往右，按“存右”。",
                        "點火，方向盤從中間慢慢往左轉，車輪剛開始動時按「存左」；再往右，按「存右」。"},
    [T_KIND_REMOTE] = {"遥控器主板", "遙控器主板"},
    [T_SUB_REMOTE] = {"方向盘  >  遥控器主板  >  车", "方向盤  >  遙控器主板  >  車"},
    [T_TX_REMOTE] = {"DAC 输出中", "DAC 輸出中"},
    [T_NO_DAC] = {"找不到 DAC", "找不到 DAC"},
    [T_HINT_REMOTE] = {"车子原装遥控器的主板，摇杆电位器换成 MCP4728（I2C 0x60）。校准点在固件里，"
                       "用电脑上的 remote_tune.html 精调。遥控器跟车照原来的方式对频。",
                       "車子原裝遙控器的主板，搖桿電位器換成 MCP4728（I2C 0x60）。校準點在固件裡，"
                       "用電腦上的 remote_tune.html 精調。遙控器跟車照原來的方式對頻。"},
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
#define MAX_TLABELS 128
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
    radio_rev_flip(c, false);
}

static void flip_thr(radio_config_t *c, intptr_t unused) {
    radio_rev_flip(c, true);
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

// Handling (the 操控 tab). The trim, end points and throttle start are set
// on the dashboard: a panel shows the live value, the driver drives and
// saves. radio_cal_set() leaves the step being set out meanwhile.
static lv_obj_t *s_cal_panel, *s_cal_title, *s_cal_live, *s_cal_saved, *s_cal_how, *s_cal_btn[3];
static float s_steer_now; // the car's steering before trim, from the last display_show()
static float s_cal_out;   // what the step being set sees: steering before end points, or throttle
static gear_t s_gear_now;
enum { ACT_CANCEL, ACT_SAVE, ACT_SAVE_L, ACT_SAVE_R };

static int clampi(int v, int lo, int hi) {
    return v < lo ? lo : (v > hi ? hi : v);
}

static void set_trim(radio_config_t *c, intptr_t permille) {
    c->trim = (int16_t)clampi((int)permille, -TRIM_MAX, TRIM_MAX);
}

static void set_end(radio_config_t *c, intptr_t side_permille) {
    int side = side_permille < 0 ? 0 : 1;
    c->steer_max[side] = (uint16_t)clampi(abs((int)side_permille), STEER_MAX_MIN, 1000);
}

static void reset_ends(radio_config_t *c, intptr_t unused) {
    c->steer_max[0] = c->steer_max[1] = 1000;
}

static void set_thr_start(radio_config_t *c, intptr_t rev_permille) {
    int rev = rev_permille < 0 ? 1 : 0;
    c->thr_start[rev] = (uint16_t)clampi(abs((int)rev_permille), 0, THR_START_MAX);
}

static void reset_thr(radio_config_t *c, intptr_t unused) {
    c->thr_start[0] = c->thr_start[1] = 0;
}

static void set_steer_start(radio_config_t *c, intptr_t side_permille) {
    int side = side_permille < 0 ? 0 : 1;
    c->steer_start[side] = (uint16_t)clampi(abs((int)side_permille), 0, STEER_START_MAX);
}

static void reset_steer_start(radio_config_t *c, intptr_t unused) {
    c->steer_start[0] = c->steer_start[1] = 0;
}

static void add_range(radio_config_t *c, intptr_t d) {
    c->steer_deg = (uint16_t)clampi(c->steer_deg + (int)d, STEER_DEG_MIN, WHEEL_DEG);
}

static void add_expo(radio_config_t *c, intptr_t d) {
    c->expo = (uint8_t)clampi(c->expo + (int)d, 0, EXPO_MAX);
}

static void on_trim_reset(lv_event_t *e) {
    edit(set_trim, 0);
}

static void on_ends_reset(lv_event_t *e) {
    edit(reset_ends, 0);
}

static void on_thr_reset(lv_event_t *e) {
    edit(reset_thr, 0);
}

static void on_steer_db_reset(lv_event_t *e) {
    edit(reset_steer_start, 0);
}

static void on_range(lv_event_t *e) {
    edit(add_range, (intptr_t)lv_event_get_user_data(e));
}

static void on_expo(lv_event_t *e) {
    edit(add_expo, (intptr_t)lv_event_get_user_data(e));
}

// The panel's buttons per step: left (hidden if none), middle, right.
static void cal_open(radio_cal_t cal) {
    static const int title[] = {
        [CAL_TRIM] = T_TRIM, [CAL_ENDS] = T_ENDS, [CAL_THROTTLE] = T_THR, [CAL_STEER_START] = T_STEER_DB};
    static const int how[] = {[CAL_TRIM] = T_TRIM_HOW,
                              [CAL_ENDS] = T_ENDS_HOW,
                              [CAL_THROTTLE] = T_THR_HOW,
                              [CAL_STEER_START] = T_STEER_DB_HOW};
    static const int btn[][3] = {[CAL_TRIM] = {-1, T_TRIM_SAVE, T_TRIM_CANCEL},
                                 [CAL_ENDS] = {T_ENDS_SAVE_L, T_ENDS_SAVE_R, T_DONE},
                                 [CAL_THROTTLE] = {-1, T_TRIM_SAVE, T_TRIM_CANCEL},
                                 [CAL_STEER_START] = {T_ENDS_SAVE_L, T_ENDS_SAVE_R, T_DONE}};
    static const int act[][3] = {[CAL_TRIM] = {0, ACT_SAVE, ACT_CANCEL},
                                 [CAL_ENDS] = {ACT_SAVE_L, ACT_SAVE_R, ACT_CANCEL},
                                 [CAL_THROTTLE] = {0, ACT_SAVE, ACT_CANCEL},
                                 [CAL_STEER_START] = {ACT_SAVE_L, ACT_SAVE_R, ACT_CANCEL}};
    radio_cal_set(cal);
    set_text(s_cal_title, tr(title[cal]));
    set_text(s_cal_how, tr(how[cal]));
    for (int i = 0; i < 3; i++) {
        if (btn[cal][i] < 0) {
            lv_obj_add_flag(s_cal_btn[i], LV_OBJ_FLAG_HIDDEN);
            continue;
        }
        lv_obj_remove_flag(s_cal_btn[i], LV_OBJ_FLAG_HIDDEN);
        set_text(lv_obj_get_child(s_cal_btn[i], 0), tr(btn[cal][i]));
        lv_obj_set_user_data(s_cal_btn[i], (void *)(intptr_t)act[cal][i]);
    }
    lv_obj_add_flag(s_setup, LV_OBJ_FLAG_HIDDEN);
    lv_obj_remove_flag(s_cal_panel, LV_OBJ_FLAG_HIDDEN);
}

static void on_cal_start(lv_event_t *e) {
    cal_open((radio_cal_t)(intptr_t)lv_event_get_user_data(e));
}

static void cal_close(void) {
    radio_cal_set(CAL_NONE);
    lv_obj_add_flag(s_cal_panel, LV_OBJ_FLAG_HIDDEN);
}

static void on_cal_btn(lv_event_t *e) {
    int a = (int)(intptr_t)lv_obj_get_user_data(lv_event_get_target(e));
    radio_cal_t cal = radio_cal_get();
    int v = (int)lroundf(s_cal_out * 1000.0f);
    if (a == ACT_CANCEL) {
        cal_close();
    } else if (cal == CAL_TRIM) {
        edit(set_trim, (intptr_t)lroundf(s_steer_now * 1000.0f));
        cal_close();
        ffb_recentre(); // the wheel is still held where the car ran straight
    } else if (cal == CAL_ENDS) {
        // Each side from its own side of the centre only.
        if ((a == ACT_SAVE_L && v < 0) || (a == ACT_SAVE_R && v > 0)) {
            edit(set_end, v);
        }
    } else if (cal == CAL_STEER_START) {
        if ((a == ACT_SAVE_L && v < 0) || (a == ACT_SAVE_R && v > 0)) {
            edit(set_steer_start, v);
        }
    } else if (cal == CAL_THROTTLE) {
        // Forward in a forward gear, reverse in R; nothing in N or braking.
        if ((s_gear_now >= GEAR_1 && v > 0) || (s_gear_now == GEAR_R && v < 0)) {
            edit(set_thr_start, v);
            cal_close();
        }
    }
}

// "偏右 2.4%" for thousandths of full lock.
static void trim_text(char *buf, size_t n, int permille) {
    if (permille == 0) {
        snprintf(buf, n, "%s", tr(T_TRIM_ZERO));
    } else {
        snprintf(buf, n, tr(permille < 0 ? T_TRIM_L_FMT : T_TRIM_R_FMT), abs(permille) / 10.0);
    }
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

enum { TAB_CAR, TAB_RADIO, TAB_DRIVE, TAB_HANDLE, TAB_STATUS, TABS };
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
    if (radio_cal_get() != CAL_NONE) {
        cal_close();
    }
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

static lv_obj_t *s_car_top; // the active car's name on the dashboard

static void build_top(lv_obj_t *scr) {
    lv_obj_t *setup = button(scr, 1024 - M - 64, 10, 64, 48, C_DIM, &lv_font_montserrat_24, LV_SYMBOL_SETTINGS);
    lv_obj_set_style_border_color(setup, hex(C_EDGE), 0);
    lv_obj_set_style_bg_opa(setup, LV_OPA_10, 0);
    lv_obj_add_event_cb(setup, on_setup_open, LV_EVENT_CLICKED, NULL);
    s_car_top = label(scr, &cjk_16, C_DIM, "");
    lv_obj_set_width(s_car_top, 200);
    lv_obj_set_style_text_align(s_car_top, LV_TEXT_ALIGN_RIGHT, 0);
    lv_obj_set_pos(s_car_top, 1024 - M - 64 - 12 - 200, 24);
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

static lv_obj_t *s_vol_val, *s_trim_val;

static lv_obj_t *s_sound_btn[SOUND_VOICES];

static void on_sound(lv_event_t *e) {
    ui_sound_set((int)(intptr_t)lv_event_get_user_data(e));
}

static void on_vol(lv_event_t *e) {
    int v = ui_vol_get() + (int)(intptr_t)lv_event_get_user_data(e);
    ui_vol_set(v < 0 ? 0 : (v > 100 ? 100 : v));
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

    // Engine sound: which car, right of the top speed row; volume right of
    // the force feedback row.
    const int vx = 600;
    setup_label(t, vx, 88, T_SOUND);
    static const int sound_names[SOUND_VOICES] = {T_SOUND_ROAD, T_SOUND_RALLY, T_SOUND_M4};
    for (int i = 0; i < SOUND_VOICES; i++) {
        s_sound_btn[i] = button(t, vx + i * 128, 112, 120, 56, C_AMBER, &cjk_20, "");
        track(lv_obj_get_child(s_sound_btn[i], 0), sound_names[i]);
        lv_obj_add_event_cb(s_sound_btn[i], on_sound, LV_EVENT_CLICKED, (void *)(intptr_t)i);
    }
    setup_label(t, vx, 270, T_VOL);
    for (int i = 0; i < 2; i++) {
        lv_obj_t *b = button(t, vx + i * 260, 294, 68, 56, C_DIM, &lv_font_montserrat_20, i ? "+10" : "-10");
        lv_obj_add_event_cb(b, on_vol, LV_EVENT_CLICKED, (void *)(intptr_t)(i ? 10 : -10));
    }
    s_vol_val = label(t, &lv_font_montserrat_32, C_TEXT, "");
    lv_obj_set_width(s_vol_val, 180);
    lv_obj_set_style_text_align(s_vol_val, LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_set_pos(s_vol_val, vx + 74, 304);

    setup_label(t, M + 8, 440, T_FLIP);
    lv_obj_t *fb = button(t, M + 8, 464, 260, 56, C_CYAN, &cjk_20, "");
    track(lv_obj_get_child(fb, 0), T_FLIP_BTN);
    lv_obj_add_event_cb(fb, on_flip, LV_EVENT_CLICKED, NULL);
    lv_obj_t *flh = track(label(t, &cjk_16, C_DIM, ""), T_FLIP_HINT);
    lv_obj_set_width(flh, vx - M - 8 - 24);
    lv_label_set_long_mode(flh, LV_LABEL_LONG_WRAP);
    lv_obj_set_pos(flh, M + 8, 530);
}

// A value between minus and plus buttons; returns the value label.
static lv_obj_t *stepper(lv_obj_t *t, int x, int y, const int steps[], const char *const names[], int n,
                         lv_event_cb_t cb) {
    const int bw = 64, vw = 140;
    for (int i = 0; i < n; i++) {
        int bx = x + i * (bw + 6) + (i >= n / 2 ? vw + 12 : 0);
        lv_obj_t *b = button(t, bx, y, bw, 56, C_DIM, &lv_font_montserrat_20, names[i]);
        lv_obj_add_event_cb(b, cb, LV_EVENT_CLICKED, (void *)(intptr_t)steps[i]);
    }
    lv_obj_t *v = label(t, &cjk_32, C_TEXT, "");
    lv_obj_set_width(v, vw);
    lv_obj_set_style_text_align(v, LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_set_pos(v, x + (n / 2) * (bw + 6), y + 10);
    return v;
}

// A value, a button that sets it on the dashboard, and one back to the
// default; returns the value label.
static lv_obj_t *cal_row(lv_obj_t *t, int x, int y, int set_id, radio_cal_t cal, int reset_id, lv_event_cb_t reset) {
    lv_obj_t *v = label(t, &cjk_20, C_TEXT, "");
    lv_obj_set_width(v, 200);
    lv_label_set_long_mode(v, LV_LABEL_LONG_WRAP);
    lv_obj_set_pos(v, x, y + 4);
    lv_obj_t *sb = button(t, x + 206, y, 140, 56, C_AMBER, &cjk_20, "");
    track(lv_obj_get_child(sb, 0), set_id);
    lv_obj_add_event_cb(sb, on_cal_start, LV_EVENT_CLICKED, (void *)(intptr_t)cal);
    lv_obj_t *rb = button(t, x + 352, y, 110, 56, C_DIM, &cjk_20, "");
    track(lv_obj_get_child(rb, 0), reset_id);
    lv_obj_add_event_cb(rb, reset, LV_EVENT_CLICKED, NULL);
    return v;
}

static lv_obj_t *hint_at(lv_obj_t *t, int x, int y, int id) {
    lv_obj_t *h = track(label(t, &cjk_16, C_DIM, ""), id);
    lv_obj_set_width(h, 470);
    lv_label_set_long_mode(h, LV_LABEL_LONG_WRAP);
    lv_obj_set_pos(h, x, y);
    return h;
}

static lv_obj_t *s_range_val, *s_expo_val, *s_ends_val, *s_thr_val, *s_steer_db_val;

// Handling tab: how the active car answers the wheel and the pedals.
static void build_handle_tab(lv_obj_t *t) {
    const int lx = M + 8, rx = 532;
    static const int rsteps[4] = {-90, -10, 10, 90};
    static const char *const rnames[4] = {"-90", "-10", "+10", "+90"};
    setup_label(t, lx, 78, T_RANGE);
    s_range_val = stepper(t, lx, 102, rsteps, rnames, 4, on_range);
    hint_at(t, lx, 166, T_RANGE_HINT);

    static const int esteps[2] = {-10, 10};
    static const char *const enames[2] = {"-10", "+10"};
    setup_label(t, rx, 78, T_EXPO);
    s_expo_val = stepper(t, rx, 102, esteps, enames, 2, on_expo);
    hint_at(t, rx, 166, T_EXPO_HINT);

    setup_label(t, lx, 250, T_ENDS);
    s_ends_val = cal_row(t, lx, 274, T_TRIM_SET, CAL_ENDS, T_ENDS_RESET, on_ends_reset);
    hint_at(t, lx, 338, T_ENDS_HINT);

    setup_label(t, rx, 250, T_THR);
    s_thr_val = cal_row(t, rx, 274, T_THR_SET, CAL_THROTTLE, T_TRIM_RESET, on_thr_reset);
    hint_at(t, rx, 338, T_THR_HINT);

    setup_label(t, lx, 420, T_TRIM);
    s_trim_val = cal_row(t, lx, 444, T_TRIM_SET, CAL_TRIM, T_TRIM_RESET, on_trim_reset);
    hint_at(t, lx, 508, T_TRIM_HINT);

    setup_label(t, rx, 420, T_STEER_DB);
    s_steer_db_val = cal_row(t, rx, 444, T_STEER_DB_SET, CAL_STEER_START, T_TRIM_RESET, on_steer_db_reset);
    hint_at(t, rx, 508, T_STEER_DB_HINT);
}

// ---- cars --------------------------------------------------------------------

static lv_obj_t *s_car_btn[CAR_COUNT], *s_car_name[CAR_COUNT], *s_car_info[CAR_COUNT];
static lv_obj_t *s_kbd_box, *s_kbd_ta;

static void highlight(lv_obj_t *b, bool on, uint32_t color);

static void car_name(int i, char *buf, size_t n) {
    car_t c = car_get(i);
    if (c.name[0]) {
        snprintf(buf, n, "%s", c.name);
    } else {
        snprintf(buf, n, tr(T_CAR_FMT), i + 1);
    }
}

static void on_car(lv_event_t *e) {
    car_select((int)(intptr_t)lv_event_get_user_data(e));
    s_kmh = ui_topspeed_get();
}

static void on_rename_done(lv_event_t *e) {
    if (lv_event_get_code(e) == LV_EVENT_READY) {
        car_rename(car_active(), lv_textarea_get_text(s_kbd_ta));
    }
    lv_obj_add_flag(s_kbd_box, LV_OBJ_FLAG_HIDDEN);
}

static void on_rename(lv_event_t *e) {
    car_t c = car_get(car_active());
    lv_textarea_set_text(s_kbd_ta, c.name);
    lv_obj_remove_flag(s_kbd_box, LV_OBJ_FLAG_HIDDEN);
}

// Cars tab: pick the car you are driving; the radio and driving tabs then
// edit that car.
static void build_car_tab(lv_obj_t *t) {
    setup_label(t, M + 8, 78, T_CAR_PICK);
    const int cols = 3, cw = (1024 - 2 * M - 16 - (cols - 1) * 12) / cols, ch = 150;
    for (int i = 0; i < CAR_COUNT; i++) {
        int x = M + 8 + (i % cols) * (cw + 12), y = 100 + (i / cols) * (ch + 12);
        lv_obj_t *b = button(t, x, y, cw, ch, C_CYAN, &cjk_24, "");
        lv_obj_add_event_cb(b, on_car, LV_EVENT_CLICKED, (void *)(intptr_t)i);
        s_car_btn[i] = b;
        s_car_name[i] = lv_obj_get_child(b, 0);
        lv_obj_align(s_car_name[i], LV_ALIGN_TOP_LEFT, 8, 10);
        s_car_info[i] = label(b, &cjk_16, C_DIM, "");
        lv_obj_set_width(s_car_info[i], cw - 32);
        lv_label_set_long_mode(s_car_info[i], LV_LABEL_LONG_WRAP);
        lv_obj_set_style_text_line_space(s_car_info[i], 6, 0);
        lv_obj_align(s_car_info[i], LV_ALIGN_TOP_LEFT, 8, 56);
    }
    lv_obj_t *rn = button(t, M + 8, 440, 220, 60, C_CYAN, &cjk_20, "");
    track(lv_obj_get_child(rn, 0), T_RENAME);
    lv_obj_add_event_cb(rn, on_rename, LV_EVENT_CLICKED, NULL);
    lv_obj_t *hint = track(label(t, &cjk_16, C_DIM, ""), T_CAR_HINT);
    lv_obj_set_width(hint, 1024 - 2 * M - 260);
    lv_label_set_long_mode(hint, LV_LABEL_LONG_WRAP);
    lv_obj_set_pos(hint, M + 8 + 240, 446);

    // Rename: Latin letters and digits (the fonts carry no other input).
    s_kbd_box = lv_obj_create(t);
    lv_obj_remove_style_all(s_kbd_box);
    lv_obj_set_size(s_kbd_box, 1024, 600 - 70);
    lv_obj_set_pos(s_kbd_box, 0, 70);
    lv_obj_set_style_bg_color(s_kbd_box, hex(C_BG), 0);
    lv_obj_set_style_bg_opa(s_kbd_box, LV_OPA_COVER, 0);
    lv_obj_add_flag(s_kbd_box, LV_OBJ_FLAG_HIDDEN);
    s_kbd_ta = lv_textarea_create(s_kbd_box);
    lv_textarea_set_one_line(s_kbd_ta, true);
    lv_textarea_set_max_length(s_kbd_ta, CAR_NAME_LEN - 1);
    lv_obj_set_style_text_font(s_kbd_ta, &lv_font_montserrat_28, 0);
    lv_obj_set_size(s_kbd_ta, 600, 64);
    lv_obj_set_pos(s_kbd_ta, (1024 - 600) / 2, 16);
    lv_obj_t *kb = lv_keyboard_create(s_kbd_box);
    lv_obj_set_size(kb, 1024, 420);
    lv_obj_align(kb, LV_ALIGN_BOTTOM_MID, 0, 0);
    lv_obj_set_style_text_font(kb, &lv_font_montserrat_24, 0);
    lv_keyboard_set_textarea(kb, s_kbd_ta);
    lv_obj_add_event_cb(kb, on_rename_done, LV_EVENT_READY, NULL);
    lv_obj_add_event_cb(kb, on_rename_done, LV_EVENT_CANCEL, NULL);
}

static void show_cars(void) {
    char buf[96], name[48];
    static const int sounds[SOUND_VOICES] = {T_SOUND_ROAD, T_SOUND_RALLY, T_SOUND_M4};
    for (int i = 0; i < CAR_COUNT; i++) {
        car_t c = car_get(i);
        highlight(s_car_btn[i], car_active() == i, C_CYAN);
        car_name(i, name, sizeof(name));
        set_text(s_car_name[i], name);
        const char *radio = c.radio.kind == RADIO_ELRS          ? "ELRS"
                            : c.radio.kind == RADIO_MULTI_PPM ? tr(T_KIND_PPM)
                            : c.radio.kind == RADIO_REMOTE    ? tr(T_KIND_REMOTE)
                                                              : MULTI_PROTOS[c.radio.proto].name;
        snprintf(buf, sizeof(buf), "%s\n%d km/h  ·  %s", radio, c.top_kmh,
                 tr(sounds[c.sound < SOUND_VOICES ? c.sound : 0]));
        set_text(s_car_info[i], buf);
    }
    car_name(car_active(), name, sizeof(name));
    set_text(s_car_top, name);
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

    // Tabs: car, radio, driving, status. Pages first, so the header
    // buttons sit on top of them.
    for (int i = 0; i < TABS; i++) {
        lv_obj_t *t = lv_obj_create(p);
        lv_obj_remove_style_all(t);
        lv_obj_set_size(t, 1024, 600);
        lv_obj_remove_flag(t, LV_OBJ_FLAG_SCROLLABLE);
        lv_obj_remove_flag(t, LV_OBJ_FLAG_CLICKABLE);
        s_tab_page[i] = t;
    }
    for (int i = 1; i < TABS; i++) {
        lv_obj_add_flag(s_tab_page[i], LV_OBJ_FLAG_HIDDEN);
    }
    static const int tabs[TABS] = {T_TAB_CAR, T_SETUP_TITLE, T_TAB_DRIVE, T_TAB_HANDLE, T_STATUS};
    for (int i = 0; i < TABS; i++) {
        s_tab_btn[i] = button(p, M + 8 + i * 118, 12, 112, 48, C_CYAN, &cjk_20, "");
        track(lv_obj_get_child(s_tab_btn[i], 0), tabs[i]);
        lv_obj_add_event_cb(s_tab_btn[i], on_tab, LV_EVENT_CLICKED, (void *)(intptr_t)i);
    }
    build_car_tab(s_tab_page[TAB_CAR]);
    build_drive_tab(s_tab_page[TAB_DRIVE]);
    build_handle_tab(s_tab_page[TAB_HANDLE]);
    build_status(s_tab_page[TAB_STATUS]);
    lv_obj_t *done = button(p, 1024 - M - 160, 12, 160, 48, C_GREEN, &cjk_20, "");
    track(lv_obj_get_child(done, 0), T_DONE);
    lv_obj_add_event_cb(done, on_setup_close, LV_EVENT_CLICKED, NULL);
    static const char *langs[2] = {"简体", "繁體"};
    for (int i = 0; i < 2; i++) {
        s_lang_btn[i] = button(p, 1024 - M - 160 - 16 - (2 - i) * 104, 12, 96, 48, C_DIM, &cjk_20, langs[i]);
        lv_obj_add_event_cb(s_lang_btn[i], on_lang, LV_EVENT_CLICKED, (void *)(intptr_t)i);
    }

    lv_obj_t *r = s_tab_page[TAB_RADIO];
    // Which radio transmits.
    setup_label(r, M + 8, 78, T_OUTPUT);
    static const int kinds[RADIO_KINDS] = {-1, T_KIND_SERIAL, T_KIND_PPM, T_KIND_REMOTE};
    const int kw = (1024 - 2 * M - 16 - (RADIO_KINDS - 1) * 12) / RADIO_KINDS;
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

// The setting panel over the dashboard (trim, end points, throttle start),
// hidden until one of the 操控 tab's buttons; cal_open() fills it in.
static void build_cal_panel(lv_obj_t *scr) {
    const int w = 600, h = 230;
    lv_obj_t *p = lv_obj_create(scr);
    lv_obj_remove_style_all(p);
    lv_obj_set_size(p, w, h);
    lv_obj_set_pos(p, (1024 - w) / 2, 600 - h - 24);
    lv_obj_set_style_radius(p, 16, 0);
    lv_obj_set_style_bg_color(p, hex(C_BG), 0);
    lv_obj_set_style_bg_opa(p, LV_OPA_90, 0);
    lv_obj_set_style_border_color(p, hex(C_AMBER), 0);
    lv_obj_set_style_border_width(p, 2, 0);
    lv_obj_remove_flag(p, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_add_flag(p, LV_OBJ_FLAG_HIDDEN);
    s_cal_panel = p;
    s_cal_title = label(p, &cjk_16, C_DIM, "");
    lv_obj_set_pos(s_cal_title, 20, 14);
    s_cal_live = label(p, &cjk_32, C_TEXT, "");
    lv_obj_set_pos(s_cal_live, 20, 40);
    s_cal_saved = label(p, &cjk_16, C_DIM, "");
    lv_obj_set_width(s_cal_saved, 300);
    lv_obj_set_style_text_align(s_cal_saved, LV_TEXT_ALIGN_RIGHT, 0);
    lv_obj_set_pos(s_cal_saved, w - 20 - 300, 52);
    s_cal_how = label(p, &cjk_16, C_DIM, "");
    lv_obj_set_width(s_cal_how, w - 40);
    lv_label_set_long_mode(s_cal_how, LV_LABEL_LONG_WRAP);
    lv_obj_set_pos(s_cal_how, 20, 90);
    for (int i = 0; i < 3; i++) {
        s_cal_btn[i] = button(p, w - 20 - (3 - i) * 140 - (2 - i) * 12, h - 20 - 56, 140, 56,
                              i == 2 ? C_DIM : C_GREEN, &cjk_20, "");
        lv_obj_add_event_cb(s_cal_btn[i], on_cal_btn, LV_EVENT_CLICKED, NULL);
    }
}

static void ends_text(char *buf, size_t n, const radio_config_t *c) {
    snprintf(buf, n, tr(T_ENDS_FMT), (c->steer_max[0] + 5) / 10, (c->steer_max[1] + 5) / 10);
}

static void thr_text(char *buf, size_t n, const radio_config_t *c) {
    snprintf(buf, n, tr(T_THR_FMT), c->thr_start[0] / 10.0, c->thr_start[1] / 10.0);
}

static void steer_db_text(char *buf, size_t n, const radio_config_t *c) {
    snprintf(buf, n, tr(T_STEER_DB_FMT), c->steer_start[0] / 10.0, c->steer_start[1] / 10.0);
}

// "向左 4.2%", or centred.
static void side_text(char *buf, size_t n, float v) {
    int pm = (int)lroundf(v * 1000.0f);
    if (pm == 0) {
        snprintf(buf, n, "%s", tr(T_TRIM_ZERO));
    } else {
        snprintf(buf, n, tr(pm < 0 ? T_SIDE_L_FMT : T_SIDE_R_FMT), abs(pm) / 10.0);
    }
}

static void show_cal(const display_state_t *s) {
    const radio_config_t *c = &s->cfg;
    s_steer_now = radio_steer_base(c, s->ctl.steering);
    s_gear_now = s->ctl.gear;
    radio_cal_t cal = radio_cal_get();
    if (cal == CAL_NONE || lv_obj_has_flag(s_cal_panel, LV_OBJ_FLAG_HIDDEN)) {
        return;
    }
    char buf[64], saved[64];
    if (cal == CAL_TRIM) {
        s_cal_out = s_steer_now;
        trim_text(buf, sizeof(buf), (int)lroundf(s_steer_now * 1000.0f));
        saved[0] = 0;
    } else if (cal == CAL_ENDS) {
        // What the servo gets with no end points (trim included).
        float v = s_steer_now + c->trim / 1000.0f;
        s_cal_out = v < -1.0f ? -1.0f : (v > 1.0f ? 1.0f : v);
        side_text(buf, sizeof(buf), s_cal_out);
        ends_text(saved, sizeof(saved), c);
    } else if (cal == CAL_STEER_START) {
        // The wheel shaped, without the dead band (left out while it's set).
        s_cal_out = s_steer_now;
        side_text(buf, sizeof(buf), s_cal_out);
        steer_db_text(saved, sizeof(saved), c);
    } else {
        s_cal_out = s->ctl.output.throttle;
        if (s_gear_now == GEAR_N) {
            snprintf(buf, sizeof(buf), "%s", tr(T_THR_LIVE_N));
        } else {
            snprintf(buf, sizeof(buf), tr(s_gear_now == GEAR_R ? T_THR_LIVE_R : T_THR_LIVE_F),
                     fabsf(s_cal_out) * 100.0f);
        }
        thr_text(saved, sizeof(saved), c);
    }
    set_text(s_cal_live, buf);
    char line[80];
    if (saved[0]) {
        snprintf(line, sizeof(line), tr(T_SAVED_FMT), saved);
    } else {
        line[0] = 0;
    }
    set_text(s_cal_saved, line);
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
    build_cal_panel(scr);
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
        } else if (s->cfg.kind == RADIO_REMOTE && !remote_status().found) {
            n = T_NO_DAC, nc = C_RED;
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
    } else if (cfg->kind == RADIO_REMOTE) {
        set_text(s_sub, tr(T_SUB_REMOTE));
    } else {
        set_text(s_sub, tr(T_SUB_PPM));
    }
    if (cfg->kind == RADIO_REMOTE) {
        // The toy remote: one way, no telemetry; show whether the DAC answers.
        remote_status_t rs = remote_status();
        set_text(s_tx_label, tr(rs.found ? T_TX_REMOTE : T_NO_DAC));
        lv_obj_set_style_text_color(s_tx_label, hex(rs.found ? C_CYAN : C_RED), 0);
        snprintf(buf, sizeof(buf), "DAC %u / %u", rs.steer, rs.thr);
        set_text(s_rssi_label, buf);
        set_text(s_lq_label, tr(T_NO_TELEM));
        for (int i = 0; i < LQ_SEGS; i++) {
            lv_obj_set_style_bg_color(s_lq_seg[i], hex(C_TRACK), 0);
        }
    } else if (cfg->kind != RADIO_ELRS) {
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
    snprintf(buf, sizeof(buf), "%d%%", ui_vol_get());
    set_text(s_vol_val, buf);
    for (int i = 0; i < SOUND_VOICES; i++) {
        highlight(s_sound_btn[i], ui_sound_get() == i, C_AMBER);
    }
    for (int i = 0; i < MULTI_PROTO_COUNT && i < 16; i++) {
        highlight(s_proto_btn[i], c->proto == i, c->kind == RADIO_MULTI_SERIAL ? C_AMBER : C_DIM);
    }
    snprintf(buf, sizeof(buf), "%d", c->rx_num);
    set_text(s_rx_val, buf);
    snprintf(buf, sizeof(buf), "%d", c->option);
    set_text(s_opt_val, buf);
    highlight(s_rev_steer, radio_rev(c, false), C_CYAN);
    trim_text(buf, sizeof(buf), c->trim);
    set_text(s_trim_val, buf);
    snprintf(buf, sizeof(buf), "%d°", c->steer_deg);
    set_text(s_range_val, buf);
    snprintf(buf, sizeof(buf), "%d%%", c->expo);
    set_text(s_expo_val, buf);
    ends_text(buf, sizeof(buf), c);
    set_text(s_ends_val, buf);
    thr_text(buf, sizeof(buf), c);
    set_text(s_thr_val, buf);
    steer_db_text(buf, sizeof(buf), c);
    set_text(s_steer_db_val, buf);
    highlight(s_rev_thr, radio_rev(c, true), C_CYAN);

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
    } else if (c->kind == RADIO_REMOTE) {
        hint = tr(T_HINT_REMOTE);
    } else {
        hint = tr(T_HINT_PPM);
    }
    set_text(s_setup_hint, hint);
}

void display_show(const display_state_t *s) {
    if (s_tab_page[TAB_CAR] == NULL || !bsp_display_lock(20)) {
        return;
    }
    show_drive(s);
    show_cal(s);
    show_status(s);
    show_link(s);
    show_setup(s);
    show_cars();
    bsp_display_unlock();
}
