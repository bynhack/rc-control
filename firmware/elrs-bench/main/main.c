// Bench test for the module-based carrier: ELRS EP2 -> CRSF -> ESP32-S3 -> PWM -> ESC.
// One binary runs on the ESP32-S3-Zero and on an S3 DevKit (see README.md); pins as on carrier v8 (v7: CRSF RX 5, TX 6).
#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/uart.h"
#include "driver/ledc.h"
#include "driver/rmt_tx.h"
#include "esp_timer.h"
#include "nvs_flash.h"
#include "nvs.h"

#define PIN_CRSF_RX 13  // from the EP2's TX pad
#define PIN_CRSF_TX 14  // to the EP2's RX pad
#define PIN_ESC_S1 8    // CH1 steering
#define PIN_ESC_S2 7    // CH2 throttle
#define PIN_RGB_ZERO 21 // the S3-Zero's WS2812
#define PIN_RGB_DEVKIT 48
#define CRSF_UART UART_NUM_1
#define CRSF_BAUD 420000

#define NEUTRAL_US 1500
#define FAILSAFE_MS 200 // no channel frame for this long: throttle to neutral
#define DROP_MS 250     // a gap this long counts as a link drop
#define PWM_HZ 50
#define PWM_BITS 14

typedef struct {
    uint32_t seconds;     // with a link
    uint32_t drops;
    uint32_t max_gap_ms;
    int32_t min_lq;
    int32_t min_rssi;
    uint32_t crc_errors;
} summary_t;

static summary_t s = {.min_lq = 101, .min_rssi = 0};
static volatile uint32_t bytes, frames, ch_frames, link_frames, devinfo;
static volatile int64_t last_ch_us, first_byte_us, first_ch_us;
static volatile int ch[4] = {NEUTRAL_US, NEUTRAL_US, NEUTRAL_US, NEUTRAL_US};
static volatile int lq = -1, rssi;
static int64_t boot_us;

static uint8_t crc8(const uint8_t *p, int n)
{
    uint8_t c = 0;
    while (n--) {
        c ^= *p++;
        for (int i = 0; i < 8; i++) c = c & 0x80 ? (c << 1) ^ 0xD5 : c << 1;
    }
    return c;
}

// ---- PWM ------------------------------------------------------------------------------
static void pwm_write(ledc_channel_t c, int us)
{
    if (us < 1000) us = 1000;
    if (us > 2000) us = 2000;
    ledc_set_duty(LEDC_LOW_SPEED_MODE, c, (uint32_t)us * (1 << PWM_BITS) * PWM_HZ / 1000000);
    ledc_update_duty(LEDC_LOW_SPEED_MODE, c);
}

static void pwm_init(void)
{
    ledc_timer_config_t t = {.speed_mode = LEDC_LOW_SPEED_MODE, .duty_resolution = PWM_BITS,
                             .timer_num = LEDC_TIMER_0, .freq_hz = PWM_HZ, .clk_cfg = LEDC_AUTO_CLK};
    ESP_ERROR_CHECK(ledc_timer_config(&t));
    int pins[2] = {PIN_ESC_S1, PIN_ESC_S2};
    for (int i = 0; i < 2; i++) {
        ledc_channel_config_t c = {.gpio_num = pins[i], .speed_mode = LEDC_LOW_SPEED_MODE, .channel = i,
                                   .timer_sel = LEDC_TIMER_0,
                                   .duty = (uint32_t)NEUTRAL_US * (1 << PWM_BITS) * PWM_HZ / 1000000};
        ESP_ERROR_CHECK(ledc_channel_config(&c));
    }
}

// ---- CRSF -----------------------------------------------------------------------------
static void on_frame(const uint8_t *f)
{
    uint8_t type = f[2];
    const uint8_t *p = f + 3;
    frames++;
    if (type == 0x16) { // RC channels: 16 x 11 bits, little endian
        int64_t now = esp_timer_get_time();
        if (!first_ch_us) first_ch_us = now;
        if (last_ch_us) {
            uint32_t gap = (now - last_ch_us) / 1000;
            if (gap > s.max_gap_ms) s.max_gap_ms = gap;
            if (gap >= DROP_MS) s.drops++;
        }
        last_ch_us = now;
        ch_frames++;
        uint32_t acc = 0;
        int bits = 0, n = 0;
        for (int i = 0; i < 22 && n < 4; i++) {
            acc |= (uint32_t)p[i] << bits;
            bits += 8;
            if (bits >= 11) {
                ch[n++] = 1500 + ((int)(acc & 0x7FF) - 992) * 5 / 8;
                acc >>= 11;
                bits -= 11;
            }
        }
        pwm_write(0, ch[0]);
        pwm_write(1, ch[1]);
    } else if (type == 0x14) { // link statistics
        link_frames++;
        rssi = -(int)p[0]; // uplink RSSI of antenna 1, dBm
        lq = p[2];
        if (lq < s.min_lq) s.min_lq = lq;
        if (rssi < s.min_rssi) s.min_rssi = rssi;
    } else if (type == 0x29) {
        devinfo++;
    }
}

