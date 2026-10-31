"""Fan-cooled mount for a Walksnail Avatar Ascent Lite+ VTX and its camera,
built as low as possible: it goes inside the car.

One part, vtx_mount.stl, printed floor down:
  - a frame with four corner posts around the VTX. There is no floor under
    the VTX: it goes into the frame from below and sits straight on the
    car's top deck, which saves the floor's thickness.
  - the 25 mm fan screws onto pads at the tops of the posts, so there is no
    separate cap plate. The pads sit inside the air gap over the VTX's
    corners; the sides stay open for the exhaust and the VTX's cables.
  - a tilting camera cradle in front and an antenna sleeve at the back.
  - the VTX has plugs and wires on three sides, so the floor ring around
    the pocket is a slot on every side, between the posts: the plugs and
    wire roots fold down into it as the VTX goes in from below. A thin bar
    round the outside holds the posts together.
  - two screw bosses on the centre line, one behind the frame and one in
    the cable gap in front, that bolt down through the deck's two slots.
    The deck is only 7 mm wide there, so the screws are 36 mm apart: one
    in each slot, the VTX over the bridge between them.

Hardware:
  4x M2 x 9 self-tapping   fan -> pads (FAN_T + PAD_T)
  2x M2 x 4                camera side holes, through the cradle cheeks
  2x M2 x 8 + nyloc nut    bosses -> through the deck slots, nuts underneath
  thermal pad (optional)   VTX bottom -> deck

Coordinates: VTX centred on x = y = 0, camera facing +y, deck along y,
z = up from the deck's top face.

Run:  python vtx_mount.py  -> out/vtx_mount.stl, out/vtx_preview.png,
      out/vtx_mount.html (design walkthrough, built from vtx_viewer.html)
"""

import base64
import json
import os
import sys

import numpy as np
from manifold3d import Manifold

from enclosure import OUT, box, cyl, preview, to_trimesh

FIT = 0.3

# ---- parts (given by the user) ---------------------------------------------------
VTX_W, VTX_H = 23.5, 8.0  # square
CAM_W, CAM_H = 14.0, 12.0  # camera body, across the cheeks x height
CAM_L = 12.0  # MEASURE: camera body depth behind the lens barrel
CAM_PIVOT_BACK = 6.0  # MEASURE: side screw hole to the back of the camera
LENS_D, LENS_L = 10.0, 6.0  # MEASURE: lens barrel
ANT_D = 3.5  # antenna, thickest part
FAN_W, FAN_HOLES = 25.0, 20.0
FAN_T = 7.0  # 2507 fan (the user's)

# ---- mount -----------------------------------------------------------------------
FLOOR = 1.5  # frame and camera floor; none under the VTX
AIR_GAP = 3.0  # VTX top to the fan's underside
PAD_T = 2.0  # fan pads at the post tops, inside the air gap
POST = 3.5  # corner posts: this far past the VTX pocket
BAR = 2.0  # floor bar round the outside of the cable slots, ties the posts together
FAN_PILOT = 1.7  # M2 self-tapping into the pads
CABLE_GAP = 9.0  # VTX front to the camera's back: room for the ribbon to bend
CHEEK_T, CHEEK_L = 2.0, 11.0
TILT_CLEAR = 3.0  # camera bottom above the floor when level
# Antenna sleeve: low on a rib behind the back-left post, a C that the
# antenna's thick end snaps into from behind; the coax leaves at the bottom.
ANT_WALL, ANT_SLIT = 1.2, 2.8  # slit narrower than the antenna: it snaps in
ANT_SLEEVE_H = 12.0
ANT_SLEEVE_Z0 = FLOOR + 4.0  # room under the sleeve for the coax to bend
MAST_T = 2.0
# Car top deck: a 7 mm strip with two 2 mm slots along it, the mount sits on top.
DECK_W, DECK_SLOT = 7.0, 2.0
DECK_T = 2.0  # MEASURE: plate thickness (only sets the screw length)
DECK_SLOTS = ((-30.0, -3.0), (9.0, 31.0))  # MEASURE: estimated from the photo, ~27 and ~22 long, 12 apart
DECK_HOLE = 2.4  # M2 through the boss, loose so it lines up with the slot
BOSS_R, BOSS_T = 2.5, 2.5  # under the screw head; the floor alone is 1.5

