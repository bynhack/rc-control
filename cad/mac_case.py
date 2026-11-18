"""P4 case in the shape of the 1984 Macintosh, on the MOZA wheel base.

The Waveshare ESP32-P4-WIFI6-Touch-LCD-7B sits in the front of a little
all-in-one: a face leaned back 8 degrees with the screen in a bevelled
recess and a floppy slot in the chin, a body that narrows and drops towards
the back, a carrying-handle groove on top and a recessed foot. Everything
the old desk stand carried goes inside: the speaker behind the chin (it
sounds through the floppy slot), the MULTI module on its cover in the back
wall, the ELRS Nano on the floor, the two SMA jacks in the top.

Parts:
  mac_front.stl      the face. The board's glass presses on the back of the
                     bevel, located by a rim; four posts carry the bracket.
                     A lip goes into the body, two tabs with teeth at the
                     bottom hook into the floor, two blocks at the top take
                     the closing screws. Prints face down.
  mac_body.stl       the rest: walls, top (handle groove, SMA holes, two
                     closing screws), back (the MULTI cover's window, vents,
                     a cable notch), floor (speaker stops, the MOZA screws)
                     and the foot. Windows in the left wall for the two
                     USB-C, the USB-A and the power switch, one in the right
                     wall for BOOT / RESET. Prints standing on its back.
  mac_bracket.stl    a flat plate that clamps the board to the face: four
                     M2.5 countersunk screws into the board's standoffs, four
                     M2.5 x 8 self-tapping screws into the face's posts.
  p4_multi_cover.stl unchanged, from p4_case.py.

Closing: hang the face's teeth in the floor's pockets, swing the top in,
two M2.5 x 10 self-tapping screws down through the top into the blocks.
The body is screwed to the MOZA first (two M3 x 12 socket heads from inside,
through the floor and a bar in the foot), through the open front.

World frame: X right (0 in the middle), Y away from the viewer, Z up, the
MOZA's top at Z = 0. Face frame: x = X, y = depth into the body from the
face, z = up along the face from its bottom edge.

Run:  python mac_case.py  -> out/mac_front.stl, out/mac_body.stl,
      out/mac_bracket.stl, out/mac_preview.png, out/mac_assembly.html
"""

import json
import os
import sys

import numpy as np
from manifold3d import CrossSection, JoinType, Manifold, OpType

from cad import OUT, box, cyl, preview, rrect, to_trimesh
import p4_case as p4
from p4_case import (BUTTONS_Y, COVER_T, CV_SCREWS, CV_WIN, GH, GW, HOLE_X, HOLE_Y, NUT_T, PCB_DY, PH_WIN, PIN12_WIN,
                     PLATE, SMA_BODY, SMA_HEX, SMA_HOLE, SPK_D, SPK_L, SPK_W, STACK, SWITCH_Y, UART_C_Y, USB_A_Y, USB_C_Y,
                     USBC_Z, pcb_back)

# ---- outline ------------------------------------------------------------------
TILT = 8.0  # the face leaned back from vertical
FOOT_H = 6.0  # the recessed foot under the body
W = 2.4  # walls
BW = 190.0  # face width
CHIN, TOP_B = 64.0, 20.0  # face below and above the glass
FH = CHIN + GH + TOP_B  # face height, along it
R = 10.0  # face corners
EDGE_CH = 1.0  # chamfer round the face's front edge
D = 125.0  # depth at the floor
BWB, BH, RB = 166.0, 165.0, 14.0  # the back: width, height over the foot, corners
BACK_CH = 2.0  # chamfer round the back edge (it prints on it)
FACE_T = 5.0  # the face's thickness; the glass's front lies on its back

T = np.radians(TILT)
sT, cT = np.sin(T), np.cos(T)

# ---- screen -------------------------------------------------------------------
OVL = 2.5  # the face's opening overlaps the glass's black border this much (MEASURE the border)
BEVEL_EDGE = 0.8  # straight edge left at the opening, under the bevel
RIM_T, RIM_D, RIM_FIT = 1.6, 3.0, 0.3  # rim round the glass
gf = pcb_back + STACK  # the tray frame's glass front (p4_case's frame for the board)
POSTS = [(x, z) for x in (-45.0, 45.0) for z in (CHIN - 6.0, CHIN + GH + 6.0)]  # bracket posts, face frame (x, up)
POST_R, PILOT = 3.5, 2.2  # M2.5 x 8 self-tapping
POST_D = FACE_T + gf - PLATE  # post ends level with the board's standoff ends
BRACKET_T = 3.0
M25_R, CSK_D = 1.45, 4.7  # M2.5 clearance and countersunk head