static void crsf_rx_task(void *arg)
{
    static uint8_t f[64], buf[256];
    int have = 0;
    for (;;) {
        int n = uart_read_bytes(CRSF_UART, buf, sizeof buf, pdMS_TO_TICKS(10));
        if (n > 0 && !first_byte_us) first_byte_us = esp_timer_get_time();
        for (int i = 0; i < n; i++) {
            bytes++;
            uint8_t b = buf[i];
            if (have == 0) {
                if (b == 0xC8 || b == 0xEA || b == 0xEE || b == 0xEC) f[have++] = b;
                continue;
            }
            if (have == 1 && (b < 2 || b > 62)) { // not a length: resync
                have = 0;
                continue;
            }
            f[have++] = b;
            if (have >= 2 && have == f[1] + 2) {
                if (crc8(f + 2, f[1] - 1) == f[have - 1]) on_frame(f);
                else s.crc_errors++;
                have = 0;
            }
        }
        // failsafe, also before the first frame
        int64_t age = esp_timer_get_time() - last_ch_us;
        if (!last_ch_us || age > FAILSAFE_MS * 1000) pwm_write(1, NEUTRAL_US);
    }
}

static void crsf_send(uint8_t type, const uint8_t *p, int n)
{
    uint8_t f[64] = {0xC8, (uint8_t)(n + 2), type};
    memcpy(f + 3, p, n);
    f[3 + n] = crc8(f + 2, n + 1);
    uart_write_bytes(CRSF_UART, f, n + 4);
}

static void crsf_init(void)
{
    uart_config_t c = {.baud_rate = CRSF_BAUD, .data_bits = UART_DATA_8_BITS, .parity = UART_PARITY_DISABLE,
                       .stop_bits = UART_STOP_BITS_1, .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
                       .source_clk = UART_SCLK_DEFAULT};
    ESP_ERROR_CHECK(uart_driver_install(CRSF_UART, 2048, 512, 0, NULL, 0));
    ESP_ERROR_CHECK(uart_param_config(CRSF_UART, &c));
    ESP_ERROR_CHECK(uart_set_pin(CRSF_UART, PIN_CRSF_TX, PIN_CRSF_RX, UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE));
    gpio_set_pull_mode(PIN_CRSF_RX, GPIO_PULLUP_ONLY);
}

// ---- status LED: drives both boards' WS2812 pins --------------------------------------
static rmt_channel_handle_t rgb_ch[2];
static rmt_encoder_handle_t rgb_enc;

static void rgb_init(void)
{
    int pins[2] = {PIN_RGB_ZERO, PIN_RGB_DEVKIT};
    for (int i = 0; i < 2; i++) {
        rmt_tx_channel_config_t c = {.gpio_num = pins[i], .clk_src = RMT_CLK_SRC_DEFAULT,
                                     .resolution_hz = 10000000, .mem_block_symbols = 48, .trans_queue_depth = 2};
        ESP_ERROR_CHECK(rmt_new_tx_channel(&c, &rgb_ch[i]));
        ESP_ERROR_CHECK(rmt_enable(rgb_ch[i]));
    }
    rmt_bytes_encoder_config_t e = {.bit0 = {.level0 = 1, .duration0 = 3, .level1 = 0, .duration1 = 9},
                                    .bit1 = {.level0 = 1, .duration0 = 9, .level1 = 0, .duration1 = 3},
                                    .flags.msb_first = 1};
    ESP_ERROR_CHECK(rmt_new_bytes_encoder(&e, &rgb_enc));
}

// White and blue on purpose: the two boards' LEDs may swap red and green.
static void rgb_set(uint8_t w, uint8_t b)
{
    uint8_t grb[3] = {w, w, (uint8_t)(w + b)};
    rmt_transmit_config_t t = {.loop_count = 0};
    for (int i = 0; i < 2; i++) {
        rmt_transmit(rgb_ch[i], rgb_enc, grb, 3, &t);
        rmt_tx_wait_all_done(rgb_ch[i], 20);
    }
}

