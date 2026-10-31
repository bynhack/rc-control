"""Test cage for the 1:28 rally car (windscreen cut out, the camera inside):
the shape of the room inside the shell above the chassis' top deck (the
copper plate), to feel that room before the parts go on it. Set it on the
deck, put the shell on, and see where it touches: the notches along the top
edges, every 10 mm from the front, say where.

The room, measured from the chassis floor (deck at 21): 68 long; the roof
48 high at the windscreen's top edge and 51 at the back; 48 wide under the
roof, sloping out to 60, then 70 lower down.

One part, minicar_cage.stl: a thin open-topped tub whose outside is that
room. Printed floor down, it needs no support: its sides only lean in.

Coordinates: x = forward (the front at x = L), y = across (centred), z = up
from the deck's top face.

Run:  python minicar_cage.py  -> out/minicar_cage.stl, out/minicar_cage_preview.png
"""

import os
import sys

import numpy as np
from manifold3d import CrossSection, JoinType, Manifold

from enclosure import OUT, box, preview, to_trimesh

DECK = 21.0  # chassis floor to the deck's top
L = 68.0
H_FRONT, H_REAR = 48.0 - DECK, 51.0 - DECK  # roof over the deck, at the front and the back
W_ROOF, W_SLOPE, W_LOW = 48.0, 60.0, 70.0
Z_LOW, Z_SLOPE = 10.0, 15.5  # MEASURE: where the width steps from 70 to 60, and where the slope to 48 starts (guessed; the step kept at 45 degrees or steeper, so it prints)
SKIN = 1.6  # walls and floor
TICK = 10.0


def roof(x):
    return H_REAR + (H_FRONT - H_REAR) * x / L


def profile():
    """The room's cross-section (y, z), at its back end's roof height."""
    half = [(W_LOW / 2, Z_LOW), (W_SLOPE / 2, Z_SLOPE), (W_ROOF / 2, H_REAR)]
    return CrossSection([[(-W_LOW / 2, 0.0), (W_LOW / 2, 0.0)] + half + [(-y, z) for y, z in reversed(half)]])


def along_x(cs, x0, x1):
    """A (y, z) outline extruded from x0 to x1."""
    return Manifold.extrude(cs, x1 - x0).transform(np.array([[0, 0, 1, x0], [1, 0, 0, 0], [0, 1, 0, 0]]))


def cage():
    sloped_roof = Manifold.hull_points([(x, y, z) for x in (0.0, L) for y in (-50.0, 50.0) for z in (-10.0, roof(x))])
    outer = along_x(profile(), 0.0, L) ^ sloped_roof
    room = profile().offset(-SKIN, JoinType.Miter)
    room += CrossSection.square([W_ROOF - 2 * SKIN, 30.0]).translate([-(W_ROOF / 2 - SKIN), H_REAR - 5.0])  # open top
    out = outer - along_x(room, SKIN, L - SKIN)
    # Notches on the top edges, counted from the front.
    k = 1
    while L - k * TICK > 0:
        x = L - k * TICK
        d = 0.6 * (2 if k % 5 == 0 else 1)
        out -= box(x - 0.3, -W_LOW, roof(x) - d, x + 0.3, W_LOW, roof(x) + 1)
        k += 1
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    c = cage()
    if c.is_empty() or len(c.decompose()) != 1:
        sys.exit("cage: not a single solid")
    to_trimesh(c).export(os.path.join(OUT, "minicar_cage.stl"))
    preview([("on the deck", [(c, (0.62, 0.68, 0.76))], 25, -60), ("from the front", [(c, (0.62, 0.68, 0.76))], 15, 10)],
            os.path.join(OUT, "minicar_cage_preview.png"))
    lo, hi = c.bounding_box()[:3], c.bounding_box()[3:]
    print(f"cage: {hi[0]-lo[0]:.0f} long x {hi[1]-lo[1]:.0f} wide x {hi[2]-lo[2]:.0f} high, {c.volume()/1000:.1f} cm3")


if __name__ == "__main__":
    main()
