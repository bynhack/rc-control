"""3D-printable case for the current wheel controller.

Holds the ESP32-S3-N16R8 devboard, the 1.28" GC9A01 round screen, a USB-A
female breakout for the wheel, and the BETAFPV ELRS 2.4GHz 1W Micro module in
a bay on the back (antenna up, like a radio's module bay).

Two parts, both print without supports:
  body.stl   top face on the bed (exported already flipped)
  plate.stl  flat; the bottom plate, bay lip and board cradles

Assembly coordinates: x = width (left -> right), y = depth (front -> back),
z = up. The plate is z 0..PLATE, the body sits on it.

Run:  python enclosure.py            -> out/body.stl, out/plate.stl, out/preview.png
Needs: pip install manifold3d numpy trimesh matplotlib

Every dimension marked MEASURE was estimated; check it with calipers before
printing and re-run.
"""

import os
import sys

import numpy as np
from manifold3d import CrossSection, JoinType, Manifold, set_circular_segments

set_circular_segments(64)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")

# ---- printer / fit ---------------------------------------------------------
FIT = 0.4  # clearance around parts that slide in

# ---- shell -----------------------------------------------------------------
W, D, H = 75.0, 78.0, 38.0  # body outside, H measured from the plate top
WALL, TOP = 2.4, 2.4
PLATE = 3.0
R = 4.0  # vertical corner radius

# ---- ESP32-S3-N16R8 devboard (given: 27.8 x 59.6) ----------------------------
BOARD_L, BOARD_W, BOARD_T = 59.6, 27.8, 1.6
BOARD_LIFT = 12.0  # board underside above the plate: room for header pins + Dupont
USB_STACK = 3.2  # USB-C receptacle height above the PCB

# ---- GC9A01 round screen ----------------------------------------------------
GLASS_W, GLASS_H = 35.6, 38.1  # given panel outline (H along y)
VIEW_D = 32.4  # given display area
SCREEN_C = (W / 2, 24.0)  # centre on the top face

# ---- USB-A female breakout for the wheel (MEASURE your breakout) ----------
USBA_HOLE = (13.6, 6.2)  # receptacle opening, width x height
USBA_C = (20.0, PLATE + 9.0)  # y, z of the opening centre on the right wall

# ---- BETAFPV ELRS 2.4GHz 1W Micro module (given: 45 body, 53 rails, 60/64 tall)
MOD_W_RAILS = 53.0
MOD_T = 24.0  # MEASURE: module thickness, back face (pins) to front face
BAY_WALL = 3.0
BAY_LIP_H = 14.0  # front lip height; the face (screen, fan, joystick) stays clear
PIN_SLOT = (42.0, 24.0)  # opening in the rear wall for the module's pin wires

# ---- screws (M3 self-tapping, plate -> body) --------------------------------
BOSS_R, PILOT_R, CLEAR_R, HEAD_R = 3.5, 1.3, 1.7, 3.0


def box(x0, y0, z0, x1, y1, z1):
    return Manifold.cube([x1 - x0, y1 - y0, z1 - z0]).translate([x0, y0, z0])


def cyl(x, y, z0, z1, r, r_top=None):
    return Manifold.cylinder(z1 - z0, r, r if r_top is None else r_top).translate([x, y, z0])


def rrect(w, d, r):
    """Rounded rectangle cross-section, origin at its lower-left corner."""
    return CrossSection.square([w - 2 * r, d - 2 * r]).offset(r, JoinType.Round).translate([r, r])


def rbox(x0, y0, z0, w, d, h, r):
    return Manifold.extrude(rrect(w, d, r), h).translate([x0, y0, z0])


# ---- derived positions -------------------------------------------------------
Z0 = PLATE  # body bottom
ZT = PLATE + H  # body top
board_x0 = WALL + FIT  # USB edge against the left wall
board_y1 = D - WALL - 2.6  # leaves room for the cradle wall and the plate rim
board_y0 = board_y1 - BOARD_W
board_z0 = Z0 + BOARD_LIFT
board_cy = (board_y0 + board_y1) / 2

