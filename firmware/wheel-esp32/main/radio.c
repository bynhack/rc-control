#include "radio.h"

#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "nvs.h"
#include "nvs_flash.h"

static const char *TAG = "radio";

#define NVS_NS "radio"
#define NVS_KEY "cfg"
#define NVS_KEY_LANG "lang"
#define NVS_KEY_DASH "dash"
#define NVS_KEY_KMH "kmh"
#define DEFAULT_KMH 30
#define NVS_KEY_FFB "ffb"
#define NVS_KEY_FLIP "flip"
#define DEFAULT_FFB 40
// Bump when radio_config_t changes, so an old blob is ignored.
#define CFG_VERSION 1

// Surface protocols first; names are shown on the screen (display_p4.c
// fonts must cover them). Option: CC2500 fine tune (S-FHSS -50 is the
// IRX4+ seller's value), DSM channel count.
const multi_proto_t MULTI_PROTOS[] = {
    {"富斯 AFHDS 2A", 28, 0, 0},  {"富斯 AFHDS", 1, 0, 0},       {"Futaba S-FHSS", 21, 0, -50},
    {"FrSky D8", 3, 0, 0},        {"FrSky D16", 15, 0, 0},       {"Spektrum DSM", 6, 4, 7},
    {"京商 FHSS", 73, 0, 0},      {"京商 Hype", 73, 1, 0},       {"京商 KT-17", 93, 0, 0},
    {"樂迪 RadioLink", 74, 0, 0}, {"Traxxas", 43, 0, 0},         {"Losi", 89, 0, 0},
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

int ui_lang_get(void) {
    uint8_t v = 0;
    nvs_handle_t h;
    if (nvs_open(NVS_NS, NVS_READONLY, &h) == ESP_OK) {
        nvs_get_u8(h, NVS_KEY_LANG, &v);
        nvs_close(h);
    }
    return v == 1 ? 1 : 0;
}

void ui_lang_set(int lang) {
    nvs_handle_t h;
    if (nvs_open(NVS_NS, NVS_READWRITE, &h) == ESP_OK) {
        nvs_set_u8(h, NVS_KEY_LANG, (uint8_t)lang);
        nvs_commit(h);
        nvs_close(h);
    }
}

int ui_dash_get(void) {
    uint8_t v = 0;
    nvs_handle_t h;
    if (nvs_open(NVS_NS, NVS_READONLY, &h) == ESP_OK) {
        nvs_get_u8(h, NVS_KEY_DASH, &v);
        nvs_close(h);
    }
    return v;
}

void ui_dash_set(int dash) {
    nvs_handle_t h;
    if (nvs_open(NVS_NS, NVS_READWRITE, &h) == ESP_OK) {
        nvs_set_u8(h, NVS_KEY_DASH, (uint8_t)dash);
        nvs_commit(h);
        nvs_close(h);
    }
}

int ui_topspeed_get(void) {
    uint8_t v = DEFAULT_KMH;
    nvs_handle_t h;
    if (nvs_open(NVS_NS, NVS_READONLY, &h) == ESP_OK) {
        nvs_get_u8(h, NVS_KEY_KMH, &v);
        nvs_close(h);
    }
    return v < 5 ? DEFAULT_KMH : v;
}

void ui_topspeed_set(int kmh) {
    nvs_handle_t h;
    if (nvs_open(NVS_NS, NVS_READWRITE, &h) == ESP_OK) {
        nvs_set_u8(h, NVS_KEY_KMH, (uint8_t)kmh);
        nvs_commit(h);
        nvs_close(h);
    }
}

// Read often (ffb.c polls it), so cached after the first read.
static int s_ffb = -1;

int ui_ffb_get(void) {
    if (s_ffb < 0) {
        uint8_t v = DEFAULT_FFB;
        nvs_handle_t h;
        if (nvs_open(NVS_NS, NVS_READONLY, &h) == ESP_OK) {
            nvs_get_u8(h, NVS_KEY_FFB, &v);
            nvs_close(h);
        }
        s_ffb = v > 100 ? DEFAULT_FFB : v;
    }
    return s_ffb;
}

void ui_ffb_set(int pct) {
    s_ffb = pct;
    nvs_handle_t h;
    if (nvs_open(NVS_NS, NVS_READWRITE, &h) == ESP_OK) {
        nvs_set_u8(h, NVS_KEY_FFB, (uint8_t)pct);
        nvs_commit(h);
        nvs_close(h);
    }
}

bool ui_flip_get(void) {
    uint8_t v = 0;
    nvs_handle_t h;
    if (nvs_open(NVS_NS, NVS_READONLY, &h) == ESP_OK) {
        nvs_get_u8(h, NVS_KEY_FLIP, &v);
        nvs_close(h);
    }
    return v == 1;
}

void ui_flip_set(bool flip) {
    nvs_handle_t h;
    if (nvs_open(NVS_NS, NVS_READWRITE, &h) == ESP_OK) {
        nvs_set_u8(h, NVS_KEY_FLIP, flip ? 1 : 0);
        nvs_commit(h);
        nvs_close(h);
    }
}