# ---- chin ---------------------------------------------------------------------
FLOPPY = (20.0, 26.0, 72.0, 4.5)  # slot centre x, up; width, height
FLOPPY_CH = 3.5  # its 45 degree surround

# ---- joint between face and body ------------------------------------------------
LIP, LIP_T, LIP_FIT = 4.0, 1.6, 0.3
TABS_X = (-72.0, 80.0)  # bottom tabs with teeth into floor pockets
BLOCKS_X = (-70.0, 70.0)  # top blocks for the closing screws

# ---- inside -----------------------------------------------------------------------
floor_top = FOOT_H + W
SPK_X = FLOPPY[0]  # speaker centred behind the slot
SPK_FIT = 0.3
spk_front = (FACE_T + SPK_FIT + (floor_top + SPK_W - FOOT_H) * sT) / cT  # its top front edge just clears the face
spk_back = spk_front + SPK_D
spk_mid = floor_top + SPK_W / 2
STOP_X = (SPK_X - 30.0, SPK_X + 30.0)  # fins behind it, touching only at its middle (its back slopes)
STOP_H = 4.0  # fin face reaches this far over its middle
MOZA_X, MOZA_Y = (-35.0, 35.0), 60.0  # the MOZA's two M3 holes, 70 apart
M3_R = 1.7
NANO = p4.NANO
NANO_AT = (-72.0, 40.0)  # its corner on the floor
# MULTI cover on the back wall: window centre (X, Z); the board's u runs to -X, v down.
CV_AT = (10.0, 115.0)
PAD_T, PAD_R = 3.2, 4.5  # nut pads inside the back wall (wall + pad = 5.6, as before)
NUT_R = (5.0 + 0.3) / np.sqrt(3)
# SMA jacks in the top, near the back corners, square to the top.
SMA_X, SMA_Y = (-62.0, 62.0), D - 18.0
# Handle groove across the top.
GROOVE = (D - 36.0, 96.0, 36.0, 9.0)  # centre Y, length along X, width at the top, depth


# ---- frames ---------------------------------------------------------------------
def f2w(m):
    """Face frame -> world."""
    return m.rotate([-TILT, 0, 0]).translate([0, 0, FOOT_H])


def w2f(m):
    return m.translate([0, 0, -FOOT_H]).rotate([TILT, 0, 0])


def f2w_pt(x, d, z):
    return np.array([x, d * cT + z * sT, FOOT_H - d * sT + z * cT])


def depth_of(y, z):
    """A world point's depth behind the face's outer plane."""
    return y * cT - (z - FOOT_H) * sT


# The board in p4_case's tray frame (x right, y up, z towards the viewer) -> face frame.
TRAY_TO_FACE = np.array([
    [1, 0, 0, -GW / 2],
    [0, 0, -1, FACE_T + gf],
    [0, 1, 0, CHIN],
])


def tray_to_world(m):
    return f2w(m.transform(TRAY_TO_FACE))


def slab(x0, z0, w, h, r, y):
    """A thin rounded rectangle in an x-z plane at y (face frame or world alike)."""
    return Manifold.extrude(rrect(w, h, r), 0.01).rotate([90, 0, 0]).translate([x0, y, z0])


def prism_xz(cs, d0, d1):
    """A cross-section in the face's (x, up) plane, from depth d0 to d1."""
    return Manifold.extrude(cs.mirror([0, 1]), d1 - d0).translate([0, 0, d0]).rotate([-90, 0, 0])


def prism_yz(points, x0, x1):
    """A polygon in the world's (Y, Z) plane, from X = x0 to x1."""
    m = Manifold.extrude(CrossSection([p4.ccw(points)]), x1 - x0).translate([0, 0, x0])
    return m.transform(np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0]]))


def fcyl(x, z, d0, d1, r, r1=None):
    """A cylinder along the face frame's depth."""
    return Manifold.cylinder(d1 - d0, r, r if r1 is None else r1).rotate([-90, 0, 0]).translate([x, d0, z])


def teardrop_z(x, y, z0, z1, r):
    """Upright hole in the world, with a 45 degree point towards -Y (up as the body prints)."""
    tip = CrossSection([[(-r * 0.7071, -r * 0.7071), (0, -r * 1.4142), (r * 0.7071, -r * 0.7071)]])
    return Manifold.extrude(CrossSection.circle(r, 32) + tip, z1 - z0).translate([x, y, z0])