pocket = VTX_W / 2 + FIT  # half-width of the VTX pocket
outer = pocket + POST  # half-width of the post square
z_vtx_top = VTX_H
z_fan = z_vtx_top + AIR_GAP  # fan underside = post tops
pad_in = FAN_HOLES / 2 - 2.3  # pads reach this far in, enough to hold the fan screws
pivot_y = pocket + 1.0 + CABLE_GAP + CAM_PIVOT_BACK
pivot_z = FLOOR + TILT_CLEAR + CAM_H / 2
cheek_x = CAM_W / 2 + FIT  # inner face of each cheek
front = pivot_y + CHEEK_L / 2
ant_r_in = ANT_D / 2 + 0.15
ant_r_out = ant_r_in + ANT_WALL
ant_c = (-pocket, -(outer + 1.0 + ant_r_out))  # behind the back-left post
ant_z0, ant_top = ANT_SLEEVE_Z0, ANT_SLEEVE_Z0 + ANT_SLEEVE_H
# Just outside the cable slots, behind the frame and in the cable gap in front.
deck_screws = (-(outer + BOSS_R + 0.05), outer + BOSS_R + 0.05)


def mount():
    out = box(-outer - BAR, -outer - BAR, 0, outer + BAR, front, FLOOR)

    # Corner posts up to the fan, each with a pad reaching in over the VTX's
    # corner (PAD_T thick, under the fan) for the fan screw.
    for sx in (-1, 1):
        for sy in (-1, 1):
            xs = sorted((sx * (pocket - 2), sx * outer))
            ys = sorted((sy * (pocket - 2), sy * outer))
            out += box(xs[0], ys[0], 0, xs[1], ys[1], z_fan)
            xs = sorted((sx * pad_in, sx * outer))
            ys = sorted((sy * pad_in, sy * outer))
            pad = box(xs[0], ys[0], z_fan - PAD_T, xs[1], ys[1], z_fan)
            out += pad
    # The VTX pocket goes right through: the VTX stands on the roof.
    out -= box(-pocket, -pocket, -1, pocket, pocket, z_fan - PAD_T)
    # Cable slots: the floor ring between the posts, on all four sides, so
    # the VTX goes in whichever way round its plugs and wires need.
    out -= box(-(pocket - 2), -outer, -1, pocket - 2, outer, FLOOR + 1)
    out -= box(-outer, -(pocket - 2), -1, outer, pocket - 2, FLOOR + 1)
    for sx in (-1, 1):
        for sy in (-1, 1):
            out -= cyl(sx * FAN_HOLES / 2, sy * FAN_HOLES / 2, z_fan - PAD_T - 1, z_fan + 1, FAN_PILOT / 2)

    # Camera cradle: two cheeks, rounded on top, a pivot hole for each side screw.
    for sx in (-1, 1):
        x0, x1 = sorted((sx * cheek_x, sx * (cheek_x + CHEEK_T)))
        cheek = box(x0, pivot_y - CHEEK_L / 2, 0, x1, pivot_y + CHEEK_L / 2, pivot_z)
        cheek += Manifold.cylinder(x1 - x0, CHEEK_L / 2).rotate([0, 90, 0]).translate([x0, pivot_y, pivot_z])
        out += cheek
        out -= Manifold.cylinder(CHEEK_T + 2, 1.1).rotate([0, 90, 0]).translate([x0 - 1, pivot_y, pivot_z])
    # Floor between the cheeks dropped out so the camera can tilt further.
    out -= box(-cheek_x, pivot_y - CHEEK_L / 2 - 1, -1, cheek_x, front + 1, FLOOR + 1)

    # Antenna: foot on the floor (more 3M area), a rib from the corner post
    # to the sleeve, the slit facing backwards.
    ax, ay = ant_c
    out += box(ax - 4.0, ay - ant_r_out, 0, ax + 4.0, -outer, FLOOR)
    out += box(ax - MAST_T / 2, ay + ant_r_in, 0, ax + MAST_T / 2, -outer + 0.5, ant_top)
    out += cyl(ax, ay, ant_z0, ant_top, ant_r_out)
    out += cyl(ax, ay, ant_z0 - ANT_WALL - 0.2, ant_z0, ant_r_in, ant_r_out)  # chamfer: no overhang under the sleeve
    out -= cyl(ax, ay, ant_z0 - 3, ant_top + 1, ant_r_in)
    out -= box(ax - ANT_SLIT / 2, ay - ant_r_out - 1, ant_z0 - 3, ax + ANT_SLIT / 2, ay, ant_top + 1)

    # Deck screws: a boss on the centre line for each, the back one on a tab
    # that the floor grows to hold it.
    back = deck_screws[0]
    out += box(-DECK_W / 2, back - BOSS_R, 0, DECK_W / 2, -outer, FLOOR)
    for y in deck_screws:
        out += cyl(0, y, 0, BOSS_T, BOSS_R)
        out -= cyl(0, y, -1, BOSS_T + 1, DECK_HOLE / 2)
    return out