bay_in_half = MOD_W_RAILS / 2 + FIT
bay_y_lip = D + MOD_T + 2 * FIT  # inner face of the lip
bay_y1 = bay_y_lip + BAY_WALL

bosses = [  # body screw columns, clear of the board, screen tab and USB-A
    (WALL + BOSS_R, WALL + BOSS_R),
    (W - WALL - BOSS_R, WALL + BOSS_R),
    (W - WALL - BOSS_R, D - WALL - BOSS_R),
    (WALL + BOSS_R, 40.0),
]
# Outside the bay walls, so they stay clear of the module's rails.
bay_bosses = [(W / 2 + s * (bay_in_half + BAY_WALL + BOSS_R - 1.5), bay_y1 - BOSS_R) for s in (-1, 1)]


def body():
    shell = rbox(0, 0, Z0, W, D, H, R) - rbox(WALL, WALL, Z0 - 1, W - 2 * WALL, D - 2 * WALL, H - TOP + 1, R - WALL)

    for x, y in bosses:
        shell += cyl(x, y, Z0, ZT, BOSS_R) - cyl(x, y, Z0 - 1, Z0 + 12, PILOT_R)

    # Bay side walls, full height, out from the rear wall.
    for s in (-1, 1):
        xi = W / 2 + s * bay_in_half
        x0, x1 = (xi - BAY_WALL, xi) if s < 0 else (xi, xi + BAY_WALL)
        shell += box(x0, D - WALL, Z0, x1, bay_y1, ZT)
    for x, y in bay_bosses:
        shell += cyl(x, y, Z0, ZT, BOSS_R) - cyl(x, y, Z0 - 1, Z0 + 12, PILOT_R)

    cut = Manifold()
    # Screen: viewing window with an outward chamfer, glass pocket behind it.
    sx, sy = SCREEN_C
    cut += cyl(sx, sy, ZT - TOP - 1, ZT + 1, VIEW_D / 2 + 0.2)
    cut += cyl(sx, sy, ZT - 0.8, ZT + 0.01, VIEW_D / 2 + 0.2, VIEW_D / 2 + 1.0)
    gw, gh = GLASS_W + 2 * 0.3, GLASS_H + 2 * 0.3
    cut += rbox(sx - gw / 2, sy - gh / 2, ZT - TOP - 1, gw, gh, 1 + TOP / 2, 10.0)

    # USB-C ports (CH340C and OTG) through the left wall.
    uz = board_z0 + BOARD_T + USB_STACK / 2
    cut += box(-1, board_cy - (BOARD_W - 1) / 2, uz - 4.25, WALL + 1, board_cy + (BOARD_W - 1) / 2, uz + 4.25)

    # USB-A for the wheel through the right wall.
    uw, uh = USBA_HOLE
    cut += box(W - WALL - 1, USBA_C[0] - uw / 2, USBA_C[1] - uh / 2, W + 1, USBA_C[0] + uw / 2, USBA_C[1] + uh / 2)

    # Rear wall notch for the module's pin wires, open at the bottom.
    pw, ph = PIN_SLOT
    cut += box(W / 2 - pw / 2, D - WALL - 1, Z0 - 1, W / 2 + pw / 2, D + 1, Z0 + ph)

    return shell - cut


