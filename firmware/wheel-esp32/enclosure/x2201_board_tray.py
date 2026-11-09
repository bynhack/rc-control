"""Tray for the Geeks X2201's own receiver / ESC board, on the chassis' two
diagonal screw bosses (42 mm apart, centre to centre).

The bosses don't line up with the board's holes, so the tray screws onto
the bosses and the board clips into the tray: two fixed lips with end stops
at the corners of the board's plain long edge, three snap hooks on the
connector edge, in the gaps between the connectors. Tilt the board, slide
its plain edge under the lips, push the connector edge down past the hooks.
The board sits on two thin rails along its long edges, SEAT_H over the
plate, so its solder pins and the two screw heads stay clear under it:
screw the tray down first, then clip the board in. Both ends are open for
the wires.

Board sizes are measured off a photo (the 2-pin XH housings, 9.9 mm wide,
as the scale): MEASURE them, and the bosses' offsets along and across the
board, before printing. Only the 42 mm diagonal is known.

One part, x2201_board_tray.stl, printed plate down, no support (the lips
and catches overhang under 1 mm). PETG: the hooks flex ~2 %, PLA may crack.

Coordinates: x = along the board (centred on the bosses' midpoint), y =
across (the connector edge at -y), z = up from the bosses' tops.

Run:  python x2201_board_tray.py  -> out/x2201_board_tray.stl, out/x2201_board_tray_preview.png
"""

import os
import sys

import numpy as np
from manifold3d import CrossSection, Manifold

from cad import OUT, box, cyl, preview, rbox, to_trimesh

# ---- chassis bosses ----------------------------------------------------------------
BOSS_GAP = 42.0  # centre to centre (measured)
BOSS_DX = 39.0  # MEASURE: their offset along the board; across is what's left of 42
BOSS_DY = float(np.sqrt(BOSS_GAP**2 - BOSS_DX**2))
BOSS_SIGN = 1  # +1: the +x boss is on the plain (+y) side; -1 mirrors the diagonal
SCREW_R = 1.1  # M2 self-tapping clearance; use the car's screws, 2 mm longer than before
PAD_R, PAD_H = 3.2, 1.5  # pads under the plate on the bosses, so it clears whatever lies between

# ---- the board (MEASURE) -----------------------------------------------------------
BL, BW, PCB_T = 85.0, 22.0, 1.6
BOARD_DX, BOARD_DY = 0.0, 0.0  # board centre from the bosses' midpoint
# Connectors on the -y edge, x from the board's left end, for the preview and the hooks' gaps.
CONNS = [(0.0, 9.0), (18.5, 36.5), (43.0, 52.5), (54.0, 61.0)]
HOOKS_X = [13.5, 39.7, 73.0]  # hook centres, x from the board's left end, in those gaps

# ---- tray ----------------------------------------------------------------------------
PT = 2.0  # plate
SEAT_H = 3.5  # plate top to the board's underside
RAIL_W = 1.2  # rails under the board's long edges (MEASURE: pins near the edge)
FIT = 0.25  # clearance round the board
LIP, LIP_T, LIP_TH, LIP_L = 0.9, 2.0, 1.2, 7.0  # fixed lips: overhang, wall, thickness, length
HOOK_W, ARM_T, CATCH, GAP = 5.0, 1.0, 0.5, 0.6  # snap hooks: width, arm, catch, slot to the plate
R = 2.0

Z0 = PAD_H + PT  # plate top
ZB = Z0 + SEAT_H  # board underside
ZT = ZB + PCB_T  # board top


def board_x(x):
    """x from the board's left end -> tray x."""
    return BOARD_DX - BL / 2 + x


def bosses():
    return [(BOSS_DX / 2, BOSS_SIGN * BOSS_DY / 2), (-BOSS_DX / 2, -BOSS_SIGN * BOSS_DY / 2)]


def along_x(profile, x0, x1):
    """A (u, z) profile, u outward from the board's -y edge, from x0 to x1."""
    cs = CrossSection([profile])
    m = Manifold.extrude(cs, x1 - x0).transform(np.array([[0, 0, 1, x0], [-1, 0, 0, 0], [0, 1, 0, 0]]))
    return m.translate([0, BOARD_DY - BW / 2, 0])


def hook(xc):
    """Arm outside the -y edge, joined to the plate only by a foot at the
    bottom (a slot either side of it), so it flexes over its full height."""
    u0, u1 = FIT, FIT + ARM_T
    z_catch = ZT + 0.1
    lead = (CATCH + FIT) * 1.3
    prof = [(u1, 0.0 + PAD_H), (u1, z_catch + lead), (u0, z_catch + lead), (-CATCH, z_catch), (u0, z_catch),
            (u0, PAD_H + 0.8), (-GAP - 0.5, PAD_H + 0.8), (-GAP - 0.5, PAD_H)]
    return along_x(prof, xc - HOOK_W / 2, xc + HOOK_W / 2)


