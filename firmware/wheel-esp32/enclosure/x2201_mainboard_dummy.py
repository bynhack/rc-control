"""A printed stand-in for the X2201 main board, made straight from its KiCad
file (x2201_datum.BOARD_PCB), to try in the car before the board is made:
its outline, the two mounting holes, and a block for every part on it, with
an arrow on each side-entry connector to where its plug goes in (the plug
and its wire take another 6 to 8 that way).

Nothing is typed in from the board: the outline (Edge.Cuts), the holes
(every drilled pad) and each part's footprint (its body on F.Fab, else its
courtyard, else its silkscreen) come from the file, so a change there is a
re-run here. KiCad has no heights for most parts (no 3D models for the
side-entry JSTs or the SuperMini), so HEIGHTS gives them by footprint, and
EXTRA adds what the footprints don't draw (the SuperMini's USB-C).

Under the board only pins and wire joints stick out (~2): not modelled, as
the part prints flat. Every drilled pad is a hole through the board instead,
to see where they land. The front arrow is engraved underneath.

KiCad's Y runs down the screen, so the board's (X, Y) with z up is the board
mirrored: the STL is x = X, y = Ymax - Y (the front edge, KiCad Y = 0, at
the top), z up from the board's underside. Where it sits in the car: see
x2201_datum.py.

Print it board down. The USB-C hangs 2.2 past the rear edge (no support);
the EP2 hangs 7.4 past it: support it.

Run:  python x2201_mainboard_dummy.py  -> out/x2201_mainboard_dummy.stl, out/x2201_mainboard_dummy_preview.png
"""

import os
import re
import sys

from manifold3d import CrossSection, Manifold, OpType

from cad import OUT, box, cyl, preview, to_trimesh
from kicad_board import Board
from x2201_datum import BOARD_PCB, POST, board_to_chassis

PCB = 1.6
HOLE_ALLOWANCE = 0.1  # added to unplated (mounting) holes: printed holes come out small (3.6 -> 3.7 fitted)

# Height over the board's top, by footprint name (first match). Datasheet
# guesses; None = not a block (wire pads: holes only).
HEIGHTS = [
    (r"^JST_ZH_.*Horizontal", 3.5),
    (r"^JST_PH_.*Horizontal", 4.7),
    (r"^LED_D3\.0mm", 5.0),  # standing; bent toward the rear it's lower
    (r"^PinHeader_.*Vertical", 8.5),  # 2.5 plastic, 6 pin
    (r"^L_Changjiang_FXL0420", 2.0),
    (r"^C_1206", 1.6),
    (r"^C_0805", 1.25),
    (r"^R_0805", 0.6),
    (r"_0402_", 0.5),
    (r"^SOT-23", 1.2),
    (r"^D_SOD-323", 1.0),
    (r"^HTSSOP", 1.2),
    (r"^LGA-", 1.0),
    (r"^Diodes_PowerDI3333", 0.9),
    (r"^SolderWire", None),
]
# By reference, for footprints the board draws itself (no library name).
REF_HEIGHTS = {"U1": 3.5,  # the SuperMini: headers 2.5 + its PCB 1.0
               "J8": None}  # the EP2's 4 pads: holes only, the EP2 is in EXTRA
REF_SKIP = {"MH1", "MH2"}
# What the footprints don't draw, relative to that part's footprint origin
# (KiCad X, Y): (X0, Y0, X1, Y1, z0 and z1 over the board, the way it points).
EXTRA = {
    "U1": [(4.5, 16.3, 13.8, 25.7, 3.5, 6.7, (0, 1))],  # the SuperMini's USB-C, 2.2 past the rear edge
    # The EP2 receiver soldered on J8's pads on short pins, lying flat, hanging
    # past the rear edge for a clear RF path. MEASURE: ~10 x 10 (guess), 1 off
    # the board, 3 thick (modelled solid down to the board, so it prints in one
    # piece); centred across the 4 pads, from 1 in front of them.
    "J8": [(-1.19, -1.0, 8.81, 9.0, 0.0, 4.0, (0, 1))],
}

ENGRAVE = 0.5


def height(f):
    if f.ref in REF_HEIGHTS:
        return REF_HEIGHTS[f.ref]
    for pat, h in HEIGHTS:
        if re.search(pat, f.name):
            return h
    print(f"  {f.ref} ({f.name}): no height in HEIGHTS, 1.0 used", file=sys.stderr)
    return 1.0


def polygon(pts):
    area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1]))
    return CrossSection([pts if area > 0 else pts[::-1]])