def plate():
    out = rbox(0, 0, 0, W, bay_y1, PLATE, R)

    # Locating rim just inside the body walls, broken around the bosses and the pin notch.
    rim = rbox(WALL + 0.3, WALL + 0.3, PLATE, W - 2 * (WALL + 0.3), D - 2 * (WALL + 0.3), 2.0, max(R - WALL - 0.3, 0.5))
    rim -= rbox(WALL + 1.5, WALL + 1.5, PLATE - 1, W - 2 * (WALL + 1.5), D - 2 * (WALL + 1.5), 4.0, 0.5)
    for x, y in bosses:
        rim -= cyl(x, y, 0, 10, BOSS_R + 0.6)
    rim -= box(W / 2 - PIN_SLOT[0] / 2, D - 10, 0, W / 2 + PIN_SLOT[0] / 2, D + 1, 10)
    out += rim

    # Bay lip between the bay side walls.
    out += box(W / 2 - bay_in_half + FIT, bay_y_lip, PLATE, W / 2 + bay_in_half - FIT, bay_y1, PLATE + BAY_LIP_H)

    # Board cradles: corner posts with a ledge, locating walls on the long edges.
    bx0, bx1 = board_x0, board_x0 + BOARD_L
    ledge_top = board_z0
    for cx in (bx0, bx1):
        for cy in (board_y0, board_y1):
            inward_x = 1 if cx == bx0 else -1
            inward_y = 1 if cy == board_y0 else -1
            # Ledge: 3 x 3 under the corner.
            lx0, lx1 = sorted((cx, cx + inward_x * 3.0))
            ly0, ly1 = sorted((cy, cy + inward_y * 3.0))
            out += box(lx0, ly0, PLATE, lx1, ly1, ledge_top)
            # Wall along the long edge, outside the board, rising past it.
            wy0, wy1 = sorted((cy - inward_y * FIT, cy - inward_y * (FIT + 1.6)))
            out += box(lx0, wy0, PLATE, lx1, wy1, ledge_top + BOARD_T + 2.0)
            if cx == bx1:  # end stop on the far short edge (the USB end stays open)
                out += box(cx + FIT, ly0, PLATE, cx + FIT + 1.6, ly1, ledge_top + BOARD_T + 2.0)

    holes = Manifold()
    for x, y in bosses + bay_bosses:
        holes += cyl(x, y, -1, PLATE + 1, CLEAR_R)
        holes += cyl(x, y, -1, 1.6, HEAD_R + 0.1, CLEAR_R)  # countersink-ish head recess
    for x, y in [(8, 8), (W - 8, 8), (8, bay_y1 - 8), (W - 8, bay_y1 - 8)]:
        holes += cyl(x, y, -1, 0.8, 5.0)  # rubber feet
    return out - holes


def ghosts():
    """Rough stand-ins for the parts, for the preview only."""
    g = []
    g.append(box(board_x0, board_y0, board_z0, board_x0 + BOARD_L, board_y1, board_z0 + BOARD_T))
    g.append(box(board_x0 + 30, board_y0 + 4, board_z0 + BOARD_T, board_x0 + 48, board_y1 - 4, board_z0 + BOARD_T + 3.2))
    sx, sy = SCREEN_C
    g.append(cyl(sx, sy, ZT - TOP / 2 - 3.2, ZT - TOP / 2, GLASS_W / 2))
    mz0 = PLATE
    g.append(box(W / 2 - 22.5, D + FIT, mz0, W / 2 + 22.5, D + FIT + MOD_T, mz0 + 60))
    g.append(cyl(W / 2, D + FIT + MOD_T / 2, mz0 + 60, mz0 + 75, 3.2))
    return g


def to_trimesh(m):
    import trimesh

    mesh = m.to_mesh()
    return trimesh.Trimesh(vertices=np.asarray(mesh.vert_properties)[:, :3], faces=np.asarray(mesh.tri_verts), process=True)


