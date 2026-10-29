#include "sound.h"

#include <math.h>
#include <stdbool.h>

#include "bsp/esp-bsp.h"
#include "control.h"
#include "esp_codec_dev.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "radio.h"

static const char *TAG = "sound";

#define SR 22050 // the BSP's I2S default
#define BLOCK 256
#define BLOCK_S ((float)BLOCK / SR)

// A four-cylinder: one firing every half turn, so firing Hz = rpm / 30.
#define IDLE_RPM 900.0f
#define RED_RPM 7000.0f
// Starting: the starter spins the engine at CRANK_RPM, the first cylinders
// sputter from SPUTTER_S, it catches at CATCH_S, flares and settles.
#define CRANK_RPM 220.0f
#define SPUTTER_S 0.55f
#define CATCH_S 0.9f
#define FLARE_S 1.2f
#define FLARE_RPM 1000.0f // above idle
#define STARTER_HZ 150.0f
#define STOP_RPM 150.0f

// ---- tiny DSP ----------------------------------------------------------------

static uint32_t s_seed = 0x1234567;

static float noise(void) {
    s_seed ^= s_seed << 13;
    s_seed ^= s_seed >> 17;
    s_seed ^= s_seed << 5;
    return (float)(int32_t)s_seed / 2147483648.0f;
}

// Two-pole resonator: an impulse rings at hz, decaying over decay_s, with
// a peak of about the impulse's size.
typedef struct {
    float a1, a2, g, y1, y2;
} reso_t;

static void reso_tune(reso_t *r, float hz, float decay_s) {
    float w = 2.0f * (float)M_PI * hz / SR;
    float rr = expf(-1.0f / (decay_s * SR));
    r->a1 = 2.0f * rr * cosf(w);
    r->a2 = -rr * rr;
    r->g = sinf(w);
}

static inline float reso_run(reso_t *r, float x) {
    float y = r->a1 * r->y1 + r->a2 * r->y2 + x * r->g;
    r->y2 = r->y1;
    r->y1 = y;
    return y;
}

// ---- engine ------------------------------------------------------------------

typedef struct {
    float rpm, load;
    float phase; // 0..1 between firings
    int cyl;
    float crank_t;    // seconds since the key turned, < 0 when not cranking
    float flare_left; // seconds of the flare after catching
    float starter;    // starter motor loudness 0..1 (fades when it lets go)
    float st_phase, comp_phase;
    bool was_on;
    float level;      // the last block's firing level
    float pop_left;   // seconds of an overrun pop still sounding
    float rasp_left;  // seconds of the current firing's noise burst
    float rasp_amp;
    reso_t body, mid, high;
    float dc_x, dc_y, hiss;
} engine_t;

// Slightly uneven cylinders give the beat a real engine has.
static const float CYL_GAIN[4] = {1.0f, 0.84f, 1.08f, 0.92f};

// Where the revs want to be, from the driving model.
static void target(const control_view_t *v, float *rpm, float *load) {
    if (!v->engine) {
        *rpm = 0;
        *load = 0;
        return;
    }
    *load = v->gas;
    if (v->gear == GEAR_N) {
        *rpm = IDLE_RPM + v->gas * (RED_RPM * 0.92f - IDLE_RPM);
        return;
    }
    // Speed within the gear: every gear sweeps idle to redline, so an
    // upshift drops the revs and a downshift raises them.
    float frac = v->gear_max > 0 ? fabsf(v->speed) / v->gear_max : 0;
    frac = frac > 1 ? 1 : frac;
    float r = IDLE_RPM + frac * (RED_RPM * 0.95f - IDLE_RPM);
    // Pulling away the clutch slips, so the revs run ahead of the car.
    float slip = IDLE_RPM + v->gas * 2000.0f * (1.0f - frac);
    *rpm = r > slip ? r : slip;
}

