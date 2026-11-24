// Lap transponder on the board's IR LED (D6 through Q4, IO5): the same frames as firmware/transponder, so
// the finish-line arch (firmware/lap-arch) reads this car the same way.
//   38 kHz carrier, a third on; T = 400 us
//   header burst 4T, gap 2T; 8 bits LSB first, each burst 1T then gap 1T (0) or 2T (1):
//   bits 0..3 the car number, 4..7 its complement; stop burst 1T; then 4 ms + a random 0..8 ms.
// The LED only ever lights in these bursts: R6 is an 0805 and would burn about 0.4 W if IO5 stayed high.
#include "car.h"
#include "settings.h"

#include "driver/rmt_tx.h"
#include "esp_log.h"
#include "esp_random.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "ir";

#define T_US 400

static rmt_channel_handle_t chan;
static rmt_encoder_handle_t copy;

static int build(rmt_symbol_word_t *s, int car)
{
    int data = (car & 0x0f) | ((~car & 0x0f) << 4);
    int n = 0;
    s[n++] = (rmt_symbol_word_t){.level0 = 1, .duration0 = 4 * T_US, .level1 = 0, .duration1 = 2 * T_US};
    for (int i = 0; i < 8; i++) {
        int gap = (data >> i) & 1 ? 2 : 1;
        s[n++] = (rmt_symbol_word_t){.level0 = 1, .duration0 = T_US, .level1 = 0, .duration1 = gap * T_US};
    }
    // stop burst, then the fixed 4 ms (the random part is a task delay)
    s[n++] = (rmt_symbol_word_t){.level0 = 1, .duration0 = T_US, .level1 = 0, .duration1 = 4000};
    return n;
}

static void ir_task(void *arg)
{
    rmt_symbol_word_t sym[10];
    rmt_transmit_config_t tx = {.loop_count = 0, .flags.eot_level = 0};
    for (;;) {
        if (!g_set.ir_on) {
            vTaskDelay(pdMS_TO_TICKS(100));
            continue;
        }
        int n = build(sym, g_set.car_no);
        rmt_transmit(chan, copy, sym, n * sizeof sym[0], &tx);
        rmt_tx_wait_all_done(chan, 100);
        vTaskDelay(pdMS_TO_TICKS(esp_random() % 9));  // 0..8 ms, so two cars side by side drift apart
    }
}

void ir_init(void)
{
    rmt_tx_channel_config_t cfg = {
        .gpio_num = PIN_IR,
        .clk_src = RMT_CLK_SRC_DEFAULT,
        .resolution_hz = 1000000,  // 1 us ticks
        .mem_block_symbols = 48,
        .trans_queue_depth = 2,
    };
    ESP_ERROR_CHECK(rmt_new_tx_channel(&cfg, &chan));
    rmt_carrier_config_t carrier = {.frequency_hz = 38000, .duty_cycle = 0.33f};
    ESP_ERROR_CHECK(rmt_apply_carrier(chan, &carrier));
    rmt_copy_encoder_config_t cc = {};
    ESP_ERROR_CHECK(rmt_new_copy_encoder(&cc, &copy));
    ESP_ERROR_CHECK(rmt_enable(chan));
    xTaskCreatePinnedToCore(ir_task, "ir", 3072, NULL, 6, NULL, 0);
    ESP_LOGI(TAG, "car %d on IO%d", g_set.car_no, PIN_IR);
}
