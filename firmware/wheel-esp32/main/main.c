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
//   Start (36)          ignition on / off (starts in neutral, pedals released)
//   right / left paddle gear up / down (14 / 13): R N 1 2 3
//   P (32)              emergency stop
//   N (19)              bind the MULTI module

#include <math.h>
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
#include "ffb.h"
#include "multi.h"
#include "radio.h"
#if CONFIG_IDF_TARGET_ESP32P4
#include "sound.h"
#endif
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
#define BTN_GEAR_UP 14
#define BTN_GEAR_DOWN 13
#define BTN_ESTOP 32
// N: binds the MULTI module (multi.h)
#define BTN_BIND 19

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

static const char *gear_name(gear_t g) {
    static const char *names[] = {"R", "N", "1", "2", "3"};
    return names[g - GEAR_R];
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
        if (control_view(now_us).engine) {
            control_ignition_off("OFF");
            ESP_LOGI(TAG, "engine off");
        } else {
            const char *why = control_ignition_on(now_us);
            ESP_LOGI(TAG, "ignition: %s", why ? why : "ON");
        }
    }
    if ((pressed & WHEEL_BUTTON(BTN_BIND)) && radio_config().kind == RADIO_MULTI_SERIAL) {
        multi_bind();
    }
    for (int i = 0; i < 2; i++) {
        if (pressed & WHEEL_BUTTON(i ? BTN_GEAR_DOWN : BTN_GEAR_UP)) {
            const char *why = control_shift(i ? -1 : 1, now_us);
            ESP_LOGI(TAG, "gear %s%s%s", gear_name(control_view(now_us).gear), why ? "  refused: " : "", why ? why : "");
        }
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
                control_input(axes.steering, axes.gas, axes.brake, now);
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
            ffb_detach();
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

    hid_host_dev_info_t info = {0};
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
    if (info.VID == MOZA_VID) {
        ffb_attach(handle);
    }
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

// Force feedback like a car with power steering: light when parked, the
// self-centring grows with speed, a little damping for weight.
#define FFB_SPRING_OFF 0.10f
#define FFB_SPRING_SLOW 0.15f
#define FFB_SPRING_FAST 0.70f
#define FFB_DAMPER_OFF 0.25f
#define FFB_DAMPER_SLOW 0.15f
#define FFB_DAMPER_FAST 0.35f
// Recentring: a spring's pull is in proportion to how far off centre the
// wheel is, so a few degrees of trim would hardly move it. Its centre goes
// past the middle by RECENTRE_GAIN times the offset (at least
// RECENTRE_MIN_PUSH), which shrinks to nothing on arrival; done once within
// RECENTRE_DONE for RECENTRE_SETTLE_US.
#define FFB_SPRING_RECENTRE 1.0f
#define FFB_DAMPER_RECENTRE 0.40f
#define RECENTRE_GAIN 4.0f
#define RECENTRE_MIN_PUSH 0.03f
#define RECENTRE_DONE 0.005f
#define RECENTRE_SETTLE_US 300000

// A car that reaches full lock early on the wheel (steer_deg) gets a
// stiffer centring spring, so it pulls about as hard at the car's lock as
// before at the wheel's, up to SPRING_SCALE_MAX times.
#define SPRING_SCALE_MAX 2.5f

static void drive_ffb(const control_view_t *c, const radio_config_t *cfg, bool fresh) {
    if (!fresh) {
        ffb_set(0.0f, 0.0f);
        ffb_set_stop(1.0f);
        return;
    }
    float lock = (float)cfg->steer_deg / (float)WHEEL_DEG;
    ffb_set_stop(lock);
    float scale = fminf(1.0f / lock, SPRING_SCALE_MAX);
    static int64_t settled_at = -1;
    if (ffb_recentring()) {
        float p = c->steering;
        int64_t now = esp_timer_get_time();
        if (fabsf(p) > RECENTRE_DONE) {
            settled_at = -1;
            float push = fmaxf(fabsf(p) * RECENTRE_GAIN, RECENTRE_MIN_PUSH);
            ffb_set_centre(p > 0.0f ? -push : push);
        } else {
            ffb_set_centre(0.0f);
            if (settled_at < 0) {
                settled_at = now;
            } else if (now - settled_at > RECENTRE_SETTLE_US) {
                ffb_recentre_stop();
            }
        }
        ffb_set(FFB_SPRING_RECENTRE, FFB_DAMPER_RECENTRE);
        return;
    }
    settled_at = -1;
    ffb_set_centre(0.0f);
    if (!c->engine) {
        ffb_set(FFB_SPRING_OFF * scale, FFB_DAMPER_OFF);
        return;
    }
    float v = fabsf(c->speed);
    ffb_set((FFB_SPRING_SLOW + (FFB_SPRING_FAST - FFB_SPRING_SLOW) * v) * scale,
            FFB_DAMPER_SLOW + (FFB_DAMPER_FAST - FFB_DAMPER_SLOW) * v);
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
            .axes = a,
            .vid = vid,
            .pid = pid,
            .rate = rate,
            .ctl = control_view(now),
            .radio = crsf_status(),
            .multi = multi_status(),
            .cfg = radio_config(),
            .button = (button && now - button_at < (int64_t)BUTTON_SHOW_MS * 1000) ? button : 0,
        };
        display_show(&ds);
        drive_ffb(&ds.ctl, &ds.cfg, fresh);

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
        printf("steer %+5.2f  gas %4.2f  brake %4.2f  | %s %s  out %+5.2f %+5.2f  | %s %s rssi %d lq %d  | %4.0f "
               "rpt/s%s\n",
               a.steering, a.gas, a.brake, c.engine ? "ON " : "OFF", gear_name(c.gear), c.output.steering,
               c.output.throttle, radio_kind_name(ds.cfg.kind), r.link ? "LINK" : (r.module ? "TX  " : "NOTX"),
               r.rssi, r.lq, rate, fresh ? "" : "  STALE");
    }
}

void app_main(void) {
    ESP_LOGI(TAG, "wheel USB host test: plug the wheel base into the ESP32-OTG port");
    s_device_events = xQueueCreate(8, sizeof(device_event_t));
    control_init((int64_t)HEARTBEAT_TIMEOUT_MS * 1000);
    radio_init();
    crsf_start();
    multi_start();
    display_init();
#if CONFIG_IDF_TARGET_ESP32P4
    sound_start();
#endif

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
