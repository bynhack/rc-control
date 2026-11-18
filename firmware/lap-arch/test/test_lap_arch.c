// Host tests for the arch's decoder and lap tracker: `make -C test`.
//
// A model of the transponder (firmware/transponder/transponder.c) makes the
// IR bursts; a model of a TSOP-style receiver turns each into a low pulse
// with the datasheet's delay and width error; several receivers and cars are
// wired-AND (the union of their low pulses), with optional noise; the
// resulting edges go through the decoder and the lap tracker.

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "../main/ir_decode.h"
#include "../main/laps.h"

#define T IR_T_US
#define CYCLE_US 26.3  // 38 kHz

static int failures;
#define CHECK(cond, ...)                                     \
	do {                                                       \
		if (!(cond)) {                                           \
			failures++;                                            \
			printf("FAIL %s:%d: ", __FILE__, __LINE__);            \
			printf(__VA_ARGS__);                                   \
			printf("\n");                                          \
		}                                                        \
	} while (0)

// ---- random ----

static uint64_t rs = 88172645463325252ull;
static uint32_t rnd(void)
{
	rs ^= rs << 13;
	rs ^= rs >> 7;
	rs ^= rs << 17;
	return (uint32_t)(rs >> 16);
}
static double urand(double a, double b) { return a + (b - a) * (rnd() / 4294967296.0); }

// ---- intervals of "receiver output low" ----

typedef struct { int64_t s, e; } iv_t;
typedef struct { iv_t *v; int n, cap; } ivs_t;

static void iv_add(ivs_t *l, int64_t s, int64_t e)
{
	if (e <= s)
		return;
	if (l->n == l->cap) {
		l->cap = l->cap ? l->cap * 2 : 1024;
		l->v = realloc(l->v, l->cap * sizeof(iv_t));
	}
	l->v[l->n++] = (iv_t){s, e};
}

static int iv_cmp(const void *a, const void *b)
{
	int64_t d = ((const iv_t *)a)->s - ((const iv_t *)b)->s;
	return d < 0 ? -1 : d > 0;
}

// ---- the transponder ----

typedef struct { int64_t s, e; } burst_t;
typedef struct {
	int car;
	int64_t start, end;  // first burst start, last burst end
	burst_t b[10];
} txframe_t;

// One frame at t, exactly as transponder.c sends it. Returns its end.
static int64_t tx_frame(int car, int64_t t, txframe_t *f)
{
	int data = (car & 0x0f) | ((~car & 0x0f) << 4);
	int n = 0;
	f->car = car;
	f->start = t;
	f->b[n++] = (burst_t){t, t + 4 * T};
	t += 6 * T;
	for (int i = 0; i < 8; i++) {
		f->b[n++] = (burst_t){t, t + T};
		t += ((data >> i) & 1) ? 3 * T : 2 * T;
	}
	f->b[n++] = (burst_t){t, t + T};
	f->end = t + T;
	return f->end;
}

// The gap the transponder waits before its next frame: 4 ms + 0..8 ms.
static int64_t tx_gap(void) { return 10 * T + rnd() % 8000; }

// ---- the receivers ----

#define MAXRX 6
typedef struct {
	int receivers;    // wired-AND
	int distort;      // datasheet delay and width error
	double spikes_per_s, dropout_p;
	// Per receiver, set by rx_frame(): how late it answers and how much it
	// stretches a burst. These follow signal strength, so they hold for a
	// frame (a few ms) and differ between receivers.
	double delay[MAXRX], stretch[MAXRX];
} rx_t;

// Output starts 7..15 cycles after a burst; its width is the burst's -5..+6
// cycles. A little wider than the TSOP382xx datasheet (doc 82491 rev 2.1:
// 7..13 and +-5), to leave margin. Each receiver anywhere in that
// range, independently: the worst case for wired-AND.
static void rx_frame(rx_t *rx)
{
	for (int r = 0; r < rx->receivers; r++) {
		rx->delay[r] = urand(7 * CYCLE_US, 15 * CYCLE_US);
		rx->stretch[r] = urand(-5 * CYCLE_US, 6 * CYCLE_US);
	}
}

