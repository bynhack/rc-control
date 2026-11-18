#include "ir_decode.h"

#define T IR_T_US

// Marks or spaces shorter than this are noise: a spike is dropped, a dropout
// inside a burst is bridged. Kept short because a 1T gap can shrink to well
// under 100 us: each receiver may stretch a burst by 160 us, and wired-AND
// adds the spread of their delays (a near receiver answers sooner than a far
// one).
#define GLITCH_US 40

// Burst lengths. A 1T burst comes out 270..560 us, more with several
// receivers wired-AND; the 4T header 1470..1760 us.
#define BIT_MARK_MAX (5 * T / 2)       // 1000
#define HDR_MARK_MIN (5 * T / 2)       // 1000
#define HDR_MARK_MAX (6 * T)           // 2400

// Burst start to burst start.
#define HDR_PERIOD_MIN (19 * T / 4)    // 1900, nominal 6T = 2400
#define HDR_PERIOD_MAX (29 * T / 4)    // 2900
#define BIT_PERIOD_MIN (3 * T / 2)     //  600, nominal 2T = 800 (a 0)
#define BIT_PERIOD_SPLIT (5 * T / 2)   // 1000
#define BIT_PERIOD_MAX (18 * T / 5)    // 1440, nominal 3T = 1200 (a 1)

// From the stop burst's start, nothing may start for this long: 1T burst +
// at least 10T gap = 4400 us nominal, less the receivers' jitter.
#define STOP_QUIET (17 * T / 2)        // 3400

void ir_decoder_init(ir_decoder_t *d)
{
	*d = (ir_decoder_t){.level = 1, .bits = -1};
}

static int is_header(int64_t len, int64_t period)
{
	return len >= HDR_MARK_MIN && len <= HDR_MARK_MAX && period >= HDR_PERIOD_MIN && period <= HDR_PERIOD_MAX;
}

// One confirmed burst: its start, its length, and the time to the next
// burst's start.
static void mark(ir_decoder_t *d, int64_t start, int64_t len, int64_t period)
{
	if (d->bits >= 0) {
		int bit = -1;
		if (len <= BIT_MARK_MAX && period >= BIT_PERIOD_MIN && period <= BIT_PERIOD_MAX)
			bit = period >= BIT_PERIOD_SPLIT;
		if (bit >= 0) {
			d->data |= (unsigned)bit << d->bits;
			if (++d->bits < 8)
				return;
			// The 8th bit's period ends where the stop burst starts.
			d->bits = -1;
			unsigned car = d->data & 0x0f, inv = d->data >> 4;
			if ((car ^ inv) != 0x0f || car == 0) {
				d->bad_check++;
				return;
			}
			// Hold it until the quiet after the stop burst is seen.
			d->pending = 1;
			d->stop_start = start + period;
			d->frame.car = (int)car;
			d->frame.start_us = d->frame_start;
			d->frame.t_us = (d->frame_start + d->stop_start + T) / 2;  // header start to stop end
			return;
		}
		d->bad_timing++;
		d->bits = -1;
		// Fall through: this burst may be the next frame's header.
	}
	if (is_header(len, period)) {
		d->bits = 0;
		d->data = 0;
		d->frame_start = start;
	}
}

// The pending frame, if its stop burst was short and nothing has started
// since, for long enough.
static int release(ir_decoder_t *d, int64_t t, ir_frame_t *out)
{
	if (!d->pending || t - d->stop_start < STOP_QUIET)
		return 0;
	d->pending = 0;
	if (d->prev_start != d->stop_start || d->prev_end - d->prev_start > BIT_MARK_MAX) {
		d->bad_timing++;
		return 0;
	}
	d->frames++;
	*out = d->frame;
	return 1;
}

int ir_decoder_poll(ir_decoder_t *d, int64_t now, ir_frame_t *out)
{
	if (d->in_mark)
		return 0;  // the stop burst (or something after it) hasn't ended
	return release(d, now, out);
}

int ir_decoder_edge(ir_decoder_t *d, int64_t t, int level, ir_frame_t *out)
{
	level = level != 0;
	if (level == d->level)
		return 0;  // a missed edge pair; the timing checks will reject what it broke
	d->level = level;

	if (level == 0) {
		// Burst starts.
		d->in_mark = 1;
		if (d->have_prev && !d->reopened && t - d->prev_end < GLITCH_US) {
			d->reopened = 1;  // a dropout: the previous burst goes on
			return 0;
		}
		d->reopened = 0;
		d->cur_start = t;
		return release(d, t, out);
	}

	// Burst ends.
	if (!d->in_mark)
		return 0;
	d->in_mark = 0;
	if (d->reopened) {
		d->reopened = 0;
		d->prev_end = t;
		return 0;
	}
	if (t - d->cur_start < GLITCH_US)
		return 0;  // a spike
	if (d->pending) {
		d->pending = 0;  // a real burst started too soon after the stop burst
		d->not_quiet++;
	}
	if (d->have_prev)
		mark(d, d->prev_start, d->prev_end - d->prev_start, d->cur_start - d->prev_start);
	d->have_prev = 1;
	d->prev_start = d->cur_start;
	d->prev_end = t;
	return 0;
}
