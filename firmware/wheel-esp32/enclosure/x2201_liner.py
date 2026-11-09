"""The X2201's black inner liner (the "glass" under the shell's window
openings), from a 3D scan: its outer top surface as a height map, in the
test cage's coordinates (x2201_cage.py). The FPV mount has to fit under it.

The scan (Revopoint point cloud, the liner standing on the turntable) holds
the turntable too. build() fits that plane and cuts it away, lines the liner
up along x, and finds its front: the low end (the dash is lower than the
boot). It is registered to the cage where the centre line crosses the
windscreen's mid height. The scanner looked down from above, so the liner's
sides under the roof's edge are missing: the height map takes the highest
point per 1 mm cell, fills gaps from the nearest cell, and the room's width
still comes from the cage's section (the measured 68).

x2201_liner.npz (in this folder, small) is what the mount reads. It also
gives a printable replica of the liner, to set on the chassis and check
against the real one: x2201_liner_replica.stl, a REPLICA_T shell under the
scanned top, cut to where the scan saw the liner (its roof openings and the
screw hole stay open; the sides the scanner could not see are missing).
Print it as it sits, with tree supports under the roof.

Run:  python x2201_liner.py <scan.ply>  -> rebuilds x2201_liner.npz, then the replica
      python x2201_liner.py             -> the replica from x2201_liner.npz
        -> out/x2201_liner_replica.stl, out/x2201_liner_preview.png

Coordinates as in x2201_cage.py: x = forward from the cage's back end (the
windscreen's foot at x = L), y = across, z = up from the chassis' strips.
"""

import os
import sys

import numpy as np
from manifold3d import Manifold, Mesh, OpType

from cad import OUT, box, preview, to_trimesh
from x2201_cage import L, Z_COWL, Z_WS_TOP, WS_RUN, along_x, section

HERE = os.path.dirname(os.path.abspath(__file__))
NPZ = os.path.join(HERE, "x2201_liner.npz")
LINER_T = 1.0  # MEASURE: the liner's wall
CELL = 1.0
REPLICA_T = 1.2  # the replica's wall, square to its surface