// A burst as the receivers in `seen_by` (a bit mask) see it. Wired-AND: all
// into out[0]; split: receiver r into out[r], one input and decoder each.
static void rx_burst_to(const rx_t *rx, int64_t s, int64_t e, unsigned seen_by, ivs_t *outs, int split)
{
	for (int r = 0; r < rx->receivers; r++) {
		if (!(seen_by >> r & 1))
			continue;
		ivs_t *out = &outs[split ? r : 0];
		int64_t os = s, oe = e;
		if (rx->distort) {
			// Plus a cycle of jitter: the burst's start against the carrier's phase.
			os = s + (int64_t)(rx->delay[r] + urand(-CYCLE_US, CYCLE_US));
			oe = os + (e - s) + (int64_t)(rx->stretch[r] + urand(-CYCLE_US, CYCLE_US));
		}
		if (rx->dropout_p > 0 && urand(0, 1) < rx->dropout_p && oe - os > 300) {
			int64_t m = os + (int64_t)urand(100, (double)(oe - os - 150));
			int64_t w = (int64_t)urand(10, 35);
			iv_add(out, os, m);
			iv_add(out, m + w, oe);
		} else {
			iv_add(out, os, oe);
		}
	}
}

static void rx_burst(const rx_t *rx, int64_t s, int64_t e, ivs_t *out)
{
	rx_burst_to(rx, s, e, ~0u, out, 0);
}

static void rx_noise(const rx_t *rx, int64_t t0, int64_t t1, ivs_t *out)
{
	int n = (int)(rx->spikes_per_s * (t1 - t0) / 1e6);
	for (int i = 0; i < n; i++) {
		int64_t s = t0 + (int64_t)urand(0, (double)(t1 - t0));
		iv_add(out, s, s + (int64_t)urand(5, 80));
	}
}

// Merge the low intervals (wired-AND) and feed their edges to the decoder.
typedef struct { int car; int64_t t; int64_t start; } rxframe_t;

static int frame_cmp(const void *a, const void *b)
{
	int64_t d = ((const rxframe_t *)a)->t - ((const rxframe_t *)b)->t;
	return d < 0 ? -1 : d > 0;
}

static int decode(ivs_t *l, rxframe_t *got, int max, ir_decoder_t *d)
{
	qsort(l->v, l->n, sizeof(iv_t), iv_cmp);
	ir_decoder_init(d);
	int n = 0;
	ir_frame_t f;
	for (int i = 0; i < l->n;) {
		int64_t s = l->v[i].s, e = l->v[i].e;
		for (i++; i < l->n && l->v[i].s <= e; i++)
			if (l->v[i].e > e)
				e = l->v[i].e;
		if (ir_decoder_edge(d, s, 0, &f) && n < max)
			got[n++] = (rxframe_t){f.car, f.t_us, f.start_us};
		if (ir_decoder_edge(d, e, 1, &f) && n < max)
			got[n++] = (rxframe_t){f.car, f.t_us, f.start_us};
		// The firmware polls every few ms; between two edges is enough here.
		int64_t next = i < l->n ? l->v[i].s : e + 1000000;
		for (int64_t p = e + 1000; p < next; p += 1000)
			if (ir_decoder_poll(d, p, &f) && n < max) {
				got[n++] = (rxframe_t){f.car, f.t_us, f.start_us};
				break;
			}
	}
	return n;
}

// ---- tests ----

#define MAXF 20000
static txframe_t sent[MAXF];
static rxframe_t got[MAXF];

// One car, always in view. Returns frames decoded; counts wrong car numbers
// and checks each decoded frame matches a sent one in time.
static int run_one_car(rx_t *rx, int frames, int *wrong, int fixed_car)
{
	ivs_t l = {0};
	int64_t t = 1000;
	for (int i = 0; i < frames; i++) {
		int car = fixed_car ? fixed_car : 1 + (int)(rnd() % 15);
		t = tx_frame(car, t, &sent[i]) + tx_gap();
		rx_frame(rx);
		for (int k = 0; k < 10; k++)
			rx_burst(rx, sent[i].b[k].s, sent[i].b[k].e, &l);
	}
	rx_noise(rx, 0, t, &l);
	ir_decoder_t d;
	int n = decode(&l, got, MAXF, &d);
	*wrong = 0;
	int j = 0;
	for (int i = 0; i < n; i++) {
		// Match by time: the decoded start is the header start plus the receiver delay.
		while (j < frames && sent[j].start + 1000 < got[i].start)
			j++;
		if (j == frames || got[i].car != sent[j].car || got[i].start < sent[j].start) {
			(*wrong)++;
			continue;
		}
		int64_t mid = (sent[j].start + sent[j].end) / 2;
		CHECK(got[i].t - mid > -50 && got[i].t - mid < 700, "frame middle off by %lld us", (long long)(got[i].t - mid));
	}
	free(l.v);
	return n;
}

static void test_nominal(void)
{
	rx_t rx = {.receivers = 1};
	for (int car = 1; car <= 15; car++) {
		int wrong, n = run_one_car(&rx, 20, &wrong, car);
		CHECK(n == 20 && wrong == 0, "car %d nominal: %d/20 decoded, %d wrong", car, n, wrong);
	}
	printf("nominal timing, cars 1..15: ok\n");
}

