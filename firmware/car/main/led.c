// Status on the SuperMini's own WS2812 (GPIO48):
//   green      link up
//   blue blink no link (radio off, or the EP2 not bound)
//   red blink  battery low: throttle off
//   white blink USB power only, no battery
#include "car.h"

#include "driver/rmt_tx.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static rmt_channel_handle_t chan;
static rmt_encoder_handle_t enc;

static void rgb(uint8_t r, uint8_t g, uint8_t b)
{
    uint8_t grb[3] = {g, r, b};
    rmt_transmit_config_t tx = {.loop_count = 0};
    rmt_transmit(chan, enc, grb, 3, &tx);
    rmt_tx_wait_all_done(chan, 10);
}

static void led_task(void *arg)
{
    for (int t = 0;; t++) {
        vTaskDelay(pdMS_TO_TICKS(250));
        bool blink = t & 1;
        if (!g_car.battery)
            blink ? rgb(8, 8, 8) : rgb(0, 0, 0);
        else if (g_car.low)
            blink ? rgb(24, 0, 0) : rgb(0, 0, 0);
        else if (car_link_ok())
            rgb(0, 16, 0);
        else
            blink ? rgb(0, 0, 24) : rgb(0, 0, 0);
    }
}

void led_init(void)
{
    rmt_tx_channel_config_t cfg = {
        .gpio_num = PIN_RGB,
        .clk_src = RMT_CLK_SRC_DEFAULT,
        .resolution_hz = 10000000,  // 0.1 us ticks
        .mem_block_symbols = 48,
        .trans_queue_depth = 2,
    };
    if (rmt_new_tx_channel(&cfg, &chan) != ESP_OK)
        return;
    rmt_bytes_encoder_config_t bc = {
        .bit0 = {.level0 = 1, .duration0 = 3, .level1 = 0, .duration1 = 9},  // 0.3 us high, 0.9 us low
        .bit1 = {.level0 = 1, .duration0 = 9, .level1 = 0, .duration1 = 3},
        .flags.msb_first = 1,
    };
    if (rmt_new_bytes_encoder(&bc, &enc) != ESP_OK || rmt_enable(chan) != ESP_OK)
        return;
    rgb(0, 0, 0);
}

void led_task_start(void)
{
    if (chan)
        xTaskCreatePinnedToCore(led_task, "led", 2560, NULL, 2, NULL, 0);
}

