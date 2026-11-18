"""The X2201's black inner liner, modelled: the plastic part that sits under
the alloy shell, its top against the inside of the roof. Print it, put it
in the shell and see where it fits.

A designed part, not a copy of the scan: its top is a few smooth curves,
its outline straight lines and round corners. The numbers (heights, widths,
the openings, the screw points) were read off the 3D scan of the real liner
(Revopoint, its whole top).

The top, across the car at any x: the roof, a shallow arc (ROOFLINE at the
centre, CAMBER down to the sides); the side, a straight slope (SIDE_SLOPE)
up from the flange at BASE_W; the flange, flat at FLANGE_Z. Each is the
lower of the two where they meet, rounded (SHOULDER_R). Behind the roof the
rear window panel stands REAR_STEP proud of the quarters beside it.

The part is WALL under that top, square to it, cut to the outline, with:
  - the roof window: two slots, the bar between them with a screw hole;
  - the front ears, each with a screw hole (a tube under it);
  - the back screw tubes, down to the chassis.

Coordinates: x = forward (the windscreen and the deck at +x), y = across
(centred), z = up from the bottom of the back screw tubes.

Run:  python x2201_liner_model.py  -> out/x2201_liner_model.stl, out/x2201_liner_model_preview.png
Print it roof up, rim on the bed, tree supports under the roof.
"""

import os

import numpy as np
from manifold3d import CrossSection, FillRule, JoinType, Manifold, Mesh, OpType

from cad import OUT, cyl, preview, to_trimesh

WALL = 1.2  # MEASURE: the real liner's wall (the old notes say 1.0)
CLEAR = 0.3  # the top this far under the real liner's top (~0.1 under its scan's middle), so it slides in
GRID = 0.4  # the top surface's mesh

# ---- the top: (x, value) along the car, smooth between ---------------------------
# The roof's height on the centre line: the fastback from the back end, the
# roof (highest at x -5), the windscreen down to the deck in front of it.
ROOFLINE = [(-60, 6.5), (-57, 8.6), (-55, 11.0), (-50, 13.6), (-45, 16.0), (-40, 18.3), (-35, 20.3), (-30, 22.1),
            (-25, 23.3), (-15, 24.6), (-5, 25.5), (5, 25.3), (15, 24.1), (25, 22.3), (30, 19.8), (35, 17.2), (40, 14.4),
            (45, 11.3), (48, 9.4), (51, 8.2), (67, 8.2)]
# The roof's arc across: it drops CAMBER * y^2 from the centre line (flatter
# over the cab, rounder over the windscreen).
# The back end is a round nose, the windscreen rounder than the roof.
CAMBER = [(-60, 0.011), (-55, 0.0105), (-50, 0.0045), (-45, 0.0041), (-40, 0.0039), (-30, 0.0043), (-25, 0.0038),
          (-20, 0.0047), (-10, 0.0053), (-5, 0.0055), (5, 0.0048), (20, 0.0045), (25, 0.0076), (35, 0.0083), (40, 0.0086),
          (47, 0.0086), (52, 0.0), (67, 0.0)]
# The side: up from the flange at BASE_W (half width), SIDE_SLOPE up per across.
BASE_W = [(-60, 30.0), (-50, 31.5), (-45, 30.5), (-40, 30.3), (-35, 30.8), (-30, 31.3), (-25, 32.3), (-20, 34.2),
          (-15, 34.8), (-10, 34.9), (-5, 34.0), (0, 34.5), (5, 34.7), (20, 34.5), (25, 33.3), (30, 33.3), (35, 34.0),
          (67, 34.0)]
SIDE_SLOPE = [(-60, 0.6), (-50, 1.1), (-45, 1.6), (-40, 2.1), (-30, 2.1), (-25, 1.75), (-5, 1.75), (0, 1.6), (5, 1.6),
              (10, 1.75), (15, 1.75), (20, 1.6), (25, 1.75), (30, 2.1), (67, 2.1)]
SHOULDER_R = 5.0  # the roof into the side
# The flange the liner stands on: lower between x -20 and -10 (over the
# chassis there), highest under the deck.
FLANGE_Z = [(-60, 6.5), (-50, 6.6), (-45, 7.4), (-35, 7.8), (-25, 7.6), (-21, 5.2), (-11, 5.2), (-5, 7.2), (20, 7.4),
            (35, 7.6), (45, 7.9), (50, 8.2), (67, 8.2)]
