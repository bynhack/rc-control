// CRSF from the EP2 (ELRS receiver) on UART1: RC channels and link statistics in, battery telemetry out.
// Frame: [address][length][type][payload][crc8], length = type + payload + crc, CRC-8 poly 0xD5 over type
// and payload.
#include "car.h"

#include <string.h>

#include "driver/uart.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "crsf";

#define CRSF_UART UART_NUM_1
#define CRSF_BAUD 420000             // ELRS receivers' default
#define ADDR_FC 0xC8                 // flight controller: what a receiver talks to
#define TYPE_BATTERY 0x08
#define TYPE_LINK_STATS 0x14
#define TYPE_CHANNELS 0x16

static uint8_t crc8(const uint8_t *p, int n)
{
    uint8_t crc = 0;
    while (n--) {
        crc ^= *p++;
        for (int i = 0; i < 8; i++)
            crc = crc & 0x80 ? (uint8_t)(crc << 1) ^ 0xD5 : (uint8_t)(crc << 1);
    }
    return crc;
}

static void handle(const uint8_t *f, int len)
{
    // f = [type][payload...], len without the crc
    int64_t now = esp_timer_get_time();
    switch (f[0]) {
    case TYPE_CHANNELS:
        if (len < 23)
            return;
        {
            // 16 channels of 11 bits, little-endian bit order
            const uint8_t *p = f + 1;
            uint32_t bits = 0;
            int nbits = 0, c = 0;
            for (int i = 0; i < 22 && c < 16; i++) {
                bits |= (uint32_t)p[i] << nbits;
                nbits += 8;
                while (nbits >= 11 && c < 16) {
                    g_car.ch[c++] = bits & 0x7FF;
                    bits >>= 11;
                    nbits -= 11;
                }
            }
        }
        g_car.ch_us = now;
        g_car.frames++;
        break;
    case TYPE_LINK_STATS:
        if (len < 11)
            return;
        g_car.rssi = -(int8_t)f[1];  // uplink RSSI antenna 1, sent as a positive number
        g_car.lq = f[3];
        g_car.link_us = now;
        break;
    }
}

static void crsf_task(void *arg)
{
    static uint8_t buf[64];
    int n = 0;
    uint8_t rx[128];
    for (;;) {
        int got = uart_read_bytes(CRSF_UART, rx, sizeof rx, pdMS_TO_TICKS(20));
        for (int i = 0; i < got; i++) {
            uint8_t b = rx[i];
            if (n == 0) {
                // Receivers address frames to the FC (0xC8); some send 0xEE or 0xEA
                if (b == ADDR_FC || b == 0xEE || b == 0xEA)
                    buf[n++] = b;
                continue;
            }
            if (n == 1 && (b < 2 || b > 62)) {
                n = 0;  // not a length: resync
                continue;
            }
            buf[n++] = b;
            if (n >= 2 && n == buf[1] + 2) {
                int len = buf[1] - 1;  // type + payload
                if (crc8(buf + 2, len) == buf[n - 1])
                    handle(buf + 2, len);
                else
                    g_car.bad_frames++;
                n = 0;
            }
        }
    }
}

void crsf_send_battery(float volts, uint8_t percent)
{
    // Battery sensor: voltage and current in 0.1 units, big-endian; capacity used (mAh, 24 bits); remaining %
    uint8_t f[12];
    uint16_t dv = volts > 0 ? (uint16_t)(volts * 10.0f + 0.5f) : 0;
    f[0] = ADDR_FC;
    f[1] = 10;  // type + 8 payload + crc
    f[2] = TYPE_BATTERY;
    f[3] = dv >> 8;
    f[4] = dv & 0xFF;
    f[5] = 0;  // current: no sensor
    f[6] = 0;
    f[7] = 0;  // capacity used: unknown
    f[8] = 0;
    f[9] = 0;
    f[10] = percent;
    f[11] = crc8(f + 2, 9);
    uart_write_bytes(CRSF_UART, f, sizeof f);
}

bool car_link_ok(void)
{
    int64_t t = g_car.ch_us;
    return t && esp_timer_get_time() - t < LINK_TIMEOUT_US;
}

void crsf_init(void)
{
    uart_config_t cfg = {
        .baud_rate = CRSF_BAUD,
        .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_DEFAULT,
    };
    ESP_ERROR_CHECK(uart_driver_install(CRSF_UART, 512, 256, 0, NULL, 0));
    ESP_ERROR_CHECK(uart_param_config(CRSF_UART, &cfg));
    ESP_ERROR_CHECK(uart_set_pin(CRSF_UART, PIN_CRSF_TX, PIN_CRSF_RX, UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE));
    for (int i = 0; i < 16; i++)
        g_car.ch[i] = 992;
    xTaskCreatePinnedToCore(crsf_task, "crsf", 3072, NULL, 10, NULL, 1);
    ESP_LOGI(TAG, "UART1 %d baud, RX IO%d, TX IO%d", CRSF_BAUD, PIN_CRSF_RX, PIN_CRSF_TX);
}