def build(ply):
    import trimesh
    from scipy import ndimage

    p = np.asarray(trimesh.load(ply).vertices, dtype=float)
    # The turntable: RANSAC on a tenth of the points, then a least-squares fit.
    rng = np.random.default_rng(0)
    sub = p[::10]
    best = (0, None, None)
    for _ in range(300):
        a, b, c = sub[rng.integers(0, len(sub), 3)]
        n = np.cross(b - a, c - a)
        if np.linalg.norm(n) < 1e-6:
            continue
        n /= np.linalg.norm(n)
        k = int((np.abs((sub - a) @ n) < 0.4).sum())
        if k > best[0]:
            best = (k, n, a)
    _, n, a = best
    q = p[np.abs((p - a) @ n) < 0.6]
    c0 = q.mean(0)
    n = np.linalg.svd(q[::5] - c0, full_matrices=False)[2][2]
    h = (p - c0) @ n
    if np.median(h[np.abs(h) > 0.6]) < 0:
        n, h = -n, -h
    e1 = np.cross(n, [0, 0, 1.0])
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(n, e1)
    pts = np.c_[(p - c0) @ e1, (p - c0) @ e2, h]
    pts = pts[pts[:, 2] > 2.5]  # off the turntable
    m = np.median(pts[:, :2], 0)
    pts = pts[np.linalg.norm(pts[:, :2] - m, axis=1) < 75]  # the liner, not the turntable's markers
    # Long axis along x, centred.
    c = pts[:, :2].mean(0)
    v = np.linalg.eigh(np.cov((pts[:, :2] - c).T))[1][:, 1]
    xy = (pts[:, :2] - c) @ np.array([v, [-v[1], v[0]]]).T
    xy[:, 1] -= (np.percentile(xy[:, 1], 0.5) + np.percentile(xy[:, 1], 99.5)) / 2
    z = pts[:, 2]

    def centre_top(x):
        s = (np.abs(xy[:, 0] - x) < 1) & (np.abs(xy[:, 1]) < 4)
        return np.percentile(z[s], 98) if s.sum() > 10 else np.nan

    lo, hi = xy[:, 0].min(), xy[:, 0].max()
    if np.nanmean([centre_top(x) for x in np.arange(hi - 15, hi)]) < np.nanmean([centre_top(x) for x in np.arange(lo, lo + 15)]):
        xy[:, 0] = -xy[:, 0]  # the front (the low end) to -x
    # Register: the windscreen's mid height, cage x where the cage's windscreen has it.
    z_mid = (Z_COWL + Z_WS_TOP) / 2
    xs = np.arange(xy[:, 0].min(), xy[:, 0].max(), 0.5)
    tops = np.array([centre_top(x) for x in xs])
    cross = xs[np.nanargmax(np.where(np.isnan(tops), -1, tops) >= z_mid)]
    cage_x = L - WS_RUN * (z_mid - Z_COWL) / (Z_WS_TOP - Z_COWL)
    X = cage_x + (cross - xy[:, 0])  # the scan's front is -x, the cage's +x
    Y = xy[:, 1]
    # Height map: the top surface, per cell.
    gx = np.arange(np.floor(X.min()), np.ceil(X.max()) + CELL, CELL)
    gy = np.arange(-45.0, 45.0 + CELL, CELL)
    ix = np.clip(((X - gx[0]) / CELL).astype(int), 0, len(gx) - 1)
    iy = np.clip(((Y - gy[0]) / CELL).astype(int), 0, len(gy) - 1)
    H = np.full((len(gx), len(gy)), np.nan)
    order = np.lexsort((z, iy, ix))
    keys = ix[order] * len(gy) + iy[order]
    last = np.r_[keys[1:] != keys[:-1], True]
    H.flat[keys[last]] = z[order][last]  # the highest point per cell
    seen = ~np.isnan(H)  # where the liner is (its openings stay out)
    H = ndimage.median_filter(np.nan_to_num(H, nan=-1), size=3)
    H[H < 0] = np.nan
    idx = ndimage.distance_transform_edt(np.isnan(H), return_distances=False, return_indices=True)
    H = H[tuple(idx)]  # gaps (the roof's openings, the hidden sides) from the nearest cell
    np.savez_compressed(NPZ, x=gx + CELL / 2, y=gy + CELL / 2, top=H.astype(np.float32), seen=seen)
    print(f"liner: x {gx[0]:.0f} .. {gx[-1]:.0f} (cage's back end 0, windscreen foot {L:.0f}), top {np.nanmax(H):.1f}")
    for x in range(int(gx[0]) // 5 * 5, int(gx[-1]), 5):
        i = int(np.clip((x - gx[0]) / CELL, 0, len(gx) - 1))
        print(f"  x {x:4d}: centre top {H[i, len(gy) // 2]:.1f}")


def heightfield(x, y, top):
    """A solid from z = -5 up to top(x, y) over the grid."""
    nx, ny = top.shape
    X, Y = np.meshgrid(x, y, indexing="ij")
    up = np.c_[X.ravel(), Y.ravel(), top.ravel()]
    down = np.c_[X.ravel(), Y.ravel(), np.full(nx * ny, -5.0)]
    verts = np.r_[up, down].astype(np.float32)
    k = lambda i, j: i * ny + j  # noqa: E731
    off = nx * ny
    tris = []
    for i in range(nx - 1):
        for j in range(ny - 1):
            a, b, c, d = k(i, j), k(i + 1, j), k(i + 1, j + 1), k(i, j + 1)
            tris += [(a, b, c), (a, c, d), (a + off, c + off, b + off), (a + off, d + off, c + off)]
    edge = [k(i, 0) for i in range(nx)] + [k(nx - 1, j) for j in range(1, ny)] + \
        [k(i, ny - 1) for i in range(nx - 2, -1, -1)] + [k(0, j) for j in range(ny - 2, 0, -1)]
    for a, b in zip(edge, edge[1:] + edge[:1]):
        tris += [(a, b + off, b), (a, a + off, b + off)]
    return Manifold(Mesh(vert_properties=verts, tri_verts=np.array(tris, dtype=np.uint32)))


def liner_room():
    """The room under the liner: under its top less its wall, as wide as the cage's section."""
    d = np.load(NPZ)
    under = heightfield(d["x"], d["y"], d["top"] - LINER_T)
    return under ^ along_x(section(), float(d["x"][0]), float(d["x"][-1]))


def liner_shell():
    """The liner itself, for the preview: LINER_T under its top."""
    d = np.load(NPZ)
    return heightfield(d["x"], d["y"], d["top"]) - heightfield(d["x"], d["y"], d["top"] - LINER_T)


def replica():
    """The liner as the scan saw it: a REPLICA_T shell under the (smoothed)
    top, only over the cells the scan saw, small gaps closed."""
    from scipy import ndimage

    d = np.load(NPZ)
    x, y = d["x"], d["y"]
    top = ndimage.gaussian_filter(d["top"].astype(float), 0.8)
    seen = ndimage.binary_closing(d["seen"], iterations=2)
    holes = ndimage.binary_fill_holes(seen) & ~seen
    lab, n = ndimage.label(holes)
    for k in range(1, n + 1):  # specks in the scan: filled; the openings (and the screw hole) stay
        if (lab == k).sum() < 8:
            seen[lab == k] = True
    seen = ndimage.binary_opening(seen, iterations=1)  # ragged edges
    gx, gy = np.gradient(top, CELL)
    under = top - np.minimum(REPLICA_T * np.sqrt(1 + gx ** 2 + gy ** 2), 3 * REPLICA_T)
    skin = heightfield(x, y, top) - heightfield(x, y, under)
    cols = []  # the seen cells, as runs of boxes along y
    for i in range(len(x)):
        j = 0
        while j < len(y):
            if seen[i, j]:
                j0 = j
                while j < len(y) and seen[i, j]:
                    j += 1
                cols.append(box(x[i] - CELL / 2, y[j0] - CELL / 2, -10, x[i] + CELL / 2, y[j - 1] + CELL / 2, 40))
            j += 1
    out = skin ^ Manifold.batch_boolean(cols, OpType.Add)
    parts = sorted(out.decompose(), key=lambda m: -m.volume())
    return parts[0]  # crumbs off the edges dropped


if __name__ == "__main__":
    if len(sys.argv) == 2:
        build(sys.argv[1])
    elif len(sys.argv) != 1:
        sys.exit("usage: python x2201_liner.py [scan.ply]")
    os.makedirs(OUT, exist_ok=True)
    r = replica()
    to_trimesh(r).export(os.path.join(OUT, "x2201_liner_replica.stl"))
    grey = (0.3, 0.32, 0.36)
    preview([("replica", [(r, grey)], 30, -60), ("from the side (front to the right)", [(r, grey)], 0, -90),
             ("from above", [(r, grey)], 89, -90), ("from below", [(r, grey)], -50, -60)],
            os.path.join(OUT, "x2201_liner_preview.png"))
    lo, hi = r.bounding_box()[:3], r.bounding_box()[3:]
    print(f"replica: {hi[0]-lo[0]:.1f} long x {hi[1]-lo[1]:.1f} wide x {hi[2]-lo[2]:.1f} high "
          f"(z {lo[2]:.1f} .. {hi[2]:.1f}), {r.volume() / 1000:.1f} cm3")
