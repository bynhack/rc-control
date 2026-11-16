"""The whole room inside the X2201's black liner, from the scan
(x2201_liner.npz): everything between the chassis' top and the liner's
inside, over the liner's whole footprint. Boards, the VTX, the fan and the
camera all go in it.

Two parts:
x2201_room.stl
  - the room as one solid: a reference body to import into CAD and lay
    parts out in. Its top is the liner's inside (LINER_T under the scanned
    top) less CLEAR; the roof openings are filled, so the room runs on
    under them.
x2201_interior_cage.stl, printed standing as it sits, tree supports under the roof
  - the room's outside as a cage: ribs every PITCH along x and y, a wall
    round the footprint's edge where the roof doesn't come down to the
    chassis (the dash at the front), and a band along the bottom. Set it on
    the chassis with everything off, put the liner and shell on and see
    where it touches; then set parts inside it and see where they hit it.
    The ribs are at x and y = multiples of PITCH in the cage's coordinates;
    the front is the low end (the dash).

Coordinates as in x2201_cage.py: x = forward from the test cage's back end
(the windscreen's foot at x = L), y = across (centred), z = up from the
chassis' top.

Run:  python x2201_interior.py  -> out/x2201_room.stl, out/x2201_interior_cage.stl,
      out/x2201_interior_preview.png
"""

import os
import sys

import numpy as np
from manifold3d import Manifold, OpType

from cad import OUT, box, preview, to_trimesh
from x2201_liner import CELL, LINER_T, NPZ, footprint, heightfield, normal_t, prism, smooth_top

CLEAR = 0.3  # the cage's outside under the liner's inside
RIB_T = 1.2  # ribs, walls and band: thickness square to the surface
RIB_W = 1.6  # ribs: width
PITCH = 10.0
WALL_CELLS = 2  # the edge wall: this many 1 mm cells in from the footprint's edge
BAND_H = 2.0  # the bottom band
MIN_ROOM = 1.0  # cells with less room than this are left out


def room_parts():
    from scipy import ndimage

    d = np.load(NPZ)
    x, y = d["x"], d["y"]
    ceil = smooth_top(d) - LINER_T - CLEAR
    foot = footprint(d, openings=False) & (ceil > MIN_ROOM)
    foot = ndimage.binary_opening(foot, iterations=1)
    lab, n = ndimage.label(foot)
    foot = lab == np.argmax(np.bincount(lab.ravel())[1:]) + 1  # one piece
    above = box(x[0] - 5, y[0] - 5, 0, x[-1] + 5, y[-1] + 5, 40)
    room = heightfield(x, y, ceil) ^ prism(x, y, foot) ^ above
    return d, x, y, ceil, foot, room


def cage(x, y, ceil, foot, room):
    from scipy import ndimage

    skin = room - heightfield(x, y, ceil - normal_t(ceil, RIB_T))
    inner = ndimage.binary_erosion(foot, iterations=WALL_CELLS)
    walls = room - prism(x, y, inner)
    ribs = [box(k * PITCH - RIB_W / 2, y[0] - 5, -1, k * PITCH + RIB_W / 2, y[-1] + 5, 40)
            for k in range(int(np.floor(x[0] / PITCH)), int(np.ceil(x[-1] / PITCH)) + 1)]
    ribs += [box(x[0] - 5, k * PITCH - RIB_W / 2, -1, x[-1] + 5, k * PITCH + RIB_W / 2, 40)
             for k in range(int(np.floor(y[0] / PITCH)), int(np.ceil(y[-1] / PITCH)) + 1)]
    ribs.append(box(x[0] - 5, y[0] - 5, -1, x[-1] + 5, y[-1] + 5, BAND_H))
    out = (skin + walls) ^ Manifold.batch_boolean(ribs, OpType.Add)
    parts = sorted(out.decompose(), key=lambda m: -m.volume())
    return parts[0], len(parts) - 1, sum(p.volume() for p in parts[1:])


def main():
    os.makedirs(OUT, exist_ok=True)
    d, x, y, ceil, foot, room = room_parts()
    if room.is_empty():
        sys.exit("room: empty")
    c, n_crumbs, v_crumbs = cage(x, y, ceil, foot, room)
    to_trimesh(room).export(os.path.join(OUT, "x2201_room.stl"))
    to_trimesh(c).export(os.path.join(OUT, "x2201_interior_cage.stl"))
    grey, blue = (0.62, 0.68, 0.76), (0.55, 0.7, 0.9)
    preview([("cage", [(c, grey)], 30, -60), ("cage, from the side (front to the right)", [(c, grey)], 0, -90),
             ("cage, from above", [(c, grey)], 89, -90), ("the room (x2201_room.stl)", [(room, blue)], 30, -60)],
            os.path.join(OUT, "x2201_interior_preview.png"))
    for name, m in (("room", room), ("cage", c)):
        lo, hi = m.bounding_box()[:3], m.bounding_box()[3:]
        print(f"{name}: x {lo[0]:.1f} .. {hi[0]:.1f}, y {lo[1]:.1f} .. {hi[1]:.1f}, z {lo[2]:.1f} .. {hi[2]:.1f}; "
              f"{m.volume() / 1000:.1f} cm3")
    if n_crumbs:
        print(f"cage: {n_crumbs} loose bits dropped ({v_crumbs:.1f} mm3)")
    # The room's height over a grid, for laying parts out.
    print("room height (mm) at y = 0 / the width with >= 10 mm of room, every 10 mm along x:")
    j0 = int(np.argmin(np.abs(y)))
    for k in range(int(np.ceil(x[0] / PITCH)), int(np.floor(x[-1] / PITCH)) + 1):
        i = int(np.argmin(np.abs(x - k * PITCH)))
        h = np.where(foot[i], ceil[i], 0)
        tall = np.nonzero(h >= 10)[0]
        w = f"{y[tall[-1]] - y[tall[0]] + CELL:.0f}" if len(tall) else "-"
        print(f"  x {k * PITCH:5.0f}: {h[j0]:5.1f} high, {w} wide")


if __name__ == "__main__":
    main()
