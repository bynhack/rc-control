// Lap tracker: turns decoded frames into one crossing per pass under the arch.
//
// A car is read for as long as it is under the arch, a few frames at racing
// speed. Its crossing is the middle of the first and last frame read, which
// doesn't depend on how wide the arch's view is, as long as it is about
// symmetric. A pass ends when that car hasn't been read for pass_gap.
//
// Plain C, no ESP-IDF: the host tests build it too.

#ifndef LAPS_H
#define LAPS_H

#include <stdint.h>

#define LAP_CARS 16  // car numbers 1..15

typedef enum {
	LAP_EV_START,     // the car's first crossing since a reset: lap 0, no lap time
	LAP_EV_LAP,       // a lap: lap >= 1, lap_us set
	LAP_EV_TOO_SOON,  // a crossing under min_lap after the last one: not counted
} lap_ev_kind_t;

typedef struct {
	lap_ev_kind_t kind;
	int car;
	int lap;          // laps completed, 0 at the start crossing
	int64_t t_us;     // the crossing
	int64_t lap_us;   // since the previous crossing (0 for a start)
	int frames;       // frames read in this pass
	int64_t span_us;  // first to last frame
} lap_event_t;

typedef struct {
	int open;
	int64_t first_us, last_us;
	int frames;
	int crossed;      // has a counted crossing
	int64_t cross_us;
	int laps;
} lap_car_t;

typedef struct {
	lap_car_t car[LAP_CARS];
	int64_t pass_gap_us, min_lap_us;
} lap_tracker_t;

void lap_init(lap_tracker_t *lt, int64_t pass_gap_us, int64_t min_lap_us);
void lap_reset(lap_tracker_t *lt);  // forget all laps (a new race)
void lap_frame(lap_tracker_t *lt, int car, int64_t t_us);

// Close the passes that have ended by now_us. Returns 1 and fills *ev for
// one of them; call until it returns 0.
int lap_poll(lap_tracker_t *lt, int64_t now_us, lap_event_t *ev);

#endif
