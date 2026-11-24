// Gyro: ST LSM6DSV16X at I2C 0x6A (SA0 low), SDA IO11, SCL IO10, 4.7k pull-ups on the board.
// Only the z rate (yaw) is used, for the steering assist in drive.c. Missing or not answering: the car
// drives without it (hardware/PLAN.md: a board may come without the gyro).
// Zero rate: no calibration at power-on, so the car can be held or moved however while it boots. The zero is
// kept in NVS and refreshed whenever the car sits still: 1 s with the throttle off and the rate steady.
// A board that has never sat still has no zero yet and reads 0 (no assist) until it does.
// Registers from the LSM6DSV16X datasheet (DS13510): WHO_AM_I 0Fh = 70h, CTRL2 11h (gyro ODR / mode),
// CTRL3 12h (BDU, IF_INC), CTRL6 15h (gyro full scale), OUTZ_L_G 26h. To check on the first board.
#include "car.h"

#include <math.h>

#include "driver/i2c_master.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "nvs.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "imu";

#define ADDR 0x6A
#define WHO_AM_I 0x0F
#define WHO_AM_I_VAL 0x70
#define CTRL2 0x11
#define CTRL3 0x12
#define CTRL6 0x15
#define OUTZ_L_G 0x26
#define ODR_G_960HZ 0x09        // high-performance mode (OP_MODE_G = 000)
#define FS_G_1000DPS 0x03
#define DPS_PER_LSB 0.035f      // at +-1000 dps
#define WINDOW 200              // 1 s at 200 Hz
#define STILL_PP 1.2f           // deg/s peak to peak over the window: steady enough to be standing still
#define STILL_MAX_SHIFT 5.0f    // a still window this far from the known zero is a slow turn, not a zero
#define SAVE_SHIFT 0.3f         // write the zero back to NVS when it has moved this far
#define SAVE_GAP_US (60LL * 1000 * 1000)

static i2c_master_dev_handle_t dev;

static esp_err_t wr(uint8_t reg, uint8_t val)
{
    uint8_t b[2] = {reg, val};
    return i2c_master_transmit(dev, b, 2, 20);
}

static esp_err_t rd(uint8_t reg, uint8_t *out, size_t n)
{
    return i2c_master_transmit_receive(dev, &reg, 1, out, n, 20);
}

static bool read_z(float *dps)
{
    uint8_t b[2];
    if (rd(OUTZ_L_G, b, 2) != ESP_OK)
        return false;
    *dps = (int16_t)(b[0] | b[1] << 8) * DPS_PER_LSB;
    return true;
}

// zero rate in NVS as milli-deg/s, beside the settings blob (own key: the blob's size stays the same)
static bool bias_load(float *b)
{
    nvs_handle_t h;
    int32_t v;
    if (nvs_open("car", NVS_READONLY, &h) != ESP_OK)
        return false;
    bool ok = nvs_get_i32(h, "gbias", &v) == ESP_OK;
    nvs_close(h);
    if (ok)
        *b = v / 1000.0f;
    return ok;
}

static void bias_save(float b)
{
    nvs_handle_t h;
    if (nvs_open("car", NVS_READWRITE, &h) != ESP_OK)
        return;
    nvs_set_i32(h, "gbias", (int32_t)(b * 1000.0f));
    nvs_commit(h);
    nvs_close(h);
}

static void imu_task(void *arg)
{
    float bias = 0, saved = 0, z;
    bool have = bias_load(&bias);
    bool stored = have;  // NVS holds a zero
    saved = bias;
    int64_t saved_at = -SAVE_GAP_US;
    g_car.gyro_bias = bias;
    g_car.gyro_zeroed = have;
    if (have)
        ESP_LOGI(TAG, "zero %.2f deg/s from NVS", bias);
    else
        ESP_LOGI(TAG, "no zero yet: waiting for the car to sit still");

    float sum = 0, lo = 1e9f, hi = -1e9f;
    int n = 0;
    bool quiet = true;  // throttle off through the window
    TickType_t wake = xTaskGetTickCount();
    int fails = 0;
    for (;;) {
        vTaskDelayUntil(&wake, pdMS_TO_TICKS(5));
        if (!read_z(&z)) {
            if (++fails == 20) {
                g_car.imu_ok = false;
                g_car.yaw_dps = 0;
                ESP_LOGW(TAG, "gyro stopped answering: assist off");
            }
            continue;
        }
        fails = 0;
        g_car.imu_ok = true;
        g_car.yaw_dps = have ? z - bias : 0;

        sum += z;
        lo = z < lo ? z : lo;
        hi = z > hi ? z : hi;
        quiet = quiet && g_car.throttle_out == 0;
        if (++n < WINDOW)
            continue;
        float mean = sum / n;
        if (quiet && hi - lo < STILL_PP && (!have || fabsf(mean - bias) < STILL_MAX_SHIFT)) {
            bias = have ? bias + 0.5f * (mean - bias) : mean;
            have = true;
            g_car.gyro_bias = bias;
            g_car.gyro_zeroed = true;
            int64_t now = esp_timer_get_time();
            if (!stored || (fabsf(bias - saved) > SAVE_SHIFT && now - saved_at > SAVE_GAP_US)) {
                bias_save(bias);
                stored = true;
                saved = bias;
                saved_at = now;
                ESP_LOGI(TAG, "zero %.2f deg/s saved", bias);
            }
        }
        sum = 0, lo = 1e9f, hi = -1e9f, n = 0, quiet = true;
    }
}

void imu_init(void)
{
    i2c_master_bus_config_t bc = {
        .i2c_port = I2C_NUM_0,
        .sda_io_num = PIN_SDA,
        .scl_io_num = PIN_SCL,
        .clk_source = I2C_CLK_SRC_DEFAULT,
        .glitch_ignore_cnt = 7,
    };
    i2c_master_bus_handle_t bus;
    if (i2c_new_master_bus(&bc, &bus) != ESP_OK)
        return;
    if (i2c_master_probe(bus, ADDR, 20) != ESP_OK) {
        ESP_LOGW(TAG, "no gyro at 0x%02X: driving without it", ADDR);
        return;
    }
    i2c_device_config_t dc = {.dev_addr_length = I2C_ADDR_BIT_LEN_7, .device_address = ADDR, .scl_speed_hz = 400000};
    if (i2c_master_bus_add_device(bus, &dc, &dev) != ESP_OK)
        return;
    uint8_t id = 0;
    if (rd(WHO_AM_I, &id, 1) != ESP_OK || id != WHO_AM_I_VAL) {
        ESP_LOGW(TAG, "WHO_AM_I 0x%02X, expected 0x%02X: driving without the gyro", id, WHO_AM_I_VAL);
        return;
    }
    wr(CTRL3, 0x44);  // BDU (don't mix halves of two samples), IF_INC (auto-increment)
    wr(CTRL6, FS_G_1000DPS);
    wr(CTRL2, ODR_G_960HZ);
    xTaskCreatePinnedToCore(imu_task, "imu", 3072, NULL, 8, NULL, 1);
    ESP_LOGI(TAG, "LSM6DSV16X found");
}
