#include "crsf.h"

#include <string.h>

#include "control.h"
#include "driver/gpio.h"
#include "driver/uart.h"
#include "esp_log.h"
#include "esp_rom_gpio.h"
#include "esp_timer.h"
#include "soc/gpio_pins.h"
#include "soc/uart_periph.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "radio.h"

static const char *TAG = "crsf";

#define CRSF_UART UART_NUM_1
#if CONFIG_IDF_TARGET_ESP32P4
// Waveshare P4 7B: P3 expansion terminal. The board's UART terminal (H8) is
// UART0 on GPIO37/38, shared with the CH343P console, so it can't be used.
// CRSF_PIN carries both directions in one-wire mode, or only ours (to the
// module's RX) in two-wire mode, where the module's TX comes in on
// CRSF_RX_PIN.
#define CRSF_PIN 28
#define CRSF_RX_PIN 30
#else
#define CRSF_PIN 17
#define CRSF_RX_PIN 16
#endif
#define CRSF_BAUD 400000
#define FRAME_PERIOD_MS 4
// One device ping every this many frames (~1 s), to tell TX alive from dead.
#define PING_EVERY 250
#define MODULE_TIMEOUT_US (3 * 1000 * 1000)
#define LINK_TIMEOUT_US (1500 * 1000)

// Same as the PC program's rc-control.toml.
#define STEERING_CHANNEL 1
#define THROTTLE_CHANNEL 2

#define ADDR_TX_MODULE 0xEE
#define ADDR_HANDSET 0xEA
#define ADDR_FC 0xC8
#define TYPE_LINK_STATS 0x14
#define TYPE_RC_CHANNELS 0x16
#define TYPE_DEVICE_PING 0x28
#define CH_MIN 172
#define CH_CENTER 992
#define CH_MAX 1811
#define CHANNELS 16

static portMUX_TYPE s_lock = portMUX_INITIALIZER_UNLOCKED;
static int64_t s_module_at = -1;
static int64_t s_link_at = -1;
static int s_rssi, s_lq;
static uint32_t s_frames;

static uint8_t crc8(const uint8_t *d, size_t n) {
    uint8_t crc = 0;
    for (size_t i = 0; i < n; i++) {
        crc ^= d[i];
        for (int b = 0; b < 8; b++) {
            crc = (crc & 0x80) ? (uint8_t)((crc << 1) ^ 0xD5) : (uint8_t)(crc << 1);
        }
    }
    return crc;
}

// Wraps body (type + payload) into a frame for the TX module; returns length.
static size_t frame(const uint8_t *body, size_t n, uint8_t *out) {
    out[0] = ADDR_TX_MODULE;
    out[1] = (uint8_t)(n + 1);
    memcpy(out + 2, body, n);
    out[2 + n] = crc8(body, n);
    return n + 3;
}

static uint16_t to_channel(float v) {
    v = v < -1.0f ? -1.0f : (v > 1.0f ? 1.0f : v);
    float span = v < 0 ? (CH_CENTER - CH_MIN) : (CH_MAX - CH_CENTER);
    int ch = (int)(CH_CENTER + v * span + (v < 0 ? -0.5f : 0.5f));
    return (uint16_t)(ch < CH_MIN ? CH_MIN : (ch > CH_MAX ? CH_MAX : ch));
}

static size_t rc_frame(const uint16_t ch[CHANNELS], uint8_t *out) {
    uint8_t body[23] = {TYPE_RC_CHANNELS};
    uint32_t acc = 0;
    int bits = 0, i = 1;
    for (int c = 0; c < CHANNELS; c++) {
        acc |= (uint32_t)(ch[c] & 0x7FF) << bits;
        bits += 11;
        while (bits >= 8) {
            body[i++] = (uint8_t)acc;
            acc >>= 8;
            bits -= 8;
        }
    }
    return frame(body, sizeof(body), out);
}

// ELRS sends RSSI as a signed byte; classic CRSF the magnitude.
static int rssi_dbm(uint8_t b) {
    int s = (int8_t)b;
    return s > 0 ? -s : s;
}

// Anything with a good CRC that is not one of our own frame types came from
// the module (in one-wire mode line_tx() keeps our own bytes off the
// receiver).
static void parse(const uint8_t *data, size_t n) {
    static uint8_t buf[128];
    static size_t len;
    if (len + n > sizeof(buf)) {
        len = 0;
    }
    memcpy(buf + len, data, n);
    len += n;

    size_t i = 0;
    while (i + 4 <= len) {
        uint8_t a = buf[i], l = buf[i + 1];
        if ((a != ADDR_HANDSET && a != ADDR_TX_MODULE && a != ADDR_FC) || l < 2 || l > 64) {
            i++;
            continue;
        }
        if (i + 2 + l > len) {
            break;
        }
        const uint8_t *body = buf + i + 2;
        if (crc8(body, l - 1) != buf[i + 1 + l]) {
            i++;
            continue;
        }
        uint8_t type = body[0];
        int64_t now = esp_timer_get_time();
        if (type != TYPE_RC_CHANNELS && type != TYPE_DEVICE_PING) {
            portENTER_CRITICAL(&s_lock);
            s_module_at = now;
            if (type == TYPE_LINK_STATS && l >= 11) {
                // payload: up_rssi1 up_rssi2 up_lq up_snr ant mode power dn_rssi dn_lq dn_snr
                s_link_at = now;
                s_rssi = rssi_dbm(body[1]);
                s_lq = body[3];
            }
            portEXIT_CRITICAL(&s_lock);
        }
        i += 2 + l;
    }
    memmove(buf, buf + i, len - i);
    len -= i;
}

