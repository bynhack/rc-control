// Standalone wheel controller on the Waveshare ESP32-P4 7B: wheel base over
// USB host in, the selected radio out (radio.h), no PC. Known bases
// (wheel.h: T300RS, MOZA R5) are parsed, the one picked on the screen or
// whichever is plugged in; any other HID device has its report descriptor
// and changing raw reports dumped so its layout can be worked out.
//
// Wiring:
//   USB-A (OTG)        <- wheel base
//   GPIO28 / GPIO30    -> ELRS module (crsf.h)
//   GPIO29             -> MULTI module (multi.h)
//   I2C terminal       -> MCP4728 for a toy remote (remote.h)
//   UART0              -> log and bench console, 115200, the "USB TO UART" port
//
// Wheel buttons (BUTTONS below has each base's numbers):
//   Start               ignition on / off (starts in neutral, pedals released)
//   right / left paddle gear up / down: R N 1 2 3
//   P / Cross           emergency stop
//   N / Triangle        bind the MULTI module

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
#include "remote.h"
#include "sound.h"
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

typedef struct {
    int arm, gear_up, gear_down, estop, bind;
} buttons_t;

// MOZA R5 numbering read off the log. T300RS (PS3 / PC mode): 1 / 2 left /
// right paddle (checked on the wheel); the rest in the order hid-tmff2's
// descriptor gives, 3 Cross, 4 Square, 5 Circle, 6 Triangle, 10 Start, still
// to check against "button N" on the screen.
static const buttons_t BUTTONS[WHEEL_KINDS] = {
    [WHEEL_MOZA] = {.arm = 36, .gear_up = 14, .gear_down = 13, .estop = 32, .bind = 19},
    [WHEEL_T300] = {.arm = 10, .gear_up = 2, .gear_down = 1, .estop = 3, .bind = 6},
};

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
static wheel_kind_t s_kind;
static int s_last_button;
static int64_t s_last_button_at_us;

static const char *gear_name(gear_t g) {
    static const char *names[] = {"R", "N", "1", "2", "3"};
    return names[g - GEAR_R];
}

// Button actions fire on the press edge.
static void handle_buttons(wheel_kind_t kind, uint64_t now_b, int64_t now_us) {
    const buttons_t *btn = &BUTTONS[kind];
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

    if (pressed & WHEEL_BUTTON(btn->estop)) {
        control_estop();
        ESP_LOGW(TAG, "E-STOP");
        return;
    }
    if (pressed & WHEEL_BUTTON(btn->arm)) {
        if (control_view(now_us).engine) {
            control_ignition_off("OFF");
            ESP_LOGI(TAG, "engine off");
        } else {
            const char *why = control_ignition_on(now_us);
            ESP_LOGI(TAG, "ignition: %s", why ? why : "ON");
        }
    }
    if ((pressed & WHEEL_BUTTON(btn->bind)) && radio_config().kind == RADIO_MULTI_SERIAL) {
        multi_bind();
    }
    for (int i = 0; i < 2; i++) {
        if (pressed & WHEEL_BUTTON(i ? btn->gear_down : btn->gear_up)) {
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
            // A base that isn't the one picked on the screen is left alone.
            wheel_kind_t kind = s_kind;
            bool ok = wheel_wanted(kind, ui_wheel_get()) && wheel_parse(kind, data, len, &axes);
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
                handle_buttons(kind, axes.buttons, now);
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
            s_kind = WHEEL_NONE;
            portEXIT_CRITICAL(&s_lock);
            break;
        case HID_HOST_INTERFACE_EVENT_TRANSFER_ERROR:
            ESP_LOGW(TAG, "transfer error");
            break;
        default:
            break;
    }
}

// A T300 first shows up as b65d. Ask its model, then tell it to switch, as
// Linux's hid-thrustmaster does; it drops off the bus and comes back as
// b66e. The interrupt packets first keep some bases from crashing.
static void t300_switch(hid_host_device_handle_t handle) {
    static const uint8_t setup[5][9] = {
        {0x42, 0x01},
        {0x0a, 0x04, 0x90, 0x03},
        {0x0a, 0x04, 0x00, 0x0c},
        {0x0a, 0x04, 0x12, 0x10},
        {0x0a, 0x04, 0x00, 0x06},
    };
    for (int i = 0; i < 5; i++) {
        hid_host_device_send_output_report(handle, setup[i], i ? 8 : 9);
    }
    uint8_t r[16] = {0};
    size_t n = 0;
    if (hid_host_device_vendor_request(handle, 0xc1, 73, 0, 0, r, sizeof(r), &n) != ESP_OK || n < 8) {
        ESP_LOGW(TAG, "T300: no answer to the model request");
        return;
    }
    // Answer type 0x49 or 0x47; the model is at b6 in both.
    uint16_t type = r[0] | (r[1] << 8);
    uint16_t model = r[6] | (r[7] << 8);
    if ((type != 0x49 && type != 0x47) || (model >> 8) != 0x02) {
        ESP_LOGW(TAG, "T300: model %04x (answer %04x) is not a T300, left as it is", model, type);
        return;
    }
    ESP_LOGI(TAG, "T300 model %04x: switching to its full mode", model);
    // It drops off before answering, so an error here is expected.
    hid_host_device_vendor_request(handle, 0x41, 83, 0x0005, 0, NULL, 0, NULL);
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
    wheel_kind_t kind = WHEEL_NONE;
    if (hid_host_get_device_info(handle, &info) == ESP_OK) {
        kind = wheel_kind(info.VID, info.PID);
        const char *name = wheel_kind_name(kind);
        ESP_LOGI(TAG, "device %04x:%04x  %ls / %ls  (%s%s)", info.VID, info.PID, info.iManufacturer, info.iProduct,
                 name ? name : "unknown layout, dumping reports",
                 name && !wheel_wanted(kind, ui_wheel_get()) ? ", not the one picked on the screen" : "");
        portENTER_CRITICAL(&s_lock);
        s_vid = info.VID;
        s_pid = info.PID;
        s_kind = kind;
        portEXIT_CRITICAL(&s_lock);
    }
    if (info.VID == T300_VID && info.PID == T300_PID_BOOT) {
        if (wheel_wanted(WHEEL_T300, ui_wheel_get())) {
            t300_switch(handle);
        }
        return;
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
    if (kind != WHEEL_NONE) {
        ffb_attach(handle, kind);
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
        wheel_kind_t kind;
        int button;
        int64_t button_at;
        portENTER_CRITICAL(&s_lock);
        vid = s_vid;
        pid = s_pid;
        kind = s_kind;
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
            .kind = kind,
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
    sound_start();
    remote_start();

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
