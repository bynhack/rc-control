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

// Four cylinders: one firing every half turn, so firing Hz = rpm / 30.
// Starting: the starter spins the engine at CRANK_RPM, the first cylinders
// sputter from SPUTTER_S, it catches at CATCH_S, flares and settles.
#define CRANK_RPM 220.0f
#define SPUTTER_S 0.55f
#define CATCH_S 0.9f
#define FLARE_S 1.2f
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

// Second-order high-pass (Butterworth). The little speaker can't play
// below about 150 Hz: driving it there only rattles the cone, which
// sounds like a broken speaker, and wastes the headroom.
typedef struct {
    float b0, b1, b2, a1, a2, x1, x2, y1, y2;
} hpf_t;

static void hpf_tune(hpf_t *f, float hz) {
    float w = 2.0f * (float)M_PI * hz / SR, c = cosf(w), al = sinf(w) / (2.0f * 0.7071f);
    float a0 = 1.0f + al;
    f->b0 = (1.0f + c) / 2.0f / a0;
    f->b1 = -(1.0f + c) / a0;
    f->b2 = f->b0;
    f->a1 = -2.0f * c / a0;
    f->a2 = (1.0f - al) / a0;
}

static inline float hpf_run(hpf_t *f, float x) {
    float y = f->b0 * x + f->b1 * f->x1 + f->b2 * f->x2 - f->a1 * f->y1 - f->a2 * f->y2;
    f->x2 = f->x1;
    f->x1 = x;
    f->y2 = f->y1;
    f->y1 = y;
    return y;
}

#define SPEAKER_LOW_HZ 150.0f

// Limiter: peaks held to LIM_CEIL of full scale. The gain drops within
// about a millisecond and comes back over about a tenth of a second.
#define LIM_CEIL 0.8f
#define LIM_ATTACK 0.05f
#define LIM_RECOVER 0.0005f
#define LIM_RELEASE 0.9995f

// ---- voices ------------------------------------------------------------------

// What makes one car sound unlike another.
typedef struct {
    int cyl;                           // 4: firing Hz = rpm / 30; 6: rpm / 20
    float idle, red, flare;            // rpm; flare = above idle on starting
    float body_hz, body_k, body_decay; // exhaust: body_hz + rpm * body_k
    float mid_hz, mid_k, mid_decay;    // the bark above it
    float high_hz;                     // rasp
    float rasp;                        // noise per firing
    float rough;                       // firing-to-firing jitter
    float lump;                        // extra jitter at idle
    float overrun_rpm;                 // pops and crackle above this, off the gas
    float pop_chance, pop_amp, pop_s;  // overrun pops / anti-lag bangs
    float crackle_chance;              // small cracks on the overrun
    float drive;                       // into the soft clip
    float turbo, bov;                  // whistle, blow-off: 0 = none, 1 = rally
    float cut_s;                       // upshift ignition cut, ends in a bang
    bool blip;                         // throttle blip on downshifts
    float dogbox;                      // straight-cut gear whine and clunk
    float gravel;                      // stones and rumble
} voice_t;