// ---- last run, so a test inside the shell can be read back afterwards --------------------
static void summary_save(void)
{
    nvs_handle_t h;
    if (nvs_open("bench", NVS_READWRITE, &h) == ESP_OK) {
        nvs_set_blob(h, "last", &s, sizeof s);
        nvs_commit(h);
        nvs_close(h);
    }
}

static void summary_print_last(void)
{
    nvs_handle_t h;
    summary_t l;
    size_t n = sizeof l;
    if (nvs_open("bench", NVS_READONLY, &h) != ESP_OK) return;
    if (nvs_get_blob(h, "last", &l, &n) == ESP_OK && n == sizeof l)
        printf("\n[上次] 連線 %lu 秒, 斷線 %lu 次, 最長間隔 %lu ms, 最低 LQ %ld, 最低 RSSI %ld dBm, CRC 錯誤 %lu\n\n",
               (unsigned long)l.seconds, (unsigned long)l.drops, (unsigned long)l.max_gap_ms, (long)l.min_lq,
               (long)l.min_rssi, (unsigned long)l.crc_errors);
    nvs_close(h);
}

// ---- main -----------------------------------------------------------------------------
void app_main(void)
{
    boot_us = esp_timer_get_time();
    if (nvs_flash_init() != ESP_OK) {
        nvs_flash_erase();
        nvs_flash_init();
    }
    pwm_init(); // neutral on both outputs from here on
    crsf_init();
    rgb_init();
    vTaskDelay(pdMS_TO_TICKS(1500)); // give the USB console time to come up
    summary_print_last();
    printf("ELRS bench: EP2 TX -> GPIO%d, EP2 RX <- GPIO%d, %d baud; S1 GPIO%d, S2 GPIO%d\n",
           PIN_CRSF_RX, PIN_CRSF_TX, CRSF_BAUD, PIN_ESC_S1, PIN_ESC_S2);
    xTaskCreatePinnedToCore(crsf_rx_task, "crsf", 4096, NULL, 10, NULL, 1);

    uint32_t tick = 0, last_bytes = 0, last_ch = 0;
    for (;;) {
        for (int i = 0; i < 10; i++) { // 1 s, LED in 100 ms steps
            bool up = last_ch_us && esp_timer_get_time() - last_ch_us < FAILSAFE_MS * 1000;
            if (!up) rgb_set(0, 0);
            else if (lq >= 90) rgb_set(0, 24);
            else if (lq >= 70) rgb_set(16, 0);
            else rgb_set(i % 2 ? 16 : 0, 0);
            vTaskDelay(pdMS_TO_TICKS(100));
        }
        tick++;
        uint32_t b = bytes, c = ch_frames;
        bool link = c != last_ch;
        if (link) s.seconds++;
        const char *state = b == 0 ? "無資料（EP2 未連上發射端，或 EP2 TX 沒接到 GPIO13）"
                            : c == 0 && frames == 0 ? "有訊號但無有效幀（線接反、鮑率或 EP2 還是 PWM 模式）"
                            : !link ? "斷線（已輸出油門中位）" : "正常";
        printf("t=%lus %-6s ch/s=%lu byte/s=%lu CH1=%d CH2=%d LQ=%d RSSI=%d | 斷線=%lu 最長間隔=%lums 最低LQ=%ld 最低RSSI=%ld CRC錯=%lu 回覆=%lu\n",
               (unsigned long)tick, state, (unsigned long)(c - last_ch), (unsigned long)(b - last_bytes), ch[0], ch[1],
               lq, rssi, (unsigned long)s.drops, (unsigned long)s.max_gap_ms, (long)(s.min_lq > 100 ? -1 : s.min_lq),
               (long)s.min_rssi, (unsigned long)s.crc_errors, (unsigned long)devinfo);
        if (first_ch_us && tick == 5 + (uint32_t)(first_ch_us / 1000000))
            printf("首個位元組 %lld ms，首個通道幀 %lld ms（自開機）\n", (long long)(first_byte_us - boot_us) / 1000,
                   (long long)(first_ch_us - boot_us) / 1000);
        last_bytes = b;
        last_ch = c;

        uint8_t bat[8] = {0, 74}; // fixed 7.4 V, proves only that our TX line drives the EP2's UART
        crsf_send(0x08, bat, sizeof bat);
        uint8_t ping[2] = {0x00, 0xC8};
        crsf_send(0x28, ping, sizeof ping); // informational: not every ELRS build answers
        if (tick % 10 == 0 && s.seconds) summary_save();
    }
}
