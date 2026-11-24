// X2201 car main board: pins and the shared state. Pin map and circuit: hardware/PLAN.md.
#pragma once

#include <stdbool.h>
#include <stdint.h>

// ---- pins (ESP32-S3 SuperMini on hardware/x2201-mainboard) ----
#define PIN_HOLD 43      // TX: high holds the buck's EN through D5, low lets the board turn off
#define PIN_BTN 44       // RX: the power button through Q6, low while pressed (internal pull-up)
#define PIN_CRSF_RX 13   // from the EP2's TX
#define PIN_CRSF_TX 12   // to the EP2's RX
#define PIN_SDA 11       // gyro, LSM6DSV16X at 0x6A
#define PIN_SCL 10
#define PIN_VBAT 9       // battery x 22 / 122, ADC1 channel 8
#define PIN_SERVO 8
#define PIN_IN1 7        // DRV8874 IN1 (forward), PWM mode: 10 forward, 01 reverse, 11 brake, 00 coast
#define PIN_VTX_EN 6     // high powers the VTX (Q3 -> Q2)
#define PIN_IR 5         // the IR LED through Q4: high = lit
#define PIN_IN2 4        // DRV8874 IN2 (reverse)
#define PIN_IMU_INT 3
#define PIN_RGB 48       // the SuperMini's own WS2812

// ---- CRSF channels, as the wheel controller sends them (firmware/wheel-controller/main/crsf.c) ----
#define CH_STEER 0  // channel 1
#define CH_THROTTLE 1  // channel 2

// ---- the car's state, written by one task each, read by the rest ----
typedef struct {
    // CRSF, written by crsf.c
    uint16_t ch[16];          // 172..1811, 992 centre
    int64_t ch_us;            // esp_timer time of the last channels frame, 0 = never
    uint32_t frames;          // channel frames received
    uint32_t bad_frames;      // CRC errors
    uint8_t lq;               // uplink link quality, %
    int8_t rssi;              // uplink RSSI, dBm
    int64_t link_us;          // time of the last link statistics frame
    // battery.c
    float vbat;               // volts, filtered; 0 until the first reading
    bool battery;             // a battery is connected (vbat > 4 V)
    bool low;                 // under the cut-off: no throttle
    // imu.c
    bool imu_ok;
    float yaw_dps;            // z rate, zero removed; 0 until a zero is known
    float gyro_bias;          // the zero rate in use, deg/s
    bool gyro_zeroed;         // a zero is known (from NVS, or the car has sat still once)
    // drive.c
    float throttle_out;       // -1..1 after the ESC logic (negative = reverse, braking reads 0)
    float steer_out;          // -1..1 sent to the servo, gyro included
} car_state_t;

extern volatile car_state_t g_car;

// Link considered alive while channels keep coming
#define LINK_TIMEOUT_US (300 * 1000)
bool car_link_ok(void);

// ---- modules ----
void settings_init(void);
void power_init(void);          // the very first thing: hold the power
void power_task_start(void);
void power_off(void);           // never returns
void power_release_for_usb(void);
void crsf_init(void);
void crsf_send_battery(float volts, uint8_t percent);
void drive_init(void);
void drive_task_start(void);
void battery_init(void);
float battery_read_now(void);   // one raw reading, volts
void battery_task_start(void);
void ir_init(void);
void imu_init(void);
void led_init(void);
void led_task_start(void);
void console_task_start(void);
