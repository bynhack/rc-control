"""The printed frame of the X2201's FPV mount for when the carrier board
(pcb/x2201_carrier.py) is its base: x2201_fpv_mount.py without its plate and
rails, screwed onto the board instead.

The board takes the plate's place, on 1 mm 3M VHB tape on the chassis'
strips (as BRIDGE). On it, one printed part, printed the way it sits (the board
side down), no support (the nut pockets and the fan pads bridge):
  - the VTX's four posts and the fan pads, and the front stop, as in
    x2201_fpv_mount.py, the posts joined by a low rail along each side;
  - the camera's cheeks, tied to the stop by two low bars outside the
    camera cable's way;
  - four ears outside the posts, over the board's M2 SMT nuts: a pocket
    over each nut, an M2 x 4 screw from the top.
The board's parts are in front of the VTX, between the ears and in the plug
row behind it, clear of the frame. Set the VTX on the board, then lower the
frame over it.

Hardware:
  4x M2 x 4                ears -> the board's SMT nuts
  4x M2 x 9 self-tapping   fan -> pads
  2x M2 x 4                camera side holes, through the cheeks
  1 mm 3M VHB tape         board -> chassis strips

Coordinates as in x2201_cage.py (x forward from the cage's back end, y
across, z up from the chassis' strips). The board's y is the car's -y.

Run:  python x2201_carrier_frame.py  -> out/x2201_carrier_frame.stl, out/x2201_carrier_frame_preview.png
"""

import os
import sys

from manifold3d import Manifold

from cad import OUT, box, cyl, preview, rbox, to_trimesh
from x2201_cage import shell_room
import x2201_fpv_mount as fm

# ---- the board (pcb/x2201_carrier.py) -----------------------------------------------------------
BRIDGE = fm.BRIDGE  # VHB tape: the board's underside
PCB_T = 1.6
X0, X1, HW = 3.6, 61.8, 26.0  # outline: the plate and the plug row behind it (v4: 4 mm more at the front)
NOTCH = (51.8, 56.0)  # x: a notch under the camera's cheeks, 1.2 high, over v4's decoupling caps
NOTCH_H = 1.2
NUTS = [(17.6, 18.6), (35.7, 18.6)]  # x, |y|: M2 SMT nuts, both sides
NUT_D, NUT_H = 4.0, 2.0  # MEASURE: the nut's outside and height (e.g. Wurth 9774020151R)
# The board's parts, as keep-out boxes (x0, |y|0, x1, |y|1, height over the board), both sides.
PARTS = [(40.25, 10.0, 57.8, 26.0, 4.0),  # the nearest pads start at x 40.27 (C1)
         (20.85, 15.9, 32.4, 26.0, 2.0),  # the transponder, between the ears
         (5.5, 0.0, 12.3, 25.1, 6.0),  # the plug row along the back edge
         # v4 (hardware/archive/x2201-carrier-v4), so one frame fits both boards:
         (40.25, 9.8, 61.8, 26.0, 4.0),  # ESP32-S3-MINI-1 (right), the ESC plug and the 3V3 regulator (left)
         (46.0, 0.0, 62.9, 6.8, 3.4),  # under the camera: the USB-C (1.1 past the front edge), the LED, CC resistors
         (NOTCH[0], 6.6, NOTCH[1], 9.6, 1.0),  # U1's decoupling, under the cheeks' notch
         (20.85, 15.9, 32.4, 26.0, 2.0),  # the VTX switch, between the ears
         (20.0, 22.2, 33.2, 26.0, 2.0),  # and outside them
         (33.0, 22.8, 40.25, 26.0, 1.0),  # EN's R / C, outside the right front ear
         (12.3, 15.9, 14.4, 25.1, 1.0)]  # the battery's divider, by the plug row

# ---- frame ---------------------------------------------------------------------------------------
EAR_T = 1.6  # over the nut pocket
EAR_W = 6.4  # along x
POCKET_FIT = 0.3
LINK_H = 3.0
SCREW_R = 1.15