# ---- stand-ins for the checks and the preview ------------------------------------
def vtx():
    return box(-VTX_W / 2, -VTX_W / 2, 0, VTX_W / 2, VTX_W / 2, z_vtx_top)


def fan():
    return box(-FAN_W / 2, -FAN_W / 2, z_fan, FAN_W / 2, FAN_W / 2, z_fan + FAN_T)


def deck():
    slab = box(-DECK_W / 2, -45, -DECK_T, DECK_W / 2, 45, 0)
    for y0, y1 in DECK_SLOTS:
        slab -= box(-DECK_SLOT / 2, y0, -DECK_T - 1, DECK_SLOT / 2, y1, 1)
    return slab


def deck_screw(y):
    return cyl(0, y, -DECK_T - 2.0, BOSS_T, 1.0)  # M2 shank, through the boss, the deck and the nut


def antenna():
    ax, ay = ant_c
    return cyl(ax, ay, ant_z0, ant_z0 + 30, ANT_D / 2)  # thick end only; the coax drops below


def camera(tilt=0.0):
    body = box(-CAM_W / 2, -CAM_PIVOT_BACK, -CAM_H / 2, CAM_W / 2, CAM_L - CAM_PIVOT_BACK, CAM_H / 2)
    lens = Manifold.cylinder(LENS_L, LENS_D / 2).rotate([-90, 0, 0]).translate([0, CAM_L - CAM_PIVOT_BACK, 0])
    return (body + lens).rotate([tilt, 0, 0]).translate([0, pivot_y, pivot_z])


def tris_b64(m):
    mesh = m.to_mesh()
    verts = np.asarray(mesh.vert_properties, dtype=np.float32)[:, :3]
    return base64.b64encode(verts[np.asarray(mesh.tri_verts)].astype("<f4").tobytes()).decode("ascii")


def export_page(path, tilts):
    """Fills vtx_viewer.html with the meshes and numbers -> a standalone page."""
    m = mount()
    camera_local = camera(0).translate([0, -pivot_y, -pivot_z])  # the page tilts it about x
    data = {
        "parts": {name: tris_b64(p) for name, p in
                  [("mount", m), ("vtx", vtx()), ("fan", fan()), ("antenna", antenna()), ("camera", camera_local),
                   ("deck", deck())]},
        "pivot": [0, pivot_y, pivot_z],
        "tilt": [tilts[0], tilts[-1]],
        "z": {"vtx_top": z_vtx_top, "fan": z_fan, "fan_top": z_fan + FAN_T},
        "half": {"pocket": pocket, "outer": outer, "pad_in": pad_in},
        "antenna": [*ant_c, ant_z0, ant_top, ant_r_in],
        "screws": [[0, y, BOSS_T, BOSS_R] for y in deck_screws],
        "deck": {"w": DECK_W, "t": DECK_T, "spacing": deck_screws[1] - deck_screws[0]},
        "thick": {"floor": FLOOR, "pad_t": PAD_T, "post": POST, "cheek_t": CHEEK_T, "ant_wall": ANT_WALL, "air_gap": AIR_GAP,
                  "fan_t": FAN_T, "vtx_h": VTX_H, "boss_t": BOSS_T, "total": z_fan + FAN_T},
        "volume": m.volume() / 1000,
    }
    src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vtx_viewer.html")
    with open(src, encoding="utf-8") as f:
        page = f.read().replace("/*DATA*/null", json.dumps(data))
    with open(path, "w", encoding="utf-8") as f:
        f.write(page)


