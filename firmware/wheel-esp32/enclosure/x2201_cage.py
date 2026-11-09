"""Test cage for the Geeks X2201 (1:22, 220 x 82 x 61 overall, alloy shell):
the shape of the cab's room inside the shell, where the Walksnail Avatar
Ascent Lite+ camera looks out through the windscreen (driver's view) and the
VTX sits behind it. Set it on the chassis under the cab, put the shell on,
and see where it touches: the notches along the side walls' top edges,
every 10 mm from the front (deeper every 50), say where.

Every size here is GUESSED from the car's overall size; this print is how
they get measured. Too big and the shell won't close: file or note where it
hits. Too small: measure the gap. Then change the numbers and print again.

The side walls' top edge is the cab's side outline: the cowl at the front,
up the windscreen to its top edge, then the fastback roofline (a low arc,
then a long gentle slope to the back end). The walls lean in towards the roof (the shell's tumblehome). Front and back are
walls up to the outline; the top is open.

The floor is only two strips along the sides: the chassis' middle has a
channel with screw posts and wiring along it, so the floor's middle is open,
and the front and back walls have a notch at the bottom for the wires. The
walls over the notches tie the two sides together.

One part, x2201_cage.stl, printed floor down, no support: the walls only
lean in.

Coordinates: x = forward (the cowl at x = L), y = across (centred),
z = up from what the cage stands on under the cab.

Run:  python x2201_cage.py  -> out/x2201_cage.stl, out/x2201_cage_preview.png
"""

import os
import sys

import numpy as np
from manifold3d import CrossSection, JoinType, Manifold

from cad import OUT, box, preview, to_trimesh

# ---- the cab's room (all MEASURE) -------------------------------------------------
L = 84.0  # the back end to the windscreen's foot (measured: 74 to the rear window's top edge, +10)
Z_COWL = 5.0  # windscreen's foot (measured: the opening is 15 high under the top edge)
WS_RUN = 22.0  # windscreen: its top edge is this far back from its foot
Z_WS_TOP = 20.0  # windscreen's top edge (measured)
Z_ROOF = 24.0  # the roof's highest point (measured: the base to the highest point)
# The roofline behind the windscreen's top edge, (x, z) back to the cage's back
# end: traced from a side photo of the shell, scaled by the two measured
# heights. A fastback: a low arc over the cab, then a long gentle slope down
# past the rear window's top edge (x = 10) for the last 10 mm.
ROOFLINE = [(56.0, 22.0), (51.0, 23.6), (46.0, 24.0), (37.0, 24.0), (28.0, 23.6), (23.0, 22.4), (16.0, 21.0), (10.0, 20.0),
            (0.0, 18.0)]
W_LOW, Z_BELT = 68.0, 12.0  # full width up to the belt line, where the sides start leaning in (measured)
W_ROOF = 52.0  # width under the roof
SKIN = 1.6  # walls and floor
TICK = 10.0
MID_W = 30.0  # MEASURE: open floor down the middle, over the chassis' channel and posts
NOTCH_H = 8.0  # MEASURE: wire notch at the bottom of the front and back walls (bridged over)

# ---- Ascent Lite+ stand-ins, for the preview only -----------------------------------
VTX_W, VTX_H = 23.5, 8.0
FAN_W, FAN_T, AIR_GAP = 25.0, 7.0, 3.0
CAM_W, CAM_H, CAM_L = 14.0, 12.0, 12.0
LENS_D, LENS_L = 10.0, 6.0

SIDE = [(0.0, 0.0), (L, 0.0), (L, Z_COWL), (L - WS_RUN, Z_WS_TOP)] + ROOFLINE


def top(x):
    """The side outline's height at x."""
    return float(np.interp(x, [p[0] for p in SIDE[2:]][::-1], [p[1] for p in SIDE[2:]][::-1]))


def along_x(cs, x0, x1):
    """A (y, z) outline extruded from x0 to x1."""
    return Manifold.extrude(cs, x1 - x0).transform(np.array([[0, 0, 1, x0], [1, 0, 0, 0], [0, 1, 0, 0]]))


def along_y(cs, w):
    """An (x, z) outline extruded across y, centred."""
    return Manifold.extrude(cs, w).transform(np.array([[1, 0, 0, 0], [0, 0, 1, -w / 2], [0, 1, 0, 0]]))


def section():
    """The room's cross-section (y, z), to the roof."""
    half = [(W_LOW / 2, Z_BELT), (W_ROOF / 2, Z_ROOF)]
    return CrossSection([[(-W_LOW / 2, 0.0), (W_LOW / 2, 0.0)] + half + [(-y, z) for y, z in reversed(half)]])


