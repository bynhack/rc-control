"""Driver's-view FPV mount for the Geeks X2201: a Walksnail Avatar Ascent Lite+
camera looking out through the windscreen, its VTX behind it under a 25 mm
fan, all inside the shell in the room the test cage (x2201_cage.py)
describes. The room is low (24 at the roof's highest point, 20 at the
windscreen's top edge), so everything is stacked as flat as it goes.

One part, x2201_fpv_mount.stl, printed rails down, no support (the plate
bridges between the rails):
  - two rails on the chassis' two flat strips either side of its middle
    channel (3M tape), and a plate across them, BRIDGE over the channel's
    screw posts and wiring;
  - the VTX on the plate, between four posts beside its corners. Pads on the
    posts' tops reach in over its corners, and the fan screws onto them. The
    posts only stand beside the VTX, so it slides in from the back under the
    pads, against a stop at the front; a thermal pad or tape under it keeps
    it there. Its cables come out between the posts on every side;
  - the camera in front, between two cheeks, on its two M2 side screws: the
    tilt pivot. The lens sits at the windscreen opening's mid height, as far
    forward as the windscreen's slope lets it.

Hardware:
  4x M2 x 9 self-tapping   fan -> pads (FAN_T + PAD_T)
  2x M2 x 4                camera side holes, through the cheeks
  3M VHB tape              rails -> chassis strips
  thermal pad or tape      VTX -> plate

The fan has only 1 to 4 mm of air over it under the roof; a vent or scoop
cut in the roof over it would let it breathe (and the alloy shell gets hot).
The VTX's antenna must get out of the alloy shell: that is not in this part.

Coordinates as in x2201_cage.py: x = forward from the cage's back end (the
windscreen's foot at x = L), y = across (centred), z = up from the chassis'
strips.

Run:  python x2201_fpv_mount.py  -> out/x2201_fpv_mount.stl, out/x2201_fpv_preview.png
"""

import os
import sys

import numpy as np
from manifold3d import Manifold

from cad import OUT, box, cyl, preview, rbox, to_trimesh
from x2201_cage import L, MID_W, Z_COWL, Z_WS_TOP, shell_room
from x2201_liner import NPZ, liner_room, liner_shell

FIT = 0.3

# ---- parts (as in vtx_mount.py) ------------------------------------------------------
VTX_W, VTX_H = 23.5, 8.0  # square
CAM_W, CAM_H = 14.0, 12.0  # camera body, across the cheeks x height
CAM_L = 12.0  # MEASURE: camera body depth behind the lens barrel
CAM_PIVOT_BACK = 6.0  # MEASURE: side screw hole to the back of the camera
LENS_D, LENS_L = 10.0, 6.0  # MEASURE: lens barrel
FAN_W, FAN_HOLES = 25.0, 20.0
FAN_T = 7.0  # 2507 fan

# ---- mount -----------------------------------------------------------------------------
BRIDGE = 1.0  # MEASURE: the plate's underside over the strips: room over the channel's posts and wires
PLATE = 1.2  # thin: the fan is right under the liner at its back corners
RAIL_Y = (MID_W / 2 + 1.0, MID_W / 2 + 11.0)  # rails: on the strips, clear of the channel
AIR_GAP = 2.5  # VTX top to the fan's underside
PAD_T = 2.0  # pads on the post tops, inside the air gap
POST, POST_L = 3.5, 6.0  # posts beside the VTX's corners: thick (across), long (along x)
STOP = 1.5  # the VTX's stop at the front, between the front posts
FAN_PILOT = 1.7  # M2 self-tapping into the pads
CABLE_GAP = 5.0  # VTX front to the camera's back: the camera cable's bend
CHEEK_T, CHEEK_L = 2.0, 11.0
LENS_CLEAR = 1.0  # lens and body to the windscreen, level
TILT = (-15, 15)  # tilt range checked, nose down .. up

z0 = BRIDGE + PLATE  # VTX's underside
z_fan = z0 + VTX_H + AIR_GAP  # fan underside = pad tops
pocket = VTX_W / 2 + FIT
pad_in = FAN_HOLES / 2 - 2.3  # pads reach in this far: enough round the fan screws
pivot_z = (Z_COWL + Z_WS_TOP) / 2  # lens at the windscreen opening's mid height


ROOM = liner_room()  # under the scanned liner: everything but the lens
SHELL = shell_room()  # the lens reaches through a hole in the liner's windscreen, up to the shell's