FLANGE_R = 1.0
# The rear window panel: |y| < PANEL_Y, REAR_STEP over the quarters beside it.
PANEL_Y = 20.5
REAR_STEP = [(-60, 1.0), (-48, 2.4), (-27, 2.0), (-21, 0.0), (67, 0.0)]

# ---- the outline (y >= 0, mirrored), corners rounded OUTLINE_R ----------------------
OUTLINE = [
    (57.0, 0.0), (57.0, 13.0), (64.5, 14.0), (65.5, 22.5), (60.0, 27.0), (53.0, 27.0), (47.0, 30.5), (42.0, 34.5),
    (36.0, 36.0), (22.0, 36.0), (-22.0, 35.0), (-25.0, 39.0), (-47.0, 39.0), (-51.0, 32.0), (-57.0, 27.0),
    (-57.0, 0.0),
]
OUTLINE_R = 1.5

# ---- the roof window: two slots, the bar between them ----------------------------------
SLOT_X = (-19.5, 17.0)
SLOT_Y = (4.0, 19.0)  # |y|
SLOT_R = 2.5
BAR_HOLE = (-0.8, 0.0)  # the screw hole in the bar
BAR_HOLE_D = 2.2  # MEASURE

# ---- screw points (centres, both sides) ------------------------------------------------
BACK_TUBE = (-56.2, 22.1)
TUBE_OD, TUBE_Z0 = 7.0, 1.5  # MEASURE: the back tubes, down to the chassis
FRONT_HOLE = (53.2, 20.1)
FRONT_TUBE_Z0 = 4.4  # MEASURE: the tubes under the front ears
HOLE_D = 4.6  # MEASURE


def along(table, x):
    """A (x, value) table at x, smooth between (PCHIP: no overshoot)."""
    from scipy.interpolate import PchipInterpolator

    t = np.array(table, float)
    return PchipInterpolator(t[:, 0], t[:, 1], extrapolate=True)(x)


def smin(a, b, r):
    """The lower of a and b, the corner where they meet rounded over r."""
    h = np.clip(r - np.abs(a - b), 0, None) / r
    return np.minimum(a, b) - h * h * r / 4


def top_surface():
    """The top's height over a grid (x, y)."""
    # Off the round numbers: a grid line through a hole's or the outline's
    # vertex would leave the booleans touching edges.
    xs = np.arange(-62.0137, 67.0 + GRID, GRID)
    ys = np.arange(-44.0119, 44.0 + GRID, GRID)
    X, Y = np.meshgrid(xs, ys, indexing="ij")
    ay = np.abs(Y)
    col = lambda t: along(t, xs)[:, None]  # noqa: E731
    roof = col(ROOFLINE) - col(CAMBER) * ay ** 2
    # The quarters beside the rear window panel, REAR_STEP lower.
    beside = np.clip((ay - PANEL_Y) / 1.5 + 0.5, 0, 1)
    beside = beside * beside * (3 - 2 * beside)
    roof = roof - col(REAR_STEP) * beside
    side = col(FLANGE_Z) + col(SIDE_SLOPE) * (col(BASE_W) - ay)
    top = smin(roof, side, SHOULDER_R)
    top = -smin(-top, -col(FLANGE_Z) + 0 * ay, FLANGE_R)  # never under the flange
    return xs, ys, top - CLEAR


def heightfield(x, y, top, z0):
    """A solid from z0 up to top(x, y) over the grid."""
    nx, ny = top.shape
    X, Y = np.meshgrid(x, y, indexing="ij")
    verts = np.r_[np.c_[X.ravel(), Y.ravel(), top.ravel()], np.c_[X.ravel(), Y.ravel(), np.full(nx * ny, z0)]]
    i, j = np.meshgrid(np.arange(nx - 1), np.arange(ny - 1), indexing="ij")
    a = (i * ny + j).ravel()
    b, c, d = a + ny, a + ny + 1, a + 1
    off = nx * ny
    tris = [np.c_[a, b, c], np.c_[a, c, d], np.c_[a, c, b] + off, np.c_[a, d, c] + off]
    edge = np.r_[np.arange(nx) * ny, (nx - 1) * ny + np.arange(1, ny), np.arange(nx - 2, -1, -1) * ny + ny - 1,
                 np.arange(ny - 2, 0, -1)]
    e0, e1 = edge, np.roll(edge, -1)
    tris += [np.c_[e0, e1 + off, e1], np.c_[e0, e0 + off, e1 + off]]
    return Manifold(Mesh(vert_properties=verts.astype(np.float32), tri_verts=np.vstack(tris).astype(np.uint32)))


