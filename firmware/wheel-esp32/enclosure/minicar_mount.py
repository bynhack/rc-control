"""Carrier for the 1:28 rally car's FPV and radio parts, inside the shell, on
the chassis' top deck (the copper plate), in the room the test cage
(minicar_cage.py) describes: 68 long, the roof 27 over the deck at the front
and 30 at the back, 70 wide low down, 60, then 48 under the roof.

Two parts, printed flat, no support:
minicar_mount.stl
  - a 2 mm plate on the deck, two countersunk M2 slots on its centre line
    (slots, as the deck's holes are not measured yet); its front left corner
    cut away, beside the camera, for the battery;
  - at the back, the Walksnail VTX: it drops in from above and sits on the
    plate, held at its four corners by right-angle posts, its cables out
    between them;
  - in front of it, a flat bed for the brushed ESC (3M tape), a little to
    the right, clear of the battery;
  - at the front, the camera between two cheeks, looking out through the
    cut-away windscreen, its tilt set on the M2 side screws;
  - on the right beside the VTX, a flat for the ELRS receiver (tape; its
    tower antenna is on it);
  - on the left side, a tab that holds the ESC's power switch, its slider
    out through a slot in the shell's side.
minicar_fan_cap.stl
  - a square frame over the posts, screwed to their tops after the VTX is
    in; the 25 mm fan screws onto it and blows down through it.

Hardware:
  2x M2 x 6 + hex nut      plate -> deck, countersunk in the plate, nuts under the deck
  4x M2 x 8 self-tapping   fan cap -> posts
  4x M2 x 9 self-tapping   fan -> fan cap
  2x M2 x 4                camera side holes
  2x M2 x 4 self-tapping   switch ears -> tab
  3M tape                  ESC, receiver

Coordinates: x = forward (the front at x = L), y = left, z = up from the
deck's top face.

Run:  python minicar_mount.py  -> out/minicar_mount.stl, out/minicar_mount_preview.png,
      out/minicar_assembly.html (3D assembly, built from minicar_viewer.html)
"""

import json
import os
import sys

import numpy as np
from manifold3d import CrossSection, Manifold, OpType

from cad import OUT, box, cyl, preview, rbox, rrect, to_trimesh
from p4_case import tris_b64
from minicar_cage import H_FRONT, H_REAR, L, W_LOW, W_ROOF, W_SLOPE, Z_LOW, Z_SLOPE
from vtx_mount import (CAM_H, CAM_L, CAM_PIVOT_BACK, CAM_W, FAN_HOLES, FAN_T, FAN_W, LENS_D, LENS_L, VTX_H, VTX_W)

FIT = 0.3
PLATE = 2.0
PLATE_W = 56.0  # the plate's width, less where it needs to reach out
# VTX and fan, at the back.
AIR_GAP = 2.5  # VTX top to the cap's underside, room for the antenna's IPEX plug; the fan is a cap's thickness higher
CAP_T = PLATE  # as thick as the plate
POST = 4.0  # leaves an M2 pilot a wall of over 1 mm
GRIP_L = 6.0  # the posts' arms along the VTX's sides from each corner, as thick as the posts
GRIP_R = 0.8  # the arms' ends rounded; the outside corner is round about the screw's pilot, like the cap
FAN_PILOT = 1.7  # M2 self-tapping, fan -> cap
POST_PILOT, CAP_HOLE = 1.7, 2.3  # M2 self-tapping, cap -> posts
vtx_c = (0.5 + VTX_W / 2 + FIT + POST, 0.0)  # its centre: the posts at the plate's back edge
pocket = VTX_W / 2 + FIT
outer = pocket + POST
z_cap = PLATE + VTX_H + AIR_GAP  # post tops = the cap's underside
z_fan = z_cap + CAP_T  # fan underside
# ESC (taped), in front of the VTX.
ESC = (23.0, 30.0, 8.0)  # along x, across, high (measured)
esc_x0 = vtx_c[0] + outer + 0.3
ESC_Y = -4.5  # its centre, moved right: clear of the battery
# Camera, at the front.
CHEEK_T = 3.0  # nothing else beside the camera: thick for stiffness
PIVOT_Z = 18.0  # camera's middle over the deck: in the windscreen's opening, over the ESC's front end
TILT = (-10, 10)
pivot_x = L - LENS_L - (CAM_L - CAM_PIVOT_BACK) + 5.0  # the lens 5 out past the room's front (the windscreen is cut away)
cheek_y = CAM_W / 2 + FIT
# Receiver (taped).
RX = (17.0, 10.5, 3.0)
# Power switch (measured): body through the tab, ears screwed to its inside.
SW = (11.5, 6.6)
SW_PITCH = 15.5
TAB_T = 2.5  # the switch's tab: the ears' M2 self-tapping screws bite 2.5
sw_x = esc_x0 + ESC[0] / 2
SW_Z = PLATE + SW[1] / 2 + 1.0  # low: the shell's side steps in above Z_LOW
DECK_SLOTS = ((6.0, 18.0), (46.0, 58.0))  # x from-to of the two M2 slots
# The battery's room: the plate's front left corner, from the front posts to
# the front, beside the camera's left cheek, kept clear of everything.
BATT_X0 = 36.0
BATT_Y0 = cheek_y + CHEEK_T + 1.0


