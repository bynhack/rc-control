#include "display.h"

#include "sdkconfig.h"

#if CONFIG_IDF_TARGET_ESP32S3

#include <math.h>
#include <stdio.h>
#include <string.h>

#include "driver/spi_master.h"
#include "esp_lcd_gc9a01.h"
#include "esp_lcd_panel_io.h"
#include "esp_lcd_panel_ops.h"
#include "esp_log.h"
#include "esp_lvgl_port.h"
#include "wheel.h"

static const char *TAG = "display";

#define PIN_SCLK 12
#define PIN_MOSI 11
#define PIN_CS 10
#define PIN_DC 9
#define PIN_RST 8
#define LCD_HOST SPI2_HOST
#define LCD_SIZE 240
// 80 MHz is the GC9A01 limit; jumper wires are happier at 40.
#define LCD_PCLK_HZ (40 * 1000 * 1000)
#define LCD_DRAW_LINES 40

// Same palette as the PC dashboard.
#define COL_BG 0x05070c
#define COL_TRACK 0x161c28
#define COL_DIM 0x5c6a80
#define COL_TEXT 0xe8eef8
#define COL_FWD 0x22d3ee
#define COL_REV 0xfb923c
#define COL_STEER 0xa78bfa
#define COL_OK 0x34d399
#define COL_WARN 0xf59e0b
#define COL_STOP 0xef4444

static lv_obj_t *s_throttle_arc;
static lv_obj_t *s_steer_arc;
static lv_obj_t *s_value;
static lv_obj_t *s_caption;
static lv_obj_t *s_status;
static lv_obj_t *s_detail;
static lv_obj_t *s_button;