def above(z):
    return box(-500, -500, z, 500, 500, 500)


def behind_face(d):
    """World half-space deeper than d behind the face."""
    return f2w(box(-500, d, -500, 500, 600, 600))


def top_z(y):
    """The top's outer surface over Y, at X = 0."""
    p0 = f2w_pt(0, EDGE_CH, FH)
    p1 = np.array([0, D - BACK_CH, FOOT_H + BH])
    return p0[2] + (y - p0[1]) * (p1[2] - p0[2]) / (p1[1] - p0[1])


TOP_SLOPE = np.arctan2(top_z(0) - top_z(100), 100)


# ---- body -------------------------------------------------------------------------
def outer():
    front = f2w(slab(-BW / 2 + EDGE_CH, EDGE_CH, BW - 2 * EDGE_CH, FH - 2 * EDGE_CH, R - EDGE_CH, 0.01)
                + slab(-BW / 2, 0, BW, FH, R, EDGE_CH))
    back = slab(-BWB / 2, FOOT_H, BWB, BH, RB, D - BACK_CH) \
        + slab(-BWB / 2 + BACK_CH, FOOT_H + BACK_CH, BWB - 2 * BACK_CH, BH - 2 * BACK_CH, RB - BACK_CH, D)
    return (front + back).hull() ^ above(FOOT_H)


def cavity():
    # The front slab starts lower and is cut at the floor, so the floor stays flat.
    front = f2w(slab(-BW / 2 + W, W - 1.0, BW - 2 * W, FH - 2 * W + 1.0, R - W, -1.0))
    back = slab(-BWB / 2 + W, FOOT_H + W - 1.0, BWB - 2 * W, BH - 2 * W + 1.0, RB - W, D - W)
    return (front + back).hull() ^ above(floor_top)


def groove(grow=0.0):
    """The handle groove (grow: the same, its walls' thickness bigger, for the cavity side)."""
    yc, length, w, depth = GROOVE
    zt = top_z(yc)
    run = (w - 12.0) / 2  # its sides lean further than 45 degrees from the top: they hang as the body prints
    up = 5.0  # the sides carry on above the top: the top slopes, so it meets them a little higher in front
    pts = [(yc - w / 2 - up * run / depth, zt + up), (yc - w / 2 + run, zt - depth),
           (yc + w / 2 - run, zt - depth), (yc + w / 2 + up * run / depth, zt + up)]
    cs = CrossSection([pts])
    if grow:
        cs = cs.offset(grow, JoinType.Miter)
    return prism_yz(cs.to_polygons()[0], -length / 2 - grow, length / 2 + grow)


def foot():
    """Recessed foot, hollow; its back and its front's inside at 45 degrees (they hang as the body prints)."""
    hw = BWB / 2 - 8.0
    out = (box(-hw, 8.0, 0, hw, D - 10.0, 0.01) + box(-hw, 8.0, FOOT_H - 0.01, hw, D - 4.0, FOOT_H + 0.01)).hull()
    hi = hw - W
    out -= (box(-hi, 8.0 + W, -1, hi, D - 10.0 - W, -0.99) + box(-hi, 8.0 + W + FOOT_H + 1, FOOT_H - 0.01, hi, D - 4.0 - W, FOOT_H)).hull()
    # A bar across under the MOZA screws.
    out += (box(-45, MOZA_Y - 6, 0, 45, MOZA_Y + 6, 0.01) + box(-45, MOZA_Y - 6, FOOT_H - 0.01, 45, MOZA_Y + 12, FOOT_H + 0.01)).hull()
    return out


def fin(x, y0, z_top, top_len=3.0, t=W):
    """A fin on the floor along Y: square front at y0, 45 degree back."""
    pts = [(y0, floor_top - 0.1), (y0, z_top), (y0 + top_len, z_top), (y0 + top_len + z_top - floor_top + 0.1, floor_top - 0.1)]
    return prism_yz(pts, x - t / 2, x + t / 2)


COVER_TO_WORLD = np.array([
    [-1, 0, 0, CV_AT[0] + (CV_WIN[0] + CV_WIN[2]) / 2],
    [0, 0, -1, D + COVER_T],
    [0, -1, 0, CV_AT[1] + (CV_WIN[1] + CV_WIN[3]) / 2],
])


def cover_w(m):
    return m.transform(COVER_TO_WORLD)


