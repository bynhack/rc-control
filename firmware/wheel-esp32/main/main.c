// Standalone wheel controller: wheel base over USB host in, CRSF to an ELRS
// TX module out, no PC. Known bases (wheel.h: T300RS, MOZA R5) are parsed;
// any other HID device has its report descriptor and changing raw reports
// dumped so its layout can be worked out.
//
// Wiring:
//   ESP32-OTG port  <- wheel base (via OTG adapter; the port must supply 5 V)
//   GPIO17          -> ELRS TX module CRSF pin (crsf.h)
//   GPIO8..12       -> round status screen (display.h)
//   UART0 (TX0)     -> log, 115200; CH340C port or a 3.3 V-safe USB-TTL
//
// Wheel buttons (MOZA R5 numbering, read off the log):
//   Start (36)          arm / disarm (arming needs the pedals released)
//   right / left paddle speed tier up / down (14 / 13)
//   P (32)              emergency stop

#include <stdio.h>
#include <string.h>

#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include "usb/hid_host.h"
#include "usb/usb_host.h"

#include "control.h"
#include "crsf.h"
#include "display.h"
#include "wheel.h"

static const char *TAG = "wheel";

#define RAW_REPORTS_TO_DUMP 8
// Raw dumps of changing reports from unknown devices, at most this often.
#define CHANGE_DUMP_MS 50
#define UI_PERIOD_MS 33
// Log every Nth screen update (~10 Hz).
#define PRINT_EVERY 3
// A report this stale means the wheel is gone or stuck.
#define STALE_MS 250
// No wheel input for this long: outputs go neutral and the car disarms.
#define HEARTBEAT_TIMEOUT_MS 300
// Shows the last pressed button number on screen this long, for mapping.
#define BUTTON_SHOW_MS 2000

#define BTN_ARM 36
#define BTN_SPEED_UP 14
#define BTN_SPEED_DOWN 13
#define BTN_ESTOP 32

typedef struct {
    hid_host_device_handle_t handle;
    hid_host_driver_event_t event;
} device_event_t;

static QueueHandle_t s_device_events;

// Latest parsed state, written by the HID driver task, read by the printer.
static portMUX_TYPE s_lock = portMUX_INITIALIZER_UNLOCKED;
static wheel_axes_t s_axes;
static int64_t s_axes_at_us = -1;
static uint32_t s_reports;
static uint16_t s_vid, s_pid; // 0 while nothing is attached
static int s_last_button;
static int64_t s_last_button_at_us;

static const char *speed_name(speed_t s) {
    return s == SPEED_HIGH ? "H" : (s == SPEED_MID ? "M" : "L");
}

// Button actions fire on the press edge.
static void handle_buttons(uint64_t now_b, int64_t now_us) {
    static uint64_t prev;
    uint64_t pressed = now_b & ~prev;
    prev = now_b;
    if (!pressed) {
        return;
    }

    int n = __builtin_ctzll(pressed) + 1;
    portENTER_CRITICAL(&s_lock);
    s_last_button = n;
    s_last_button_at_us = now_us;
    portEXIT_CRITICAL(&s_lock);
    ESP_LOGI(TAG, "button %d", n);

    if (pressed & WHEEL_BUTTON(BTN_ESTOP)) {
        control_estop();
        ESP_LOGW(TAG, "E-STOP");
        return;
    }
    if (pressed & WHEEL_BUTTON(BTN_ARM)) {
        if (control_view(now_us).armed) {
            control_disarm("DISARMED");
            ESP_LOGI(TAG, "disarmed");
        } else {
            const char *why = control_arm(now_us);
            ESP_LOGI(TAG, "arm: %s", why ? why : "ARMED");
        }
    }
    speed_t sp = control_speed();
    if ((pressed & WHEEL_BUTTON(BTN_SPEED_UP)) && sp < SPEED_HIGH) {
        control_set_speed(sp + 1);
        ESP_LOGI(TAG, "speed %s", speed_name(sp + 1));
    } else if ((pressed & WHEEL_BUTTON(BTN_SPEED_DOWN)) && sp > SPEED_LOW) {
        control_set_speed(sp - 1);
        ESP_LOGI(TAG, "speed %s", speed_name(sp - 1));
    }
}