def shell():
    """WALL under the top, square to it."""
    x, y, top = top_surface()
    gx, gy = np.gradient(top, GRID)
    under = top - np.minimum(WALL * np.sqrt(1 + gx ** 2 + gy ** 2), 4 * WALL)
    z0 = top.min() - 10
    return heightfield(x, y, top, z0) - heightfield(x, y, under, z0 - 1)


def outline():
    pts = OUTLINE + [(x, -y) for x, y in OUTLINE[::-1] if y > 0]
    area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1]))
    cs = CrossSection([pts if area > 0 else pts[::-1]], FillRule.NonZero)
    r = OUTLINE_R
    return cs.offset(-r, JoinType.Round).offset(2 * r, JoinType.Round).offset(-r, JoinType.Round)


def prism(cs, z0=-20.0, z1=60.0):
    return Manifold.extrude(cs, z1 - z0).translate([0, 0, z0])


def window():
    def rrect(x0, y0, x1, y1, r):
        return CrossSection.square([x1 - x0 - 2 * r, y1 - y0 - 2 * r]).translate([x0 + r, y0 + r]).offset(r, JoinType.Round)

    a, b = SLOT_Y
    cs = rrect(SLOT_X[0], a, SLOT_X[1], b, SLOT_R) + rrect(SLOT_X[0], -b, SLOT_X[1], -a, SLOT_R)
    return prism(cs) + cyl(BAR_HOLE[0], BAR_HOLE[1], -20, 60, BAR_HOLE_D / 2)


def screw_points(part):
    """The back tubes and the front holes (with their tubes under the ears).
    Each tube runs up into the skin all round, however the top slopes over it."""
    x, y, top = top_surface()
    under_top = heightfield(x, y, top - 0.3, top.min() - 20)
    tubes, holes = [], []
    for (cx, cy), z0 in ((BACK_TUBE, TUBE_Z0), (FRONT_HOLE, FRONT_TUBE_Z0)):
        for s in (1, -1):
            tubes.append(cyl(cx, s * cy, z0, 60, TUBE_OD / 2))
            holes.append(cyl(cx, s * cy, z0 - 1, 60, HOLE_D / 2))
    tubes = Manifold.batch_boolean(tubes, OpType.Add) ^ under_top
    return (part + tubes) - Manifold.batch_boolean(holes, OpType.Add)


def build():
    return screw_points((shell() ^ prism(outline())) - window())


def main():
    liner = build()
    z0 = liner.bounding_box()[2]
    # The booleans leave slivers a float32 STL would fold into doubled edges.
    liner = liner.translate([0, 0, -z0]).simplify(0.002)
    os.makedirs(OUT, exist_ok=True)
    to_trimesh(liner).export(os.path.join(OUT, "x2201_liner_model.stl"))
    grey = (0.3, 0.32, 0.36)
    preview([("liner", [(liner, grey)], 30, -60), ("from the side (front to the right)", [(liner, grey)], 0, -90),
             ("from above", [(liner, grey)], 89, -90), ("from below", [(liner, grey)], -50, -60)],
            os.path.join(OUT, "x2201_liner_model_preview.png"))
    lo, hi = liner.bounding_box()[:3], liner.bounding_box()[3:]
    print(f"liner: {hi[0]-lo[0]:.1f} long x {hi[1]-lo[1]:.1f} wide x {hi[2]-lo[2]:.1f} high, "
          f"{liner.volume() / 1000:.1f} cm3, genus {liner.genus()} (the window's 2 slots, the bar's hole, 4 screw holes: 7)")


if __name__ == "__main__":
    main()