def sma_pose(m, x):
    """A part built along +z with its seat on the top at z = 0 -> on the top at (x, SMA_Y), square to it."""
    return m.rotate([-np.degrees(TOP_SLOPE), 0, 0]).translate([x, SMA_Y, top_z(SMA_Y)])


def side_windows():
    """Windows in the side walls for the board's edge ports, face frame."""
    d = lambda z: FACE_T + gf - z  # tray z -> depth
    cut = Manifold()
    xl0, xl1 = -BW / 2 - 5, -GW / 2 - 1.0
    for y in (UART_C_Y, USB_C_Y):
        cut += box(xl0, d(USBC_Z + 4.0), CHIN + y - 6.25, xl1, d(USBC_Z - 4.0), CHIN + y + 6.25)
    za = pcb_back - 2.85
    cut += box(xl0, d(za + 4.5), CHIN + USB_A_Y - 8.5, xl1, d(za - 4.5), CHIN + USB_A_Y + 8.5)
    cut += box(xl0, d(pcb_back + 1.0), CHIN + SWITCH_Y - 5.0, xl1, d(PLATE + 0.3), CHIN + SWITCH_Y + 5.0)
    cut += box(GW / 2 + 1.0, d(pcb_back + 1.0), CHIN + BUTTONS_Y[0], BW / 2 + 5, d(PLATE + 0.3), CHIN + BUTTONS_Y[1])
    return cut


def closing_screws():
    """(X, Y, inner top Z) of the two closing screws."""
    out = []
    for x in BLOCKS_X:
        b = block(x)
        lo, hi = b.bounding_box()[:3], b.bounding_box()[3:]
        out.append((x, (lo[1] + hi[1]) / 2, hi[2] + 0.3))
    return out


def body():
    shell = (outer() - groove()) - (cavity() - groove(W))
    shell ^= behind_face(FACE_T)
    shell += foot()

    # Floor: speaker stops and guides, pockets for the face's teeth.
    for x in STOP_X:
        shell += fin(x, spk_back + SPK_FIT, spk_mid + STOP_H)
    for x in (SPK_X - SPK_L / 2 - SPK_FIT - W / 2, SPK_X + SPK_L / 2 + SPK_FIT + W / 2):
        shell += fin(x, spk_front + 1.0, floor_top + 10.0, top_len=SPK_D - 1.0)
    # MULTI cover: nut pads inside the back wall.
    pad_in = COVER_T + W + PAD_T
    for x, y in CV_SCREWS:
        shell += cover_w(cyl(x, y, COVER_T + W - 0.5, pad_in, PAD_R))
    cut = Manifold()
    for x in TABS_X:
        cut += box(x - 3.0, 11.4, FOOT_H + 0.4, x + 3.0, 18.2, floor_top + 1)
    for x in MOZA_X:
        cut += teardrop_z(x, MOZA_Y, -1, floor_top + 1, M3_R)
    for x, y in CV_SCREWS:
        cut += cover_w(cyl(x, y, COVER_T - 1, pad_in + 1, M25_R))
        cut += cover_w(Manifold.cylinder(NUT_T + 1.4, NUT_R, circular_segments=6).translate([x, y, pad_in - NUT_T - 0.4]))
    cut += cover_w(p4.cv_window())
    # Back: vents and a cable notch (holes in the face it prints on).
    for k in range(5):
        z = 24.0 + 8.0 * k
        cut += box(28, D - 6, z, 78, D + 1, z + 3.5)
    cut += box(-78, D - 6, floor_top + 2, -48, D + 1, floor_top + 14)
    # Top: SMA jacks, closing screws.
    for x in SMA_X:
        tip = CrossSection([[(-0.7071 * SMA_HOLE / 2, -0.7071 * SMA_HOLE / 2), (0, -1.4142 * SMA_HOLE / 2), (0.7071 * SMA_HOLE / 2, -0.7071 * SMA_HOLE / 2)]])
        cut += sma_pose(Manifold.extrude(CrossSection.circle(SMA_HOLE / 2, 48) + tip, 12).translate([0, 0, -8]), x)
    for x, y, zi in closing_screws():
        zo = top_z(y)
        cut += cyl(x, y, zi - 1, zo + 1, M25_R)
        cut += cyl(x, y, zo - (CSK_D / 2 - M25_R), zo + 0.01, M25_R, CSK_D / 2 + 0.01)
    cut += f2w(side_windows())
    return shell - cut


# ---- face ---------------------------------------------------------------------------
def block(x):
    """A block at the top of the face's inside, under the top, for a closing screw (world)."""
    b = f2w(box(x - 5, FACE_T - 0.01, CHIN + GH + RIM_FIT + RIM_T, x + 5, FACE_T + 12, FH + 5))
    return b ^ cavity().translate([0, 0, -0.3])


