// Steering servo and the DRV8874 brushed ESC.
//
// The ESC behaves like a hobby car ESC, which is what the wheel controller expects (it sends "brake, then
// reverse" for the R gear): forward; pulling back while going forward brakes; back to neutral, then pulling
// back again reverses. Neutral coasts.
//
// DRV8874 in PWM mode (PMODE high): IN1 IN2 = 10 forward, 01 reverse, 11 brake, 00 coast. Driving uses slow
// decay at 20 kHz: forward holds IN1 high and PWMs IN2, so each off-time brakes instead of coasting. That
// keeps the speed close to linear in the throttle at the low end, which a drift car needs.
//
// Safety: no channels for LINK_TIMEOUT_US (or none yet) -> coast and centre the steering. Battery under the
// cut-off -> no throttle.
#include "car.h"
#include "settings.h"

#include <math.h>

#include "driver/ledc.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "drive";

#define SERVO_TIMER LEDC_TIMER_0
#define SERVO_CH LEDC_CHANNEL_0
#define SERVO_HZ 50
#define SERVO_BITS LEDC_TIMER_14_BIT
#define MOTOR_TIMER LEDC_TIMER_1
#define MOTOR_CH1 LEDC_CHANNEL_1
#define MOTOR_CH2 LEDC_CHANNEL_2
#define MOTOR_HZ 20000
#define MOTOR_BITS LEDC_TIMER_10_BIT
#define MOTOR_FULL (1 << 10)
#define DEADBAND 0.04f
#define REVERSE_ARM_MS 100  // neutral this long after a brake arms reverse
#define LOOP_MS 5

static float ch_norm(uint16_t v)
{
    // 172..1811 -> -1..1, 992 = 0
    float x = ((float)v - 992.0f) / 819.0f;
    return x < -1 ? -1 : x > 1 ? 1 : x;
}

static void servo_us(float us)
{
    uint32_t duty = (uint32_t)(us * (1 << 14) / (1000000.0f / SERVO_HZ));
    ledc_set_duty(LEDC_LOW_SPEED_MODE, SERVO_CH, duty);
    ledc_update_duty(LEDC_LOW_SPEED_MODE, SERVO_CH);
}

static void motor_pins(uint32_t d1, uint32_t d2)
{
    ledc_set_duty(LEDC_LOW_SPEED_MODE, MOTOR_CH1, d1);
    ledc_update_duty(LEDC_LOW_SPEED_MODE, MOTOR_CH1);
    ledc_set_duty(LEDC_LOW_SPEED_MODE, MOTOR_CH2, d2);
    ledc_update_duty(LEDC_LOW_SPEED_MODE, MOTOR_CH2);
}

// d: -1..1 drive (negative = reverse), brake: 0..1 (used when d == 0)
static void motor(float d, float brake)
{
    if (g_set.motor_rev)
        d = -d;
    uint32_t on = (uint32_t)(fabsf(d) * MOTOR_FULL + 0.5f);
    if (d > 0)
        motor_pins(MOTOR_FULL, MOTOR_FULL - on);  // IN1 high, IN2 high = brake during the off-time
    else if (d < 0)
        motor_pins(MOTOR_FULL - on, MOTOR_FULL);
    else if (brake > 0) {
        uint32_t b = (uint32_t)(brake * MOTOR_FULL + 0.5f);
        motor_pins(b, b);  // both high = brake, both low = coast
    } else
        motor_pins(0, 0);
}

