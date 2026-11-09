#include "remote.h"

#include "bsp/esp-bsp.h"
#include "control.h"
#include "driver/i2c_master.h"
#include "driver/uart.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "radio.h"

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static const char *TAG = "remote";

#define DAC_ADDR 0x60
// 100 kHz like the probe: the lead from the I2C terminal is long.
#define DAC_HZ 100000
#define PERIOD_MS 10
#define PROBE_EVERY_MS 2000
// Write only on a change, plus a refresh: the bus is shared with the touch panel.
#define REFRESH_MS 500

// Codes 0..4095 = 0..3.3 V. The remote runs from the same 3V3 (the DAC
// board's top-row VCC). Three points per channel, found on the bench with
// tools/remote_tune.html: full one way, rest, full the other way. The output
// never leaves the full points: outside them the remote's chip misreads the
// pots (the throttle at 2.1 V drives forward). Rest is the middle of the
// car's dead band; the dead bands themselves are handling (radio.h
// steer_start / thr_start), like any other car's. JC-02T-2.4G remote.
#define DAC_MAX 4095
#define STEER_LEFT 3320
#define STEER_CENTER 2020
#define STEER_RIGHT 660
#define THR_REVERSE 1720
#define THR_CENTER 1507
#define THR_FORWARD 1320

// Bench test without the wheel, lines on the log UART:
//   "d <A> <B>"            set the DAC codes directly
//   "x"                    back to the wheel
//   "w <steer> <gas> <brake>"  a simulated wheel sample (-1..1, 0..1, 0..1),
//                          through the driving model like the real one; send
//                          it every 50 ms, the model stops the engine after
//                          300 ms without one
//   "k start|up|down|stop" ignition, gear up / down, e-stop
//   "name <text>"          rename the active car
//   "kind <0..3>"          the active car's radio (radio_kind_t)
//   "dead <steerL> <steerR> <thrF> <thrR>"  the active car's dead bands, thousandths
//   "scan"                 log every address answering on the I2C bus
// While "w" samples arrive the state is logged 5 times a second for the page.
#define CONSOLE_UART UART_NUM_0

static portMUX_TYPE s_lock = portMUX_INITIALIZER_UNLOCKED;
static remote_status_t s_status;
static int s_override_a = -1, s_override_b = -1;
static int64_t s_sim_at = -1;
static int64_t s_override_at;
// The page repeats "d" every 0.5 s; without one for this long (a closed or
// crashed page) the wheel takes the remote back.
#define OVERRIDE_HOLD_MS 1500

#define SIM_LOG_MS 200
#define SIM_ACTIVE_MS 500

static const char *gear_name(gear_t g) {
    static const char *names[] = {"R", "N", "1", "2", "3"};
    return names[g - GEAR_R];
}

static void sim_key(const char *k) {
    int64_t now = esp_timer_get_time();
    const char *why = NULL;
    if (!strcmp(k, "start")) {
        if (control_view(now).engine) {
            control_ignition_off("OFF");
        } else {
            why = control_ignition_on(now);
        }
    } else if (!strcmp(k, "up") || !strcmp(k, "down")) {
        why = control_shift(k[0] == 'u' ? 1 : -1, now);
    } else if (!strcmp(k, "stop")) {
        control_estop();
    } else {
        return;
    }
    control_view_t v = control_view(now);
    ESP_LOGI(TAG, "sim key %s: engine %s gear %s%s%s", k, v.engine ? "ON" : "OFF", gear_name(v.gear),
             why ? "  refused: " : "", why ? why : "");
}