def lip():
    m = w2f(cavity()).rotate([90, 0, 0])  # face frame (x, depth, up) -> (x, -up, depth)
    inner = m.slice(FACE_T + 0.01) ^ m.slice(FACE_T + LIP + 0.5)
    ring = inner.offset(-LIP_FIT, JoinType.Round) - inner.offset(-LIP_FIT - LIP_T, JoinType.Round)
    return Manifold.extrude(ring, LIP + 0.01).translate([0, 0, FACE_T - 0.01]).rotate([-90, 0, 0])


def tab(x):
    """Bottom tab along the floor, its tooth into the floor's pocket (world)."""
    t = box(x - 4, 3.0, floor_top + 0.25, x + 4, 20.0, floor_top + 3.25)
    t += (box(x - 2.5, 12.0, floor_top + 0.2, x + 2.5, 17.0, floor_top + 0.3)
          + box(x - 2.5, 14.0, FOOT_H + 0.7, x + 2.5, 17.0, FOOT_H + 0.8)).hull()
    return t


def front():
    """The face, in the face frame."""
    out = w2f(outer()) ^ box(-500, -1, -500, 500, FACE_T, 500)
    ox0, oz0 = -GW / 2 + OVL, CHIN + OVL
    ow, oh = GW - 2 * OVL, GH - 2 * OVL
    b = FACE_T - BEVEL_EDGE  # the bevel: 45 degrees from the face down to the opening
    out -= (slab(ox0 - b - 0.5, oz0 - b - 0.5, ow + 2 * b + 1, oh + 2 * b + 1, 2.5 + b, -0.5) + slab(ox0, oz0, ow, oh, 2.0, b)).hull()
    out -= box(ox0, -1, oz0, ox0 + ow, FACE_T + 1, oz0 + oh)
    fx, fz, fw, fh = FLOPPY
    c = FLOPPY_CH
    x0, z0 = fx - fw / 2, fz - fh / 2
    out -= (slab(x0 - c - 0.5, z0 - c - 0.5, fw + 2 * c + 1, fh + 2 * c + 1, fh / 2 + c + 0.5, -0.5) + slab(x0, z0, fw, fh, fh / 2 - 0.01, c)).hull()
    out -= (slab(x0, z0, fw, fh, fh / 2 - 0.01, -1) + slab(x0, z0, fw, fh, fh / 2 - 0.01, FACE_T + 1)).hull()

    # Rim round the glass, posts, lip, top blocks, bottom tabs.
    g0x, g0z, gw, gh = -GW / 2 - RIM_FIT, CHIN - RIM_FIT, GW + 2 * RIM_FIT, GH + 2 * RIM_FIT
    out += prism_xz(rrect(gw + 2 * RIM_T, gh + 2 * RIM_T, 1.0 + RIM_T).translate([g0x - RIM_T, g0z - RIM_T])
                    - rrect(gw, gh, 1.0).translate([g0x, g0z]), FACE_T - 0.01, FACE_T + RIM_D)
    for x, z in POSTS:
        out += fcyl(x, z, FACE_T - 0.01, POST_D, POST_R)
        out -= fcyl(x, z, POST_D - 10, POST_D + 1, PILOT / 2)
    out += lip()
    for x in BLOCKS_X:
        out += w2f(block(x))
    for x in TABS_X:
        out += w2f(tab(x))
    for x, y, zi in closing_screws():
        out -= w2f(cyl(x, y, zi - 10, zi + 1, PILOT / 2))
    return out


# ---- bracket --------------------------------------------------------------------------
def bracket():
    """Clamps the board to the face; face frame, from the standoff ends back."""
    d0 = POST_D
    x0, z0 = -GW / 2 + 0.5, CHIN - 10.0
    out = prism_xz(rrect(GW - 1.0, GH + 20.0, 4.0).translate([x0, z0]), d0, d0 + BRACKET_T)
    win = CrossSection()
    tx = lambda x: x - GW / 2  # tray x -> face x
    px0, py0, px1, py1 = PH_WIN
    win += CrossSection.square([px1 - px0 + 5, py1 - py0 + 2]).translate([tx(px0 - 1), CHIN + py0 - 1])
    for a, b in PIN12_WIN:
        win += CrossSection.square([b - a + 2, 12.5]).translate([tx(a - 1), CHIN + PCB_DY])
    win += rrect(118.0, 54.0, 6.0).translate([tx(22.0), CHIN + 22.0])
    out -= prism_xz(win, d0 - 1, d0 + BRACKET_T + 1)
    sink = CSK_D / 2 - M25_R
    for x in HOLE_X:
        for y in HOLE_Y:
            out -= fcyl(tx(x), CHIN + y, d0 - 1, d0 + BRACKET_T + 1, M25_R)
            out -= fcyl(tx(x), CHIN + y, d0 + BRACKET_T - sink, d0 + BRACKET_T + 0.01, M25_R, M25_R + sink)
    for x, z in POSTS:
        out -= fcyl(x, z, d0 - 1, d0 + BRACKET_T + 1, M25_R)
    return out


