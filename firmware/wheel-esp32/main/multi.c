#include "multi.h"

#include "sdkconfig.h"

#include "control.h"
#include "driver/rmt_tx.h"
#include "driver/uart.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "multi";

#define MULTI_UART UART_NUM_2
#if CONFIG_IDF_TARGET_ESP32P4
#define MULTI_PIN 30
#else
#define MULTI_PIN 18
#endif
// 100000 baud 8E2. Not inverted: the IRX4+ only lights its red LED solid
// (valid input) this way round; inverted it blinks.
#define MULTI_BAUD 100000
#define MULTI_INVERT 0
#define FRAME_PERIOD_MS 7
// 1: send plain PPM (dial 1-E, the module's own protocol table and
// bind button). For telling the module's side from ours.
#define MULTI_PPM 1
#define PPM_CHANNELS 8
#define PPM_FRAME_US 22500
#define PPM_PULSE_US 300
// MULTI's PPM range: 1100 us = -100 %, 1900 us = +100 %.
#define PPM_CENTER_US 1500
#define PPM_SPAN_US 400
// The module only binds while the bind bit is set; some receivers take a while.
#define BIND_MS 30000

// The car's protocol, from the MULTI protocol list (Multiprotocol.h).
// FlySky AFHDS 2A, PWM_SBUS (as dial 2 of group 1): the car's FS-GT2E radio and its MXO-Racing
// RXC42-AG receiver. Bind order for that receiver: both powered, start the
// TX bind (wheel button N), then hold the receiver's button ~2 s.
// (Futaba S-FHSS would be protocol 21, option -50: the IRX4+ fine tune.)
#define PROTOCOL 28
#define SUB_PROTOCOL 2
#define RX_NUM 0
#define OPTION 0
#define LOW_POWER 0

#define STEERING_CHANNEL 1
#define THROTTLE_CHANNEL 2
#define STEERING_INVERT 1
#define THROTTLE_INVERT 0

// Channel values: 204 = -100 %, 1024 = centre, 1843 = +100 %.
#define CH_MIN 204
#define CH_CENTER 1024
#define CH_MAX 1843
#define CHANNELS 16

#define HDR_PROTO_0_31 0x55
#define HDR_PROTO_32_63 0x54
#define BIT_BIND 0x80
#define BIT_LOW_POWER 0x80
#define BIT_DISABLE_CH_MAPPING 0x01

static portMUX_TYPE s_lock = portMUX_INITIALIZER_UNLOCKED;
static int64_t s_bind_until = -1;
static uint32_t s_frames;

static uint16_t to_channel(float v) {
    v = v < -1.0f ? -1.0f : (v > 1.0f ? 1.0f : v);
    float span = v < 0 ? (CH_CENTER - CH_MIN) : (CH_MAX - CH_CENTER);
    return (uint16_t)(CH_CENTER + v * span + (v < 0 ? -0.5f : 0.5f));
}

// 27-byte frame: header, protocol + flags, rx num + sub protocol + power,
// option, 16 x 11-bit channels (SBUS packing), extended flags.
static void build_frame(const uint16_t ch[CHANNELS], bool bind, uint8_t out[27]) {
    out[0] = PROTOCOL < 32 ? HDR_PROTO_0_31 : HDR_PROTO_32_63;
    out[1] = (PROTOCOL & 0x1F) | (bind ? BIT_BIND : 0);
    out[2] = (RX_NUM & 0x0F) | ((SUB_PROTOCOL & 0x07) << 4) | (LOW_POWER ? BIT_LOW_POWER : 0);
    out[3] = (uint8_t)(int8_t)OPTION;
    uint32_t acc = 0;
    int bits = 0, i = 4;
    for (int c = 0; c < CHANNELS; c++) {
        acc |= (uint32_t)(ch[c] & 0x7FF) << bits;
        bits += 11;
        while (bits >= 8) {
            out[i++] = (uint8_t)acc;
            acc >>= 8;
            bits -= 8;
        }
    }
    // Protocol bits 6-7, RX num bits 4-5; channels go out as sent.
    out[26] = ((PROTOCOL >> 6) & 0x03) << 6 | ((RX_NUM >> 4) & 0x03) << 4 | BIT_DISABLE_CH_MAPPING;
}

static void sender_task(void *arg) {
    uint8_t out[27];
    uint16_t ch[CHANNELS];
    TickType_t wake = xTaskGetTickCount();
    for (;;) {
        int64_t now = esp_timer_get_time();
        control_tick(now);
        control_output_t o = control_output(now);
        for (int c = 0; c < CHANNELS; c++) {
            ch[c] = CH_CENTER;
        }
        ch[STEERING_CHANNEL - 1] = to_channel(STEERING_INVERT ? -o.steering : o.steering);
        ch[THROTTLE_CHANNEL - 1] = to_channel(THROTTLE_INVERT ? -o.throttle : o.throttle);
        portENTER_CRITICAL(&s_lock);
        bool bind = s_bind_until >= 0 && now < s_bind_until;
        s_frames++;
        portEXIT_CRITICAL(&s_lock);
        build_frame(ch, bind, out);
        uart_write_bytes(MULTI_UART, out, sizeof(out));
        vTaskDelayUntil(&wake, pdMS_TO_TICKS(FRAME_PERIOD_MS));
    }
}

