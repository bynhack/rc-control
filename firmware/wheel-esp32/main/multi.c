#include "multi.h"

#include "sdkconfig.h"

#include "control.h"
#include "driver/gpio.h"
#include "driver/rmt_tx.h"
#include "driver/uart.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "radio.h"

static const char *TAG = "multi";

#define MULTI_UART UART_NUM_2
#if CONFIG_IDF_TARGET_ESP32P4
#define MULTI_PIN 29
#else
#define MULTI_PIN 18
#endif
// 100000 baud 8E2. Not inverted: the IRX4+ only lights its red LED solid
// (valid input) this way round; inverted it blinks.
#define MULTI_BAUD 100000
#define MULTI_INVERT 0
#define FRAME_PERIOD_MS 7
// PPM for the module's dial positions 1-E: its own protocol table and bind
// button. 8 channels in a 22.5 ms frame.
#define PPM_CHANNELS 8
#define PPM_FRAME_US 22500
#define PPM_PULSE_US 300
// MULTI's PPM range: 1100 us = -100 %, 1900 us = +100 %.
#define PPM_CENTER_US 1500
#define PPM_SPAN_US 400
// The module only binds while the bind bit is set; some receivers take a while.
#define BIND_MS 30000
#define LOW_POWER 0

#define STEERING_CHANNEL 1
#define THROTTLE_CHANNEL 2

// Channel values: 204 = -100 %, 1024 = centre, 1843 = +100 %.
#define CH_MIN 204
#define CH_CENTER 1024
#define CH_MAX 1843
#define CHANNELS 16

#define HDR_PROTO_BIT5_CLEAR 0x55
#define HDR_PROTO_BIT5_SET 0x54
#define BIT_BIND 0x80
#define BIT_LOW_POWER 0x80
#define BIT_DISABLE_CH_MAPPING 0x01

static portMUX_TYPE s_lock = portMUX_INITIALIZER_UNLOCKED;
static int64_t s_bind_until = -1;
static uint32_t s_frames;
static radio_kind_t s_mode = RADIO_ELRS; // what the pin is set up for

static rmt_channel_handle_t s_rmt;
static rmt_encoder_handle_t s_copy;

static uint16_t to_channel(float v) {
    v = v < -1.0f ? -1.0f : (v > 1.0f ? 1.0f : v);
    float span = v < 0 ? (CH_CENTER - CH_MIN) : (CH_MAX - CH_CENTER);
    return (uint16_t)(CH_CENTER + v * span + (v < 0 ? -0.5f : 0.5f));
}

static uint16_t to_ppm_us(float v) {
    v = v < -1.0f ? -1.0f : (v > 1.0f ? 1.0f : v);
    return (uint16_t)(PPM_CENTER_US + v * PPM_SPAN_US);
}

// 27-byte frame: header, protocol + flags, rx num + sub protocol + power,
// option, 16 x 11-bit channels (SBUS packing), extended flags.
static void build_frame(const radio_config_t *c, const uint16_t ch[CHANNELS], bool bind, uint8_t out[27]) {
    const multi_proto_t *p = &MULTI_PROTOS[c->proto];
    out[0] = (p->protocol & 0x20) ? HDR_PROTO_BIT5_SET : HDR_PROTO_BIT5_CLEAR;
    out[1] = (p->protocol & 0x1F) | (bind ? BIT_BIND : 0);
    out[2] = (c->rx_num & 0x0F) | ((p->sub & 0x07) << 4) | (LOW_POWER ? BIT_LOW_POWER : 0);
    out[3] = (uint8_t)c->option;
    uint32_t acc = 0;
    int bits = 0, i = 4;
    for (int n = 0; n < CHANNELS; n++) {
        acc |= (uint32_t)(ch[n] & 0x7FF) << bits;
        bits += 11;
        while (bits >= 8) {
            out[i++] = (uint8_t)acc;
            acc >>= 8;
            bits -= 8;
        }
    }
    // Protocol bits 6-7, RX num bits 4-5; channels go out as sent.
    out[26] = ((p->protocol >> 6) & 0x03) << 6 | ((c->rx_num >> 4) & 0x03) << 4 | BIT_DISABLE_CH_MAPPING;
}

static void send_serial(const radio_config_t *c, float steer, float thr, int64_t now) {
    uint16_t ch[CHANNELS];
    uint8_t out[27];
    for (int n = 0; n < CHANNELS; n++) {
        ch[n] = CH_CENTER;
    }
    ch[STEERING_CHANNEL - 1] = to_channel(steer);
    ch[THROTTLE_CHANNEL - 1] = to_channel(thr);
    portENTER_CRITICAL(&s_lock);
    bool bind = s_bind_until >= 0 && now < s_bind_until;
    portEXIT_CRITICAL(&s_lock);
    build_frame(c, ch, bind, out);
    uart_write_bytes(MULTI_UART, out, sizeof(out));
}