def render(parts, elev, azim, size=(760, 560)):
    """Orthographic z-buffer render with flat shading; returns an RGB array."""
    e, a = np.radians(elev), np.radians(azim)
    view = np.array([np.cos(e) * np.cos(a), np.cos(e) * np.sin(a), np.sin(e)])  # towards the eye
    right = np.cross([0, 0, 1], view)
    right /= np.linalg.norm(right)
    up = np.cross(view, right)
    light = view + 0.6 * up - 0.3 * right
    light /= np.linalg.norm(light)

    meshes = [(to_trimesh(m), np.array(rgb)) for m, rgb in parts]
    pts = np.vstack([tm.vertices for tm, _ in meshes])
    u, v = pts @ right, pts @ up
    scale = 0.9 * min(size[0] / np.ptp(u), size[1] / np.ptp(v))
    cu, cv = (u.max() + u.min()) / 2, (v.max() + v.min()) / 2

    w, h = size
    zbuf = np.full((h, w), -np.inf)
    img = np.ones((h, w, 3))
    for tm, rgb in meshes:
        tri = tm.vertices[tm.faces]
        sx = (tri @ right - cu) * scale + w / 2
        sy = h / 2 - (tri @ up - cv) * scale
        sz = tri @ view
        n = tm.face_normals
        shade = 0.35 + 0.65 * np.abs(n @ light)
        for i in range(len(tri)):
            x, y, z = sx[i], sy[i], sz[i]
            x0, x1 = int(max(np.floor(x.min()), 0)), int(min(np.ceil(x.max()), w - 1))
            y0, y1 = int(max(np.floor(y.min()), 0)), int(min(np.ceil(y.max()), h - 1))
            if x0 > x1 or y0 > y1:
                continue
            gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
            d = (y[1] - y[2]) * (x[0] - x[2]) + (x[2] - x[1]) * (y[0] - y[2])
            if abs(d) < 1e-9:
                continue
            l0 = ((y[1] - y[2]) * (gx - x[2]) + (x[2] - x[1]) * (gy - y[2])) / d
            l1 = ((y[2] - y[0]) * (gx - x[2]) + (x[0] - x[2]) * (gy - y[2])) / d
            l2 = 1 - l0 - l1
            inside = (l0 >= -1e-6) & (l1 >= -1e-6) & (l2 >= -1e-6)
            depth = l0 * z[0] + l1 * z[1] + l2 * z[2]
            sub = zbuf[y0 : y1 + 1, x0 : x1 + 1]
            hit = inside & (depth > sub)
            sub[hit] = depth[hit]
            img[y0 : y1 + 1, x0 : x1 + 1][hit] = np.clip(rgb * shade[i], 0, 1)
    return img


def preview(scenes, path):
    """scenes: [(title, [(manifold, rgb)], elev, azim)] -> one PNG grid."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    cols = 2
    rows = (len(scenes) + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(15, 5.6 * rows), dpi=100)
    for ax, (title, parts, elev, azim) in zip(axes.flat, scenes):
        ax.imshow(render(parts, elev, azim))
        ax.set_title(title, fontsize=14)
        ax.set_axis_off()
    for ax in list(axes.flat)[len(scenes) :]:
        ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(path)


def main():
    os.makedirs(OUT, exist_ok=True)
    b, p = body(), plate()
    for name, m in [("body", b), ("plate", p)]:
        if m.is_empty():
            sys.exit(f"{name}: empty result")
    # Body prints top-down: flip so the top face lands on z = 0.
    printable_body = b.mirror([0, 0, 1]).translate([0, 0, ZT])
    to_trimesh(printable_body).export(os.path.join(OUT, "body.stl"))
    to_trimesh(p).export(os.path.join(OUT, "plate.stl"))
    case, part, ghost = (0.62, 0.68, 0.76), (0.40, 0.46, 0.55), (0.96, 0.62, 0.04)
    g = [(m, ghost) for m in ghosts()]
    preview(
        [
            ("assembled, front", [(p, part), (b, case)] + g, 25, -60),
            ("assembled, back (module bay)", [(p, part), (b, case)] + g, 22, 125),
            ("body, from below (inside)", [(b, case)], -55, -60),
            ("plate with board cradles", [(p, part)] + g[:2], 40, -50),
        ],
        os.path.join(OUT, "preview.png"),
    )
    for name, m in [("body", printable_body), ("plate", p)]:
        lo, hi = m.bounding_box()[:3], m.bounding_box()[3:]
        print(f"{name}: {hi[0]-lo[0]:.1f} x {hi[1]-lo[1]:.1f} x {hi[2]-lo[2]:.1f} mm, volume {m.volume()/1000:.1f} cm3")


if __name__ == "__main__":
    main()
