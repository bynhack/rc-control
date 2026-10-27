"""3D-printable case for the current wheel controller, v2.

Holds:
  - ESP32-S3-N16R8 devboard, USB-C to the front for flashing
  - 1.28" GC9A01 round screen in the top, stuck on with 3M foam tape
  - BETAFPV ELRS 2.4GHz 1W Micro module in a radio-style bay at the back:
    45 x 60 opening plus channels for the side latches; it slides in back
    first, antenna up, with the fan / OLED / XT30 / USB-C face left exposed
  - MB102 breadboard power module on a pedestal (3M tape), DC jack and
    mini-USB through the right wall
  - USB-A female breakout for the wheel on the left wall

Two parts, both print without supports:
  body.stl   top face on the bed (exported already turned over)
  plate.stl  flat; bottom plate with the board cradle and power pedestal

Assembly coordinates: x = width (left -> right), y = depth (front -> back),
z = up. The plate is z 0..PLATE, the body sits on it.

Run:  python enclosure.py            -> out/body.stl, out/plate.stl, out/preview.png
Needs: pip install manifold3d numpy trimesh matplotlib

Dimensions marked MEASURE were taken from product photos; check them with
calipers and re-run.
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
W, D, H = 88.0, 98.0, 64.0  # body outside, H measured from the plate top
WALL, TOP = 2.4, 2.4
PLATE = 3.0
R = 4.0  # vertical corner radius

# ---- ESP32-S3-N16R8 devboard (given: 27.8 x 59.6), long axis front-to-back --
BOARD_L, BOARD_W, BOARD_T = 59.6, 27.8, 1.6
BOARD_LIFT = 12.0  # board underside above the plate: header pins + Dupont
USB_STACK = 3.2  # USB-C receptacle height above the PCB
HEADER_KEEPOUT = 3.5  # header row width from each long edge, spacer included
BOARD_X0 = 11.0  # clear of the front-left screw column

# ---- GC9A01 round screen, 3M foam tape -------------------------------------
# Panel: 35.6 circle; the FPC folds over on the header side, making it 38.1
# that way. Display area 32.4, centred on the circle. The module's round PCB
# is larger than the glass, so the PCB rim and header tab are taped to the
# inside of the top and the glass sits in a shallow recess.
GLASS_D, GLASS_SPAN, GLASS_T = 35.6, 38.1, 1.5  # given panel outline
VIEW_D = 32.4  # given display area
TAPE_T = 1.0  # MEASURE: 3M foam tape thickness
SCREEN_C = (W / 2, 30.0)  # display centre on the top face; header tab towards -x

# ---- BETAFPV 1W Micro module (given: 45 x 60 body, 53 over the latches, 20 thick)
MOD_W, MOD_H, MOD_T = 45.0, 60.0, 20.0
MOD_W_LATCH = 53.0
LATCH_Z = (23.0, 37.0)  # MEASURE: latch band, from the module's bottom edge
BAY_FIT = 0.3  # per side in the 45 x 60 opening
BAY_WALL = 2.0
SMA_SLOT_W = 13.0  # slot in the top so the SMA and its boss slide in
# Back socket (NC / 5V-12V / GND / CRSF), seen from behind the module: 4.7-8.9 mm
# from its left edge, 3.1-16.2 mm from its bottom (from the product photo).
SOCKET_X = (4.7, 8.9)
SOCKET_Z = (3.1, 16.2)

# ---- MB102 power module (given: 52 x 38 including the DC jack overhang) ----
PWR_L, PWR_W, PWR_T = 52.0, 34.0, 1.6  # PCB; long edge front-to-back
PWR_JACK_OUT = 4.0  # DC jack nose past the PCB edge
PWR_LIFT = 10.0  # clears the breadboard pins under both ends
PWR_Y0 = 11.0
PWR_USB_Y, PWR_JACK_Y = 7.0, 46.0  # MEASURE: centres along the edge from the front end
DC_HOLE = (12.0, 12.0)
MINIUSB_HOLE = (12.0, 9.0)

# ---- USB-A female breakout for the wheel (MEASURE your breakout) ----------
USBA_HOLE = (13.6, 6.2)  # width x height
USBA_C = (40.0, PLATE + 28.0)  # y, z of the opening centre on the left wall

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


def extrude_xz(points, y0, y1):
    """Prism from a polygon in the x-z plane, spanning y0..y1."""
    cs = CrossSection([[(x, z) for x, z in points]])
    # Rotating +90 about x maps the profile's y onto z and the extrusion onto -y.
    return Manifold.extrude(cs, y1 - y0).rotate([90, 0, 0]).translate([0, y1, 0])


# ---- derived positions -------------------------------------------------------
Z0 = PLATE  # body bottom
ZT = PLATE + H  # body top
CX = W / 2

board_x0, board_x1 = BOARD_X0, BOARD_X0 + BOARD_W
board_y0 = WALL + FIT  # USB end against the front wall
board_y1 = board_y0 + BOARD_L
board_z0 = Z0 + BOARD_LIFT
board_cx = (board_x0 + board_x1) / 2

bay_half = MOD_W / 2 + BAY_FIT
bay_latch_half = MOD_W_LATCH / 2 + BAY_FIT
bay_y0 = D - MOD_T - 2 * BAY_FIT  # inner face of the bay's front wall
bay_z1 = Z0 + MOD_H + 2 * BAY_FIT  # bay ceiling
bay_outer_half = bay_latch_half + BAY_WALL
# Latch channel: full depth from LATCH_Z, 45 degree lead-in below it (the
# lead-in is the overhang when the body prints top-down).
latch_z0 = Z0 + LATCH_Z[0] - 1.0
latch_z1 = Z0 + LATCH_Z[1] + 1.5
# Seen from inside the case the module's back socket is on the -x side (the
# product photo is taken from behind the module).
socket_x = (CX - MOD_W / 2 + SOCKET_X[0], CX - MOD_W / 2 + SOCKET_X[1])

pwr_x1 = W - WALL - 0.5 - PWR_JACK_OUT  # jack edge towards the right wall
pwr_x0 = pwr_x1 - PWR_W
pwr_y0, pwr_y1 = PWR_Y0, PWR_Y0 + PWR_L
pwr_z0 = Z0 + PWR_LIFT

bosses = [
    (WALL + BOSS_R, WALL + BOSS_R),
    (W - WALL - BOSS_R, WALL + BOSS_R),
    (WALL + BOSS_R, D - WALL - BOSS_R),
    (W - WALL - BOSS_R, D - WALL - BOSS_R),
]


def bay_cavity(y0, y1):
    """The module-shaped hole: 45 x 60 plus the latch channels."""
    h = bay_half
    l = bay_latch_half
    lead = l - h
    pts = [
        (-h, Z0 - 1), (h, Z0 - 1), (h, latch_z0 - lead), (l, latch_z0), (l, latch_z1), (h, latch_z1),
        (h, bay_z1), (-h, bay_z1), (-h, latch_z1), (-l, latch_z1), (-l, latch_z0), (-h, latch_z0 - lead),
    ]
    return extrude_xz([(CX + x, z) for x, z in pts], y0, y1)


def body():
    shell = rbox(0, 0, Z0, W, D, H, R) - rbox(WALL, WALL, Z0 - 1, W - 2 * WALL, D - 2 * WALL, H - TOP + 1, R - WALL)

    for x, y in bosses:
        shell += cyl(x, y, Z0, ZT, BOSS_R) - cyl(x, y, Z0 - 1, Z0 + 12, PILOT_R)

    # Module bay: a solid block at the back, minus the module shape.
    shell += box(CX - bay_outer_half, bay_y0 - BAY_WALL, Z0, CX + bay_outer_half, D, ZT)
    cut = bay_cavity(bay_y0, D + 1)
    # SMA (and its boss) slide in through the top.
    cut += box(CX - SMA_SLOT_W / 2, bay_y0, bay_z1 - 1, CX + SMA_SLOT_W / 2, D + 1, ZT + 1)
    # Window in the bay's front wall for the header that mates with the
    # module's back socket; open at the bottom so it prints without a bridge.
    cut += box(socket_x[0] - 4.0, bay_y0 - BAY_WALL - 1, Z0 - 1, socket_x[1] + 4.0, bay_y0 + 1, Z0 + SOCKET_Z[1] + 3.0)

    # Screen: viewing window with an outward chamfer, then a shallow recess
    # for the glass (circle plus the FPC fold on the header side).
    sx, sy = SCREEN_C
    recess = max(GLASS_T - TAPE_T, 0.3)
    cut += cyl(sx, sy, ZT - TOP - 1, ZT + 1, VIEW_D / 2 + 0.2)
    cut += cyl(sx, sy, ZT - 0.8, ZT + 0.01, VIEW_D / 2 + 0.2, VIEW_D / 2 + 1.0)
    cut += cyl(sx, sy, ZT - TOP - 1, ZT - TOP + recess, GLASS_D / 2 + 0.3)
    fold_x = sx + GLASS_D / 2 - GLASS_SPAN - 0.3
    cut += box(fold_x, sy - 15, ZT - TOP - 1, sx, sy + 15, ZT - TOP + recess)

    # ESP32 USB-C ports through the front wall.
    uz = board_z0 + BOARD_T + USB_STACK / 2
    cut += box(board_cx - (BOARD_W - 1) / 2, -1, uz - 4.25, board_cx + (BOARD_W - 1) / 2, WALL + 1, uz + 4.25)

    # Power module: DC jack and mini-USB through the right wall.
    jz = pwr_z0 + PWR_T + 5.5
    uzz = pwr_z0 + PWR_T + 2.0
    for yc, (hw, hh), zc in ((pwr_y0 + PWR_JACK_Y, DC_HOLE, jz), (pwr_y0 + PWR_USB_Y, MINIUSB_HOLE, uzz)):
        cut += box(W - WALL - 1, yc - hw / 2, zc - hh / 2, W + 1, yc + hw / 2, zc + hh / 2)

    # USB-A for the wheel through the left wall.
    uw, uh = USBA_HOLE
    cut += box(-1, USBA_C[0] - uw / 2, USBA_C[1] - uh / 2, WALL + 1, USBA_C[0] + uw / 2, USBA_C[1] + uh / 2)

    return shell - cut


def plate():
    out = rbox(0, 0, 0, W, D, PLATE, R)

    # Locating rim just inside the body walls, broken around the bosses and the bay.
    rim = rbox(WALL + 0.3, WALL + 0.3, PLATE, W - 2 * (WALL + 0.3), D - 2 * (WALL + 0.3), 2.0, max(R - WALL - 0.3, 0.5))
    rim -= rbox(WALL + 1.5, WALL + 1.5, PLATE - 1, W - 2 * (WALL + 1.5), D - 2 * (WALL + 1.5), 4.0, 0.5)
    rim -= box(CX - bay_outer_half - FIT, bay_y0 - BAY_WALL - FIT, 0, CX + bay_outer_half + FIT, D + 1, 10)
    out += rim

    # Board cradle. Header rows run along both long edges almost to the
    # corners, so the board rests on ledges under the middle of its short
    # edges; walls outside the long edges locate it.
    ledge_top = board_z0
    for y0, y1 in ((board_y0, board_y0 + 2.5), (board_y1 - 2.5, board_y1)):
        out += box(board_x0 + HEADER_KEEPOUT, y0, PLATE, board_x1 - HEADER_KEEPOUT, y1, ledge_top)
    wall_top = ledge_top + BOARD_T + 2.0
    for cy in (board_y0, board_y1):
        inward = 1 if cy == board_y0 else -1
        ly0, ly1 = sorted((cy, cy + inward * 3.0))
        out += box(board_x0 - FIT - 1.6, ly0, PLATE, board_x0 - FIT, ly1, wall_top)
        out += box(board_x1 + FIT, ly0, PLATE, board_x1 + FIT + 1.6, ly1, wall_top)
    out += box(board_x0, board_y1 + FIT, PLATE, board_x1, board_y1 + FIT + 1.6, wall_top)  # end stop

    # Power module pedestal (3M tape on top), between the pin blocks at its ends.
    out += box(pwr_x0 + 5, pwr_y0 + 13, PLATE, pwr_x1 - 5, pwr_y1 - 13, pwr_z0)

    # Keep everything above the plate clear of the body's screw columns.
    for x, y in bosses:
        out -= cyl(x, y, PLATE, PLATE + 30, BOSS_R + FIT)

    holes = Manifold()
    for x, y in bosses:
        holes += cyl(x, y, -1, PLATE + 1, CLEAR_R)
        holes += cyl(x, y, -1, 1.6, HEAD_R + 0.1, CLEAR_R)  # head recess
    for x, y in [(10, 10), (W - 10, 10), (10, D - 10), (W - 10, D - 10)]:
        holes += cyl(x, y, -1, 0.8, 5.0)  # rubber feet
    return out - holes


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
        shade = 0.35 + 0.65 * np.abs(tm.face_normals @ light)
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
        if m.is_empty() or len(m.decompose()) != 1:
            sys.exit(f"{name}: not a single solid")
    # Body prints top-down: turn it over (a rotation; a mirror would swap
    # left and right) so the top face lands on z = 0.
    printable_body = b.rotate([0, 180, 0]).translate([W, 0, ZT])
    to_trimesh(printable_body).export(os.path.join(OUT, "body.stl"))
    to_trimesh(p).export(os.path.join(OUT, "plate.stl"))
    stale = os.path.join(OUT, "plate-for-mirrored-body.stl")  # v1 only
    if os.path.exists(stale):
        os.remove(stale)
    case, part = (0.62, 0.68, 0.76), (0.40, 0.46, 0.55)
    preview(
        [
            ("assembled, front", [(p, part), (b, case)], 25, -60),
            ("assembled, back (module bay)", [(p, part), (b, case)], 22, 125),
            ("body, from below (inside)", [(b, case)], -55, -60),
            ("plate", [(p, part)], 40, -50),
        ],
        os.path.join(OUT, "preview.png"),
    )
    for name, m in [("body", printable_body), ("plate", p)]:
        lo, hi = m.bounding_box()[:3], m.bounding_box()[3:]
        print(f"{name}: {hi[0]-lo[0]:.1f} x {hi[1]-lo[1]:.1f} x {hi[2]-lo[2]:.1f} mm, volume {m.volume()/1000:.1f} cm3")


if __name__ == "__main__":
    main()
