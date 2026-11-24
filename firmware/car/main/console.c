// Console on the SuperMini's USB (USB-Serial/JTAG), one command per line. `help` lists them.
#include "car.h"
#include "settings.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "driver/gpio.h"
#include "driver/usb_serial_jtag.h"
#include "driver/usb_serial_jtag_vfs.h"
#include "esp_app_desc.h"
#include "esp_system.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static void status(void)
{
    int64_t age = g_car.ch_us ? (esp_timer_get_time() - g_car.ch_us) / 1000 : -1;
    printf("battery  %.2f V%s%s\n", g_car.vbat, g_car.battery ? "" : " (none: USB only)", g_car.low ? " LOW" : "");
    printf("link     %s, LQ %u%%, RSSI %d dBm, %lu frames, %lu bad, last %lld ms ago\n", car_link_ok() ? "up" : "down",
           g_car.lq, g_car.rssi, (unsigned long)g_car.frames, (unsigned long)g_car.bad_frames, age);
    printf("channels %u %u %u %u %u %u %u %u\n", g_car.ch[0], g_car.ch[1], g_car.ch[2], g_car.ch[3], g_car.ch[4],
           g_car.ch[5], g_car.ch[6], g_car.ch[7]);
    printf("out      steer %+.2f, throttle %+.2f\n", g_car.steer_out, g_car.throttle_out);
    printf("gyro     %s, yaw %+.1f deg/s, zero %+.2f%s\n", g_car.imu_ok ? "ok" : "none", g_car.yaw_dps,
           g_car.gyro_bias, g_car.gyro_zeroed ? "" : " (not yet: let the car sit still)");
    printf("settings car %u, limit %u%%, gyro %u%%%s, motor%s, steer%s, IR %s, VTX %s, cut-off %u mV\n",
           g_set.car_no, g_set.speed_limit, g_set.gyro_gain, g_set.gyro_rev ? " rev" : "",
           g_set.motor_rev ? " rev" : "", g_set.steer_rev ? " rev" : "", g_set.ir_on ? "on" : "off",
           g_set.vtx_on ? "on" : "off", g_set.cutoff_mv);
}

static void help(void)
{
    printf("status | watch [s] | car <1-15> | limit <0-100> | gyro <0-100> | gyrorev <0|1> | motorrev <0|1>\n"
           "steerrev <0|1> | ir <0|1> | vtx <0|1> | cutoff <mV> | off | reboot | version\n");
}

static void run(char *line)
{
    char *cmd = strtok(line, " \t");
    if (!cmd)
        return;
    char *arg = strtok(NULL, " \t");
    int v = arg ? atoi(arg) : -1;
    bool save = true;
    if (!strcmp(cmd, "status"))
        status(), save = false;
    else if (!strcmp(cmd, "watch")) {
        int s = v > 0 ? v : 5;
        for (int i = 0; i < s * 5; i++) {
            printf("%5.2fV %s LQ%3u st %4u th %4u -> %+.2f %+.2f yaw %+6.1f\n", g_car.vbat,
                   car_link_ok() ? "up  " : "down", g_car.lq, g_car.ch[CH_STEER], g_car.ch[CH_THROTTLE],
                   g_car.steer_out, g_car.throttle_out, g_car.yaw_dps);
            vTaskDelay(pdMS_TO_TICKS(200));
        }
        save = false;
    } else if (!strcmp(cmd, "car") && v >= 1 && v <= 15)
        g_set.car_no = v;
    else if (!strcmp(cmd, "limit") && v >= 0 && v <= 100)
        g_set.speed_limit = v;
    else if (!strcmp(cmd, "gyro") && v >= 0 && v <= 100)
        g_set.gyro_gain = v;
    else if (!strcmp(cmd, "gyrorev") && v >= 0)
        g_set.gyro_rev = v;
    else if (!strcmp(cmd, "motorrev") && v >= 0)
        g_set.motor_rev = v;
    else if (!strcmp(cmd, "steerrev") && v >= 0)
        g_set.steer_rev = v;
    else if (!strcmp(cmd, "ir") && v >= 0)
        g_set.ir_on = v;
    else if (!strcmp(cmd, "vtx") && v >= 0) {
        g_set.vtx_on = v;
        gpio_set_level(PIN_VTX_EN, v && g_car.battery);
    } else if (!strcmp(cmd, "cutoff") && v >= 5000 && v <= 8000)
        g_set.cutoff_mv = v;
    else if (!strcmp(cmd, "off"))
        power_off();
    else if (!strcmp(cmd, "reboot"))
        esp_restart();
    else if (!strcmp(cmd, "version"))
        printf("%s %s\n", esp_app_get_description()->project_name, esp_app_get_description()->version), save = false;
    else {
        help();
        return;
    }
    if (save) {
        settings_save();
        printf("ok\n");
    }
}

static void console_task(void *arg)
{
    char line[64];
    int n = 0;
    for (;;) {
        uint8_t c;
        if (usb_serial_jtag_read_bytes(&c, 1, portMAX_DELAY) != 1)
            continue;
        if (c == '\r' || c == '\n') {
            if (n) {
                line[n] = 0;
                run(line);
                n = 0;
            }
        } else if (n < (int)sizeof line - 1)
            line[n++] = c;
    }
}

void console_task_start(void)
{
    usb_serial_jtag_driver_config_t cfg = USB_SERIAL_JTAG_DRIVER_CONFIG_DEFAULT();
    if (usb_serial_jtag_driver_install(&cfg) != ESP_OK)
        return;
    usb_serial_jtag_vfs_use_driver();
    setvbuf(stdout, NULL, _IONBF, 0);
    xTaskCreatePinnedToCore(console_task, "console", 4096, NULL, 1, NULL, 0);
}
