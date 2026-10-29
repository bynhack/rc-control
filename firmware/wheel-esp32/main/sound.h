// Engine sound on the P4 board's speaker (ES8311 codec + NS4150B amp, PH2.0
// header). Synthesised from the driving model, no samples: the starter on
// ignition, idle, revs that follow speed within the gear (so an upshift
// drops them), a free rev in neutral, and pops on the overrun. The rally
// voice adds a turbo, blow-off, anti-lag bangs, flat-shift cuts, dog-box
// whine and gravel.
#pragma once

// Which car it sounds like (saved: ui_sound_get() in radio.h).
enum { SOUND_ROAD, SOUND_RALLY, SOUND_VOICES };

void sound_start(void);