# ---- stand-ins -------------------------------------------------------------------------
def speaker():
    return box(SPK_X - SPK_L / 2, spk_front, floor_top, SPK_X + SPK_L / 2, spk_back, floor_top + SPK_W)


def nano():
    x, y = NANO_AT
    return box(x, y, floor_top, x + NANO[0], y + NANO[1], floor_top + 3.5)


def moza_screws():
    one = cyl(0, 0, 0, 3.0, 2.75) + cyl(0, 0, -12.0, 0, 1.5)
    return Manifold.batch_boolean([one.translate([x, MOZA_Y, floor_top]) for x in MOZA_X], OpType.Add)


def sma():
    out = Manifold()
    for x in SMA_X:
        w = W + 0.4  # the top is a little thicker than W across its slope
        one = cyl(0, 0, -w, 8, 6.25 / 2) + Manifold.cylinder(2.5, SMA_HEX / np.sqrt(3), circular_segments=6).translate([0, 0, -w - 2.5]) \
            + cyl(0, 0, -w - SMA_BODY, -w - 2.5, 2.5)
        out += sma_pose(one, x)
    return out


def antennas():
    return Manifold.batch_boolean([sma_pose(cyl(0, 0, 8, 108, 5.0, 4.0), x) for x in SMA_X], OpType.Add)


def pin12_plugs():
    """The two 12-pin plugs and their wires' bend, 26 behind the PCB (tray frame)."""
    return Manifold.batch_boolean([box(a + 1, PCB_DY + 1, pcb_back - 26, b - 1, PCB_DY + 11.5, pcb_back + 0.5) for a, b in PIN12_WIN], OpType.Add)


def usb_plugs():
    """The cables' overmoulds in the left wall's windows (tray frame)."""
    out = Manifold()
    for y in (UART_C_Y, USB_C_Y):
        out += box(-40, y - 5.5, USBC_Z - 3.0, -0.3, y + 5.5, USBC_Z + 3.0)
        out += box(-0.3, y - 4.2, USBC_Z - 1.2, 3, y + 4.2, USBC_Z + 1.2)
    za = pcb_back - 2.85
    out += box(-45, USB_A_Y - 8.0, za - 4.0, -0.3, USB_A_Y + 8.0, za + 4.0)
    return out


def bracket_screws():
    """Face frame: 4 countersunk into the standoffs, 4 pan heads into the posts."""
    d1 = POST_D + BRACKET_T
    out = Manifold()
    for x in HOLE_X:
        for y in HOLE_Y:
            out += fcyl(x - GW / 2, CHIN + y, d1 - 6, d1, 1.25) + fcyl(x - GW / 2, CHIN + y, d1 - 1.1, d1, 1.25, 2.35)
    for x, z in POSTS:
        out += fcyl(x, z, d1 - 8, d1, 1.25) + fcyl(x, z, d1, d1 + 1.8, 2.3)
    return out


def top_screws():
    out = Manifold()
    for x, y, zi in closing_screws():
        zo = top_z(y)
        out += cyl(x, y, zo - 10, zo - 1.1, 1.25) + cyl(x, y, zo - 1.1, zo, 1.25, 2.35)
    return out


# ---- checks ------------------------------------------------------------------------------
def islands(m, name, step=0.2):
    """Layers in print pose (z up from 0): any island with nothing under it?"""
    lo, hi = m.bounding_box()[2], m.bounding_box()[5]
    prev, bad = None, []
    for z in np.arange(lo + step / 2, hi, step):
        cs = m.slice(z)
        if prev is not None:
            for part in cs.decompose():
                if (part ^ prev).area() < 1e-3:
                    bad.append(round(float(z), 1))
        prev = cs
    print(f"{name}: {len(bad)} floating islands" + (f" at z {bad[:8]}" if bad else ""))
    return len(bad)


