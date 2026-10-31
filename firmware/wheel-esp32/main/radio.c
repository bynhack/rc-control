#include "radio.h"

#include <math.h>
#include <stddef.h>
#include <string.h>

#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "nvs.h"
#include "nvs_flash.h"

static const char *TAG = "radio";

#define NVS_NS "radio"
#define NVS_KEY "cfg" // before cars: the one radio_config_t
#define NVS_KEY_CARS "cars"
#define NVS_KEY_LANG "lang"
#define NVS_KEY_DASH "dash"
#define NVS_KEY_KMH "kmh"
#define DEFAULT_KMH 30
#define NVS_KEY_FFB "ffb"
#define NVS_KEY_FLIP "flip"
#define NVS_KEY_DUPLEX "elrs2"
#define NVS_KEY_VOL "vol"
#define NVS_KEY_SOUND "snd"
#define SOUND_COUNT 3 // sound.h SOUND_VOICES
#define DEFAULT_VOL 80
#define DEFAULT_FFB 40
// Bump when radio_config_t or car_t change, so an old blob is ignored.
#define CFG_VERSION 1
// 3: radio_config_t.trim (in what was padding, so 1 and 2 still load,
// without a trim). 4: the handling fields, after the old ones (garage_v3_t
// loads into them with the defaults).
#define GARAGE_VERSION 4

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
    uint32_t cfg[4]; // radio_config_t as it was then
} stored_t;

typedef struct {
    uint8_t version;
    uint8_t active;
    car_t cars[CAR_COUNT];
} garage_t;

// Versions 1..3: radio_config_t was its first 16 bytes.
typedef struct {
    char name[CAR_NAME_LEN];
    uint32_t radio[4];
    uint8_t top_kmh;
    uint8_t sound;
} car_v3_t;

typedef struct {
    uint8_t version;
    uint8_t active;
    car_v3_t cars[CAR_COUNT];
} garage_v3_t;

_Static_assert(sizeof(car_v3_t) == 36 && sizeof(garage_v3_t) == 220, "old garage layout");
_Static_assert(offsetof(radio_config_t, steer_deg) == 16, "new fields after the old ones");

static portMUX_TYPE s_lock = portMUX_INITIALIZER_UNLOCKED;
static garage_t s_garage;

static const car_t DEFAULT_CAR = {
    .radio = {.kind = RADIO_ELRS,
              .rev_steer = {true, true, true},
              .steer_deg = WHEEL_DEG,
              .steer_max = {1000, 1000}},
    .top_kmh = DEFAULT_KMH,
};

// Handling values out of range (or zero, from an older version) become the
// defaults.
static void fix_handling(radio_config_t *r) {
    if (r->trim < -TRIM_MAX || r->trim > TRIM_MAX) {
        r->trim = 0;
    }
    if (r->steer_deg < STEER_DEG_MIN || r->steer_deg > WHEEL_DEG) {
        r->steer_deg = WHEEL_DEG;
    }
    for (int i = 0; i < 2; i++) {
        if (r->steer_max[i] < STEER_MAX_MIN || r->steer_max[i] > 1000) {
            r->steer_max[i] = 1000;
        }
        if (r->thr_start[i] > THR_START_MAX) {
            r->thr_start[i] = 0;
        }
    }
    if (r->expo > EXPO_MAX) {
        r->expo = 0;
    }
}

static void save_garage(void) {
    portENTER_CRITICAL(&s_lock);
    garage_t g = s_garage;
    portEXIT_CRITICAL(&s_lock);
    nvs_handle_t h;
    if (nvs_open(NVS_NS, NVS_READWRITE, &h) == ESP_OK) {
        nvs_set_blob(h, NVS_KEY_CARS, &g, sizeof(g));
        nvs_commit(h);
        nvs_close(h);
    }
}

static bool car_ok(const car_t *c) {
    return c->radio.kind < RADIO_KINDS && c->radio.proto < MULTI_PROTO_COUNT && c->sound < SOUND_COUNT &&
           c->top_kmh >= 5 && c->name[CAR_NAME_LEN - 1] == 0;
}

// Set when the saved cars are an older version, so they are saved again.
static bool s_upgraded;

