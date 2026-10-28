#include "radio.h"

#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "nvs.h"
#include "nvs_flash.h"

static const char *TAG = "radio";

#define NVS_NS "radio"
#define NVS_KEY "cfg"
// Bump when radio_config_t changes, so an old blob is ignored.
#define CFG_VERSION 1

// Surface protocols first. Option: CC2500 fine tune (S-FHSS -50 is the
// IRX4+ seller's value), DSM channel count.
const multi_proto_t MULTI_PROTOS[] = {
    {"AFHDS 2A", 28, 0, 0},  {"AFHDS", 1, 0, 0},      {"S-FHSS", 21, 0, -50}, {"FRSKY D8", 3, 0, 0},
    {"FRSKY D16", 15, 0, 0}, {"DSM AUTO", 6, 4, 7},   {"KYOSHO FHSS", 73, 0, 0}, {"KYOSHO HYPE", 73, 1, 0},
    {"KYOSHO2", 93, 0, 0},   {"RADIOLINK", 74, 0, 0}, {"TRAXXAS", 43, 0, 0},  {"LOSI", 89, 0, 0},
};
const int MULTI_PROTO_COUNT = sizeof(MULTI_PROTOS) / sizeof(MULTI_PROTOS[0]);

typedef struct {
    uint8_t version;
    radio_config_t cfg;
} stored_t;

static portMUX_TYPE s_lock = portMUX_INITIALIZER_UNLOCKED;
// The MXO car (FlySky) is bound through the module's dial, so PPM; the
// ELRS car wants steering reversed.
static radio_config_t s_cfg = {
    .kind = RADIO_MULTI_PPM,
    .proto = 0,
    .rev_steer = {true, true, true},
};

void radio_init(void) {
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        nvs_flash_erase();
        err = nvs_flash_init();
    }
    ESP_ERROR_CHECK(err);
    nvs_handle_t h;
    if (nvs_open(NVS_NS, NVS_READONLY, &h) == ESP_OK) {
        stored_t st;
        size_t len = sizeof(st);
        if (nvs_get_blob(h, NVS_KEY, &st, &len) == ESP_OK && len == sizeof(st) && st.version == CFG_VERSION &&
            st.cfg.kind < RADIO_KINDS && st.cfg.proto < MULTI_PROTO_COUNT) {
            s_cfg = st.cfg;
        }
        nvs_close(h);
    }
    ESP_LOGI(TAG, "%s, %s rx %d option %d", radio_kind_name(s_cfg.kind), MULTI_PROTOS[s_cfg.proto].name,
             s_cfg.rx_num, s_cfg.option);
}

radio_config_t radio_config(void) {
    portENTER_CRITICAL(&s_lock);
    radio_config_t c = s_cfg;
    portEXIT_CRITICAL(&s_lock);
    return c;
}

void radio_set(const radio_config_t *c) {
    portENTER_CRITICAL(&s_lock);
    s_cfg = *c;
    portEXIT_CRITICAL(&s_lock);
    stored_t st = {.version = CFG_VERSION, .cfg = *c};
    nvs_handle_t h;
    if (nvs_open(NVS_NS, NVS_READWRITE, &h) == ESP_OK) {
        nvs_set_blob(h, NVS_KEY, &st, sizeof(st));
        nvs_commit(h);
        nvs_close(h);
    }
    ESP_LOGI(TAG, "set %s, %s rx %d option %d", radio_kind_name(c->kind), MULTI_PROTOS[c->proto].name, c->rx_num,
             c->option);
}

const char *radio_kind_name(radio_kind_t k) {
    switch (k) {
        case RADIO_ELRS:
            return "ELRS";
        case RADIO_MULTI_SERIAL:
            return "MULTI";
        case RADIO_MULTI_PPM:
            return "MULTI PPM";
        default:
            return "?";
    }
}