def main():
    os.makedirs(OUT, exist_ok=True)
    m = mount()
    if m.is_empty() or len(m.decompose()) != 1:
        sys.exit("mount: not a single solid")

    checks = {"mount x vtx": (m ^ vtx()).volume(), "mount x fan": (m ^ fan()).volume(),
              "mount x antenna": (m ^ antenna()).volume(), "fan x antenna": (fan() ^ antenna()).volume(),
              "mount x deck": (m ^ deck()).volume(), "vtx x deck": (vtx() ^ deck()).volume()}
    # Each deck screw has to pass through a slot, not the metal.
    for y in deck_screws:
        checks[f"screw y={y:.1f} hits deck"] = (deck_screw(y) ^ deck()).volume()
        checks[f"screw y={y:.1f} hits mount"] = (deck_screw(y) ^ m).volume()
    # The fan has to sit on the pads, not hang in the air.
    checks["fan not seated"] = 0.0 if (m ^ fan().translate([0, 0, -0.2])).volume() > 1 else 1.0
    tilts = []
    for t in range(-40, 41, 5):
        cam = camera(t)
        if max((m ^ cam).volume(), (vtx() ^ cam).volume(), (fan() ^ cam).volume()) < 0.01:
            tilts.append(t)
    for k, v in checks.items():
        print(f"{k}: {v:.3f}")
    print(f"camera tilts clear: {tilts[0]} .. {tilts[-1]} deg" if tilts else "camera hits at every tilt")
    if max(checks.values()) > 0.01 or 0 not in tilts:
        sys.exit("parts overlap")

    to_trimesh(m).export(os.path.join(OUT, "vtx_mount.stl"))
    for stale in ("vtx_base.stl", "vtx_cap.stl"):  # the two-part version
        if os.path.exists(os.path.join(OUT, stale)):
            os.remove(os.path.join(OUT, stale))
    case, part, dark = (0.62, 0.68, 0.76), (0.40, 0.46, 0.55), (0.15, 0.17, 0.2)
    preview(
        [
            ("assembled", [(m, case), (vtx(), part), (fan(), dark), (antenna(), dark), (camera(-15), dark), (deck(), part)], 25, -55),
            ("assembled, back", [(m, case), (vtx(), part), (fan(), dark), (antenna(), dark), (camera(-15), dark), (deck(), part)], 25, 130),
            ("mount", [(m, case)], 40, -55),
            ("mount, from below", [(m, case)], -50, -55),
        ],
        os.path.join(OUT, "vtx_preview.png"),
    )
    export_page(os.path.join(OUT, "vtx_mount.html"), tilts)
    lo, hi = m.bounding_box()[:3], m.bounding_box()[3:]
    print(f"mount: {hi[0]-lo[0]:.1f} x {hi[1]-lo[1]:.1f} x {hi[2]-lo[2]:.1f} mm, volume {m.volume()/1000:.1f} cm3")
    print(f"deck screws at y = {deck_screws[0]:.2f}, {deck_screws[1]:.2f} ({deck_screws[1] - deck_screws[0]:.1f} apart)")
    print(f"installed height: fan top {z_fan + FAN_T:.1f} mm, camera cheeks {pivot_z + CHEEK_L / 2:.1f} mm, antenna sleeve {ant_top:.1f} mm")


if __name__ == "__main__":
    main()
