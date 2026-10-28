// Force feedback on the wheel base, through the standard USB PID reports
// (what DirectInput games use; the MOZA R5 descriptor has them all).
//
// Two condition effects stay running: a centring spring and a damper. The
// driving code sets their strengths every frame (ffb_set); a task pushes
// changes to the base. The overall strength is the base's device gain,
// set on the dashboard (ui_ffb_get / ui_ffb_set in radio.h).
#pragma once

#include "usb/hid_host.h"

// After hid_host_device_start(): resets the base's effects and creates ours.
void ffb_attach(hid_host_device_handle_t dev);
void ffb_detach(void);

// 0..1 each: centring spring stiffness and damping.
void ffb_set(float spring, float damper);
