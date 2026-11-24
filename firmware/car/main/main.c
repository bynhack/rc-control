// X2201 car main board (hardware/x2201-mainboard), ESP32-S3 SuperMini.
// CRSF from the EP2 drives the servo and the DRV8874; the IR LED sends the car number to the lap arch; the
// battery comes back to the wheel over CRSF. WiFi, MQTT and OTA come next (docs/platform-plan.md, stage 3, 4).
#include "car.h"
#include "settings.h"

#include "driver/gpio.h"
#include "esp_log.h"
#include "esp_ota_ops.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "car";

volatile car_state_t g_car;

void app_main(void)
{
    power_init();  // hold the power before anything else
    settings_init();
    battery_init();

    // No battery: USB only. Release the hold at once (see power_release_for_usb)
    float v = battery_read_now();
    g_car.vbat = v;
    g_car.battery = v > 4.0f;
    if (!g_car.battery)
        power_release_for_usb();

    gpio_reset_pin(PIN_VTX_EN);
    gpio_set_direction(PIN_VTX_EN, GPIO_MODE_OUTPUT);
    gpio_set_level(PIN_VTX_EN, g_set.vtx_on && g_car.battery);  // never without a battery: VBAT would be 0

    drive_init();  // servo centred, motor coasting
    led_init();
    crsf_init();
    imu_init();
    ir_init();

    drive_task_start();
    battery_task_start();
    power_task_start();
    led_task_start();
    console_task_start();

    const esp_app_desc_t *d = esp_app_get_description();
    ESP_LOGI(TAG, "%s %s, car %d, battery %.2f V", d->project_name, d->version, g_set.car_no, v);

    // A new image boots "pending verify" after an OTA (rollback on, docs/platform-plan.md section 5). The checks
    // that matter here: everything above came up and we've run 5 s without a reset.
    vTaskDelay(pdMS_TO_TICKS(5000));
    esp_ota_img_states_t st;
    if (esp_ota_get_state_partition(esp_ota_get_running_partition(), &st) == ESP_OK && st == ESP_OTA_IMG_PENDING_VERIFY)
        esp_ota_mark_app_valid_cancel_rollback();
}
