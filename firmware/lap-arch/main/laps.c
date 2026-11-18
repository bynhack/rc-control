#include "laps.h"

void lap_init(lap_tracker_t *lt, int64_t pass_gap_us, int64_t min_lap_us)
{
	lt->pass_gap_us = pass_gap_us;
	lt->min_lap_us = min_lap_us;
	lap_reset(lt);
}

void lap_reset(lap_tracker_t *lt)
{
	for (int i = 0; i < LAP_CARS; i++)
		lt->car[i] = (lap_car_t){0};
}

void lap_frame(lap_tracker_t *lt, int car, int64_t t)
{
	if (car < 1 || car >= LAP_CARS)
		return;
	lap_car_t *c = &lt->car[car];
	if (!c->open) {
		c->open = 1;
		c->first_us = t;
		c->frames = 0;
	}
	// Frames from several decoders (one per input) may come slightly out of order.
	if (t < c->first_us)
		c->first_us = t;
	if (t > c->last_us || c->frames == 0)
		c->last_us = t;
	c->frames++;
}

int lap_poll(lap_tracker_t *lt, int64_t now, lap_event_t *ev)
{
	for (int i = 1; i < LAP_CARS; i++) {
		lap_car_t *c = &lt->car[i];
		if (!c->open || now - c->last_us < lt->pass_gap_us)
			continue;
		c->open = 0;
		int64_t t = c->first_us + (c->last_us - c->first_us) / 2;
		*ev = (lap_event_t){.car = i, .t_us = t, .frames = c->frames, .span_us = c->last_us - c->first_us};
		if (!c->crossed) {
			ev->kind = LAP_EV_START;
		} else if (t - c->cross_us < lt->min_lap_us) {
			ev->kind = LAP_EV_TOO_SOON;  // stopped under the arch, or backed through it
			ev->lap = c->laps;
			ev->lap_us = t - c->cross_us;
			return 1;
		} else {
			ev->kind = LAP_EV_LAP;
			ev->lap_us = t - c->cross_us;
			c->laps++;
		}
		c->crossed = 1;
		c->cross_us = t;
		ev->lap = c->laps;
		return 1;
	}
	return 0;
}