// The starter motor: a geared whine that spins up, labours (lower and
// louder) on every compression stroke, so it goes "rur-rur-rur", with the
// odd cylinder sputtering towards the end. Fades out once it lets go.
// Returns the whine; compressions and sputters go into *x_body, the
// engine's exhaust resonator.
static float starter_sample(engine_t *e, bool cranking, float *x_body) {
    float target = cranking ? 1.0f : 0.0f;
    e->starter += (target - e->starter) * (cranking ? 0.0008f : 0.0004f);
    if (e->starter < 0.001f) {
        return 0;
    }
    float t = cranking ? e->crank_t : CATCH_S;
    float spin = t < 0.15f ? t / 0.15f : 1.0f;
    // Compressions: four per two turns.
    e->comp_phase += CRANK_RPM * spin / 30.0f / SR;
    if (e->comp_phase >= 1.0f) {
        e->comp_phase -= 1.0f;
        float p = cranking ? (t - SPUTTER_S) / (CATCH_S - SPUTTER_S) : 0;
        if (p > 0 && noise() * 0.5f + 0.5f < p) {
            *x_body += 3.0f; // a cylinder fires
        } else if (cranking) {
            *x_body += 0.8f; // air through the valves
        }
    }
    float m = 0.5f - 0.5f * cosf(2.0f * (float)M_PI * e->comp_phase);
    // Let go: no load, it freewheels up in pitch as it fades.
    float hz = STARTER_HZ * spin * (cranking ? 1.0f - 0.2f * m : 1.3f);
    e->st_phase += hz / SR;
    e->st_phase -= (int)e->st_phase;
    float ph = 2.0f * (float)M_PI * e->st_phase;
    float whine = sinf(ph) + 0.6f * sinf(2 * ph) + 0.4f * sinf(3 * ph) + 0.3f * sinf(5 * ph) + 0.35f * noise();
    float amp = 0.45f * e->starter * spin * (cranking ? 0.55f + 0.45f * m : 1.0f);
    return amp * whine;
}