def cage():
    outer = shell_room()
    room = section().offset(-SKIN, JoinType.Miter)
    room += CrossSection.square([W_ROOF - 2 * SKIN, 30.0]).translate([-(W_ROOF / 2 - SKIN), Z_ROOF - 5.0])  # open top
    out = outer - along_x(room, SKIN, L - SKIN)
    # Open middle: the floor between the strips, and a notch through each end wall.
    out -= box(-1, -MID_W / 2, -1, L + 1, MID_W / 2, NOTCH_H)
    # Notches on the side walls' top edges, counted from the front.
    k = 1
    while L - k * TICK > 0:
        x = L - k * TICK
        d = 0.6 * (2 if k % 5 == 0 else 1)
        out -= box(x - 0.3, -W_LOW, top(x) - d, x + 0.3, W_LOW, top(x) + 1)
        k += 1
    return out


def shell_room():
    """The room inside the shell: the cage's outside."""
    return along_x(section(), 0.0, L) ^ along_y(CrossSection([SIDE]), W_LOW + 2)


def screen_x(z):
    """The windscreen's inside, x at height z (between the cowl and its top edge)."""
    return L - WS_RUN * (z - Z_COWL) / (Z_WS_TOP - Z_COWL)


def camera(lens_x):
    cz = (Z_COWL + Z_WS_TOP) / 2 - CAM_H / 2  # lens at the windscreen's mid height
    cam = box(lens_x - CAM_L, -CAM_W / 2, cz, lens_x, CAM_W / 2, cz + CAM_H)
    return cam + Manifold.cylinder(LENS_L, LENS_D / 2).rotate([0, 90, 0]).translate([lens_x, 0, cz + CAM_H / 2])


def stand_ins():
    """The lens at the windscreen's mid height (it must see over the cowl and
    under the roof's edge), as far forward as it fits under the shell; the
    VTX and fan on the floor behind it, 8 mm of ribbon between."""
    room = shell_room()
    lens_x = L - LENS_L
    while lens_x > CAM_L and (camera(lens_x) - room).volume() > 0.01:
        lens_x -= 0.25
    cam = camera(lens_x)
    vx = lens_x - CAM_L - 8.0 - VTX_W / 2
    vtx = box(vx - VTX_W / 2, -VTX_W / 2, SKIN, vx + VTX_W / 2, VTX_W / 2, SKIN + VTX_H)
    z_fan = SKIN + VTX_H + AIR_GAP
    fan = box(vx - FAN_W / 2, -FAN_W / 2, z_fan, vx + FAN_W / 2, FAN_W / 2, z_fan + FAN_T)
    return cam, vtx, fan


def main():
    os.makedirs(OUT, exist_ok=True)
    c = cage()
    if c.is_empty() or len(c.decompose()) != 1:
        sys.exit("cage: not a single solid")
    cam, vtx, fan = stand_ins()
    room = shell_room()
    for name, p in (("camera", cam), ("vtx", vtx), ("fan", fan)):
        if (p - room).volume() > 0.01:
            print(f"warning: {name} sticks out of the room ({(p - room).volume():.1f} mm3)")
    to_trimesh(c).export(os.path.join(OUT, "x2201_cage.stl"))
    grey, dark = (0.62, 0.68, 0.76), (0.15, 0.17, 0.2)
    with_parts = [(c, grey), (cam, dark), (vtx, (0.40, 0.46, 0.55)), (fan, dark)]
    preview([("cage", [(c, grey)], 25, -60), ("with the Ascent Lite+ (scale)", with_parts, 30, -60),
             ("from above", with_parts, 89, -90), ("from the side (front to the right)", [(c, grey)], 0, -90), ("from the front", [(c, grey)], 15, 10)],
            os.path.join(OUT, "x2201_cage_preview.png"))
    lo, hi = c.bounding_box()[:3], c.bounding_box()[3:]
    print(f"cage: {hi[0]-lo[0]:.0f} long x {hi[1]-lo[1]:.0f} wide x {hi[2]-lo[2]:.0f} high, {c.volume()/1000:.1f} cm3")
    lb = cam.bounding_box()
    zc = (lb[2] + lb[5]) / 2
    print(f"camera: body {lb[2]:.1f} .. {lb[5]:.1f} high, lens centre {zc:.1f}; "
          f"lens tip {screen_x(zc) - lb[3]:.1f} mm behind the windscreen")
    print(f"vtx + fan top at z = {fan.bounding_box()[5]:.1f}")


if __name__ == "__main__":
    main()