def overhangs(m, name, limit=50.0):
    """Area facing down steeper than `limit` degrees from vertical, off the bed (print pose)."""
    tm = to_trimesh(m)
    nz = tm.face_normals[:, 2]
    zc = tm.triangles_center[:, 2]
    down = (nz < -np.cos(np.radians(90 - limit))) & (zc > 0.3)
    print(f"{name}: {tm.area_faces[down].sum():.0f} mm2 facing down past {limit:.0f} degrees")
    return tm, down


def print_pose(m, frame):
    """The face and the bracket print on their front (depth up); the body on its back."""
    if frame == "face":
        m = m.rotate([90, 0, 0])  # (x, depth, up) -> (x, -up, depth)
        return m.translate([0, 0, -m.bounding_box()[2]])
    m = m.rotate([-90, 0, 0])  # (X, Y, Z) -> (X, Z, -Y)
    return m.translate([0, 0, -m.bounding_box()[2]])


def export_page(path, parts, checks, sizes):
    data = {
        "parts": [{"name": nm, "label": lb, "tris": p4.tris_b64(m), "color": c, "moves": mv} for nm, lb, m, c, mv in parts],
        "checks": {k: round(v, 3) for k, v in checks.items()},
        "size": sizes,
        "centre": [0, 60, 90],
    }
    src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mac_viewer.html")
    with open(src, encoding="utf-8") as f:
        page = f.read().replace("/*DATA*/null", json.dumps(data))
    with open(path, "w", encoding="utf-8") as f:
        f.write(page)