static void dump_hex(const char *label, const uint8_t *d, size_t n) {
    char line[3 * 64 + 1];
    size_t m = n < 64 ? n : 64;
    for (size_t i = 0; i < m; i++) {
        snprintf(line + 3 * i, 4, "%02x ", d[i]);
    }
    line[3 * m] = '\0';
    ESP_LOGI(TAG, "%s (%u bytes): %s", label, (unsigned)n, line);
}

// Dumps reports from a device we cannot parse, only when they change.
static void dump_if_changed(const uint8_t *d, size_t n) {
    static uint8_t last[64];
    static size_t last_len;
    static int64_t last_at;
    int64_t now = esp_timer_get_time();
    if ((n == last_len && memcmp(d, last, n) == 0) || now - last_at < (int64_t)CHANGE_DUMP_MS * 1000) {
        return;
    }
    memcpy(last, d, n);
    last_len = n;
    last_at = now;
    dump_hex("changed", d, n);
}

// Runs in the HID driver's background task.
static void interface_callback(hid_host_device_handle_t handle, const hid_host_interface_event_t event, void *arg) {
    switch (event) {
        case HID_HOST_INTERFACE_EVENT_INPUT_REPORT: {
            uint8_t data[64];
            size_t len = 0;
            if (hid_host_device_get_raw_input_report_data(handle, data, sizeof(data), &len) != ESP_OK) {
                return;
            }
            wheel_axes_t axes;
            bool ok = wheel_parse(s_vid, s_pid, data, len, &axes);
            uint32_t n;
            int64_t now = esp_timer_get_time();
            portENTER_CRITICAL(&s_lock);
            n = ++s_reports;
            if (ok) {
                s_axes = axes;
                s_axes_at_us = now;
            }
            portEXIT_CRITICAL(&s_lock);
            if (ok) {
                control_input(axes.steering, axes.throttle, now);
                handle_buttons(axes.buttons, now);
            }
            if (n <= RAW_REPORTS_TO_DUMP) {
                dump_hex(ok ? "report" : "report (unparsed)", data, len);
            } else if (!ok) {
                dump_if_changed(data, len);
            }
            break;
        }
        case HID_HOST_INTERFACE_EVENT_DISCONNECTED:
            ESP_LOGW(TAG, "interface disconnected");
            hid_host_device_close(handle);
            portENTER_CRITICAL(&s_lock);
            s_vid = s_pid = 0;
            portEXIT_CRITICAL(&s_lock);
            break;
        case HID_HOST_INTERFACE_EVENT_TRANSFER_ERROR:
            ESP_LOGW(TAG, "transfer error");
            break;
        default:
            break;
    }
}

// Runs in the HID driver's background task; hand over to the main task,
// which is allowed to open the device.
static void device_callback(hid_host_device_handle_t handle, const hid_host_driver_event_t event, void *arg) {
    const device_event_t ev = {.handle = handle, .event = event};
    xQueueSend(s_device_events, &ev, 0);
}

static void open_device(hid_host_device_handle_t handle) {
    hid_host_dev_params_t params;
    ESP_ERROR_CHECK(hid_host_device_get_params(handle, &params));
    ESP_LOGI(TAG, "HID interface connected: addr %d, iface %d, subclass %d, protocol %d", params.addr,
             params.iface_num, params.sub_class, params.proto);

    const hid_host_device_config_t config = {.callback = interface_callback, .callback_arg = NULL};
    ESP_ERROR_CHECK(hid_host_device_open(handle, &config));

    hid_host_dev_info_t info;
    if (hid_host_get_device_info(handle, &info) == ESP_OK) {
        const char *name = wheel_name(info.VID, info.PID);
        ESP_LOGI(TAG, "device %04x:%04x  %ls / %ls  (%s)", info.VID, info.PID, info.iManufacturer, info.iProduct,
                 name ? name : "unknown layout, dumping reports");
        portENTER_CRITICAL(&s_lock);
        s_vid = info.VID;
        s_pid = info.PID;
        portEXIT_CRITICAL(&s_lock);
    }
    size_t desc_len = 0;
    const uint8_t *desc = hid_host_get_report_descriptor(handle, &desc_len);
    if (desc != NULL) {
        ESP_LOGI(TAG, "report descriptor, %u bytes:", (unsigned)desc_len);
        for (size_t i = 0; i < desc_len; i += 32) {
            dump_hex("desc", desc + i, desc_len - i < 32 ? desc_len - i : 32);
        }
    }
    ESP_ERROR_CHECK(hid_host_device_start(handle));
}

