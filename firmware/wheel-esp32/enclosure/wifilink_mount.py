"""Mount for a RunCam WiFiLink 2 on the car's 8 mm round top brace.

Two parts:
  wifilink_plate.stl  flat plate the WiFiLink sits on: four M2 holes on its
                      25.5 x 25.5 pattern (screws from below into the
                      WiFiLink's bottom; checked on a print), or stick it down
                      with 3M tape. Under the plate, flush with its left
                      edge, the upper half of a clamp round the rod. Prints
                      top face down.
  wifilink_clamp.stl  lower half of the clamp, hex pockets for the nuts in
                      its underside. Two M2.5 screws from the plate's top
                      (heads sunk flush, so tighten them before the WiFiLink
                      goes on) pull the halves together round the rod; the
                      1 mm gap between them is the clamping travel. Prints
                      flat side down.

Hardware:
  4x M2 x 5            plate -> WiFiLink (plate 3 + 2 into the WiFiLink)
  2x M2.5 x 12 pan head + hex nut   plate -> clamp, round the rod

Coordinates: x = right and y along the rod, looking down at the plate's top;
z = up, the plate's top face at z = PLATE, the plate centred on x = y = 0.

Run:  python wifilink_mount.py  -> out/wifilink_plate.stl, out/wifilink_clamp.stl,
      out/wifilink_preview.png
"""

import os
import sys

from manifold3d import Manifold

from cad import OUT, box, cyl, preview, rbox, to_trimesh

# ---- parts -------------------------------------------------------------------------
WL_W, WL_D, WL_H = 34.0, 36.0, 14.0  # MEASURE: WiFiLink 2 body (only for the checks and the plate size)
WL_HOLES = 25.5  # M2, square pattern
ROD_D = 8.0  # the brace
ROD_FIT = 0.1  # groove radius over the rod's: the clamp squeezes it

# ---- mount ---------------------------------------------------------------------------
PLATE = 3.0
PLATE_W = PLATE_D = 32.0  # just round the M2 holes
WL_HOLE = 2.3  # M2 clearance
M2_HEAD = 3.8
ABOVE_ROD = 1.2  # plate material between the groove and the plate's underside
CLAMP_GAP = 1.0  # between the two halves when they're loose on the rod
CLAMP_L = 16.0  # along the rod
CLAMP_HALF_W = 10.5  # across the rod
SCREW_X = 6.4  # M2.5 clamp screws, each side of the rod
CLEAR_R = 1.45  # M2.5
HEAD_R, HEAD_SINK = 2.6, 2.0  # M2.5 pan head 4.5 x 1.75, sunk flush in the plate's top
NUT_AF, NUT_T = 5.0, 2.0  # M2.5 hex nut
CAP_UNDER = 2.0  # clamp material under the rod: the car's clearance under the brace must take this
rod_x = -PLATE_W / 2 + CLAMP_HALF_W  # the clamp block flush with the plate's left edge

rod_r = ROD_D / 2 + ROD_FIT
rod_z = -(rod_r + ABOVE_ROD)  # rod centre
split_z = rod_z  # the halves meet at the rod's centre line, minus the gap
cap_bottom = rod_z - rod_r - CAP_UNDER


def rod():
    return Manifold.cylinder(80, ROD_D / 2).rotate([-90, 0, 0]).translate([rod_x, -40, rod_z])


def groove():
    return Manifold.cylinder(CLAMP_L + 2, rod_r).rotate([-90, 0, 0]).translate([rod_x, -CLAMP_L / 2 - 1, rod_z])