static void drive_task(void *arg)
{
    bool reverse_ok = true;  // from a standstill at power-on, pulling back reverses
    bool braked = false;
    int neutral_ms = 0;
    bool was_ok = false;
    TickType_t wake = xTaskGetTickCount();
    for (;;) {
        vTaskDelayUntil(&wake, pdMS_TO_TICKS(LOOP_MS));
        bool ok = car_link_ok();
        if (ok != was_ok) {
            ESP_LOGW(TAG, "%s", ok ? "link up" : "link lost: coast, steering centred");
            was_ok = ok;
        }

        // ---- steering ----
        float steer = ok ? ch_norm(g_car.ch[CH_STEER]) : 0.0f;
        if (g_set.steer_rev)
            steer = -steer;
        float us = 1500.0f + steer * 512.0f;  // 988..2012 us, the CRSF range
        if (ok && g_car.imu_ok && g_set.gyro_gain) {
            // Counter-steer against the yaw rate: at 100 %, 1 us per deg/s
            float yaw = g_set.gyro_rev ? -g_car.yaw_dps : g_car.yaw_dps;
            float corr = -yaw * g_set.gyro_gain / 100.0f;
            corr = corr < -400 ? -400 : corr > 400 ? 400 : corr;
            us += corr;
        }
        us = us < 900 ? 900 : us > 2100 ? 2100 : us;
        servo_us(us);
        g_car.steer_out = (us - 1500.0f) / 512.0f;

        // ---- throttle ----
        float t = ok ? ch_norm(g_car.ch[CH_THROTTLE]) : 0.0f;
        if (fabsf(t) < DEADBAND)
            t = 0;
        else
            t = (t - copysignf(DEADBAND, t)) / (1.0f - DEADBAND);
        float limit = g_set.speed_limit / 100.0f;
        if (g_car.low)
            limit = 0;

        if (t > 0) {
            reverse_ok = false;  // after going forward, pulling back brakes first
            braked = false;
            motor(t * limit, 0);
            g_car.throttle_out = t * limit;
        } else if (t < 0 && reverse_ok) {
            motor(t * limit, 0);
            g_car.throttle_out = t * limit;
        } else if (t < 0) {
            braked = true;
            neutral_ms = 0;
            motor(0, -t);  // braking works even with the throttle cut
            g_car.throttle_out = 0;
        } else {
            // Brake, then neutral long enough: the next pull back reverses
            if (braked) {
                neutral_ms += LOOP_MS;
                if (neutral_ms >= REVERSE_ARM_MS) {
                    reverse_ok = true;
                    braked = false;
                }
            }
            motor(0, 0);
            g_car.throttle_out = 0;
        }
    }
}

void drive_init(void)
{
    ledc_timer_config_t st = {
        .speed_mode = LEDC_LOW_SPEED_MODE,
        .timer_num = SERVO_TIMER,
        .duty_resolution = SERVO_BITS,
        .freq_hz = SERVO_HZ,
        .clk_cfg = LEDC_AUTO_CLK,
    };
    ESP_ERROR_CHECK(ledc_timer_config(&st));
    ledc_timer_config_t mt = {
        .speed_mode = LEDC_LOW_SPEED_MODE,
        .timer_num = MOTOR_TIMER,
        .duty_resolution = MOTOR_BITS,
        .freq_hz = MOTOR_HZ,
        .clk_cfg = LEDC_AUTO_CLK,
    };
    ESP_ERROR_CHECK(ledc_timer_config(&mt));
    ledc_channel_config_t ch[] = {
        {.gpio_num = PIN_SERVO, .speed_mode = LEDC_LOW_SPEED_MODE, .channel = SERVO_CH, .timer_sel = SERVO_TIMER,
         .duty = 0},
        {.gpio_num = PIN_IN1, .speed_mode = LEDC_LOW_SPEED_MODE, .channel = MOTOR_CH1, .timer_sel = MOTOR_TIMER,
         .duty = 0},
        {.gpio_num = PIN_IN2, .speed_mode = LEDC_LOW_SPEED_MODE, .channel = MOTOR_CH2, .timer_sel = MOTOR_TIMER,
         .duty = 0},
    };
    for (int i = 0; i < 3; i++)
        ESP_ERROR_CHECK(ledc_channel_config(&ch[i]));
    servo_us(1500);
    motor(0, 0);
}

void drive_task_start(void)
{
    xTaskCreatePinnedToCore(drive_task, "drive", 4096, NULL, 9, NULL, 1);
}
