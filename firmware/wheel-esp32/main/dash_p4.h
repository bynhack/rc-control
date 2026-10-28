// The instrument clusters on the P4's main screen: several looks, switched
// by swiping left / right; the choice is saved. Only the visible one is
// drawn and updated.
#pragma once

#include <stdbool.h>

#include "control.h"
#include "lvgl.h"

typedef struct {
    bool on;     // engine running and the wheel present; otherwise dimmed
    gear_t gear;
    float power; // drive power 0..1 (output, not counting braking)
    float throttle; // signed output, for its colour
    float speed; // modelled speed -1..1
    float cap;   // the gear's power cap 0..1 (0 in neutral)
} dash_values_t;

void dash_build(lv_obj_t *scr);
void dash_show(const dash_values_t *v);