def arrow(cx, cy, d, size, z, down=False):
    """An engraved arrow centred at (cx, cy), pointing d, in the top face at z
    (or in the bottom face at z when down)."""
    dx, dy = d
    px, py = -dy, dx
    s = size / 2
    pts = [(cx + dx * s, cy + dy * s), (cx - dx * s * 0.1 + px * s * 0.8, cy - dy * s * 0.1 + py * s * 0.8),
           (cx - dx * s * 0.1 + px * s * 0.3, cy - dy * s * 0.1 + py * s * 0.3),
           (cx - dx * s + px * s * 0.3, cy - dy * s + py * s * 0.3),
           (cx - dx * s - px * s * 0.3, cy - dy * s - py * s * 0.3),
           (cx - dx * s * 0.1 - px * s * 0.3, cy - dy * s * 0.1 - py * s * 0.3),
           (cx - dx * s * 0.1 - px * s * 0.8, cy - dy * s * 0.1 - py * s * 0.8)]
    return Manifold.extrude(polygon(pts), ENGRAVE + 1).translate([0, 0, z - 1 if down else z - ENGRAVE])


def plug_way(outline, board):
    """A side-entry connector's plug goes in from the board edge it is nearest."""
    xs, ys = [p[0] for p in outline], [p[1] for p in outline]
    bx, by = [p[0] for p in board], [p[1] for p in board]
    gaps = {(-1, 0): min(xs) - min(bx), (1, 0): max(bx) - max(xs), (0, -1): min(ys) - min(by), (0, 1): max(by) - max(ys)}
    return min(gaps, key=gaps.get)


def dummy(board):
    """The board in KiCad's (X, Y) with z up: mirrored, turn it with to_car()."""
    solid = [Manifold.extrude(polygon(board.outline), PCB)]
    cuts = []
    for f in board.footprints:
        for p in f.pads:
            if p["drill"]:
                d = p["drill"] + (HOLE_ALLOWANCE if p["kind"] == "np_thru_hole" else 0)
                cuts.append(cyl(*p["at"], -1, PCB + 0.5 if p["kind"] == "thru_hole" else 30, d / 2))
        if f.ref in REF_SKIP:
            continue
        for X0, Y0, X1, Y1, z0, z1, way in EXTRA.get(f.ref, []):
            ox, oy = f.at[0], f.at[1]
            solid.append(box(ox + X0, oy + Y0, PCB + z0 - 0.01, ox + X1, oy + Y1, PCB + z1))
            cuts.append(arrow(ox + (X0 + X1) / 2, oy + Y0 + 3.5, way, 5, PCB + z1))
        h = height(f)
        outline, _ = f.outline()
        if h is None or len(outline) < 3:
            continue
        solid.append(Manifold.extrude(polygon(outline), h + 0.01).translate([0, 0, PCB - 0.01]))
        xs, ys = [p[0] for p in outline], [p[1] for p in outline]
        if f.name.startswith("JST") and "Horizontal" in f.name:
            cuts.append(arrow((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, plug_way(outline, board.outline),
                              min(max(xs) - min(xs), max(ys) - min(ys)) - 1.5, PCB + h))
    bx, by = [p[0] for p in board.outline], [p[1] for p in board.outline]
    cuts.append(arrow((min(bx) + max(bx)) / 2, (min(by) + max(by)) / 2, (0, -1), 10, 0, down=True))  # the front
    return Manifold.batch_boolean(solid, OpType.Add) - Manifold.batch_boolean(cuts, OpType.Add)


def to_car(m, board):
    """KiCad (X, Y down) -> the STL's x = X, y = Ymax - Y."""
    return m.mirror([0, 1, 0]).translate([0, max(p[1] for p in board.outline), 0])


def main():
    board = Board(BOARD_PCB)
    d = to_car(dummy(board), board)
    os.makedirs(OUT, exist_ok=True)
    to_trimesh(d).export(os.path.join(OUT, "x2201_mainboard_dummy.stl"))
    grey = (0.25, 0.45, 0.3)
    preview([("from above, front to the top", [(d, grey)], 89, -90), ("from the front right", [(d, grey)], 35, 60),
             ("from the rear left (USB-C)", [(d, grey)], 35, -120), ("underneath", [(d, grey)], -60, -60)],
            os.path.join(OUT, "x2201_mainboard_dummy_preview.png"))
    lo, hi = d.bounding_box()[:3], d.bounding_box()[3:]
    print(f"dummy from {os.path.relpath(BOARD_PCB)}: {len(board.footprints)} footprints; "
          f"x {lo[0]:.2f}..{hi[0]:.2f}, y {lo[1]:.2f}..{hi[1]:.2f}, z 0..{hi[2]:.2f}; genus {d.genus()}")
    mh1, mh2 = board.ref("MH1").at[:2], board.ref("MH2").at[:2]
    post = board_to_chassis(*mh2, mh1)
    ok = abs(post[0] - POST[0]) < 0.05 and abs(post[1] - POST[1]) < 0.05
    print(f"MH2 on the chassis: {post[0]:.2f} ahead of the M2 boss, {-post[1]:.2f} to its right; "
          f"the datum's POST {POST[0]:.2f}, {-POST[1]:.2f}: {'OK' if ok else 'MISMATCH'}")
    if not ok:
        sys.exit("the board's MH2 is not over the datum's locating post")


if __name__ == "__main__":
    main()