def roof(x):
    return H_REAR + (H_FRONT - H_REAR) * x / L


def room():
    """The room in the shell (from the cage), a little inset for clearance."""
    half = [(W_LOW / 2, Z_LOW), (W_SLOPE / 2, Z_SLOPE), (W_ROOF / 2, H_REAR)]
    prof = CrossSection([[(-W_LOW / 2, 0.0), (W_LOW / 2, 0.0)] + half + [(-y, z) for y, z in reversed(half)]]).offset(-0.5)
    m = Manifold.extrude(prof, L + 20).transform(np.array([[0, 0, 1, -10], [1, 0, 0, 0], [0, 1, 0, 0]]))
    sloped = Manifold.hull_points([(x, y, z) for x in (-10.0, L + 10) for y in (-50.0, 50.0) for z in (-10.0, roof(x) - 0.5)])
    return (m ^ sloped ^ box(0, -50, -10, L, 50, 50)) + box(0, -W_LOW / 2, -1, L, W_LOW / 2, 0.5)  # the deck is its floor


def plate():
    out = rbox(0, -PLATE_W / 2, 0, L, PLATE_W, PLATE, 3.0)
    out += rbox(sw_x - 12, -W_LOW / 2 + 0.6, 0, 24, 10, PLATE, 2.0)  # out to the switch tab
    for x0, x1 in DECK_SLOTS:
        out -= Manifold.batch_hull([cyl(x, 0, -1, PLATE + 1, 1.15) for x in (x0, x1)])
        out -= Manifold.batch_hull([cyl(x, 0, PLATE - 1.0, PLATE + 0.01, 1.15, 2.15) for x in (x0, x1)])  # countersunk
    out -= rbox(BATT_X0, BATT_Y0, -1, L + 10 - BATT_X0, 30.0, PLATE + 2, 2.0)  # the battery's corner
    return out


def post_xy():
    cx, cy = vtx_c
    m = pocket + POST / 2
    return [(cx + sx * m, cy + sy * m) for sx in (-1, 1) for sy in (-1, 1)]


def vtx_frame():
    """Four corner posts: each a right angle round one of the VTX's corners,
    POST thick, its arms GRIP_L along the VTX's sides, the outside rounded;
    an M2 pilot in the corner's top for the cap. The sides between them
    stay open for the cables."""
    cx, cy = vtx_c
    p, q = pocket, pocket + POST
    ell = CrossSection.square([q - (p - GRIP_L), POST]).translate([p - GRIP_L, p]) + \
        CrossSection.square([POST, q - (p - GRIP_L)]).translate([p, p - GRIP_L])
    m = p + POST / 2  # the pilot's centre
    ell = ell - CrossSection.square([q - m + 1, q - m + 1]).translate([m, m]) + CrossSection.circle(POST / 2, 40).translate([m, m])
    ell = ell.offset(-GRIP_R).offset(GRIP_R)  # and the arms' ends
    out = Manifold()
    for sx in (-1, 1):
        for sy in (-1, 1):
            corner = Manifold.extrude(ell.scale([sx, sy]), z_cap).translate([cx, cy, 0])
            out += corner
    for x, y in post_xy():
        out -= cyl(x, y, z_cap - 5, z_cap + 1, POST_PILOT / 2)
    return out