def lip(x0, x1, stop_at):
    """Fixed lip over the +y edge from x0 to x1, with an end stop at stop_at (x0 or x1)."""
    y_edge = BOARD_DY + BW / 2
    out = box(x0, y_edge + FIT, Z0 - 0.5, x1, y_edge + FIT + LIP_T, ZT + 0.2 + LIP_TH)
    out += box(x0, y_edge - LIP, ZT + 0.2, x1, y_edge + FIT, ZT + 0.2 + LIP_TH)
    end = BOARD_DX + (BL / 2 + FIT if stop_at > 0 else -BL / 2 - FIT - LIP_T)
    out += box(end, y_edge - 6.0, Z0 - 0.5, end + LIP_T, y_edge + FIT + LIP_T, ZT)
    return out


def tray():
    y_lo = BOARD_DY - BW / 2 - GAP  # the plate stops short of the hooks
    y_hi = BOARD_DY + BW / 2 + FIT + LIP_T
    x_lo, x_hi = BOARD_DX - BL / 2 - FIT - LIP_T, BOARD_DX + BL / 2 + FIT + LIP_T
    out = rbox(x_lo, y_lo, PAD_H, x_hi - x_lo, y_hi - y_lo, PT, R)
    for x, y in bosses():
        out += cyl(x, y, 0.0, PAD_H + 0.01, PAD_R)
    # Rails under the long edges.
    for y in (BOARD_DY - BW / 2, BOARD_DY + BW / 2 - RAIL_W):
        out += box(BOARD_DX - BL / 2, y, Z0 - 0.5, BOARD_DX + BL / 2, y + RAIL_W, ZB)
    out += lip(BOARD_DX - BL / 2 - FIT, BOARD_DX - BL / 2 + LIP_L, -1)
    out += lip(BOARD_DX + BL / 2 - LIP_L, BOARD_DX + BL / 2 + FIT, 1)
    for x in HOOKS_X:
        xc = board_x(x)
        # Rail and plate cleared round the arm, so it bends from its foot.
        out -= box(xc - HOOK_W / 2 - 0.5, BOARD_DY - BW / 2 - GAP, PAD_H + 0.8, xc + HOOK_W / 2 + 0.5,
                   BOARD_DY - BW / 2 + 0.01, ZB + 1)
        out += hook(xc)
    for x, y in bosses():
        out -= cyl(x, y, -1.0, ZB, SCREW_R)
    return out


def stand_in():
    """The board, its connectors on the -y edge and the battery board on top."""
    x0, y0 = BOARD_DX - BL / 2, BOARD_DY - BW / 2
    pcb = box(x0, y0, ZB, x0 + BL, y0 + BW, ZT)
    parts = Manifold()
    for a, b in CONNS:
        parts += box(x0 + a, y0, ZT, x0 + b, y0 + 6.0, ZT + 7.0)
    parts += box(x0 + 9.0, y0 + BW - 9.0, ZT, x0 + 18.0, y0 + BW - 7.5, ZT + 10.0)  # battery board, standing
    parts += box(x0 + 2.0, y0 + BW - 9.0, ZT, x0 + 9.0, y0 + BW - 2.0, ZT + 2.5)  # MOSFET
    return pcb, parts


def main():
    os.makedirs(OUT, exist_ok=True)
    t = tray()
    if t.is_empty() or len(t.decompose()) != 1:
        sys.exit("tray: not a single solid")
    pcb, parts = stand_in()
    if (t ^ pcb).volume() > 0.01:
        print(f"warning: the tray cuts into the board ({(t ^ pcb).volume():.2f} mm3)")
    if (t ^ parts).volume() > 0.01:
        print(f"warning: a hook or lip hits a connector ({(t ^ parts).volume():.2f} mm3)")
    to_trimesh(t).export(os.path.join(OUT, "x2201_board_tray.stl"))
    grey, green, white = (0.62, 0.68, 0.76), (0.1, 0.55, 0.3), (0.92, 0.88, 0.8)
    with_board = [(t, grey), (pcb, green), (parts, white)]
    preview([("tray", [(t, grey)], 35, -60), ("with the board", with_board, 35, -60),
             ("from above", [(t, grey)], 89, -90), ("connector edge (hooks)", with_board, 10, -90)],
            os.path.join(OUT, "x2201_board_tray_preview.png"))
    lo, hi = t.bounding_box()[:3], t.bounding_box()[3:]
    print(f"tray: {hi[0]-lo[0]:.1f} x {hi[1]-lo[1]:.1f} x {hi[2]-lo[2]:.1f}, {t.volume()/1000:.1f} cm3")
    print(f"bosses: {BOSS_DX:.1f} along x {BOSS_DY:.2f} across = {np.hypot(BOSS_DX, BOSS_DY):.2f} mm")


if __name__ == "__main__":
    main()
