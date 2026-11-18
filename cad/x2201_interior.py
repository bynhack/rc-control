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
from x2201_liner import (BACK_TUBES, BAR_HOLE, BAR_HOLE_D, CELL, FRONT_HOLES, HOLE_D, LINER_T, NPZ, ROOF_TOP, SLOTS_X,
                         SLOTS_Y, TUBE_OD, footprint, heightfield, normal_t, prism, smooth_top)

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


def sheet(x, y, ceil, foot, path):
    """The room from above, for laying parts out: its height (the liner's
    inside less CLEAR, up from the chassis) as contours, the key points with
    their coordinates, and the spacings to check on the real liner."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, FancyBboxPatch

    h = np.where(foot, ceil, np.nan)
    fig, ax = plt.subplots(figsize=(16, 11), dpi=110)
    cf = ax.contourf(x, y, h.T, levels=np.arange(0, 26, 2), cmap="viridis")
    cs = ax.contour(x, y, h.T, levels=np.arange(2, 26, 2), colors="k", linewidths=0.4, alpha=0.5)
    ax.clabel(cs, fmt="%d", fontsize=7)
    fig.colorbar(cf, ax=ax, shrink=0.8, label="room height over the chassis (mm)")
    ax.contour(x, y, foot.T.astype(float), levels=[0.5], colors="k", linewidths=1.2)

    red = "#d62728"
    for sy in (1, -1):
        ax.add_patch(FancyBboxPatch((SLOTS_X[0], min(sy * SLOTS_Y[0], sy * SLOTS_Y[1])), SLOTS_X[1] - SLOTS_X[0],
                                    SLOTS_Y[1] - SLOTS_Y[0], boxstyle="round,pad=0,rounding_size=2.5", fill=False,
                                    ec=red, lw=1.5))
        for (hx, hy), d, od in ((FRONT_HOLES, HOLE_D, None), (BACK_TUBES, HOLE_D, TUBE_OD)):
            ax.add_patch(Circle((hx, sy * hy), d / 2, fill=False, ec=red, lw=1.5))
            if od:
                ax.add_patch(Circle((hx, sy * hy), od / 2, fill=False, ec=red, lw=0.8, ls="--"))
            ax.annotate(f"({hx:.1f}, {sy * hy:+.1f})", (hx, sy * hy), (hx, sy * (hy + 6)), ha="center", fontsize=8,
                        color=red, arrowprops=dict(arrowstyle="-", color=red, lw=0.5))
    ax.add_patch(Circle(BAR_HOLE, BAR_HOLE_D / 2, fill=False, ec=red, lw=1.5))
    ax.annotate(f"bar hole ({BAR_HOLE[0]:.1f}, 0)", BAR_HOLE, (BAR_HOLE[0], 0.6), ha="center", fontsize=8, color=red)
    ax.text((SLOTS_X[0] + SLOTS_X[1]) / 2, SLOTS_Y[1] + 1, f"slots x {SLOTS_X[0]:.1f} .. {SLOTS_X[1]:.1f}, "
            f"|y| {SLOTS_Y[0]:.1f} .. {SLOTS_Y[1]:.1f}", ha="center", fontsize=8, color=red)
    ax.plot(ROOF_TOP[0], 0, "w^", ms=8)
    ax.annotate(f"roof top x {ROOF_TOP[0]:.1f}: room {ROOF_TOP[1] - LINER_T - CLEAR:.1f} high", (ROOF_TOP[0], 0),
                (ROOF_TOP[0], -3), ha="center", fontsize=8, color="w")
    ax.axhline(0, color="w", lw=0.5, ls=":")

    fx, fy = FRONT_HOLES
    bx, by = BACK_TUBES
    check = (f"CHECK on the real liner (calipers):  front holes {2 * fy:.1f} apart,  back tubes {2 * by:.1f} apart,  "
             f"front to back holes {fx - bx:.1f} along,  holes {HOLE_D} across,  wall {LINER_T} (LINER_T)")
    ax.set_title("X2201 room under the liner, from above (front to the right), cage coordinates, mm\n" + check, fontsize=10)
    ax.set_xticks(np.arange(np.ceil(x[0] / 10) * 10, x[-1] + 1, 10))
    ax.set_yticks(np.arange(-40, 41, 10))
    ax.grid(alpha=0.25)
    ax.set_aspect("equal")
    ax.set_xlim(x[0] - 2, x[-1] + 2)
    ax.set_ylim(-45, 45)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


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
    sheet(x, y, ceil, foot, os.path.join(OUT, "x2201_interior_sheet.png"))
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