def fan_cap():
    """Square frame on the posts: corners screwed to them, the fan's holes in its sides."""
    cx, cy = vtx_c
    e = outer + 1.5  # 2 mm of cap round the corner holes; at the back only to the room's end
    out = rbox(0.0, cy - e, z_cap, cx + e, 2 * e, CAP_T, 2.5)
    out -= rbox(cx - 7.5, cy - 7.5, z_cap - 1, 15, 15, CAP_T + 2, 3.0)  # the air
    for x, y in post_xy():
        out -= cyl(x, y, z_cap - 1, z_cap + CAP_T + 1, CAP_HOLE / 2)  # M2 pan head on top
    for sx in (-1, 1):
        for sy in (-1, 1):
            out -= cyl(cx + sx * FAN_HOLES / 2, cy + sy * FAN_HOLES / 2, z_cap - 1, z_cap + CAP_T + 1, FAN_PILOT / 2)
    return out


def cradle():
    out = Manifold()
    for sy in (-1, 1):
        y0, y1 = sorted((sy * cheek_y, sy * (cheek_y + CHEEK_T)))
        cheek = box(pivot_x - 5, y0, 0, pivot_x + 5, y1, PIVOT_Z) + cyl(0, 0, 0, CHEEK_T, 5).rotate([90, 0, 0]).translate([pivot_x, y1, PIVOT_Z])
        out += cheek
    out -= cyl(0, 0, 0, 40, 1.1).rotate([90, 0, 0]).translate([pivot_x, 20, PIVOT_Z])  # M2 pivots, both sides
    return out


def switch_tab():
    y_out = -W_LOW / 2 + 0.6
    # Outline in (x, z): its top corners round, and a slot open at the top
    # (the switch drops in, its ears on the tab's inside), its lips round too.
    h = Z_LOW - 0.6
    out2 = rrect(24.0, h + 3.0, 3.0).translate([sw_x - 12, -3.0])
    out2 -= CrossSection.square([SW[0] + 0.4, h]).translate([sw_x - SW[0] / 2 - 0.2, SW_Z - SW[1] / 2 - 0.2])
    out2 = out2.offset(-1.0).offset(1.0) ^ CrossSection.square([100.0, 50.0]).translate([sw_x - 50, 0.0])  # only from the plate up
    tab = Manifold.extrude(out2, TAB_T).transform(np.array([[1, 0, 0, 0], [0, 0, -1, y_out + TAB_T], [0, 1, 0, 0]]))
    for sx in (-1, 1):
        tab -= cyl(0, 0, 0, 5, 0.75).rotate([-90, 0, 0]).translate([sw_x + sx * SW_PITCH / 2, y_out - 1, SW_Z])
    return tab


def mount():
    out = plate() + vtx_frame() + cradle() + switch_tab()
    return out


# ---- stand-ins -------------------------------------------------------------------
def vtx():
    cx, cy = vtx_c
    return box(cx - VTX_W / 2, cy - VTX_W / 2, PLATE, cx + VTX_W / 2, cy + VTX_W / 2, PLATE + VTX_H)


def fan():
    cx, cy = vtx_c
    out = box(cx - FAN_W / 2, cy - FAN_W / 2, z_fan, cx + FAN_W / 2, cy + FAN_W / 2, z_fan + FAN_T)
    for sx in (-1, 1):
        for sy in (-1, 1):
            out -= cyl(cx + sx * FAN_HOLES / 2, cy + sy * FAN_HOLES / 2, z_fan - 1, z_fan + FAN_T + 1, 1.0)
    return out


def esc():
    return box(esc_x0, ESC_Y - ESC[1] / 2, PLATE, esc_x0 + ESC[0], ESC_Y + ESC[1] / 2, PLATE + ESC[2])


def rx():
    x0 = vtx_c[0] - outer + 2.0
    return box(x0, outer + 1.0, PLATE, x0 + RX[0], outer + 1.0 + RX[1], PLATE + RX[2])


def camera(tilt=0.0):
    body = box(-CAM_PIVOT_BACK, -CAM_W / 2, -CAM_H / 2, CAM_L - CAM_PIVOT_BACK, CAM_W / 2, CAM_H / 2)
    lens = cyl(0, 0, 0, LENS_L, LENS_D / 2).rotate([0, 90, 0]).translate([CAM_L - CAM_PIVOT_BACK, 0, 0])
    return (body + lens).rotate([0, -tilt, 0]).translate([pivot_x, 0, PIVOT_Z])