Z_TOP = BRIDGE + PCB_T  # the board's top: the VTX's underside
z0 = Z_TOP
AIR_GAP = fm.AIR_GAP - (PCB_T - fm.PLATE)  # keep the fan where x2201_fpv_mount has it
z_fan = z0 + fm.VTX_H + AIR_GAP
vtx_x, pocket, pivot_x, pivot_z = fm.vtx_x, fm.pocket, fm.pivot_x, fm.pivot_z
POST, POST_L, PAD_T, pad_in = fm.POST, fm.POST_L, fm.PAD_T, fm.pad_in
cheek_y, CHEEK_T, CHEEK_L = fm.cheek_y, fm.CHEEK_T, fm.CHEEK_L
EAR_H = NUT_H + 0.3 + EAR_T


def vtx_frame():
    out = Manifold()
    for sx in (-1, 1):
        for sy in (-1, 1):
            xs = sorted((vtx_x + sx * pocket, vtx_x + sx * (pocket - POST_L)))
            ys = sorted((sy * pocket, sy * (pocket + POST)))
            out += box(xs[0], ys[0], z0, xs[1], ys[1], z_fan)
            xs = sorted((vtx_x + sx * pad_in, vtx_x + sx * pocket))
            ys = sorted((sy * pad_in, sy * (pocket + POST)))
            out += box(xs[0], ys[0], z_fan - PAD_T, xs[1], ys[1], z_fan)
            out -= cyl(vtx_x + sx * fm.FAN_HOLES / 2, sy * fm.FAN_HOLES / 2, z_fan - PAD_T - 1, z_fan + 1,
                       fm.FAN_PILOT / 2)
    stop_x = vtx_x + pocket
    out += box(stop_x, -pocket - POST, z0, stop_x + fm.STOP, pocket + POST, z0 + LINK_H)
    # Low rails between the back and front posts: what the plate did. The VTX's
    # cables come out over them.
    for sy in (-1, 1):
        ys = sorted((sy * pocket, sy * (pocket + POST)))
        out += box(vtx_x - pocket + POST_L - 0.01, ys[0], z0, vtx_x + pocket - POST_L + 0.01, ys[1], z0 + LINK_H)
    return out


def ears():
    out, cut = Manifold(), Manifold()
    for nx, ny in NUTS:
        for sy in (-1, 1):
            y_in = sy * (pocket + POST - 0.01)
            y_out = sy * (ny + NUT_D / 2 + POCKET_FIT + 1.2)
            ys = sorted((y_in, y_out))
            out += rbox(nx - EAR_W / 2, ys[0], z0, EAR_W, ys[1] - ys[0], EAR_H, 1.0)
            cut += cyl(nx, sy * ny, z0, z0 + NUT_H + 0.3, NUT_D / 2 + POCKET_FIT)
            cut += cyl(nx, sy * ny, z0 - 1, z0 + EAR_H + 1, SCREW_R)
    return out, cut


def cradle():
    out = Manifold()
    stop_x = vtx_x + pocket + fm.STOP
    for sy in (-1, 1):
        y0, y1 = sorted((sy * cheek_y, sy * (cheek_y + CHEEK_T)))
        out += box(pivot_x - CHEEK_L / 2, y0, z0, pivot_x + CHEEK_L / 2, y1, pivot_z)
        out += cyl(0, 0, 0, CHEEK_T, CHEEK_L / 2).rotate([90, 0, 0]).translate([pivot_x, y1, pivot_z])
        out += box(stop_x - 0.01, y0, z0, pivot_x - CHEEK_L / 2 + 0.01, y1, z0 + LINK_H)  # link to the stop
    out -= cyl(0, 0, 0, 40, 1.1).rotate([90, 0, 0]).translate([pivot_x, 20, pivot_z])
    # The notch: a short bridge in the first layers, over v4's caps by U1.
    out -= box(NOTCH[0], -cheek_y - CHEEK_T - 1, z0 - 1, NOTCH[1], cheek_y + CHEEK_T + 1, z0 + NOTCH_H)
    return out


def frame():
    e, cut = ears()
    return (vtx_frame() + cradle() + e) - cut


