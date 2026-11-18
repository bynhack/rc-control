// Force feedback on the wheel base. The MOZA R5 takes the standard USB PID
// reports (what DirectInput games use; its descriptor has them all). The
// T300RS has its own protocol on report 0x60, as hid-tmff2 drives it.
//
// Three condition effects stay running: a centring spring, a damper and an
// end stop. The
// driving code sets their strengths every frame (ffb_set); a task pushes
// changes to the base. The overall strength is the base's device gain,
// set on the dashboard (ui_ffb_get / ui_ffb_set in radio.h).
#pragma once

#include <stdbool.h>

#include "usb/hid_host.h"
#include "wheel.h"

// After hid_host_device_start(): resets the base's effects and creates ours.
void ffb_attach(hid_host_device_handle_t dev, wheel_kind_t kind);
void ffb_detach(void);

// 0..1 each: centring spring stiffness and damping.
void ffb_set(float spring, float damper);

// End stop at the car's full lock: past -edge..+edge of the steering axis
// the wheel is pushed back hard. 1 (the default) = none.
void ffb_set_stop(float edge);

// Where the spring pulls to, -1..1 of the steering axis; 0 normally.
void ffb_set_centre(float centre);

// Bring the wheel back to the centre (after the steering trim is saved with
// the wheel held off centre). While ffb_recentring(), the driving code pulls
// it there instead of its own ffb_set(), and calls ffb_recentre_stop() once
// it has settled; it gives up by itself after a few seconds.
void ffb_recentre(void);
void ffb_recentre_stop(void);
bool ffb_recentring(void);