// One wire: drive it only while sending, then let the module talk.
// gpio_set_direction() resets the pad to plain GPIO, so the UART signals are
// (re)attached through the GPIO matrix afterwards, as ELRS's own handset
// code does.
static void line_tx(void) {
    // Feed the receiver a constant idle-high so our own bytes do not echo.
    esp_rom_gpio_connect_in_signal(GPIO_MATRIX_CONST_ONE_INPUT, UART_PERIPH_SIGNAL(CRSF_UART, SOC_UART_RX_PIN_IDX),
                                   false);
    gpio_set_pull_mode(CRSF_PIN, GPIO_FLOATING);
    gpio_set_level(CRSF_PIN, 1);
    gpio_set_direction(CRSF_PIN, GPIO_MODE_OUTPUT);
    esp_rom_gpio_connect_out_signal(CRSF_PIN, UART_PERIPH_SIGNAL(CRSF_UART, SOC_UART_TX_PIN_IDX), false, false);
}

static void line_rx(void) {
    gpio_set_direction(CRSF_PIN, GPIO_MODE_INPUT);
    gpio_set_pull_mode(CRSF_PIN, GPIO_PULLUP_ONLY);
    esp_rom_gpio_connect_in_signal(CRSF_PIN, UART_PERIPH_SIGNAL(CRSF_UART, SOC_UART_RX_PIN_IDX), false);
}

// Two wires: the UART's own pins, both always connected.
static void wire_two(void) {
    gpio_reset_pin(CRSF_PIN);
    gpio_set_pull_mode(CRSF_RX_PIN, GPIO_PULLUP_ONLY);
    ESP_ERROR_CHECK(uart_set_pin(CRSF_UART, CRSF_PIN, CRSF_RX_PIN, UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE));
}

static void wire_one(void) {
    gpio_reset_pin(CRSF_RX_PIN);
    gpio_reset_pin(CRSF_PIN);
    line_rx();
}

static void sender_task(void *arg) {
    uint8_t out[64], in[128];
    uint16_t ch[CHANNELS];
    const uint8_t ping_body[] = {TYPE_DEVICE_PING, ADDR_TX_MODULE, ADDR_HANDSET};
    TickType_t wake = xTaskGetTickCount();
    bool duplex = false;
    for (uint32_t n = 0;; n++) {
        int64_t now = esp_timer_get_time();
        control_tick(now);
        radio_config_t rc = radio_config();
        if (rc.kind != RADIO_ELRS) {
            // Another radio is selected: stay silent, so only one car moves.
            vTaskDelayUntil(&wake, pdMS_TO_TICKS(FRAME_PERIOD_MS));
            continue;
        }
        if (ui_elrs_duplex_get() != duplex) {
            duplex = !duplex;
            duplex ? wire_two() : wire_one();
            uart_flush_input(CRSF_UART);
            if (duplex) {
                ESP_LOGI(TAG, "two wires: TX GPIO%d, RX GPIO%d", CRSF_PIN, CRSF_RX_PIN);
            } else {
                ESP_LOGI(TAG, "one wire on GPIO%d", CRSF_PIN);
            }
        }
        size_t len;
        if (n % PING_EVERY == 0) {
            len = frame(ping_body, sizeof(ping_body), out);
        } else {
            control_output_t o = control_output(now);
            for (int c = 0; c < CHANNELS; c++) {
                ch[c] = CH_CENTER;
            }
            ch[STEERING_CHANNEL - 1] = to_channel(radio_steering(&rc, o.steering));
            ch[THROTTLE_CHANNEL - 1] = to_channel(radio_throttle(&rc, o.throttle, o.reverse));
            len = rc_frame(ch, out);
        }

        if (duplex) {
            uart_write_bytes(CRSF_UART, out, len);
        } else {
            line_tx();
            uart_write_bytes(CRSF_UART, out, len);
            uart_wait_tx_done(CRSF_UART, pdMS_TO_TICKS(FRAME_PERIOD_MS));
            line_rx();
        }
        portENTER_CRITICAL(&s_lock);
        s_frames++;
        portEXIT_CRITICAL(&s_lock);

        vTaskDelayUntil(&wake, pdMS_TO_TICKS(FRAME_PERIOD_MS));
        int got = uart_read_bytes(CRSF_UART, in, sizeof(in), 0);
        if (got > 0) {
            parse(in, (size_t)got);
        }
    }
}

void crsf_start(void) {
    const uart_config_t cfg = {
        .baud_rate = CRSF_BAUD,
        .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_DEFAULT,
    };
    ESP_ERROR_CHECK(uart_driver_install(CRSF_UART, 512, 0, 0, NULL, 0));
    ESP_ERROR_CHECK(uart_param_config(CRSF_UART, &cfg));
    // One wire to start with; the task switches to two if that is set. In
    // one-wire mode TX and RX share the pad and line_tx()/line_rx() switch it
    // per frame.
    wire_one();
    xTaskCreatePinnedToCore(sender_task, "crsf", 4096, NULL, 10, NULL, 1);
    ESP_LOGI(TAG, "CRSF on GPIO%d, %d baud, every %d ms", CRSF_PIN, CRSF_BAUD, FRAME_PERIOD_MS);
}

crsf_status_t crsf_status(void) {
    int64_t now = esp_timer_get_time();
    portENTER_CRITICAL(&s_lock);
    crsf_status_t s = {
        .module = s_module_at >= 0 && now - s_module_at <= MODULE_TIMEOUT_US,
        .link = s_link_at >= 0 && now - s_link_at <= LINK_TIMEOUT_US,
        .rssi = s_rssi,
        .lq = s_lq,
        .frames = s_frames,
    };
    portEXIT_CRITICAL(&s_lock);
    return s;
}