def main():
    os.makedirs(OUT, exist_ok=True)
    bd, fr_f, br_f = body(), front(), bracket()
    fr, br = f2w(fr_f), f2w(br_f)
    for name, m in [("body", bd), ("front", fr), ("bracket", br)]:
        if m.is_empty() or len(m.decompose()) != 1:
            sys.exit(f"{name}: not a single solid ({len(m.decompose())} pieces)")

    board = tray_to_world(p4.board())
    cv, mb, mbp = cover_w(p4.cover()), cover_w(p4.multi()), cover_w(p4.multi(plugs=True))
    pins, usb = tray_to_world(pin12_plugs()), tray_to_world(usb_plugs())
    spk, nn, m3, sm = speaker(), nano(), moza_screws(), sma()
    bscr, tscr = f2w(bracket_screws()), top_screws()
    checks = {
        "body x front": (bd ^ fr).volume(), "body x bracket": (bd ^ br).volume(), "front x bracket": (fr ^ br).volume(),
        "board x body": (board ^ bd).volume(), "board x front": (board ^ fr).volume(), "board x bracket": (board ^ br).volume(),
        "speaker x body": (spk ^ bd).volume(), "speaker x front": (spk ^ fr).volume(), "speaker x bracket": (spk ^ br).volume(),
        "body x cover": (bd ^ cv).volume(), "body x MULTI + plugs": (bd ^ mbp).volume(),
        "body x SMA": (bd ^ sm).volume(), "MULTI x SMA": (mbp ^ sm).volume(),
        "body x Nano": (bd ^ nn).volume(), "body x M3 screws": (bd ^ m3).volume(), "speaker x M3 screws": (spk ^ m3).volume(),
        "body x 12-pin plugs": (bd ^ pins).volume(), "speaker x 12-pin plugs": (spk ^ pins).volume(),
        "front x 12-pin plugs": (fr ^ pins).volume(), "MULTI x 12-pin plugs": (mbp ^ pins).volume(),
        "body x USB plugs": (bd ^ usb).volume(), "front x USB plugs": (fr ^ usb).volume(),
        "body x top screws": (bd ^ tscr).volume(), "body x bracket screws": (bd ^ bscr).volume(),
        "speaker x Nano": (spk ^ nn).volume(),
    }
    for k, v in checks.items():
        print(f"{k}: {v:.3f} mm3")
    # The speaker goes in from the open front, the face off.
    way = (spk.translate([0, -60, 0]) + spk).hull()
    checks["speaker's way in"] = (bd ^ way).volume()
    print(f"speaker's way in: {checks["speaker's way in"]:.3f} mm3")
    if max(checks.values()) > 0.01:
        sys.exit("parts overlap")
    if bd.bounding_box()[2] < -1e-6:
        sys.exit("below the MOZA")

    poses = {"front": print_pose(fr_f, "face"), "body": print_pose(bd, "world"), "bracket": print_pose(br_f, "face")}
    for name, m in poses.items():
        islands(m, name)
        overhangs(m, name)
        to_trimesh(m).export(os.path.join(OUT, f"mac_{name}.stl"))
    sizes = {}
    for name, m in poses.items():
        lo, hi = np.array(m.bounding_box()[:3]), np.array(m.bounding_box()[3:])
        sizes[name] = [round(v, 1) for v in hi - lo] + [round(m.volume() / 1000, 1)]
        print(f"{name}: {hi[0]-lo[0]:.1f} x {hi[1]-lo[1]:.1f} x {hi[2]-lo[2]:.1f} mm (as printed), volume {m.volume()/1000:.1f} cm3")

    beige, dark, grey = (0.86, 0.82, 0.72), (0.15, 0.17, 0.2), (0.6, 0.62, 0.66)
    preview(
        [
            ("front", [(bd, beige), (fr, beige), (board, dark), (sm + antennas(), dark)], 12, -115),
            ("back", [(bd, beige), (cv, grey), (sm + antennas(), dark)], 18, 60),
            ("face off", [(bd, beige), (spk, dark), (nn, grey), (mb, dark), (m3, grey)], 25, -120),
            ("face, inside", [(fr, beige), (board, dark), (br, grey)], 25, 60),
        ],
        os.path.join(OUT, "mac_preview.png"),
    )

    desk = box(-130, -60, -2, 130, 200, 0)
    out_y = [0, -160, 0]
    plate_go = (12, out_y)
    nuts = Manifold.batch_boolean([cover_w(p4.m25_nut(COVER_T + W + PAD_T - NUT_T - 0.4).translate([x, y, 0])) for x, y in CV_SCREWS], OpType.Add)
    sunk = (p4.HEAD_D - CSK_D) / 2  # an M2.5 head sits this much lower in the cover's M3 countersinks
    cscr = Manifold.batch_boolean([cover_w(p4.m25_screw(8, sunk).mirror([0, 0, 1]).translate([x, y, 0])) for x, y in CV_SCREWS], OpType.Add)
    parts = [
        ("desk", "MOZA 底座頂面", desk, 0xc8b49a, []),
        ("body", "機身（後殼）", bd, 0xe4dccb, [(0, [0, 0, 70])]),
        ("mscrews", "M3×12 內六角 ×2（固定到 MOZA）", m3, 0xe8e8e8, [(1, [0, -40, 60])]),
        ("nuts", "M2.5 螺母 ×4", nuts, 0xd9d9d9, [(2, [0, -40, 0])]),
        ("cover", "MULTI 面板", cv, 0xb9b3a6, [(3, [0, 0, 0]), (4, [0, 70, 0])]),
        ("multi", "MULTI 高頻頭", mb, 0x2f6b4f, [(3, [0, 40, 0]), (4, [0, 70, 0])]),
        ("cscrews", "面板螺絲 M2.5×8 ×4", cscr, 0xe8e8e8, [(5, [0, 25, 0])]),
        ("sma", "SMA＋天線", sm + antennas(), 0x1d2228, [(6, [0, 0, 45])]),
        ("nano", "ELRS Nano", nn, 0x3a5d8f, [(7, [0, -60, 40])]),
        ("speaker", "喇叭", spk, 0x2a2d33, [(8, [0, -90, 30])]),
        ("front", "前面板", fr, 0xeee7d8, [(9, [0, 0, 0]), plate_go]),
        ("board", "P4 主板＋螢幕", board, 0x22303c, [(9, [0, 50, 0]), plate_go]),
        ("bracket", "背板支架", br, 0x9aa7b4, [(10, [0, 40, 0]), plate_go]),
        ("bscrews", "支架螺絲（沉頭 ×4、自攻 ×4）", bscr, 0xe8e8e8, [(10, [0, 60, 0]), plate_go]),
        ("pins", "12-pin 插頭", pins, 0xd9732b, [(11, [0, 25, 0]), plate_go]),
        ("hdr", "MULTI 排針插頭", mbp - mb, 0xd9732b, [(11, [25, 0, 0])]),
        ("tscrews", "頂上 M2.5×10 自攻 ×2", tscr, 0xe8e8e8, [(13, [0, 0, 30])]),
        ("usb", "USB 插頭（Type-C ×2、USB-A）", usb, 0xd9732b, [(14, [-40, 0, 0])]),
    ]
    export_page(os.path.join(OUT, "mac_assembly.html"), parts, checks, sizes)


if __name__ == "__main__":
    main()