def camera_parts(px, tilt=0.0):
    body = box(-CAM_PIVOT_BACK, -CAM_W / 2, -CAM_H / 2, CAM_L - CAM_PIVOT_BACK, CAM_W / 2, CAM_H / 2)
    lens = cyl(0, 0, 0, LENS_L, LENS_D / 2).rotate([0, 90, 0]).translate([CAM_L - CAM_PIVOT_BACK, 0, 0])
    return [p.rotate([0, -tilt, 0]).translate([px, 0, pivot_z]) for p in (body, lens)]


def camera_at(px, tilt=0.0):
    body, lens = camera_parts(px, tilt)
    return body + lens


def camera_out(px, tilt=0.0, clear=0.0):
    """How much of the camera is out of its room: the body under the liner,
    the lens in the shell; each moved by `clear` forwards and upwards."""
    body, lens = camera_parts(px, tilt)
    out = 0.0
    for d in ([clear, 0, 0], [0, 0, clear]):
        out += (body.translate(d) - ROOM).volume() + (lens.translate(d) - SHELL).volume()
    return out


def find_pivot():
    """As far forward as the camera goes, level, LENS_CLEAR off the liner and the shell."""
    px = L
    while camera_out(px, 0, LENS_CLEAR) > 0.01:
        px -= 0.25
    return px