static bool load_garage(nvs_handle_t h) {
    static garage_t g; // static: too big for the stack it runs on
    size_t len = 0;
    if (nvs_get_blob(h, NVS_KEY_CARS, NULL, &len) != ESP_OK) {
        return false;
    }
    if (len == sizeof(garage_v3_t)) {
        static garage_v3_t o;
        if (nvs_get_blob(h, NVS_KEY_CARS, &o, &len) != ESP_OK || o.version < 1 || o.version > 3) {
            return false;
        }
        memset(&g, 0, sizeof(g));
        g.version = o.version;
        g.active = o.active;
        for (int i = 0; i < CAR_COUNT; i++) {
            memcpy(g.cars[i].name, o.cars[i].name, CAR_NAME_LEN);
            memcpy(&g.cars[i].radio, o.cars[i].radio, sizeof(o.cars[i].radio));
            g.cars[i].top_kmh = o.cars[i].top_kmh;
            g.cars[i].sound = o.cars[i].sound;
            if (o.version < 3) {
                g.cars[i].radio.trim = 0;
            }
        }
    } else if (len != sizeof(g) || nvs_get_blob(h, NVS_KEY_CARS, &g, &len) != ESP_OK ||
               g.version != GARAGE_VERSION) {
        return false;
    }
    if (g.active >= CAR_COUNT) {
        return false;
    }
    for (int i = 0; i < CAR_COUNT; i++) {
        if (!car_ok(&g.cars[i])) {
            g.cars[i] = DEFAULT_CAR;
        }
        fix_handling(&g.cars[i].radio);
    }
    s_upgraded = g.version != GARAGE_VERSION;
    g.version = GARAGE_VERSION;
    s_garage = g;
    return true;
}

// Before cars there was one radio setting, top speed and sound: they
// become car 1.
static void migrate(nvs_handle_t h) {
    s_garage.version = GARAGE_VERSION;
    for (int i = 0; i < CAR_COUNT; i++) {
        s_garage.cars[i] = DEFAULT_CAR;
    }
    car_t *c = &s_garage.cars[0];
    stored_t st;
    size_t len = sizeof(st);
    radio_config_t r = c->radio;
    if (nvs_get_blob(h, NVS_KEY, &st, &len) == ESP_OK && len == sizeof(st) && st.version == CFG_VERSION) {
        memcpy(&r, st.cfg, sizeof(st.cfg));
        r.trim = 0;
        if (r.kind < RADIO_KINDS && r.proto < MULTI_PROTO_COUNT) {
            c->radio = r;
        }
    }
    uint8_t v;
    if (nvs_get_u8(h, NVS_KEY_KMH, &v) == ESP_OK && v >= 5) {
        c->top_kmh = v;
    }
    if (nvs_get_u8(h, NVS_KEY_SOUND, &v) == ESP_OK && v < SOUND_COUNT) {
        c->sound = v;
    }
}

void radio_init(void) {
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        nvs_flash_erase();
        err = nvs_flash_init();
    }
    ESP_ERROR_CHECK(err);
    bool loaded = false;
    nvs_handle_t h;
    if (nvs_open(NVS_NS, NVS_READONLY, &h) == ESP_OK) {
        loaded = load_garage(h);
        if (!loaded) {
            migrate(h);
        }
        nvs_close(h);
    } else {
        migrate(0);
    }
    if (!loaded || s_upgraded) {
        save_garage();
    }
    radio_config_t c = radio_config();
    ESP_LOGI(TAG, "car %d: %s, %s rx %d option %d", s_garage.active + 1, radio_kind_name(c.kind),
             MULTI_PROTOS[c.proto].name, c.rx_num, c.option);
}

radio_config_t radio_config(void) {
    portENTER_CRITICAL(&s_lock);
    radio_config_t c = s_garage.cars[s_garage.active].radio;
    portEXIT_CRITICAL(&s_lock);
    return c;
}

void radio_set(const radio_config_t *c) {
    portENTER_CRITICAL(&s_lock);
    s_garage.cars[s_garage.active].radio = *c;
    portEXIT_CRITICAL(&s_lock);
    save_garage();
    ESP_LOGI(TAG, "set %s, %s rx %d option %d", radio_kind_name(c->kind), MULTI_PROTOS[c->proto].name, c->rx_num,
             c->option);
}

int car_active(void) {
    return s_garage.active;
}