def switch():
    y_out = -W_LOW / 2 + 0.6
    body = box(sw_x - SW[0] / 2, y_out - 2.0, SW_Z - SW[1] / 2, sw_x + SW[0] / 2, y_out + TAB_T + 5.0, SW_Z + SW[1] / 2)
    ears = box(sw_x - SW_PITCH / 2 - 2.5, y_out + TAB_T, SW_Z - SW[1] / 2, sw_x + SW_PITCH / 2 + 2.5, y_out + TAB_T + 0.8, SW_Z + SW[1] / 2)
    return body + ears


def battery_room():
    """The battery's corner, from the deck's level up, within the room."""
    return rbox(BATT_X0, BATT_Y0, -1, L + 10 - BATT_X0, 30.0, 31, 2.0) ^ room()  # its corner round like the plate's cut


def deck():
    """Stand-in for the copper top deck under the plate."""
    return box(-15, -10, -1.5, L + 15, 10, 0)


STEPS = [
    ["載板鎖到二樓板", "2 顆 M2×6 沉頭穿過載板中線的兩條槽，螺母在二樓板下面。先鎖這兩顆，圖傳和電調會蓋住它們。"],
    ["放圖傳", "圖傳主機從上面直接放進車尾的四根角柱中間，坐在載板上；排線、天線線和 V G R T 線從柱子之間出去。"],
    ["蓋風扇座", "風扇座蓋在四根柱頂上，4 顆 M2×8 自攻鎖住；風扇再用 4 顆 M2×9 自攻鎖在風扇座上，往下吹。"],
    ["貼電調", "電調用 3M 膠平貼在中間。"],
    ["裝攝像頭", "攝像頭放進車頭兩片側板中間，M2×4 從兩側鎖進側孔當轉軸；俯仰調好再鎖緊。"],
    ["貼接收機", "ELRS 接收機用 3M 膠貼在圖傳右邊，它的塔式天線直接立著，不用另外拉天線。"],
    ["放開關", "開關從上面放進左側的槽，撥桿朝外，耳朵用 M2 自攻鎖在槽板內側。"],
    ["蓋車殼", "半透明的外框是車殼裡能用的空間：所有東西都在裡面，只有鏡頭從剪掉的擋風玻璃伸出去、開關撥桿從側面伸出去。"],
]
LABELS = {"fan cap": "風扇座", "VTX's way in": "圖傳放進去的路徑", "mount": "載板", "VTX": "圖傳", "fan": "風扇", "ESC": "電調", "receiver": "接收機", "switch": "開關",
          "camera": "攝像頭", "camera body": "攝像頭機身"}


def label(key):
    """'mount x camera +5' -> Chinese, for the page."""
    out = key
    for k in sorted(LABELS, key=len, reverse=True):
        out = out.replace(k, LABELS[k])
    return out.replace(" x ", " × ").replace(" outside the room", " 超出空間")


def export_page(path, m, checks):
    parts = [
        ("deck", "二樓板（替身）", deck(), 0xb07a4a, [], 1.0),
        ("mount", "載板", m, 0x8fa3b5, [(0, [0, 0, 40])], 1.0),
        ("vtx", "圖傳主機", vtx(), 0x9aa3ad, [(1, [0, 0, 30])], 1.0),
        ("cap", "風扇座", fan_cap(), 0x8fa3b5, [(2, [0, 0, 30])], 1.0),
        ("fan", "風扇", fan(), 0x23282f, [(2, [0, 0, 45])], 1.0),
        ("esc", "電調", esc(), 0xb3312f, [(3, [0, 0, 30])], 1.0),
        ("camera", "攝像頭", camera(0), 0x2b3038, [(4, [0, 0, 30])], 1.0),
        ("rx", "ELRS 接收機", rx(), 0x3b5bab, [(5, [0, 0, 25])], 1.0),
        ("switch", "電源開關", switch(), 0x1d2228, [(6, [0, 0, 25])], 1.0),
        ("battery", "電池空間（留空）", battery_room(), 0x4caf6a, [], 0.35),
        ("room", "車殼內空間", room(), 0xcfe3f2, [(7, [0, 0, 60])], 0.18),
    ]
    data = {
        "parts": [{"name": n, "label": lb, "tris": tris_b64(g), "color": c, "moves": mv, "opacity": op} for n, lb, g, c, mv, op in parts],
        "checks": {label(k): round(v, 3) for k, v in checks.items()},
        "steps": STEPS,
        "centre": [L / 2, 0, 12],
        "views": {"back": [-70, 90, 80], "front": [150, -60, 50], "side": [L / 2, -140, 30], "below": [L / 2 + 1, 0, 160]},
        "pivot": [pivot_x, 0, PIVOT_Z],
        "tilt": list(TILT),
    }
    src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "minicar_viewer.html")
    with open(src, encoding="utf-8") as f:
        page = f.read().replace("/*DATA*/null", json.dumps(data))
    with open(path, "w", encoding="utf-8") as f:
        f.write(page)