# ---- stand-ins -----------------------------------------------------------------------------------
def board():
    out = rbox(X0, -HW, BRIDGE, X1 - X0, 2 * HW, PCB_T, 2.5)
    for nx, ny in NUTS:
        for sy in (-1, 1):
            out += cyl(nx, sy * ny, Z_TOP - 0.01, Z_TOP + NUT_H, NUT_D / 2)
    return out


def parts():
    out = Manifold()
    for x0, y0, x1, y1, h in PARTS:
        for sy in (-1, 1):
            ys = sorted((sy * y0, sy * y1))
            out += box(x0, ys[0], Z_TOP, x1, ys[1], Z_TOP + h)
    return out


def vtx():
    w = fm.VTX_W
    return box(vtx_x - w / 2, -w / 2, z0, vtx_x + w / 2, w / 2, z0 + fm.VTX_H)


def fan():
    w = fm.FAN_W
    return box(vtx_x - w / 2, -w / 2, z_fan, vtx_x + w / 2, w / 2, z_fan + fm.FAN_T)


def camera(tilt=0.0):
    return fm.camera_at(pivot_x, tilt)


def main():
    os.makedirs(OUT, exist_ok=True)
    f = frame()
    if f.is_empty() or len(f.decompose()) != 1:
        sys.exit("frame: not a single solid")
    room = shell_room()
    b = board()
    nuts_only = b - rbox(X0, -HW, BRIDGE, X1 - X0, 2 * HW, PCB_T, 2.5)
    checks = {
        "frame x VTX": (f ^ vtx()).volume(),
        "frame x fan": (f ^ fan()).volume(),
        "frame x camera": (f ^ camera()).volume(),
        "frame x board": (f ^ (b - nuts_only)).volume(),
        "frame x nuts": (f ^ nuts_only).volume(),
        "frame x board parts": (f ^ parts()).volume(),
        "VTX x board parts": (vtx() ^ parts()).volume(),
        "camera x board parts": (camera() ^ parts()).volume(),
        "VTX's way in": (f ^ box(X0 - 40, -fm.VTX_W / 2, z0, vtx_x + fm.VTX_W / 2, fm.VTX_W / 2, z0 + fm.VTX_H)).volume(),
    }
    for k, v in {"frame": f, "board": b, "board parts": parts(), "VTX": vtx(), "fan": fan()}.items():
        for d in ([0, 0, 0.5], [0, 0.5, 0], [0, -0.5, 0]):
            checks[f"{k} outside the room {d}"] = (v.translate(d) - room).volume()
    tilts = []
    for t in range(-15, 16, 5):
        c = camera(t)
        if max((f ^ c).volume(), (vtx() ^ c).volume(), (fan() ^ c).volume(), (c - room).volume(), (c ^ b).volume()) < 0.01:
            tilts.append(t)
    for k, v in checks.items():
        if v > 0.01:
            print(f"{k}: {v:.2f} mm3")
    if max(checks.values()) > 0.01 or 0 not in tilts:
        sys.exit("clashes")
    print("all clear:", len(checks), "checks")
    print(f"camera tilts clear: {tilts[0]} .. {tilts[-1]} deg")

    to_trimesh(f).export(os.path.join(OUT, "x2201_carrier_frame.stl"))
    grey, green, dark, white = (0.62, 0.68, 0.76), (0.1, 0.45, 0.25), (0.15, 0.17, 0.2), (0.85, 0.85, 0.8)
    stuff = [(b, green), (parts(), white), (vtx(), (0.4, 0.46, 0.55)), (fan(), dark), (camera(0), dark)]
    preview([("on the board", [(f, grey)] + stuff, 30, -60), ("from the side (front to the right)", [(f, grey)] + stuff, 0, -90),
             ("from above", [(f, grey), (b, green), (parts(), white)], 89, -90), ("frame alone", [(f, grey)], 35, -40)],
            os.path.join(OUT, "x2201_carrier_frame_preview.png"))
    lo, hi = f.bounding_box()[:3], f.bounding_box()[3:]
    print(f"frame: {hi[0]-lo[0]:.1f} x {hi[1]-lo[1]:.1f} x {hi[2]-lo[2]:.1f}, {f.volume()/1000:.1f} cm3; "
          f"fan top {z_fan + fm.FAN_T:.1f}")


if __name__ == "__main__":
    main()