static lv_obj_t *make_arc(lv_obj_t *parent, int size, int width, int start, int end, uint32_t track) {
    lv_obj_t *arc = lv_arc_create(parent);
    lv_obj_set_size(arc, size, size);
    lv_obj_center(arc);
    lv_arc_set_bg_angles(arc, start, end);
    lv_arc_set_range(arc, -100, 100);
    lv_arc_set_mode(arc, LV_ARC_MODE_SYMMETRICAL);
    lv_arc_set_value(arc, 0);
    lv_obj_remove_style(arc, NULL, LV_PART_KNOB);
    lv_obj_remove_flag(arc, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_set_style_arc_width(arc, width, LV_PART_MAIN);
    lv_obj_set_style_arc_width(arc, width, LV_PART_INDICATOR);
    lv_obj_set_style_arc_color(arc, lv_color_hex(track), LV_PART_MAIN);
    lv_obj_set_style_arc_rounded(arc, false, LV_PART_MAIN);
    lv_obj_set_style_arc_rounded(arc, false, LV_PART_INDICATOR);
    return arc;
}

static lv_obj_t *make_label(lv_obj_t *parent, const lv_font_t *font, uint32_t color, int y) {
    lv_obj_t *l = lv_label_create(parent);
    lv_obj_set_style_text_font(l, font, 0);
    lv_obj_set_style_text_color(l, lv_color_hex(color), 0);
    lv_obj_align(l, LV_ALIGN_CENTER, 0, y);
    lv_label_set_text(l, "");
    return l;
}

static void build_ui(void) {
    lv_obj_t *scr = lv_screen_active();
    lv_obj_set_style_bg_color(scr, lv_color_hex(COL_BG), 0);
    lv_obj_set_style_bg_opa(scr, LV_OPA_COVER, 0);

    // Outer ring: throttle, open at the bottom. LVGL angles are clockwise
    // from 3 o'clock, so 135..45 is a 270 degree sweep through the top.
    s_throttle_arc = make_arc(scr, 232, 12, 135, 45, COL_TRACK);
    // Inner arc across the top: steering.
    s_steer_arc = make_arc(scr, 196, 6, 210, 330, COL_TRACK);
    lv_obj_set_style_arc_color(s_steer_arc, lv_color_hex(COL_STEER), LV_PART_INDICATOR);

    s_status = make_label(scr, &lv_font_montserrat_20, COL_DIM, -50);
    s_value = make_label(scr, &lv_font_montserrat_48, COL_TEXT, -2);
    s_caption = make_label(scr, &lv_font_montserrat_14, COL_DIM, 32);
    s_button = make_label(scr, &lv_font_montserrat_14, COL_STEER, 52);
    s_detail = make_label(scr, &lv_font_montserrat_14, COL_DIM, 78);
}

void display_init(void) {
    const spi_bus_config_t bus = GC9A01_PANEL_BUS_SPI_CONFIG(PIN_SCLK, PIN_MOSI,
                                                             LCD_SIZE * LCD_DRAW_LINES * sizeof(uint16_t));
    ESP_ERROR_CHECK(spi_bus_initialize(LCD_HOST, &bus, SPI_DMA_CH_AUTO));

    esp_lcd_panel_io_handle_t io = NULL;
    esp_lcd_panel_io_spi_config_t io_cfg = GC9A01_PANEL_IO_SPI_CONFIG(PIN_CS, PIN_DC, NULL, NULL);
    io_cfg.pclk_hz = LCD_PCLK_HZ;
    ESP_ERROR_CHECK(esp_lcd_new_panel_io_spi((esp_lcd_spi_bus_handle_t)LCD_HOST, &io_cfg, &io));

    esp_lcd_panel_handle_t panel = NULL;
    const esp_lcd_panel_dev_config_t panel_cfg = {
        .reset_gpio_num = PIN_RST,
        .rgb_ele_order = LCD_RGB_ELEMENT_ORDER_BGR,
        .bits_per_pixel = 16,
    };
    ESP_ERROR_CHECK(esp_lcd_new_panel_gc9a01(io, &panel_cfg, &panel));
    ESP_ERROR_CHECK(esp_lcd_panel_reset(panel));
    ESP_ERROR_CHECK(esp_lcd_panel_init(panel));
    ESP_ERROR_CHECK(esp_lcd_panel_invert_color(panel, true));
    ESP_ERROR_CHECK(esp_lcd_panel_disp_on_off(panel, true));

    const lvgl_port_cfg_t port_cfg = ESP_LVGL_PORT_INIT_CONFIG();
    ESP_ERROR_CHECK(lvgl_port_init(&port_cfg));
    const lvgl_port_display_cfg_t disp_cfg = {
        .io_handle = io,
        .panel_handle = panel,
        .buffer_size = LCD_SIZE * LCD_DRAW_LINES,
        .double_buffer = true,
        .hres = LCD_SIZE,
        .vres = LCD_SIZE,
        .monochrome = false,
        .color_format = LV_COLOR_FORMAT_RGB565,
        .rotation = {.swap_xy = false, .mirror_x = true, .mirror_y = false},
        .flags = {.buff_dma = true, .swap_bytes = true},
    };
    if (lvgl_port_add_disp(&disp_cfg) == NULL) {
        ESP_LOGE(TAG, "lvgl_port_add_disp failed");
        return;
    }

    lvgl_port_lock(0);
    build_ui();
    lvgl_port_unlock();
    ESP_LOGI(TAG, "GC9A01 up");
}

static void set_label(lv_obj_t *l, const char *text, uint32_t color) {
    lv_label_set_text(l, text);
    lv_obj_set_style_text_color(l, lv_color_hex(color), 0);
}

static const char *speed_name(speed_t s) {
    return s == SPEED_HIGH ? "SPEED  H" : (s == SPEED_MID ? "SPEED  M" : "SPEED  L");
}

void display_show(const display_state_t *s) {
    if (s_value == NULL || !lvgl_port_lock(50)) {
        return;
    }
    char buf[32];
    const control_view_t *c = &s->ctl;

    // Top line: what the car will do.
    if (!s->wheel) {
        if (s->vid != 0 && !wheel_known(s->vid, s->pid)) {
            snprintf(buf, sizeof(buf), "%04X:%04X", s->vid, s->pid);
            set_label(s_status, buf, COL_STEER);
        } else {
            set_label(s_status, "NO WHEEL", COL_WARN);
        }
    } else if (c->armed) {
        set_label(s_status, "ARMED", COL_OK);
    } else if (strcmp(c->disarm_reason, "E-STOP") == 0) {
        set_label(s_status, "E-STOP", COL_STOP);
    } else {
        set_label(s_status, "SAFE", COL_WARN);
    }

    // Ring and number: the throttle actually sent when armed, else the
    // pedal demand, dimmed, so the pedals can still be checked.
    float thr = c->armed ? c->output.throttle : c->throttle_demand;
    int pct = (int)lroundf(thr * 100.0f);
    uint32_t ring = !c->armed ? COL_DIM : (pct >= 0 ? COL_FWD : COL_REV);
    lv_arc_set_value(s_throttle_arc, s->wheel ? pct : 0);
    lv_obj_set_style_arc_color(s_throttle_arc, lv_color_hex(ring), LV_PART_INDICATOR);
    lv_arc_set_value(s_steer_arc, s->wheel ? (int)lroundf(c->steering * 100.0f) : 0);
    if (s->wheel) {
        snprintf(buf, sizeof(buf), "%+d", pct);
        set_label(s_value, pct == 0 ? "0" : buf, c->armed ? COL_TEXT : COL_DIM);
    } else {
        set_label(s_value, "--", COL_DIM);
    }

    set_label(s_caption, speed_name(c->speed), COL_DIM);

    if (s->button) {
        snprintf(buf, sizeof(buf), "BTN %d", s->button);
        set_label(s_button, buf, COL_STEER);
    } else {
        lv_label_set_text(s_button, "");
    }

    // Bottom line: the radio.
    if (s->radio.link) {
        snprintf(buf, sizeof(buf), "%d dBm  LQ %d", s->radio.rssi, s->radio.lq);
        set_label(s_detail, buf, COL_OK);
    } else if (s->radio.module) {
        set_label(s_detail, "TX ONLY", COL_WARN);
    } else {
        set_label(s_detail, "NO TX", COL_STOP);
    }
    lvgl_port_unlock();
}

#endif  // CONFIG_IDF_TARGET_ESP32S3