void car_select(int i) {
    if (i < 0 || i >= CAR_COUNT) {
        return;
    }
    portENTER_CRITICAL(&s_lock);
    s_garage.active = (uint8_t)i;
    portEXIT_CRITICAL(&s_lock);
    save_garage();
    ESP_LOGI(TAG, "car %d", i + 1);
}

car_t car_get(int i) {
    portENTER_CRITICAL(&s_lock);
    car_t c = s_garage.cars[i < 0 || i >= CAR_COUNT ? 0 : i];
    portEXIT_CRITICAL(&s_lock);
    return c;
}

void car_rename(int i, const char *name) {
    if (i < 0 || i >= CAR_COUNT) {
        return;
    }
    portENTER_CRITICAL(&s_lock);
    strlcpy(s_garage.cars[i].name, name, CAR_NAME_LEN);
    portEXIT_CRITICAL(&s_lock);
    save_garage();
}

static volatile radio_cal_t s_cal;

void radio_cal_set(radio_cal_t cal) {
    s_cal = cal;
}

radio_cal_t radio_cal_get(void) {
    return s_cal;
}

static float clampf(float v) {
    return v < -1.0f ? -1.0f : (v > 1.0f ? 1.0f : v);
}

float radio_steer_shape(const radio_config_t *c, float wheel) {
    float s = clampf(wheel * (float)WHEEL_DEG / (float)c->steer_deg);
    float e = c->expo / 100.0f;
    return s * (1.0f - e) + e * s * s * s;
}

float radio_steering(const radio_config_t *c, float wheel) {
    radio_cal_t cal = s_cal;
    float s = radio_steer_shape(c, wheel);
    if (cal != CAL_TRIM) {
        s = clampf(s + c->trim / 1000.0f);
    }
    if (cal != CAL_ENDS) {
        s *= c->steer_max[s < 0.0f ? 0 : 1] / 1000.0f;
    }
    return c->rev_steer[c->kind] ? -s : s;
}

float radio_throttle(const radio_config_t *c, float throttle, bool reverse) {
    float t = throttle;
    if (s_cal != CAL_THROTTLE && (t > 0.0f || reverse)) {
        float start = c->thr_start[t > 0.0f ? 0 : 1] / 1000.0f;
        t = copysignf(start + fabsf(t) * (1.0f - start), t);
    }
    t = clampf(t);
    return c->rev_thr[c->kind] ? -t : t;
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
    return s_garage.cars[s_garage.active].top_kmh;
}

void ui_topspeed_set(int kmh) {
    s_garage.cars[s_garage.active].top_kmh = (uint8_t)kmh;
    save_garage();
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

static int s_duplex = -1;

bool ui_elrs_duplex_get(void) {
    if (s_duplex < 0) {
        uint8_t v = 0;
        nvs_handle_t h;
        if (nvs_open(NVS_NS, NVS_READONLY, &h) == ESP_OK) {
            nvs_get_u8(h, NVS_KEY_DUPLEX, &v);
            nvs_close(h);
        }
        s_duplex = v == 1;
    }
    return s_duplex == 1;
}

void ui_elrs_duplex_set(bool full) {
    s_duplex = full;
    nvs_handle_t h;
    if (nvs_open(NVS_NS, NVS_READWRITE, &h) == ESP_OK) {
        nvs_set_u8(h, NVS_KEY_DUPLEX, full ? 1 : 0);
        nvs_commit(h);
        nvs_close(h);
    }
}

static int s_vol = -1;

int ui_vol_get(void) {
    if (s_vol < 0) {
        uint8_t v = DEFAULT_VOL;
        nvs_handle_t h;
        if (nvs_open(NVS_NS, NVS_READONLY, &h) == ESP_OK) {
            nvs_get_u8(h, NVS_KEY_VOL, &v);
            nvs_close(h);
        }
        s_vol = v > 100 ? DEFAULT_VOL : v;
    }
    return s_vol;
}

void ui_vol_set(int pct) {
    s_vol = pct;
    nvs_handle_t h;
    if (nvs_open(NVS_NS, NVS_READWRITE, &h) == ESP_OK) {
        nvs_set_u8(h, NVS_KEY_VOL, (uint8_t)pct);
        nvs_commit(h);
        nvs_close(h);
    }
}

int ui_sound_get(void) {
    return s_garage.cars[s_garage.active].sound;
}

void ui_sound_set(int voice) {
    s_garage.cars[s_garage.active].sound = (uint8_t)voice;
    save_garage();
}