static uint16_t to_ppm_us(float v) {
    v = v < -1.0f ? -1.0f : (v > 1.0f ? 1.0f : v);
    return (uint16_t)(PPM_CENTER_US + v * PPM_SPAN_US);
}

// Idle high, a 300 us low pulse before every channel: the time between
// pulses is the channel value.
static void ppm_task(void *arg) {
    rmt_channel_handle_t tx;
    const rmt_tx_channel_config_t cfg = {
        .gpio_num = MULTI_PIN,
        .clk_src = RMT_CLK_SRC_DEFAULT,
        .resolution_hz = 1000000,
        .mem_block_symbols = 48,
        .trans_queue_depth = 2,
    };
    ESP_ERROR_CHECK(rmt_new_tx_channel(&cfg, &tx));
    rmt_encoder_handle_t copy;
    const rmt_copy_encoder_config_t ccfg = {};
    ESP_ERROR_CHECK(rmt_new_copy_encoder(&ccfg, &copy));
    ESP_ERROR_CHECK(rmt_enable(tx));
    const rmt_transmit_config_t tcfg = {.loop_count = 0, .flags.eot_level = 1};
    rmt_symbol_word_t sym[PPM_CHANNELS + 1];
    uint16_t us[PPM_CHANNELS];
    TickType_t wake = xTaskGetTickCount();
    for (;;) {
        int64_t now = esp_timer_get_time();
        control_tick(now);
        control_output_t o = control_output(now);
        for (int c = 0; c < PPM_CHANNELS; c++) {
            us[c] = PPM_CENTER_US;
        }
        us[STEERING_CHANNEL - 1] = to_ppm_us(STEERING_INVERT ? -o.steering : o.steering);
        us[THROTTLE_CHANNEL - 1] = to_ppm_us(THROTTLE_INVERT ? -o.throttle : o.throttle);
        uint32_t total = 0;
        for (int c = 0; c < PPM_CHANNELS; c++) {
            sym[c] = (rmt_symbol_word_t){.level0 = 0, .duration0 = PPM_PULSE_US, .level1 = 1,
                                         .duration1 = us[c] - PPM_PULSE_US};
            total += us[c];
        }
        // Sync gap, ending a little early so the next frame is queued in time.
        sym[PPM_CHANNELS] = (rmt_symbol_word_t){.level0 = 0, .duration0 = PPM_PULSE_US, .level1 = 1,
                                                .duration1 = PPM_FRAME_US - 1000 - total - PPM_PULSE_US};
        ESP_ERROR_CHECK(rmt_transmit(tx, copy, sym, sizeof(sym), &tcfg));
        vTaskDelayUntil(&wake, pdMS_TO_TICKS(PPM_FRAME_US / 1000));
    }
}

void multi_start(void) {
    if (MULTI_PPM) {
        xTaskCreatePinnedToCore(ppm_task, "ppm", 4096, NULL, 9, NULL, 1);
        ESP_LOGI(TAG, "PPM on GPIO%d, %d channels", MULTI_PIN, PPM_CHANNELS);
        return;
    }
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
    ESP_ERROR_CHECK(uart_set_pin(MULTI_UART, MULTI_PIN, UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE));
    if (MULTI_INVERT) {
        ESP_ERROR_CHECK(uart_set_line_inverse(MULTI_UART, UART_SIGNAL_TXD_INV));
    }
    xTaskCreatePinnedToCore(sender_task, "multi", 4096, NULL, 9, NULL, 1);
    ESP_LOGI(TAG, "MULTI on GPIO%d, protocol %d/%d, every %d ms", MULTI_PIN, PROTOCOL, SUB_PROTOCOL, FRAME_PERIOD_MS);
}

void multi_bind(void) {
    portENTER_CRITICAL(&s_lock);
    s_bind_until = esp_timer_get_time() + (int64_t)BIND_MS * 1000;
    portEXIT_CRITICAL(&s_lock);
    ESP_LOGI(TAG, "bind for %d s", BIND_MS / 1000);
}

multi_status_t multi_status(void) {
    int64_t now = esp_timer_get_time();
    portENTER_CRITICAL(&s_lock);
    multi_status_t s = {.binding = s_bind_until >= 0 && now < s_bind_until, .frames = s_frames};
    portEXIT_CRITICAL(&s_lock);
    return s;
}
