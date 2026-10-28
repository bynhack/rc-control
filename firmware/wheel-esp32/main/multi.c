#include "multi.h"

#include "sdkconfig.h"

#include "control.h"
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
#define BIND_MS 5000

// The car's protocol, from the MULTI protocol list (Multiprotocol.h).
// Futaba S-FHSS. No bind on the TX side: the receiver latches on to the
// first S-FHSS transmitter it hears while its bind button is held.
// OPTION is the CC2500 fine frequency tune, different for every module;
// -50 is the seller's value for the IRX4+. If the link is unstable, find
// the module's own value (MULTI docs/Frequency_Tuning.md).
#define PROTOCOL 21
#define SUB_PROTOCOL 0
#define RX_NUM 0
#define OPTION -50
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
