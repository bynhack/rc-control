"""Kids' desk screen for the P4 display: a soft white wedge with a red foot and
a black screen shell that lifts out of it.

Coordinates: x = right looking at the screen, y = back, z = up, the desk at
z = 0. The face leans back FACE_DEG. A point u along the face from the desk
and d behind it sits at y = u cos + d sin, z = u sin - d cos.

The shell keeps the P4 tray's outline, board screws and port windows, without
the antenna hole or the MULTI openings. It sits flush in a pocket in the face.

Run:  python kids_dock.py   -> out/kids_v2_*.stl
"""

import math
import os

import numpy as np
from manifold3d import CrossSection, FillRule, JoinType, Manifold, OpType

from cad import OUT, box, cyl, rbox
from p4_case import PLATE as TRAY_PLATE, USBC_Z as TRAY_USBC_Z, pcb_back as tray_pcb_back, tray_top as tray_top_p4
from p4_case import (BUTTONS_Y, FIT, FPC_DEEP, FPC_OUT, FPC_SIDE, FPC_X, GH, GW, HOLE_X, HOLE_Y, PH_WIN, PIN12_WIN,
                     STANDOFF_HEAD, STANDOFF_HOLE, SWITCH_Y, TF_SIDE, TF_X, UART_C_Y, USB_A_Y, USB_C_Y, USBC_PLUG,
                     WALL, WALL_B)

# The shell's back is thinner than the P4 tray's: only the frame and columns are left of it.
BACK_THIN = 1.0
PLATE = TRAY_PLATE - BACK_THIN
USBC_Z = TRAY_USBC_Z - BACK_THIN
pcb_back = tray_pcb_back - BACK_THIN
tray_top = tray_top_p4 - BACK_THIN

FACE_DEG = 68.0
S, C = math.sin(math.radians(FACE_DEG)), math.cos(math.radians(FACE_DEG))
FACE = [[1, 0, 0, 0], [0, C, -S, 0], [0, S, C, 0]]  # (x, u, n) -> world; n points out of the face, n = -d


def P(u, d):
    return (u * C + d * S, u * S - d * C)


def on_face(m):
    return m.transform(FACE)


def prism(points, x0, x1):
    """Polygon in the y-z plane, spanning x0..x1."""
    area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(points, points[1:] + points[:1]))
    pts = points if area > 0 else points[::-1]
    solid = Manifold.extrude(CrossSection([pts], FillRule.NonZero), x1 - x0)
    return solid.transform([[0, 0, 1, x0], [1, 0, 0, 0], [0, 1, 0, 0]])


# Two 6 x 2 mm disc magnets in the shell's back, two more facing them in the
# plate (opposite poles facing): they hold the shell in its pocket.
MAGNET_R, MAGNET_DEPTH = 3.1, 2.1
MAGNET_X = (-61.0, 61.0)  # on the two columns, clear of every window
MAGNET_Y = 72.0  # along the shell, in board coordinates

# The speaker's socket on the board's back, board coordinates: window with some margin.
# Its near side is 25 from the standoffs' centre line on the PH2.0 side (measured); y and width from a sketch.
SPK_SOCKET_SIDE = HOLE_X[1] - 25.0
SPK_SOCKET = (SPK_SOCKET_SIDE - 13.65, 86.0, SPK_SOCKET_SIDE + 2.0, 97.5)

# The backs of the shell and the pocket are open for the wires, only supports stay.
BACK_OPEN = (8.0, 8.0, GW - 8.0, 91.5)  # shell back's opening, board coordinates
COLUMN_W = 8.0  # the columns, at MAGNET_X, on both parts
LEDGE = 3.0  # the pocket's ledge, under the shell's walls

# The flex notches stop this far below the wall's top, which closes them from the front.
FPC_COVER_T = 1.2

# ---- shell ---------------------------------------------------------------------
SHELL_R = 5.0
X_HALF = GW / 2 + FIT + WALL
Y0, Y1 = -FIT - WALL_B, GH + FIT + WALL
SHELL_H = Y1 - Y0
XC = GW / 2  # board x -> shell x


