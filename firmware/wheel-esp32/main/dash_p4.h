// The instrument clusters on the P4's main screen, switched by swiping left /
// right; the choice is saved. Only the visible one is drawn and updated.
// Designs and their static images: design/dash_concepts.html,
// design/render/ (build_assets.py writes main/assets/*.bin).
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
    float steer; // -1 (left) .. +1 (right)
} dash_values_t;

void dash_build(lv_obj_t *scr);
void dash_show(const dash_values_t *v);
// Where the shared notice line sits on the current dashboard.
int dash_notice_y(void);