// drive: how hard the sound hits the soft clip (more = louder and grittier);
// master: the volume, applied after it.
static void engine_block(engine_t *e, const control_view_t *v, int16_t *out, float drive, float master) {
    float want_rpm, want_load;
    target(v, &want_rpm, &want_load);

    if (v->engine && !e->was_on) {
        e->crank_t = 0;
        e->rpm = 0;
    } else if (!v->engine) {
        e->crank_t = -1;
        e->flare_left = 0;
    }
    e->was_on = v->engine;

    bool cranking = e->crank_t >= 0;
    if (cranking) {
        e->crank_t += BLOCK_S;
        if (e->crank_t >= CATCH_S) {
            // Catches: the starter lets go, the revs flare.
            e->crank_t = -1;
            e->flare_left = FLARE_S;
            e->rpm = 500.0f;
            e->load = 0.4f;
            cranking = false;
        }
    }
    if (e->flare_left > 0) {
        e->flare_left -= BLOCK_S;
        float f = e->flare_left / FLARE_S;
        float flare = IDLE_RPM + FLARE_RPM * f * f;
        want_rpm = want_rpm > flare ? want_rpm : flare;
        want_load = want_load > 0.4f * f ? want_load : 0.4f * f;
    }
    if (cranking) {
        e->rpm = 0; // the starter part below makes the sound
        e->load = 0;
    } else {
        // Revs climb faster than they fall; free in neutral, held back by
        // the car in gear.
        bool up = want_rpm > e->rpm;
        float k = up ? (v->gear == GEAR_N ? 0.22f : 0.12f) : (v->gear == GEAR_N ? 0.07f : 0.10f);
        if (!v->engine) {
            k = 0.06f;
        }
        // ...and no faster than a real engine can spin up or down, or the
        // jump in pitch and loudness sounds like a bang.
        float step = (want_rpm - e->rpm) * k;
        float max_step = (up ? (v->gear == GEAR_N || e->flare_left > 0 ? 11000.0f : 7000.0f) : 6000.0f) * BLOCK_S;
        e->rpm += step > max_step ? max_step : (step < -max_step ? -max_step : step);
        e->load += (want_load - e->load) * 0.10f;
    }

    float rpm = e->rpm;
    bool running = rpm > STOP_RPM;
    bool overrun = v->engine && !cranking && v->gas < 0.05f && rpm > 2600.0f;
    // The exhaust note rises a little with the revs.
    reso_tune(&e->body, 85.0f + rpm * 0.018f, 0.030f);
    reso_tune(&e->mid, 380.0f + rpm * 0.03f, 0.009f);
    reso_tune(&e->high, 1700.0f, 0.004f);
    float fire_hz = rpm / 30.0f;
    // Louder under load and with the revs; quiet at idle.
    float level = 0.35f + 0.65f * e->load;
    level *= 0.6f + 0.4f * (rpm / RED_RPM);
    // Faster firings overlap in the resonators: keep the loudness in check.
    level *= sqrtf(30.0f / fmaxf(fire_hz, 30.0f));
    // Glide from the last block's level instead of stepping.
    float level0 = e->level, dlevel = (level - level0) / BLOCK;
    e->level = level;

    for (int i = 0; i < BLOCK; i++) {
        float x_body = 0, x_mid = 0, x_high = 0;
        if (running) {
            e->phase += fire_hz / SR;
            if (e->phase >= 1.0f) {
                e->phase -= 1.0f;
                e->cyl = (e->cyl + 1) & 3;
                float a = (level0 + dlevel * i) * CYL_GAIN[e->cyl] * (1.0f + 0.12f * noise());
                x_body = a * 6.0f;
                x_mid = a * 2.5f;
                e->rasp_left = 0.0025f;
                e->rasp_amp = 0.3f + 0.7f * e->load;
                if (overrun && noise() > 0.94f) {
                    e->pop_left = 0.018f;
                }
            }
        }
        if (e->rasp_left > 0) {
            e->rasp_left -= 1.0f / SR;
            x_high += e->rasp_amp * noise() * 0.8f;
        }
        if (e->pop_left > 0) {
            e->pop_left -= 1.0f / SR;
            float n = noise() * 0.7f;
            x_mid += n;
            x_high += n;
        }
        float st = starter_sample(e, cranking, &x_body);
        float s = st + reso_run(&e->body, x_body) + 0.6f * reso_run(&e->mid, x_mid) + 0.35f * reso_run(&e->high, x_high);
        // Intake hiss with load and revs.
        e->hiss += (noise() - e->hiss) * 0.2f;
        s += e->hiss * 0.05f * e->load * (rpm / RED_RPM);
        // DC block, soft clip.
        float y = s - e->dc_x + 0.995f * e->dc_y;
        e->dc_x = s;
        e->dc_y = y;
        y *= drive;
        y = y / (1.0f + fabsf(y));
        out[i] = (int16_t)(y * master * 32000.0f);
    }
}

static void sound_task(void *arg) {
    esp_codec_dev_handle_t spk = arg;
    static engine_t e;
    static int16_t buf[BLOCK];
    for (;;) {
        // Squared, so the steps sound even.
        float m = ui_vol_get() / 100.0f;
        control_view_t v = control_view(esp_timer_get_time());
        engine_block(&e, &v, buf, 0.35f, m * m);
        // Blocks until the I2S DMA has room: this is the task's clock.
        esp_codec_dev_write(spk, buf, sizeof(buf));
    }
}

void sound_start(void) {
    esp_codec_dev_handle_t spk = bsp_audio_codec_speaker_init();
    if (spk == NULL) {
        ESP_LOGE(TAG, "speaker init failed");
        return;
    }
    esp_codec_dev_sample_info_t fs = {
        .sample_rate = SR,
        .channel = 1,
        .bits_per_sample = 16,
    };
    if (esp_codec_dev_open(spk, &fs) != ESP_CODEC_DEV_OK) {
        ESP_LOGE(TAG, "speaker open failed");
        return;
    }
    // The codec's own volume tops out at 0 dB and is far quieter below
    // that: leave it full and scale the samples instead.
    esp_codec_dev_set_out_vol(spk, 100);
    xTaskCreatePinnedToCore(sound_task, "sound", 4096, spk, 6, NULL, 0);
    ESP_LOGI(TAG, "engine sound on, %d Hz", SR);
}