def shell():
    out = rbox(-X_HALF, Y0, 0, 2 * X_HALF, SHELL_H, tray_top, SHELL_R)
    out -= rbox(-XC - FIT, -FIT, PLATE, GW + 2 * FIT, GH + 2 * FIT, tray_top, 1.0)
    for x in MAGNET_X:  # the magnet is deeper than the thin back: a low boss inside
        out += cyl(x, MAGNET_Y, PLATE - 0.1, MAGNET_DEPTH + 0.6, 6.0)
    cuts = []
    for y in (UART_C_Y, USB_C_Y):
        w, h = USBC_PLUG
        cuts.append(box(-X_HALF - 1, y - w / 2, USBC_Z - h / 2, -XC + 1, y + w / 2, USBC_Z + h / 2))
    for y, h in ((USB_A_Y, 15.5), (SWITCH_Y, 10.0)):
        cuts.append(box(-X_HALF - 1, y - h / 2, PLATE, -XC + 1, y + h / 2, pcb_back + 1))
    cuts.append(box(XC - 1, BUTTONS_Y[0], PLATE, X_HALF + 1, BUTTONS_Y[1], pcb_back + 1))
    cuts.append(box(TF_X[0] - TF_SIDE - XC, Y0 - 1, PLATE + 1, TF_X[1] + TF_SIDE - XC, 1, pcb_back + 0.3))
    for x0, x1 in FPC_X:
        cuts.append(box(x0 - FPC_SIDE - XC, -FIT - FPC_OUT - FPC_DEEP, pcb_back - 1, x1 + FPC_SIDE - XC, 1, tray_top - FPC_COVER_T))
    x0, y0, x1, y1 = PH_WIN
    cuts.append(box(x0 - XC, y0, -1, x1 - XC, y1, PLATE + 1))
    x0, y0, x1, y1 = SPK_SOCKET
    cuts.append(box(x0 - XC, y0, -1, x1 - XC, y1, PLATE + 1))
    for x0, x1 in PIN12_WIN:
        cuts.append(box(x0 - XC, 1.5, -1, x1 - XC, 13.0, PLATE + 1))
    sink = STANDOFF_HEAD / 2 - STANDOFF_HOLE / 2
    for x in HOLE_X:
        for y in HOLE_Y:
            cuts.append(cyl(x - XC, y, -1, PLATE + 1, STANDOFF_HOLE / 2))
            cuts.append(cyl(x - XC, y, -1, sink, STANDOFF_HOLE / 2 + sink + 1, STANDOFF_HOLE / 2))
    # Open back: the frame carries the board's four screws, two columns carry the magnets.
    bx0, by0, bx1, by1 = BACK_OPEN
    opening = box(bx0 - XC, by0, -1, bx1 - XC, by1, PLATE + 1)
    keep = [box(x - COLUMN_W / 2, by0 - 1, -2, x + COLUMN_W / 2, by1 + 1, PLATE + 2) for x in MAGNET_X]
    keep += [cyl(x, MAGNET_Y, -2, PLATE + 2, 6.0) for x in MAGNET_X]
    cuts.append(opening - Manifold.batch_boolean(keep, OpType.Add))
    for x in MAGNET_X:
        cuts.append(cyl(x, MAGNET_Y, -1, MAGNET_DEPTH, MAGNET_R))
    return out - Manifold.batch_boolean(cuts, OpType.Add)


# ---- base ----------------------------------------------------------------------
BAND = 4.0
POCKET_U = 26.0  # the pocket's bottom edge, along the face from the desk
POCKET_FIT = 0.25
TOP_FRAME = 7.0
SIDE_FRAME = 6.0
WALL_T = 2.4
EDGE_R = 4.0
CORNER_R = 14.0
SHELL_RECESS = 0.5  # the shell's walls behind the face; the glass stands 0.3 above them
TOP_DEPTH = 23.0
REAR_LEAN = 0.0948  # rear wall: y grows this much per mm downwards