static const voice_t VOICES[SOUND_VOICES] = {
    // A plain road car.
    [SOUND_ROAD] = {.cyl = 4, .idle = 900, .red = 7000, .flare = 1000,
                    .body_hz = 85, .body_k = 0.018f, .body_decay = 0.030f,
                    .mid_hz = 380, .mid_k = 0.030f, .mid_decay = 0.009f, .high_hz = 1700,
                    .rasp = 0.8f, .rough = 0.12f, .overrun_rpm = 2600,
                    .pop_chance = 0.06f, .pop_amp = 0.7f, .pop_s = 0.018f, .drive = 0.35f},
    // A turbo four on a rally stage: lumpy idle, harder bark and rasp,
    // anti-lag bangs and crackle off the throttle, flat shifts, a dog box,
    // gravel.
    [SOUND_RALLY] = {.cyl = 4, .idle = 1100, .red = 8000, .flare = 1000,
                     .body_hz = 100, .body_k = 0.020f, .body_decay = 0.022f,
                     .mid_hz = 520, .mid_k = 0.045f, .mid_decay = 0.006f, .high_hz = 2300,
                     .rasp = 1.6f, .rough = 0.18f, .lump = 0.35f, .overrun_rpm = 2200,
                     .pop_chance = 0.20f, .pop_amp = 2.4f, .pop_s = 0.030f, .crackle_chance = 0.35f,
                     .drive = 0.40f, .turbo = 1.0f, .bov = 1.0f, .cut_s = 0.07f, .blip = true,
                     .dogbox = 1.0f, .gravel = 1.0f},
    // BMW M4: twin-turbo straight six. Smooth and even, a deep but raspy
    // baritone that hardens with the revs, a loud cold-start flare, quick
    // gearbox shifts with a short "brap", crackle on the overrun, the turbos
    // only a faint hiss.
    [SOUND_M4] = {.cyl = 6, .idle = 750, .red = 7200, .flare = 1400,
                  .body_hz = 95, .body_k = 0.016f, .body_decay = 0.028f,
                  .mid_hz = 430, .mid_k = 0.055f, .mid_decay = 0.007f, .high_hz = 2700,
                  .rasp = 1.25f, .rough = 0.05f, .lump = 0.05f, .overrun_rpm = 2500,
                  .pop_chance = 0.07f, .pop_amp = 1.5f, .pop_s = 0.022f, .crackle_chance = 0.22f,
                  .drive = 0.7f, .turbo = 0.35f, .bov = 0.2f, .cut_s = 0.035f, .blip = true},
};

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
    hpf_t hpf;
    float env, lim_gain; // limiter
    float hiss;
    // Rally extras.
    float boost; // turbo 0..1
    float whistle_ph;
    float bov_left, bov_amp, bov_t; // blow-off valve
    float prev_gas;
    gear_t last_gear;
    float cut_left;  // ignition cut on an upshift, bang at its end
    float blip_left; // throttle blip on a downshift
    float crack_left;
    float whine_ph, diff_ph;
    float rumble;
    reso_t bov, stone;
} engine_t;

// Slightly uneven cylinders give the beat a real engine has.
static const float CYL_GAIN[6] = {1.0f, 0.84f, 1.08f, 0.92f, 1.03f, 0.89f};

