"""Hole spacing test plate for the X2201 chassis: a plain rectangle with two
holes, for the M2 screw boss on the suspension block (the rear) and the support
post on the chassis plate beside it. The M2 boss holds it; the post only
locates it, its 3.5 going into the other hole.

Measured (calipers), outermost edges of the boss and the post:
  along the car   38.0  -> centres 38 - 4.95/2 - 5/2 = 33.0
  across          12.4  -> centres 12.4 - 4.95/2 - 5/2 = 7.4
  M2 boss 4.95 across; support post 5.0 outside, 3.5 hole; their tops level

Print flat, no supports. M2 x 6 to screw it down.

Run:  python x2201_hole_plate.py  -> out/x2201_hole_plate.stl
"""

import os

from cad import OUT, cyl, rbox, to_trimesh
from x2201_datum import PLATE_POST

DX, DY = PLATE_POST[0], -PLATE_POST[1]  # centre to centre: along, and across to the right (x2201_datum)
M2_HOLE = 2.4  # M2 clearance
POST_HOLE = 3.7  # the locating post's 3.5 goes in, printed holes shrink (it only locates; the M2 holds)
T = 2.0
PLATE_L, PLATE_W = 40.0, 60.0  # along the car x across; the holes centred in it


def plate():
    x0 = DX / 2 - PLATE_L / 2
    y0 = -DY / 2 - PLATE_W / 2
    x1, y1 = x0 + PLATE_L, y0 + PLATE_W
    p = rbox(x0, y0, 0, x1 - x0, y1 - y0, T, 1.0)
    return p - cyl(0, 0, -1, T + 1, M2_HOLE / 2) - cyl(DX, -DY, -1, T + 1, POST_HOLE / 2)


def main():
    p = plate()
    os.makedirs(OUT, exist_ok=True)
    to_trimesh(p).export(os.path.join(OUT, "x2201_hole_plate.stl"))
    lo, hi = p.bounding_box()[:3], p.bounding_box()[3:]
    print(f"plate {hi[0]-lo[0]:.1f} x {hi[1]-lo[1]:.1f} x {T}; holes {DX:.2f} along, {DY:.2f} across "
          f"({(DX ** 2 + DY ** 2) ** 0.5:.2f} apart); M2 {M2_HOLE}, post {POST_HOLE}; genus {p.genus()}")


if __name__ == "__main__":
    main()