shell_u = POCKET_U + POCKET_FIT
shell_back = SHELL_RECESS + tray_top
pocket_back = shell_back + 0.3
plate_back = pocket_back + WALL_T
pocket_h = SHELL_H + 2 * POCKET_FIT
pocket_hw = X_HALF + POCKET_FIT
L = POCKET_U + pocket_h + TOP_FRAME
HW = pocket_hw + SIDE_FRAME
top_rear = P(L, TOP_DEPTH)


def rear_y(z, inset=0.0):
    return top_rear[0] + (top_rear[1] - z) * REAR_LEAN - inset / math.cos(math.atan(REAR_LEAN))


def outline(inset=0.0):
    """The face's shape: big corners at the top, running off below the desk."""
    r = CORNER_R - inset
    t = L - CORNER_R
    h = HW - CORNER_R
    corners = [CrossSection.circle(r).translate([x, t]) for x in (-h, h)]
    corners += [CrossSection.circle(0.05).translate([x, -40]) for x in (-(HW - inset), HW - inset)]
    return Manifold.extrude(CrossSection.batch_hull(corners), 240).translate([0, 0, -200])


def outer():
    prof = [P(-14, 0), P(L, 0), top_rear, (rear_y(-14), -14)]
    area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(prof, prof[1:] + prof[:1]))
    inner = CrossSection([prof if area > 0 else prof[::-1]], FillRule.NonZero).offset(-EDGE_R, JoinType.Miter)
    balls = []
    for poly in inner.to_polygons():
        for y, z in np.asarray(poly):
            for x in (-(HW - EDGE_R), HW - EDGE_R):
                balls.append(Manifold.sphere(EDGE_R, 48).translate([x, float(y), float(z)]))
    return Manifold.batch_hull(balls) ^ on_face(outline()) ^ box(-200, -50, BAND, 200, 300, 300)


# Speaker: its face turned down and forward, sound runs under the pocket to the chin.
SPK_L, SPK_W, SPK_D = 100.0, 45.0, 21.0
SPK_TILT = math.radians(6.0)
SPK_FRONT = (33.0, BAND + 3.0 + SPK_W * math.sin(SPK_TILT))
a_w = (math.cos(SPK_TILT), -math.sin(SPK_TILT))  # along the face, front to back
a_d = (math.sin(SPK_TILT), math.cos(SPK_TILT))  # from the face to the back
spk_pts = [SPK_FRONT, (SPK_FRONT[0] + SPK_W * a_w[0], SPK_FRONT[1] + SPK_W * a_w[1])]
spk_pts += [(spk_pts[1][0] + SPK_D * a_d[0], spk_pts[1][1] + SPK_D * a_d[1]),
            (spk_pts[0][0] + SPK_D * a_d[0], spk_pts[0][1] + SPK_D * a_d[1])]


def speaker():
    return prism(spk_pts, -SPK_L / 2, SPK_L / 2)


def face_box(x0, x1, u0, u1, d0, d1):
    return on_face(box(x0, u0, -d1, x1, u1, -d0))


