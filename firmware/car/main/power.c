// Push-button power (hardware/PLAN.md, 開關機):
//   On:  the button lifts the buck's EN through D4; the S3 boots and holds EN with TX (IO43) through D5.
//   Off: a press reads low on RX (IO44, through Q6). The S3 drops TX, and the board goes off on release.
// The off press has to be held POWER_OFF_HOLD_MS, so a knock in a crash doesn't turn the car off.
#include "car.h"

#include "driver/gpio.h"
#include "esp_log.h"
#include "esp_sleep.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "soc/rtc_cntl_reg.h"

static const char *TAG = "power";

#define POWER_OFF_HOLD_MS 800

static bool held;

void power_init(void)
{
    // First thing in app_main: the button may already be up
    gpio_reset_pin(PIN_HOLD);
    gpio_set_direction(PIN_HOLD, GPIO_MODE_OUTPUT);
    gpio_set_level(PIN_HOLD, 1);
    held = true;

    gpio_config_t btn = {
        .pin_bit_mask = 1ULL << PIN_BTN,
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_ENABLE,  // the board has no pull-up of its own
    };
    gpio_config(&btn);
}

// USB in, no battery: the buck's VIN is 0 V, and TX through D5 would put about 3 V on its EN, over the
// LMR51430's VIN + 0.3 V. Drop the hold; the module runs from USB anyway.
void power_release_for_usb(void)
{
    if (!held)
        return;
    gpio_set_level(PIN_HOLD, 0);
    held = false;
    ESP_LOGW(TAG, "no battery: hold released (USB power only)");
}

void power_off(void)
{
    ESP_LOGW(TAG, "power off");
    // Outputs safe: motor coasting, VTX off, IR dark
    gpio_set_level(PIN_IN1, 0);
    gpio_set_level(PIN_IN2, 0);
    gpio_set_level(PIN_VTX_EN, 0);
    gpio_set_level(PIN_IR, 0);
    gpio_set_level(PIN_HOLD, 0);
    held = false;
    // As the 5 V falls, a brown-out reset would boot the S3 again, and the ROM idles TX high: through D5 that
    // lifts EN and the board turns itself back on. Turn the detector off, lock TX low and sleep until the
    // power is gone. To be tested on the board (docs/project-notes.md).
    REG_CLR_BIT(RTC_CNTL_BROWN_OUT_REG, RTC_CNTL_BROWN_OUT_RST_ENA);
    REG_CLR_BIT(RTC_CNTL_BROWN_OUT_REG, RTC_CNTL_BROWN_OUT_ENA);
    gpio_hold_en(PIN_HOLD);
    gpio_deep_sleep_hold_en();
    // Wait for the button to be let go first: while it's down, D4 keeps EN up
    while (gpio_get_level(PIN_BTN) == 0)
        vTaskDelay(pdMS_TO_TICKS(10));
    vTaskDelay(pdMS_TO_TICKS(50));
    esp_deep_sleep_start();
}

static void power_task(void *arg)
{
    // The press that turned the board on is probably still down: wait for it to be let go
    while (gpio_get_level(PIN_BTN) == 0)
        vTaskDelay(pdMS_TO_TICKS(20));
    int down_ms = 0;
    for (;;) {
        vTaskDelay(pdMS_TO_TICKS(20));
        if (gpio_get_level(PIN_BTN) == 0) {
            down_ms += 20;
            if (down_ms >= POWER_OFF_HOLD_MS && held)
                power_off();
        } else {
            down_ms = 0;
        }
    }
}

void power_task_start(void)
{
    xTaskCreatePinnedToCore(power_task, "power", 3072, NULL, 3, NULL, 0);
}