static void usb_lib_task(void *arg) {
    const usb_host_config_t config = {.skip_phy_setup = false, .intr_flags = ESP_INTR_FLAG_LEVEL1};
    ESP_ERROR_CHECK(usb_host_install(&config));
    xTaskNotifyGive((TaskHandle_t)arg);
    while (true) {
        uint32_t flags;
        usb_host_lib_handle_events(portMAX_DELAY, &flags);
        if (flags & USB_HOST_LIB_EVENT_FLAGS_NO_CLIENTS) {
            usb_host_device_free_all();
        }
    }
}

static void ui_task(void *arg) {
    uint32_t last_reports = 0;
    int64_t last_t = esp_timer_get_time();
    float rate = 0;
    for (uint32_t tick = 0;; tick++) {
        vTaskDelay(pdMS_TO_TICKS(UI_PERIOD_MS));
        wheel_axes_t a;
        int64_t at;
        uint32_t reports;
        uint16_t vid, pid;
        int button;
        int64_t button_at;
        portENTER_CRITICAL(&s_lock);
        vid = s_vid;
        pid = s_pid;
        button = s_last_button;
        button_at = s_last_button_at_us;
        a = s_axes;
        at = s_axes_at_us;
        reports = s_reports;
        portEXIT_CRITICAL(&s_lock);

        int64_t now = esp_timer_get_time();
        bool fresh = at >= 0 && (now - at) <= (int64_t)STALE_MS * 1000;
        const display_state_t ds = {
            .wheel = fresh,
            .vid = vid,
            .pid = pid,
            .rate = rate,
            .ctl = control_view(now),
            .radio = crsf_status(),
            .button = (button && now - button_at < (int64_t)BUTTON_SHOW_MS * 1000) ? button : 0,
        };
        display_show(&ds);

        if (tick % PRINT_EVERY != 0) {
            continue;
        }
        rate = (float)(reports - last_reports) * 1e6f / (float)(now - last_t);
        last_reports = reports;
        last_t = now;
        if (at < 0) {
            continue; // nothing parsed yet
        }
        control_view_t c = ds.ctl;
        crsf_status_t r = ds.radio;
        printf("steer %+5.2f  gas %4.2f  brake %4.2f  | %s %s  out %+5.2f %+5.2f  | %s rssi %d lq %d  | %4.0f rpt/s%s\n",
               a.steering, a.gas, a.brake, c.armed ? "ARMED" : "SAFE ", speed_name(c.speed), c.output.steering,
               c.output.throttle, r.link ? "LINK" : (r.module ? "TX  " : "NOTX"), r.rssi, r.lq, rate,
               fresh ? "" : "  STALE");
    }
}

void app_main(void) {
    ESP_LOGI(TAG, "wheel USB host test: plug the wheel base into the ESP32-OTG port");
    s_device_events = xQueueCreate(8, sizeof(device_event_t));
    control_init((int64_t)HEARTBEAT_TIMEOUT_MS * 1000);
    crsf_start();
    display_init();

    xTaskCreatePinnedToCore(usb_lib_task, "usb_lib", 4096, xTaskGetCurrentTaskHandle(), 2, NULL, 0);
    ulTaskNotifyTake(pdFALSE, pdMS_TO_TICKS(1000));

    const hid_host_driver_config_t hid_config = {
        .create_background_task = true,
        .task_priority = 5,
        .stack_size = 4096,
        .core_id = 0,
        .callback = device_callback,
        .callback_arg = NULL,
    };
    ESP_ERROR_CHECK(hid_host_install(&hid_config));
    xTaskCreatePinnedToCore(ui_task, "ui", 4096, NULL, 1, NULL, 1);

    device_event_t ev;
    while (true) {
        if (xQueueReceive(s_device_events, &ev, portMAX_DELAY) && ev.event == HID_HOST_DRIVER_EVENT_CONNECTED) {
            open_device(ev.handle);
        }
    }
}