static void test_distorted(void)
{
	for (int r = 1; r <= 6; r++) {
		rx_t rx = {.receivers = r, .distort = 1};
		int wrong, n = run_one_car(&rx, 5000, &wrong, 0);
		printf("receiver timing error, %d wired-AND: %d/5000 decoded, %d wrong\n", r, n, wrong);
		// Wired-AND of receivers at opposite ends of their timing range can
		// close a 1T gap; a few frames are lost that way.
		CHECK(n >= 4850 && wrong == 0, "%d receivers", r);
	}
}

static void test_noise(void)
{
	rx_t rx = {.receivers = 5, .distort = 1, .spikes_per_s = 20, .dropout_p = 0.05};
	int wrong, n = run_one_car(&rx, 5000, &wrong, 0);
	printf("plus 20 noise spikes/s and 5%% dropouts: %d/5000 decoded, %d wrong\n", n, wrong);
	CHECK(n >= 4500 && wrong == 0, "noise");
}

// Two cars in view at once, all the time: their frames collide until the
// random gaps pull them apart. Nothing may decode as a wrong car.
static void test_two_cars(void)
{
	rx_t rx = {.receivers = 5, .distort = 1};
	ivs_t l = {0};
	int64_t end = 60 * 1000000LL;
	int sent_n[16] = {0};
	for (int car = 3; car <= 4; car++) {
		int64_t t = 1000 + car * 777;
		txframe_t f;
		while (t < end) {
			t = tx_frame(car, t, &f) + tx_gap();
			sent_n[car]++;
			rx_frame(&rx);
			for (int k = 0; k < 10; k++)
				rx_burst(&rx, f.b[k].s, f.b[k].e, &l);
		}
	}
	ir_decoder_t d;
	int n = decode(&l, got, MAXF, &d);
	int per[16] = {0};
	for (int i = 0; i < n; i++)
		per[got[i].car]++;
	int wrong = n - per[3] - per[4];
	printf("cars 3 and 4 side by side for 60 s: %d/%d and %d/%d decoded, %d wrong "
	       "(rejected: %u check, %u timing, %u not quiet after)\n",
	       per[3], sent_n[3], per[4], sent_n[4], wrong, (unsigned)d.bad_check, (unsigned)d.bad_timing,
	       (unsigned)d.not_quiet);
	CHECK(wrong == 0, "two cars: %d wrong", wrong);
	free(l.v);
}

static void test_lap_tracker(void)
{
	lap_tracker_t lt;
	lap_event_t ev;
	lap_init(&lt, 200000, 2000000);
	// Pass 1 at 1.000 s: frames from 0.98 to 1.02.
	for (int64_t t = 980000; t <= 1020000; t += 20000)
		lap_frame(&lt, 5, t);
	CHECK(!lap_poll(&lt, 1100000, &ev), "pass closed too early");
	CHECK(lap_poll(&lt, 1220000, &ev) && ev.kind == LAP_EV_START && ev.car == 5 && ev.t_us == 1000000 && ev.frames == 3,
	      "start event");
	CHECK(!lap_poll(&lt, 1220000, &ev), "one event per pass");
	// A single frame at 1.5 s: under min_lap.
	lap_frame(&lt, 5, 1500000);
	CHECK(lap_poll(&lt, 1800000, &ev) && ev.kind == LAP_EV_TOO_SOON, "too soon");
	// Lap at 9.0 s.
	lap_frame(&lt, 5, 8990000);
	lap_frame(&lt, 5, 9010000);
	CHECK(lap_poll(&lt, 9300000, &ev) && ev.kind == LAP_EV_LAP && ev.lap == 1 && ev.lap_us == 8000000, "lap 1");
	lap_frame(&lt, 0, 1);
	lap_frame(&lt, 16, 1);
	CHECK(!lap_poll(&lt, 99000000, &ev), "car 0 and 16 ignored");
	lap_reset(&lt);
	lap_frame(&lt, 5, 20000000);
	CHECK(lap_poll(&lt, 20300000, &ev) && ev.kind == LAP_EV_START, "start again after reset");
	printf("lap tracker: ok\n");
}