def base():
    body = outer()
    # Inside: behind the plate, and under the pocket to the chin.
    cap = L - WALL_T
    k = REAR_LEAN
    w2 = WALL_T / math.cos(math.atan(k))
    z_e = (cap - (top_rear[0] + top_rear[1] * k - w2) * C) / (S - k * C)
    floor_u = POCKET_U - WALL_T
    inside = [P(-5, WALL_T), P(floor_u, WALL_T), P(floor_u, plate_back), P(cap, plate_back),
              (rear_y(z_e, WALL_T), z_e), (rear_y(-5, WALL_T), -5)]
    hollow = prism(inside, -(HW - WALL_T), HW - WALL_T) ^ on_face(outline(WALL_T))
    body -= hollow
    # The pocket the shell sits in.
    pocket = rbox(-pocket_hw, POCKET_U, -pocket_back, 2 * pocket_hw, pocket_h, pocket_back + 10, SHELL_R + POCKET_FIT)
    body -= on_face(pocket)
    # Ribs carry the pocket's floor up from the desk (no support in print), along the sound's way.
    rib = [P(floor_u + 0.5, WALL_T - 0.6), P(floor_u + 0.5, plate_back + 0.1)]
    rib += [(rib[1][0], BAND), (rib[0][0], BAND)]
    ribs = [prism(rib, x - 1, x + 1) for x in (-78, -54, -27, 0, 27, 54, 78)]
    body += Manifold.batch_boolean(ribs, OpType.Add) ^ prism([P(-5, 0.2), P(POCKET_U, 0.2), P(POCKET_U, 60), (120, -5)], -300, 300)
    # Chin: rows of small holes.
    holes = []
    for row, u in enumerate((10.4, 13.6, 16.8, 20.0)):
        n = 36 if row % 2 == 0 else 35
        x0 = -(n - 1) * 3.6 / 2
        holes += [cyl(x0 + i * 3.6, u, -WALL_T - 0.6, 1.0, 0.85) for i in range(n)]
    body -= on_face(Manifold.batch_boolean(holes, OpType.Add))
    # Left side: the ports, through to the shell's windows.
    def to_u(y):
        return shell_u + y - Y0

    def to_d(z):
        return shell_back - z

    def pill(u0, u1, d0, d1):
        r, dc = (d1 - d0) / 2, (d0 + d1) / 2
        rod = Manifold.cylinder(HW - pocket_hw + 2, r, r, 48).rotate([0, 90, 0])
        ends = [rod.translate([-HW - 1, u, -dc]) for u in (u0 + r, u1 - r)]
        return on_face(Manifold.batch_hull(ends))

    wy0, wy1 = UART_C_Y - 6.75, USB_A_Y + 8.25
    body -= pill(to_u(wy0), to_u(wy1), to_d(pcb_back + 3.2), to_d(PLATE - 0.4))
    body -= pill(to_u(SWITCH_Y - 5.5), to_u(SWITCH_Y + 5.5), to_d(pcb_back + 1.4), to_d(PLATE - 0.4))
    # Pocket's back: a ledge round it and two columns, the rest open for the wires.
    hw = pocket_hw - LEDGE
    opening = face_box(-hw, hw, POCKET_U + LEDGE, POCKET_U + pocket_h, pocket_back - 0.1, plate_back + 0.2)  # no ledge at the top: it would be a long bridge
    columns = [face_box(x - COLUMN_W / 2, x + COLUMN_W / 2, POCKET_U - 1, POCKET_U + pocket_h + 1, pocket_back - 1, plate_back + 1)
               for x in MAGNET_X]
    body -= opening - Manifold.batch_boolean(columns, OpType.Add)
    for x in MAGNET_X:  # stiffer behind
        body += face_box(x - COLUMN_W / 2, x + COLUMN_W / 2, POCKET_U, POCKET_U + pocket_h, plate_back - 0.1, plate_back + 2.0)
    push_u = POCKET_U + 84.0
    py, pz = P(push_u, plate_back)
    body -= Manifold.cylinder(40, 14.0).rotate([-90, 0, 0]).translate([0, py + 8.0, pz])
    # Magnets in the plate, a pad behind each.
    mag_u = to_u(MAGNET_Y)
    for x in MAGNET_X:
        body += on_face(cyl(x, mag_u, -plate_back - 2.2, -plate_back + 0.1, 6.0))
        body -= on_face(cyl(x, mag_u, -pocket_back - MAGNET_DEPTH, -pocket_back + 0.5, MAGNET_R))
    # Posts for the band's screws, each against the side wall.
    for x, y in BAND_SCREWS:
        body += cyl(x, y, BAND, BAND + 8.0, 3.5)
    for x, y in BAND_SCREWS:
        body -= cyl(x, y, BAND - 1, BAND + 7.0, 1.1)
    return body


BAND_SCREWS = [(x, y) for x in (-85.5, 85.5) for y in (12.0, 80.0)]