static void console_task(void *arg) {
    char line[48];
    int len = 0;
    for (;;) {
        uint8_t ch;
        if (uart_read_bytes(CONSOLE_UART, &ch, 1, portMAX_DELAY) != 1) {
            continue;
        }
        if (ch != '\n' && ch != '\r') {
            // Opening the port on the Mac can put a stray byte on the line.
            if (ch >= 0x20 && ch < 0x7F && len < (int)sizeof(line) - 1) {
                line[len++] = ch;
            }
            continue;
        }
        line[len] = 0;
        len = 0;
        int a, b, dl, dr, tf, tr;
        float s, g, br;
        char key[8];
        if (sscanf(line, "w %f %f %f", &s, &g, &br) == 3) {
            int64_t now = esp_timer_get_time();
            if (control_input_sim(s, g, br, now)) {
                taskENTER_CRITICAL(&s_lock);
                s_override_a = s_override_b = -1;
                s_sim_at = now;
                taskEXIT_CRITICAL(&s_lock);
            }
        } else if (line[0] == 'k' && line[1] == ' ' && sscanf(line, "k %7s", key) == 1) {
            sim_key(key);
        } else if (!strncmp(line, "name ", 5) && line[5]) {
            car_rename(car_active(), line + 5);
            ESP_LOGI(TAG, "car %d renamed %s", car_active() + 1, line + 5);
        } else if (sscanf(line, "dead %d %d %d %d", &dl, &dr, &tf, &tr) == 4 && dl >= 0 && dr >= 0 && tf >= 0 &&
                   tr >= 0 && dl <= STEER_START_MAX && dr <= STEER_START_MAX && tf <= THR_START_MAX &&
                   tr <= THR_START_MAX) {
            radio_config_t c = radio_config();
            c.steer_start[0] = dl, c.steer_start[1] = dr, c.thr_start[0] = tf, c.thr_start[1] = tr;
            radio_set(&c);
            ESP_LOGI(TAG, "dead bands: steering L %d R %d, throttle F %d R %d", dl, dr, tf, tr);
        } else if (sscanf(line, "kind %d", &a) == 1 && a >= 0 && a < RADIO_KINDS) {
            radio_config_t c = radio_config();
            c.kind = (radio_kind_t)a;
            radio_set(&c);
        } else if (sscanf(line, "d %d %d", &a, &b) == 2 && a >= 0 && a <= DAC_MAX && b >= 0 && b <= DAC_MAX) {
            taskENTER_CRITICAL(&s_lock);
            s_override_a = a, s_override_b = b;
            s_override_at = esp_timer_get_time();
            taskEXIT_CRITICAL(&s_lock);
            ESP_LOGI(TAG, "test: A %d (%.2f V)  B %d (%.2f V)", a, a * 3.3f / 4096, b, b * 3.3f / 4096);
        } else if (!strcmp(line, "scan")) {
            char found[160] = "";
            for (int addr = 0x08; addr < 0x78; addr++) {
                if (i2c_master_probe(bsp_i2c_get_handle(), addr, 20) == ESP_OK) {
                    snprintf(found + strlen(found), sizeof(found) - strlen(found), " 0x%02x", addr);
                }
            }
            ESP_LOGI(TAG, "I2C scan:%s", found[0] ? found : " nothing");
        } else if (line[0] == 'x') {
            taskENTER_CRITICAL(&s_lock);
            s_override_a = s_override_b = -1;
            taskEXIT_CRITICAL(&s_lock);
            ESP_LOGI(TAG, "test off: following the wheel");
        }
    }
}

// -1..1 onto a channel: -1 = full_neg, 0 = rest, +1 = full_pos.
static uint16_t to_code(float v, int full_neg, int rest, int full_pos) {
    v = v < -1.0f ? -1.0f : (v > 1.0f ? 1.0f : v);
    int c = rest + (int)lroundf(v < 0 ? -v * (full_neg - rest) : v * (full_pos - rest));
    return c < 0 ? 0 : (c > DAC_MAX ? DAC_MAX : c);
}

// Fast Write: A..D in turn, 2 bytes each (power-down bits 00 = on). It keeps
// the reference and gain already set (factory: VCC, x1).
static esp_err_t write_dac(i2c_master_dev_handle_t dev, uint16_t a, uint16_t b) {
    uint16_t ch[4] = {a, b, 0, 0};
    uint8_t buf[8];
    for (int i = 0; i < 4; i++) {
        buf[2 * i] = (ch[i] >> 8) & 0x0F;
        buf[2 * i + 1] = ch[i] & 0xFF;
    }
    return i2c_master_transmit(dev, buf, sizeof(buf), 50);
}

// The DAC loads its EEPROM at power-up, before the P4 has booted: keep the
// remote's rest position there (steering centre, throttle stop), or the car
// moves the moment it all powers on. Sequential Write from channel A with
// VREF = VCC, gain x1, powered on; only when the stored values differ, since
// each write wears the EEPROM.
static void store_rest(i2c_master_dev_handle_t dev) {
    const uint16_t rest[4] = {STEER_CENTER, THR_CENTER, 0, 0};
    uint8_t rd[24];
    if (i2c_master_receive(dev, rd, sizeof(rd), 50) != ESP_OK) {
        return;
    }
    bool same = true;
    for (int i = 0; i < 4; i++) {
        const uint8_t *e = &rd[i * 6 + 3]; // status, then the EEPROM's 2 bytes
        same &= (e[1] & 0xF0) == 0 && (((e[1] & 0x0F) << 8) | e[2]) == rest[i];
    }
    if (same) {
        return;
    }
    uint8_t buf[9] = {0x50};
    for (int i = 0; i < 4; i++) {
        buf[1 + 2 * i] = (rest[i] >> 8) & 0x0F;
        buf[2 + 2 * i] = rest[i] & 0xFF;
    }
    esp_err_t err = i2c_master_transmit(dev, buf, sizeof(buf), 50);
    vTaskDelay(pdMS_TO_TICKS(60)); // EEPROM write time
    ESP_LOGI(TAG, "power-up values stored: A %u B %u (%s)", rest[0], rest[1], esp_err_to_name(err));
}

