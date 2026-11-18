// Decoder for the lap-timing transponder's frames (firmware/transponder),
// as they come out of the arch's 38 kHz receivers (wired-AND, active low).
//
// Plain C, no ESP-IDF: the host tests in ../test build it too.
//
// Frame, T = 400 us:
//   header   burst 4T, gap 2T
//   8 bits   LSB first, each burst 1T then gap 1T (0) or 2T (1):
//            bits 0..3 the car number 1..15, bits 4..7 its complement
//   stop     burst 1T
//
// The receivers stretch or shrink each burst by up to ~6 carrier cycles
// (160 us) and start it 7..15 cycles late, and wired-AND makes a burst as
// long as the union of what every receiver saw. So the decoder doesn't trust
// burst or gap lengths alone: a bit is read from burst start to the next
// burst start (2T = 0, 3T = 1), the edge that moves least, and burst lengths
// only tell the header (4T) from the rest (1T).
//
// Two cars in view at once garble each other's frames, and the 4-bit
// complement alone lets about 1 in 16 garbled frames through. So a frame
// also has to end in quiet: no burst for 3.4 ms after the stop burst starts
// (the transponder waits at least 4 ms), which another car's bursts break.
// The frame is reported when that quiet is seen, on the next edge or in
// ir_decoder_poll().

#ifndef IR_DECODE_H
#define IR_DECODE_H

#include <stdint.h>

#define IR_T_US 400

typedef struct {
	int car;          // 1..15
	int64_t start_us; // the header burst's start
	int64_t t_us;     // the frame's middle: what the lap tracker uses
} ir_frame_t;

typedef struct {
	// Edge filter: one mark (burst) at a time, held until the next one is
	// confirmed, so a noise spike can't split a period.
	int level;         // last level seen, 1 = idle
	int in_mark;
	int reopened;      // the current mark is the previous one, continued past a dropout
	int64_t cur_start;
	int have_prev;
	int64_t prev_start, prev_end;
	// Frame state.
	int bits;          // -1: waiting for a header, else bits read so far
	unsigned data;
	int64_t frame_start;
	int pending;       // all 8 bits good, waiting for the quiet after the stop burst
	int64_t stop_start;
	ir_frame_t frame;
	// Counters, for the serial "stats" line.
	uint32_t frames, bad_check, bad_timing, not_quiet;
} ir_decoder_t;

void ir_decoder_init(ir_decoder_t *d);

// Feed one edge of the receivers' output, in time order. level 0 = carrier
// seen (outputs pulled low), 1 = idle. Returns 1 and fills *out when this
// edge completes a valid frame.
int ir_decoder_edge(ir_decoder_t *d, int64_t t_us, int level, ir_frame_t *out);

// Call every few ms with the current time: reports a frame whose quiet has
// passed with no edge since. Returns 1 and fills *out if so.
int ir_decoder_poll(ir_decoder_t *d, int64_t now_us, ir_frame_t *out);

#endif