// Where the revs want to be, from the driving model.
static void target(const voice_t *vc, const control_view_t *v, float *rpm, float *load) {
    if (!v->engine) {
        *rpm = 0;
        *load = 0;
        return;
    }
    *load = v->gas;
    if (v->gear == GEAR_N) {
        *rpm = vc->idle + v->gas * (vc->red * 0.92f - vc->idle);
        return;
    }
    // Speed within the gear: every gear sweeps idle to redline, so an
    // upshift drops the revs and a downshift raises them.
    float frac = v->gear_max > 0 ? fabsf(v->speed) / v->gear_max : 0;
    frac = frac > 1 ? 1 : frac;
    float r = vc->idle + frac * (vc->red * 0.95f - vc->idle);
    // Pulling away the clutch slips, so the revs run ahead of the car.
    float slip = vc->idle + v->gas * 2000.0f * (1.0f - frac);
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

// Everything but the exhaust, one sample, each part scaled by the voice:
// turbo whistle, blow-off chatter, straight-cut gear whine, gravel.
static float extras_sample(engine_t *e, const voice_t *vc, const control_view_t *v, float rpm, float speed) {
    float out = 0;
    // Turbo: a whistle that climbs with the boost, and a rush of air.
    if (e->boost > 0.02f) {
        e->whistle_ph += (2600.0f + 5200.0f * e->boost) / SR;
        e->whistle_ph -= (int)e->whistle_ph;
        out += vc->turbo * 0.10f * e->boost * e->boost * sinf(2.0f * (float)M_PI * e->whistle_ph);
        out += vc->turbo * 0.04f * e->boost * noise();
    }
    // Blow-off: "pssh", fluttering as the valve chatters.
    float x_bov = 0;
    if (e->bov_left > 0) {
        e->bov_left -= 1.0f / SR;
        e->bov_t += 1.0f / SR;
        float env = e->bov_left / 0.45f;
        float flutter = sinf(2.0f * (float)M_PI * 19.0f * e->bov_t) > 0 ? 1.0f : 0.45f;
        x_bov = noise() * 2.2f * vc->bov * e->bov_amp * env * env * flutter;
    }
    out += 0.5f * reso_run(&e->bov, x_bov);
    // Straight-cut gears whine with the revs in gear, louder off the
    // throttle; the diff whines with road speed.
    if (vc->dogbox > 0 && v->engine && v->gear != GEAR_N && speed > 0.01f) {
        float on = fminf(speed * 5.0f, 1.0f);
        e->whine_ph += rpm * 0.40f / SR;
        e->whine_ph -= (int)e->whine_ph;
        e->diff_ph += (180.0f + 1900.0f * speed) / SR;
        e->diff_ph -= (int)e->diff_ph;
        out += vc->dogbox * 0.045f * on * (0.4f + 0.6f * (1.0f - v->gas)) * sinf(2.0f * (float)M_PI * e->whine_ph);
        out += vc->dogbox * 0.025f * on * sinf(2.0f * (float)M_PI * e->diff_ph);
    }
    if (vc->gravel <= 0) {
        return out;
    }
    // Gravel: a low rumble and stones flicking off the tyres.
    e->rumble += (noise() - e->rumble) * 0.05f;
    out += vc->gravel * 0.35f * speed * e->rumble;
    float x_stone = 0;
    if (speed > 0.02f && noise() * 0.5f + 0.5f < 45.0f * speed / SR) {
        x_stone = (0.5f + 0.5f * noise()) * 3.0f * vc->gravel;
    }
    out += 0.4f * reso_run(&e->stone, x_stone);
    return out;
}

// master: the volume, applied after the soft clip.
static void engine_block(engine_t *e, const voice_t *vc, const control_view_t *v, int16_t *out, float master) {
    float want_rpm, want_load;
    target(vc, v, &want_rpm, &want_load);
    if (e->hpf.b0 == 0) {
        hpf_tune(&e->hpf, SPEAKER_LOW_HZ);
        e->lim_gain = 1.0f;
    }

    // Gear changes, the turbo, lifting off.
    if (v->gear != e->last_gear) {
        if (v->engine) {
            if (v->gear > e->last_gear && e->last_gear >= GEAR_1) {
                e->cut_left = vc->cut_s; // fast shift: cut, then bang
            } else if (vc->blip && v->gear < e->last_gear && v->gear >= GEAR_1) {
                e->blip_left = 0.12f;
            }
            if (vc->dogbox > 0) {
                e->crack_left = 0.004f; // the dog box clunk
            }
        }
        e->last_gear = v->gear;
    }
    if (e->blip_left > 0) {
        e->blip_left -= BLOCK_S;
        want_rpm += 1500.0f;
        want_load = 0.6f;
    }
    if (vc->turbo > 0) {
        float spool = e->rpm > 2200.0f ? fminf((e->rpm - 2200.0f) / 3000.0f, 1.0f) : 0.0f;
        float want_boost = v->gas * spool;
        e->boost += (want_boost - e->boost) * (want_boost > e->boost ? 0.035f : 0.12f);
        if (vc->bov > 0 && e->prev_gas - v->gas > 0.3f && e->boost > 0.3f) {
            e->bov_left = 0.45f;
            e->bov_amp = e->boost;
            e->bov_t = 0;
            e->boost *= 0.3f;
        }
    } else {
        e->boost = 0;
    }
    e->prev_gas = v->gas;

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
        float flare = vc->idle + vc->flare * f * f;
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
    bool overrun = v->engine && !cranking && v->gas < 0.05f && rpm > vc->overrun_rpm;
    // The exhaust note rises a little with the revs.
    reso_tune(&e->body, vc->body_hz + rpm * vc->body_k, vc->body_decay);
    reso_tune(&e->mid, vc->mid_hz + rpm * vc->mid_k, vc->mid_decay);
    reso_tune(&e->high, vc->high_hz, 0.004f);
    reso_tune(&e->bov, 2800.0f, 0.002f);
    reso_tune(&e->stone, 3600.0f, 0.0012f);
    float fire_hz = rpm * vc->cyl / 120.0f;
    float rough = vc->rough + (rpm < vc->idle * 1.3f ? vc->lump : 0.0f);
    float speed = fabsf(v->speed);
    bool cut_now = e->cut_left > 0;
    if (cut_now) {
        e->cut_left -= BLOCK_S;
        if (e->cut_left <= 0) {
            e->pop_left = vc->pop_s; // the bang as the spark comes back
        }
    }
    // Louder under load and with the revs; quiet at idle.
    float level = 0.35f + 0.65f * e->load;
    level *= 0.6f + 0.4f * (rpm / vc->red);
    if (cut_now) {
        level *= 0.1f;
    }
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
                e->cyl = (e->cyl + 1) % vc->cyl;
                float a = (level0 + dlevel * i) * CYL_GAIN[e->cyl] * (1.0f + rough * noise());
                x_body = a * 6.0f;
                x_mid = a * 2.5f;
                e->rasp_left = 0.0025f;
                e->rasp_amp = (0.3f + 0.7f * e->load) * vc->rasp;
                if (overrun && noise() * 0.5f + 0.5f < vc->pop_chance) {
                    e->pop_left = vc->pop_s;
                } else if (overrun && noise() * 0.5f + 0.5f < vc->crackle_chance) {
                    e->crack_left = 0.003f;
                }
            }
        }
        if (e->rasp_left > 0) {
            e->rasp_left -= 1.0f / SR;
            x_high += e->rasp_amp * noise() * 0.8f;
        }
        if (e->pop_left > 0) {
            e->pop_left -= 1.0f / SR;
            float n = noise() * vc->pop_amp;
            x_mid += n;
            x_high += n;
            x_body += n * 0.5f;
        }
        if (e->crack_left > 0) {
            e->crack_left -= 1.0f / SR;
            x_high += noise() * 1.8f;
        }
        float st = starter_sample(e, cranking, &x_body);
        float s = st + reso_run(&e->body, x_body) + 0.6f * reso_run(&e->mid, x_mid) + 0.35f * reso_run(&e->high, x_high);
        // Intake hiss with load and revs.
        e->hiss += (noise() - e->hiss) * 0.2f;
        s += e->hiss * 0.05f * e->load * (rpm / vc->red);
        s += extras_sample(e, vc, v, rpm, speed);
        // Only what the speaker can play; then a limiter turns the whole
        // sound down when it gets too loud, instead of clipping the wave
        // (clipping is what made it crackle like a broken speaker).
        float y = hpf_run(&e->hpf, s) * vc->drive;
        float a = fabsf(y);
        e->env = a > e->env ? a : e->env * LIM_RELEASE;
        float want = e->env > LIM_CEIL ? LIM_CEIL / e->env : 1.0f;
        e->lim_gain += (want - e->lim_gain) * (want < e->lim_gain ? LIM_ATTACK : LIM_RECOVER);
        y *= e->lim_gain;
        // Anything the limiter was too slow for: round off gently.
        if (fabsf(y) > 0.9f) {
            float o = fabsf(y) - 0.9f;
            y = copysignf(0.9f + o / (1.0f + o * 10.0f), y);
        }
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
        engine_block(&e, &VOICES[ui_sound_get()], &v, buf, m * m);
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