static void remote_task(void *arg) {
    i2c_master_bus_handle_t bus = bsp_i2c_get_handle();
    i2c_master_dev_handle_t dev = NULL;
    const i2c_device_config_t cfg = {
        .dev_addr_length = I2C_ADDR_BIT_LEN_7,
        .device_address = DAC_ADDR,
        .scl_speed_hz = DAC_HZ,
    };
    int64_t next_probe = 0;
    TickType_t wake = xTaskGetTickCount();
    for (;;) {
        vTaskDelayUntil(&wake, pdMS_TO_TICKS(PERIOD_MS));
        int64_t now = esp_timer_get_time();
        if (!dev) {
            if (now < next_probe) {
                continue;
            }
            next_probe = now + PROBE_EVERY_MS * 1000LL;
            if (i2c_master_probe(bus, DAC_ADDR, 50) != ESP_OK ||
                i2c_master_bus_add_device(bus, &cfg, &dev) != ESP_OK) {
                continue;
            }
            ESP_LOGI(TAG, "MCP4728 found at 0x%02x", DAC_ADDR);
            store_rest(dev);
        }
        radio_config_t rc = radio_config();
        control_output_t o = control_output(now);
        uint16_t steer = STEER_CENTER, thr = THR_CENTER;
        // Only the car set to REMOTE drives it; for any other car the remote
        // rests, so a toy car left on doesn't drive along.
        if (rc.kind == RADIO_REMOTE) {
            steer = to_code(radio_steering(&rc, o.steering), STEER_LEFT, STEER_CENTER, STEER_RIGHT);
            thr = to_code(radio_throttle(&rc, o.throttle, o.reverse), THR_REVERSE, THR_CENTER, THR_FORWARD);
        }
        taskENTER_CRITICAL(&s_lock);
        if (s_override_a >= 0 && now - s_override_at > OVERRIDE_HOLD_MS * 1000LL) {
            s_override_a = s_override_b = -1;
        }
        if (s_override_a >= 0) {
            steer = s_override_a, thr = s_override_b;
        }
        taskEXIT_CRITICAL(&s_lock);
        // The DAC first; logging (a few ms on the UART) only after it.
        static uint16_t last_steer = 0xFFFF, last_thr = 0xFFFF;
        static int64_t next_refresh;
        static bool was_ok = true;
        if (steer != last_steer || thr != last_thr || now >= next_refresh) {
            bool ok = write_dac(dev, steer, thr) == ESP_OK;
            if (ok) {
                last_steer = steer, last_thr = thr;
                next_refresh = now + REFRESH_MS * 1000LL;
            } else {
                i2c_master_bus_reset(bus);
            }
            if (ok != was_ok) {
                ESP_LOGW(TAG, "MCP4728 %s", ok ? "back" : "not answering");
                was_ok = ok;
            }
            taskENTER_CRITICAL(&s_lock);
            s_status = (remote_status_t){.found = ok, .steer = steer, .thr = thr};
            taskEXIT_CRITICAL(&s_lock);
        }
        static int64_t next_sim_log;
        taskENTER_CRITICAL(&s_lock);
        bool sim = s_sim_at >= 0 && now - s_sim_at < SIM_ACTIVE_MS * 1000LL;
        taskEXIT_CRITICAL(&s_lock);
        if (sim && now >= next_sim_log) {
            next_sim_log = now + SIM_LOG_MS * 1000LL;
            control_view_t v = control_view(now);
            ESP_LOGI(TAG, "sim: engine %s gear %s speed %+.2f out %+.2f %+.2f dac %u %u%s%s", v.engine ? "ON" : "OFF",
                     gear_name(v.gear), v.speed, o.steering, o.throttle, steer, thr, v.notice ? "  " : "",
                     v.notice ? v.notice : "");
        }
    }
}

void remote_start(void) {
    if (bsp_i2c_init() != ESP_OK) {
        ESP_LOGE(TAG, "no I2C bus");
        return;
    }
    xTaskCreatePinnedToCore(remote_task, "remote", 6144, NULL, 4, NULL, 1);
    if (uart_driver_install(CONSOLE_UART, 256, 0, 0, NULL, 0) == ESP_OK) {
        xTaskCreatePinnedToCore(console_task, "remote_con", 6144, NULL, 2, NULL, 1);
    }
}

remote_status_t remote_status(void) {
    taskENTER_CRITICAL(&s_lock);
    remote_status_t s = s_status;
    taskEXIT_CRITICAL(&s_lock);
    return s;
}
