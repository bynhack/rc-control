// Battery voltage on IO9 through 100k / 22k (x 22 / 122). Also: no battery -> release the power hold (USB
// only); under the cut-off for 2 s -> no throttle until the voltage recovers by 0.2 V; CRSF telemetry at
// 5 Hz so the wheel's dashboard shows the car's battery without the server.
#include "car.h"
#include "settings.h"

#include "esp_adc/adc_cali.h"
#include "esp_adc/adc_cali_scheme.h"
#include "esp_adc/adc_oneshot.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "battery";

#define DIVIDER (122.0f / 22.0f)
#define NO_BATTERY_V 4.0f
#define LOW_MS 2000
#define RECOVER_MV 200

static adc_oneshot_unit_handle_t adc;
static adc_cali_handle_t cali;

float battery_read_now(void)
{
    int raw = 0, mv = 0, sum = 0;
    for (int i = 0; i < 8; i++) {
        adc_oneshot_read(adc, ADC_CHANNEL_8, &raw);  // IO9 = ADC1 channel 8
        if (cali)
            adc_cali_raw_to_voltage(cali, raw, &mv);
        else
            mv = raw * 3100 / 4095;
        sum += mv;
    }
    return sum / 8 / 1000.0f * DIVIDER;
}

static uint8_t percent(float v)
{
    // 2S Li-ion/LiPo under light load: 6.4 V empty .. 8.4 V full, roughly linear in between
    float p = (v - 6.4f) / 2.0f * 100.0f;
    return p < 0 ? 0 : p > 100 ? 100 : (uint8_t)p;
}

static void battery_task(void *arg)
{
    int low_ms = 0, tick = 0;
    for (;;) {
        vTaskDelay(pdMS_TO_TICKS(50));
        float v = battery_read_now();
        g_car.vbat = g_car.vbat == 0 ? v : g_car.vbat * 0.8f + v * 0.2f;
        bool present = g_car.vbat > NO_BATTERY_V;
        if (present != g_car.battery) {
            g_car.battery = present;
            ESP_LOGI(TAG, "%s %.2f V", present ? "battery" : "no battery,", g_car.vbat);
            if (!present)
                power_release_for_usb();
        }
        float cut = g_set.cutoff_mv / 1000.0f;
        if (present && g_car.vbat < cut) {
            low_ms += 50;
            if (low_ms >= LOW_MS && !g_car.low) {
                g_car.low = true;
                ESP_LOGW(TAG, "low battery %.2f V: throttle off", g_car.vbat);
            }
        } else {
            low_ms = 0;
            if (g_car.low && g_car.vbat > cut + RECOVER_MV / 1000.0f) {
                g_car.low = false;
                ESP_LOGI(TAG, "battery recovered %.2f V", g_car.vbat);
            }
        }
        if (++tick % 4 == 0 && present)
            crsf_send_battery(g_car.vbat, percent(g_car.vbat));
    }
}

void battery_init(void)
{
    adc_oneshot_unit_init_cfg_t unit = {.unit_id = ADC_UNIT_1};
    ESP_ERROR_CHECK(adc_oneshot_new_unit(&unit, &adc));
    adc_oneshot_chan_cfg_t ch = {.atten = ADC_ATTEN_DB_12, .bitwidth = ADC_BITWIDTH_DEFAULT};
    ESP_ERROR_CHECK(adc_oneshot_config_channel(adc, ADC_CHANNEL_8, &ch));
    adc_cali_curve_fitting_config_t cc = {.unit_id = ADC_UNIT_1, .chan = ADC_CHANNEL_8, .atten = ADC_ATTEN_DB_12,
                                          .bitwidth = ADC_BITWIDTH_DEFAULT};
    if (adc_cali_create_scheme_curve_fitting(&cc, &cali) != ESP_OK) {
        cali = NULL;
        ESP_LOGW(TAG, "no ADC calibration: voltages are rough");
    }
}

void battery_task_start(void)
{
    xTaskCreatePinnedToCore(battery_task, "battery", 3072, NULL, 5, NULL, 0);
}