def cradle():
    """Fins under the speaker's two ends, a lip behind it, walls at its ends."""
    gap = 0.2
    A = (SPK_FRONT[0] - a_d[0] * gap, SPK_FRONT[1] - a_d[1] * gap)
    B = (spk_pts[1][0] - a_d[0] * gap, spk_pts[1][1] - a_d[1] * gap)
    B2 = (B[0] + 0.4 * a_w[0], B[1] + 0.4 * a_w[1])
    B3 = (B2[0] + 10 * a_d[0], B2[1] + 10 * a_d[1])
    B4 = (B3[0] + 2.5 * a_w[0], B3[1] + 2.5 * a_w[1])
    low = BAND - 0.1
    fin = [A, B, B2, B3, B4, (B4[0], low), (A[0], low)]
    Atop = (SPK_FRONT[0] + 14 * a_d[0], SPK_FRONT[1] + 14 * a_d[1])
    Btop = (spk_pts[1][0] + 14 * a_d[0], spk_pts[1][1] + 14 * a_d[1])
    end = [Atop, Btop, (Btop[0], low), (Atop[0], low)]
    parts = [prism(fin, s * 46.5 if s > 0 else -49.5, s * 49.5 if s > 0 else -46.5) for s in (-1, 1)]
    parts += [prism(end, 50.35, 52.35), prism(end, -52.35, -50.35)]
    return Manifold.batch_boolean(parts, OpType.Add)


def band(body):
    out = Manifold.extrude(body.slice(BAND + 0.01), BAND) + cradle()
    for x, y in BAND_SCREWS:
        out -= cyl(x, y, -1, BAND + 1, 1.45)
        out -= cyl(x, y, -0.01, 1.2, 2.65, 1.45)
    return out


def dock_shell(m):
    return on_face(m.translate([0, shell_u - Y0, -shell_back]))


if __name__ == "__main__":
    sh = shell()
    bd = base()
    bn = band(outer())
    spk = speaker()
    docked = dock_shell(sh)
    glass = box(-XC, 0, tray_top - 1.0, XC, GH, tray_top + 0.3)
    checks = {
        "shell x glass": (sh ^ glass).volume(),
        "base x shell": (bd ^ docked).volume(),
        "base x speaker": (bd ^ spk).volume(),
        "shell x speaker": (docked ^ spk).volume(),
        "band x speaker": (bn ^ spk).volume(),
        "base x band": (bd ^ bn).volume(),
    }
    n = np.array([0, -S, C])
    for t in (2, 10, 20, 30):
        checks[f"shell out {t}"] = (bd ^ docked.translate((n * t).tolist())).volume()
    for k, v in checks.items():
        print(f"{k}: {v:.3f} mm3")
    from cad import to_trimesh

    # Print files: base upright on its open bottom, band flat, shell on its back.
    for name, m, keep in (("base", bd, True), ("band", bn, True), ("shell", sh, True)):
        lo = np.round(np.array(m.bounding_box()[:3]), 2)
        hi = np.round(np.array(m.bounding_box()[3:]), 2)
        print(name, lo, hi, f"vol {m.volume() / 1000:.1f} cm3, genus {m.genus()}")
        tm = to_trimesh(m)
        print("  watertight", tm.is_watertight)
        tm.export(os.path.join(OUT, f"kids_v2_{name}.stl"))
    print("face length", round(L, 2), "height", round(P(L, 0)[1], 1), "width", round(2 * HW, 1), "depth", round(rear_y(BAND), 1))
    # Overhangs on the upright base: faces steeper than 45 degrees from vertical, downward.
    tm = to_trimesh(bd)
    n = tm.face_normals
    a, cen = tm.area_faces, tm.triangles_center
    low = (n[:, 2] < -math.sin(math.radians(45))) & (cen[:, 2] > BAND + 0.5)
    print("overhang total mm2", round(a[low].sum(), 1))
    for z0 in range(0, 130, 20):
        k = low & (cen[:, 2] >= z0) & (cen[:, 2] < z0 + 20)
        if a[k].sum() > 1:
            print(f"  z {z0}-{z0 + 20}: {a[k].sum():.0f} mm2, y {cen[k, 1].min():.0f}..{cen[k, 1].max():.0f}, x {cen[k, 0].min():.0f}..{cen[k, 0].max():.0f}")