// Idle high, a 300 us low pulse before every channel: the time between
// pulses is the channel value.
static void send_ppm(float steer, float thr) {
    rmt_symbol_word_t sym[PPM_CHANNELS + 1];
    uint16_t us[PPM_CHANNELS];
    for (int n = 0; n < PPM_CHANNELS; n++) {
        us[n] = PPM_CENTER_US;
    }
    us[STEERING_CHANNEL - 1] = to_ppm_us(steer);
    us[THROTTLE_CHANNEL - 1] = to_ppm_us(thr);
    uint32_t total = 0;
    for (int n = 0; n < PPM_CHANNELS; n++) {
        sym[n] = (rmt_symbol_word_t){.level0 = 0, .duration0 = PPM_PULSE_US, .level1 = 1,
                                     .duration1 = us[n] - PPM_PULSE_US};
        total += us[n];
    }
    // Sync gap, ending a little early so the next frame is queued in time.
    sym[PPM_CHANNELS] = (rmt_symbol_word_t){.level0 = 0, .duration0 = PPM_PULSE_US, .level1 = 1,
                                            .duration1 = PPM_FRAME_US - 1000 - total - PPM_PULSE_US};
    const rmt_transmit_config_t tcfg = {.loop_count = 0, .flags.eot_level = 1};
    rmt_transmit(s_rmt, s_copy, sym, sizeof(sym), &tcfg);
}

// UART and RMT share the pin; only the current mode's peripheral drives it.
// Off: held high (idle), so the module sees no input.
static void set_mode(radio_kind_t m) {
    if (m == s_mode) {
        return;
    }
    if (s_mode == RADIO_MULTI_PPM) {
        rmt_tx_wait_all_done(s_rmt, 50);
        rmt_disable(s_rmt);
        rmt_del_channel(s_rmt);
        s_rmt = NULL;
    }
    gpio_reset_pin(MULTI_PIN);
    if (m == RADIO_MULTI_SERIAL) {
        ESP_ERROR_CHECK(uart_set_pin(MULTI_UART, MULTI_PIN, UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE,
                                     UART_PIN_NO_CHANGE));
    } else if (m == RADIO_MULTI_PPM) {
        const rmt_tx_channel_config_t cfg = {
            .gpio_num = MULTI_PIN,
            .clk_src = RMT_CLK_SRC_DEFAULT,
            .resolution_hz = 1000000,
            .mem_block_symbols = 48,
            .trans_queue_depth = 2,
        };
        ESP_ERROR_CHECK(rmt_new_tx_channel(&cfg, &s_rmt));
        ESP_ERROR_CHECK(rmt_enable(s_rmt));
    } else {
        gpio_set_direction(MULTI_PIN, GPIO_MODE_OUTPUT);
        gpio_set_level(MULTI_PIN, 1);
    }
    s_mode = m;
    ESP_LOGI(TAG, "output: %s", radio_kind_name(m));
}

static void sender_task(void *arg) {
    TickType_t wake = xTaskGetTickCount();
    for (;;) {
        radio_config_t c = radio_config();
        set_mode(c.kind);
        int64_t now = esp_timer_get_time();
        control_tick(now);
        control_output_t o = control_output(now);
        float steer = radio_steering(&c, o.steering);
        float thr = radio_throttle(&c, o.throttle, o.reverse);
        TickType_t period = pdMS_TO_TICKS(FRAME_PERIOD_MS);
        if (c.kind == RADIO_MULTI_SERIAL) {
            send_serial(&c, steer, thr, now);
        } else if (c.kind == RADIO_MULTI_PPM) {
            send_ppm(steer, thr);
            period = pdMS_TO_TICKS(PPM_FRAME_US / 1000);
        }
        if (c.kind == RADIO_MULTI_SERIAL || c.kind == RADIO_MULTI_PPM) {
            portENTER_CRITICAL(&s_lock);
            s_frames++;
            portEXIT_CRITICAL(&s_lock);
        }
        vTaskDelayUntil(&wake, period);
    }
}

void multi_start(void) {
    const uart_config_t cfg = {
        .baud_rate = MULTI_BAUD,
        .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_EVEN,
        .stop_bits = UART_STOP_BITS_2,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_DEFAULT,
    };
    ESP_ERROR_CHECK(uart_driver_install(MULTI_UART, 256, 256, 0, NULL, 0));
    ESP_ERROR_CHECK(uart_param_config(MULTI_UART, &cfg));
    if (MULTI_INVERT) {
        ESP_ERROR_CHECK(uart_set_line_inverse(MULTI_UART, UART_SIGNAL_TXD_INV));
    }
    const rmt_copy_encoder_config_t ccfg = {};
    ESP_ERROR_CHECK(rmt_new_copy_encoder(&ccfg, &s_copy));
    gpio_reset_pin(MULTI_PIN);
    gpio_set_direction(MULTI_PIN, GPIO_MODE_OUTPUT);
    gpio_set_level(MULTI_PIN, 1);
    xTaskCreatePinnedToCore(sender_task, "multi", 4096, NULL, 9, NULL, 1);
    ESP_LOGI(TAG, "MULTI on GPIO%d", MULTI_PIN);
}

void multi_bind(void) {
    portENTER_CRITICAL(&s_lock);
    s_bind_until = esp_timer_get_time() + (int64_t)BIND_MS * 1000;
    portEXIT_CRITICAL(&s_lock);
    ESP_LOGI(TAG, "bind for %d s", BIND_MS / 1000);
}

void multi_bind_cancel(void) {
    portENTER_CRITICAL(&s_lock);
    s_bind_until = -1;
    portEXIT_CRITICAL(&s_lock);
}

multi_status_t multi_status(void) {
    int64_t now = esp_timer_get_time();
    portENTER_CRITICAL(&s_lock);
    multi_status_t s = {
        .binding = s_bind_until >= 0 && now < s_bind_until,
        .bind_left_s = (s_bind_until >= 0 && now < s_bind_until) ? (int)((s_bind_until - now + 999999) / 1000000) : 0,
        .frames = s_frames,
    };
    portEXIT_CRITICAL(&s_lock);
    return s;
}