// Four cars lapping. Each is in the arch's view for `window_ms` around its
// crossing (zone length / speed), seen by 3 of the 6 receivers next to its
// line. Car 2 trails car 1, except every 5th lap, when they cross side by
// side, car 1 on receivers 0..2, car 2 on 2..4 (receiver 2 sees both). `split`: each receiver on its
// own input with its own decoder, instead of wired-AND.
static void test_race(double window_ms, int split, int max_missed)
{
	enum { CARS = 4, LAPS = 30, RX = 6 };
	rx_t rx = {.receivers = RX, .distort = 1, .spikes_per_s = 20};
	ivs_t l[RX] = {{0}};
	int64_t cross[CARS + 1][LAPS + 1];
	unsigned seen_by[CARS + 1][LAPS + 1];
	int64_t end = 0;
	for (int c = 1; c <= CARS; c++) {
		int64_t t = 2000000 + (c - 1) * 700000;
		for (int k = 0; k <= LAPS; k++) {
			cross[c][k] = t;
			seen_by[c][k] = 7u << (rnd() % 4);
			t += 5000000 + rnd() % 3000000;
		}
		if (c == 2)
			for (int k = 0; k <= LAPS; k++) {
				int side = k % 5 == 0;
				cross[2][k] = cross[1][k] + (side ? rnd() % 20000 : 1500000 + rnd() % 1000000);
				if (side) {
					seen_by[1][k] = 7u;
					seen_by[2][k] = 7u << 2;
				}
			}
		if (cross[c][LAPS] > end)
			end = cross[c][LAPS];
	}
	// The transponders run all the time; only bursts inside a car's view
	// window reach the receivers.
	int64_t half = (int64_t)(window_ms * 500);
	for (int c = 1; c <= CARS; c++) {
		int64_t t = rnd() % 20000;
		int k = 0;
		txframe_t f;
		while (t < end + 1000000) {
			t = tx_frame(c, t, &f) + tx_gap();
			while (k <= LAPS && f.start > cross[c][k] + half)
				k++;
			if (k > LAPS)
				break;
			rx_frame(&rx);
			for (int b = 0; b < 10; b++)
				if (f.b[b].s >= cross[c][k] - half && f.b[b].e <= cross[c][k] + half)
					rx_burst_to(&rx, f.b[b].s, f.b[b].e, seen_by[c][k], l, split);
		}
	}
	int n = 0;
	for (int r = 0; r < (split ? RX : 1); r++) {
		rx_noise(&rx, 0, end, &l[r]);
		ir_decoder_t d;
		n += decode(&l[r], got + n, MAXF - n, &d);
	}
	qsort(got, n, sizeof(rxframe_t), frame_cmp);

	lap_tracker_t lt;
	lap_event_t ev;
	lap_init(&lt, 200000, 2000000);
	int seen[CARS + 1] = {0}, missed = 0, missed_side = 0, wrong = 0;
	int64_t worst = 0;
	int hit[CARS + 1][LAPS + 1];
	memset(hit, 0, sizeof hit);
	for (int i = 0; i <= n; i++) {
		int64_t now = i < n ? got[i].t : end + 10000000;
		while (lap_poll(&lt, now, &ev)) {
			if (ev.car < 1 || ev.car > CARS || ev.kind == LAP_EV_TOO_SOON) {
				printf("  unexpected event: car %d kind %d at %.3f s\n", ev.car, ev.kind, ev.t_us / 1e6);
				wrong++;
				continue;
			}
			int k = 0;
			for (int j = 1; j <= LAPS; j++)
				if (llabs(cross[ev.car][j] - ev.t_us) < llabs(cross[ev.car][k] - ev.t_us))
					k = j;
			int64_t err = ev.t_us - cross[ev.car][k];
			if (llabs(err) > worst)
				worst = llabs(err);
			hit[ev.car][k] = 1;
			seen[ev.car]++;
		}
		if (i < n)
			lap_frame(&lt, got[i].car, got[i].t);
	}
	for (int c = 1; c <= CARS; c++)
		for (int k = 0; k <= LAPS; k++)
			if (!hit[c][k]) {
				missed++;
				missed_side += c <= 2 && k % 5 == 0;
			}
	printf("race, %s, %3.0f ms in view: %2d of %d crossings missed (%2d of 14 side by side), %d wrong, "
	       "worst crossing error %.1f ms\n",
	       split ? "split   " : "wired-AND", window_ms, missed, CARS * (LAPS + 1), missed_side, wrong, worst / 1000.0);
	CHECK(wrong == 0, "race: wrong events");
	// A pass read on one side only (the rest collided) is off by up to half the window.
	CHECK(worst <= half + 5000, "race: crossing error %lld us", (long long)worst);
	CHECK(missed <= max_missed, "race: %d crossings missed", missed);
	for (int r = 0; r < RX; r++)
		free(l[r].v);
}

int main(void)
{
	test_nominal();
	test_distorted();
	test_noise();
	test_two_cars();
	test_lap_tracker();
	for (int split = 0; split <= 1; split++) {
		test_race(40, split, split ? 8 : 24);
		test_race(60, split, split ? 4 : 20);
		test_race(100, split, split ? 2 : 14);
	}
	if (failures) {
		printf("%d FAILED\n", failures);
		return 1;
	}
	printf("all passed\n");
	return 0;
}