def lens_hole():
    """Where the lens axis meets the liner's windscreen (its outside), and its slope there."""
    d = np.load(NPZ)
    top = d["top"][:, len(d["y"]) // 2]
    x = d["x"]
    i = int(np.argmax((x > pivot_x) & (top <= pivot_z)))
    slope = np.degrees(np.arctan2(top[i - 2] - top[i + 2], x[i + 2] - x[i - 2]))
    return float(x[i]), slope


pivot_x = find_pivot()
cheek_y = CAM_W / 2 + FIT
vtx_x = pivot_x - CAM_PIVOT_BACK - CABLE_GAP - STOP - pocket  # VTX centre
back = vtx_x - pocket - 1.0  # the plate's back end
front = pivot_x + CHEEK_L / 2


def plate():
    out = rbox(back, -RAIL_Y[1], BRIDGE, front - back, 2 * RAIL_Y[1], PLATE, 2.5)
    for sy in (-1, 1):
        y0, y1 = sorted((sy * RAIL_Y[0], sy * RAIL_Y[1]))
        out += rbox(back, y0, 0, front - back, y1 - y0, BRIDGE + 0.01, 1.0)
    return out


def vtx_frame():
    """Posts beside the VTX's corners, the fan pads on top, the front stop."""
    out = Manifold()
    for sx in (-1, 1):
        for sy in (-1, 1):
            xs = sorted((vtx_x + sx * pocket, vtx_x + sx * (pocket - POST_L)))
            ys = sorted((sy * pocket, sy * (pocket + POST)))
            out += box(xs[0], ys[0], z0 - 0.01, xs[1], ys[1], z_fan)
            # Pad: from the post in over the VTX's corner, under the fan.
            xs = sorted((vtx_x + sx * pad_in, vtx_x + sx * pocket))
            ys = sorted((sy * pad_in, sy * (pocket + POST)))
            out += box(xs[0], ys[0], z_fan - PAD_T, xs[1], ys[1], z_fan)
            out -= cyl(vtx_x + sx * FAN_HOLES / 2, sy * FAN_HOLES / 2, z_fan - PAD_T - 1, z_fan + 1, FAN_PILOT / 2)
    # Front stop: a low wall between the front posts.
    out += box(vtx_x + pocket, -pocket - POST, z0 - 0.01, vtx_x + pocket + STOP, pocket + POST, z0 + 3.0)
    return out


def cradle():
    out = Manifold()
    for sy in (-1, 1):
        y0, y1 = sorted((sy * cheek_y, sy * (cheek_y + CHEEK_T)))
        out += box(pivot_x - CHEEK_L / 2, y0, z0 - 0.01, pivot_x + CHEEK_L / 2, y1, pivot_z)
        out += cyl(0, 0, 0, CHEEK_T, CHEEK_L / 2).rotate([90, 0, 0]).translate([pivot_x, y1, pivot_z])
    out -= cyl(0, 0, 0, 40, 1.1).rotate([90, 0, 0]).translate([pivot_x, 20, pivot_z])  # M2 pivots, both sides
    return out


def mount():
    return plate() + vtx_frame() + cradle()


# ---- stand-ins -------------------------------------------------------------------------
def vtx():
    return box(vtx_x - VTX_W / 2, -VTX_W / 2, z0, vtx_x + VTX_W / 2, VTX_W / 2, z0 + VTX_H)


def fan():
    out = box(vtx_x - FAN_W / 2, -FAN_W / 2, z_fan, vtx_x + FAN_W / 2, FAN_W / 2, z_fan + FAN_T)
    for sx in (-1, 1):
        for sy in (-1, 1):
            out -= cyl(vtx_x + sx * FAN_HOLES / 2, sy * FAN_HOLES / 2, z_fan - 1, z_fan + FAN_T + 1, 1.0)
    return out


def camera(tilt=0.0):
    return camera_at(pivot_x, tilt)


def channel():
    """The chassis' middle channel, its posts and wires: the plate's underside must clear it."""
    return box(back - 5, -MID_W / 2, -5, front + 5, MID_W / 2, BRIDGE - 0.01)


def main():
    os.makedirs(OUT, exist_ok=True)
    m = mount()
    if m.is_empty() or len(m.decompose()) != 1:
        sys.exit("mount: not a single solid")
    room = ROOM
    parts = {"VTX": vtx(), "fan": fan(), "camera": camera()}
    checks = {f"mount x {k}": (m ^ v).volume() for k, v in parts.items()}
    checks["VTX x fan"] = (vtx() ^ fan()).volume()
    checks["VTX x camera"] = (vtx() ^ camera()).volume()
    checks["mount x channel"] = (m ^ channel()).volume()
    # The VTX slides in from the back, under the pads.
    checks["mount x VTX's way in"] = (m ^ box(back - 40, -VTX_W / 2, z0, vtx_x + VTX_W / 2, VTX_W / 2, z0 + VTX_H)).volume()
    checks["fan not seated"] = 0.0 if (m ^ fan().translate([0, 0, -0.2])).volume() > 1 else 1.0
    # In the shell, with 0.5 mm to spare upwards and sideways.
    for k, v in {"mount": m, "VTX": vtx(), "fan": fan()}.items():
        for d in ([0, 0, 0.5], [0, 0.5, 0], [0, -0.5, 0]):
            checks[f"{k} outside the room {d}"] = (v.translate(d) - room).volume()
    tilts = []
    for t in range(TILT[0], TILT[1] + 1, 5):
        c = camera(t)
        if max((m ^ c).volume(), (vtx() ^ c).volume(), (fan() ^ c).volume(), camera_out(pivot_x, t)) < 0.01:
            tilts.append(t)
    for k, v in checks.items():
        if v > 0.01:
            print(f"{k}: {v:.2f} mm3")
    if max(checks.values()) > 0.01 or 0 not in tilts:
        sys.exit("clashes")
    print("all clear:", len(checks), "checks")
    print(f"camera tilts clear of the mount and the shell: {tilts[0]} .. {tilts[-1]} deg")

    to_trimesh(m).export(os.path.join(OUT, "x2201_fpv_mount.stl"))
    case, dark, grey = (0.62, 0.68, 0.76), (0.15, 0.17, 0.2), (0.55, 0.6, 0.66)
    stuff = [(vtx(), grey), (fan(), dark), (camera(0), dark)]
    preview([("loaded", [(m, case)] + stuff, 25, -60), ("under the liner (scan)", [(m, case), (liner_shell() ^ box(-30, 0, -10, 120, 60, 40), (0.3, 0.32, 0.36))] + stuff, 20, -110),
             ("from the side (front to the right)", [(m, case)] + stuff, 0, -90), ("mount alone", [(m, case)], 35, -40)],
            os.path.join(OUT, "x2201_fpv_preview.png"))
    lo, hi = m.bounding_box()[:3], m.bounding_box()[3:]
    print(f"mount: {hi[0]-lo[0]:.1f} long x {hi[1]-lo[1]:.1f} wide x {hi[2]-lo[2]:.1f} high, {m.volume()/1000:.1f} cm3")
    print(f"x from {back:.1f} to {front:.1f} (cage's back end = 0, windscreen foot = {L:.0f}); pivot x {pivot_x:.1f} z {pivot_z:.1f}")
    print(f"fan top {z_fan + FAN_T:.1f}; lens tip {pivot_x + CAM_L - CAM_PIVOT_BACK + LENS_L:.1f}")
    hx, slope = lens_hole()
    d = np.load(NPZ)
    print(f"lens hole in the liner: centre x {hx:.1f}, {L - hx:.1f} behind the windscreen's foot, z {pivot_z:.1f}; "
          f"windscreen {slope:.0f} deg from flat -> hole {LENS_D + 1:.0f} wide x {(LENS_D + 1) / max(np.sin(np.radians(slope)), 0.2):.0f} along the slope")


if __name__ == "__main__":
    main()