def plate():
    out = rbox(-PLATE_W / 2, -PLATE_D / 2, 0, PLATE_W, PLATE_D, PLATE, 3.0)
    out += box(rod_x - CLAMP_HALF_W, -CLAMP_L / 2, split_z + CLAMP_GAP / 2, rod_x + CLAMP_HALF_W, CLAMP_L / 2, 0.1)
    out -= groove()
    for sx in (-1, 1):
        for sy in (-1, 1):
            out -= cyl(sx * WL_HOLES / 2, sy * WL_HOLES / 2, -1, PLATE + 1, WL_HOLE / 2)
    for sx in (-1, 1):
        x = rod_x + sx * SCREW_X
        out -= cyl(x, 0, split_z - 1, PLATE + 1, CLEAR_R)
        out -= cyl(x, 0, PLATE - HEAD_SINK, PLATE + 1, HEAD_R)
    return out


def clamp():
    out = box(rod_x - CLAMP_HALF_W, -CLAMP_L / 2, cap_bottom, rod_x + CLAMP_HALF_W, CLAMP_L / 2, split_z - CLAMP_GAP / 2)
    out -= groove()
    nut_r = (NUT_AF + 0.3) / 3 ** 0.5
    for sx in (-1, 1):
        x = rod_x + sx * SCREW_X
        out -= cyl(x, 0, cap_bottom - 1, split_z + 1, CLEAR_R)
        out -= Manifold.cylinder(NUT_T + 1.3, nut_r, circular_segments=6).translate([x, 0, cap_bottom - 1])
    return out


# ---- stand-ins -----------------------------------------------------------------------
def wifilink():
    return box(-WL_W / 2, -WL_D / 2, PLATE, WL_W / 2, WL_D / 2, PLATE + WL_H)


def m2_heads():
    """Room the M2 screw heads need under the plate."""
    out = Manifold()
    for sx in (-1, 1):
        for sy in (-1, 1):
            out += cyl(sx * WL_HOLES / 2, sy * WL_HOLES / 2, -2.5, 0, M2_HEAD / 2 + 0.3)
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    p, c = plate(), clamp()
    for name, m in [("plate", p), ("clamp", c)]:
        if m.is_empty() or len(m.decompose()) != 1:
            sys.exit(f"{name}: not a single solid")
    checks = {"plate x rod": (p ^ rod()).volume(), "clamp x rod": (c ^ rod()).volume(), "plate x clamp": (p ^ c).volume(),
              "plate x wifilink": (p ^ wifilink()).volume(), "plate x M2 heads": (p ^ m2_heads()).volume(),
              "clamp x M2 heads": (c ^ m2_heads()).volume()}
    for k, v in checks.items():
        print(f"{k}: {v:.3f} mm3")
    if max(checks.values()) > 0.01:
        sys.exit("parts overlap")

    to_trimesh(p.mirror([0, 0, 1])).export(os.path.join(OUT, "wifilink_plate.stl"))  # top face down
    to_trimesh(c).export(os.path.join(OUT, "wifilink_clamp.stl"))
    case, part, dark = (0.62, 0.68, 0.76), (0.40, 0.46, 0.55), (0.15, 0.17, 0.2)
    preview(
        [
            ("on the rod", [(p, case), (c, case), (rod(), (0.7, 0.15, 0.15)), (wifilink(), dark)], 20, -55),
            ("from below", [(p, case), (c, case), (rod(), (0.7, 0.15, 0.15))], -35, -55),
            ("plate", [(p, case)], -40, 30),
            ("clamp", [(c, case)], 35, 30),
        ],
        os.path.join(OUT, "wifilink_preview.png"),
    )
    lo, hi = p.bounding_box()[:3], p.bounding_box()[3:]
    print(f"plate: {hi[0]-lo[0]:.1f} x {hi[1]-lo[1]:.1f} x {hi[2]-lo[2]:.1f} mm")
    head_bottom = PLATE - HEAD_SINK
    print(f"M2.5 x 12 tip: {(head_bottom - 12) - cap_bottom:.1f} mm above the clamp's underside, loose (nut pocket {NUT_T + 0.3:.1f} deep)")
    print(f"rod top to WiFiLink bottom: {PLATE - (rod_z + ROD_D / 2):.1f} mm, clamp under the rod: {rod_z - ROD_D / 2 - cap_bottom:.1f} mm")


if __name__ == "__main__":
    main()
