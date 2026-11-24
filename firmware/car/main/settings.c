#include "settings.h"

#include "esp_log.h"
#include "nvs.h"
#include "nvs_flash.h"

static const char *TAG = "settings";

settings_t g_set = {
    .car_no = 1,
    .speed_limit = 100,
    .gyro_gain = 0,
    .gyro_rev = false,
    .motor_rev = false,
    .steer_rev = false,
    .ir_on = true,
    .vtx_on = true,
    .cutoff_mv = 6000,  // 3.0 V a cell
};

#define KEY "car"

void settings_init(void)
{
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        nvs_flash_erase();
        err = nvs_flash_init();
    }
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "nvs: %s, using defaults", esp_err_to_name(err));
        return;
    }
    nvs_handle_t h;
    if (nvs_open("car", NVS_READONLY, &h) != ESP_OK)
        return;  // first boot: defaults
    settings_t s;
    size_t len = sizeof s;
    if (nvs_get_blob(h, KEY, &s, &len) == ESP_OK && len == sizeof s)
        g_set = s;
    nvs_close(h);
    if (g_set.car_no < 1 || g_set.car_no > 15)
        g_set.car_no = 1;
    if (g_set.speed_limit > 100)
        g_set.speed_limit = 100;
}

void settings_save(void)
{
    nvs_handle_t h;
    if (nvs_open("car", NVS_READWRITE, &h) != ESP_OK)
        return;
    nvs_set_blob(h, KEY, &g_set, sizeof g_set);
    nvs_commit(h);
    nvs_close(h);
}