def main():
    os.makedirs(OUT, exist_ok=True)
    m = mount()
    if m.is_empty() or len(m.decompose()) != 1:
        sys.exit("mount: not a single solid")
    parts = {"VTX": vtx(), "fan": fan(), "ESC": esc(), "receiver": rx(), "switch": switch(), "fan cap": fan_cap()}
    checks = {f"mount x {k}": (m ^ v).volume() for k, v in parts.items()}
    # The VTX must go in from straight above with the cap off.
    cx, cy = vtx_c
    for k, v in {"mount": m, "ESC": esc(), "camera": camera(TILT[0]) + camera(TILT[1])}.items():
        checks[f"{k} x battery"] = (v ^ battery_room()).volume()
    checks["mount x VTX's way in"] = (m ^ box(cx - VTX_W / 2, cy - VTX_W / 2, PLATE, cx + VTX_W / 2, cy + VTX_W / 2, 60)).volume()
    for t in range(TILT[0], TILT[1] + 1, 5):
        c = camera(t)
        checks[f"mount x camera {t:+d}"] = (m ^ c).volume()
        checks[f"ESC x camera {t:+d}"] = (esc() ^ c).volume()
    names = list(parts)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            checks[f"{a} x {b}"] = (parts[a] ^ parts[b]).volume()
    r = room()
    outside = {"mount": m, **parts, "camera body": camera(0) ^ box(-50, -50, -50, L, 50, 50)}
    for k, v in outside.items():
        if k == "switch":
            continue  # its slider goes out through the shell
        checks[f"{k} outside the room"] = (v - r).volume()
    bad = {k: v for k, v in checks.items() if v > 0.01}
    for k, v in checks.items():
        if v > 0.01:
            print(f"{k}: {v:.2f} mm3")
    if bad:
        sys.exit("clashes")
    print("all clear:", len(checks), "checks")
    to_trimesh(m).export(os.path.join(OUT, "minicar_mount.stl"))
    to_trimesh(fan_cap().translate([0, 0, -z_cap])).export(os.path.join(OUT, "minicar_fan_cap.stl"))
    case, dark = (0.62, 0.68, 0.76), (0.18, 0.2, 0.24)
    stuff = [(vtx(), (0.55, 0.6, 0.66)), (fan(), dark), (fan_cap(), case), (esc(), (0.7, 0.2, 0.2)), (rx(), (0.3, 0.4, 0.7)), (camera(0), dark), (switch(), dark)]
    preview([("loaded", [(m, case)] + stuff, 25, -60), ("from the front", [(m, case)] + stuff, 15, 20),
             ("in the room", [(m, case), (r, (0.85, 0.9, 0.95))], 20, -120), ("mount alone", [(m, case)], 35, -40)],
            os.path.join(OUT, "minicar_mount_preview.png"))
    export_page(os.path.join(OUT, "minicar_assembly.html"), m, checks)
    lo, hi = m.bounding_box()[:3], m.bounding_box()[3:]
    print(f"mount: {hi[0]-lo[0]:.0f} x {hi[1]-lo[1]:.0f} x {hi[2]-lo[2]:.0f} mm, {m.volume()/1000:.1f} cm3; fan top {z_fan + FAN_T:.1f} under a {roof(vtx_c[0]):.1f} roof")


if __name__ == "__main__":
    main()
