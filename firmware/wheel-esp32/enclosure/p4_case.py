"""Desk case for the Waveshare ESP32-P4-WIFI6-Touch-LCD-7B (7" 1024x600).

Three parts:
  p4_tray.stl         the back of the display: a tray the board screws into
                      through its own M2.5 standoffs (countersunk screws from
                      outside), walls around the glass with windows for the
                      side ports, TF card and the cable plugs. Prints flat,
                      back face on the bed.
  p4_stand.stl        one profile, extruded along the stand's width and
                      printed standing on an end (the STL is placed so), with
                      3 mm walls: a shell (floor on the MOZA, back wall, top,
                      the slope the tray lies on, a front panel with the
                      speaker grille) and an inverted V under the slope that
                      makes a triangle with the floor and carries the tray.
                      The V's legs have rows of diamond windows, the slope
                      three windows behind the tray; every opening ends in 45
                      degree points along the print's height, so the only
                      span is the MULTI window's top edge (a ~35 mm bridge).
                      The tray is held by four M2.5 x 10 countersunk screws
                      from inside the tray (before the board goes in), nuts
                      in diamond pads under the slope. The box speaker faces
                      forward behind the grille, slid in from the stand's open
                      end into a slot (a stop at the far end, an M2.5 x 8
                      self-tapping screw and washer at the near one). Two M3 x 6 socket heads hold the
                      floor to the MOZA wheel base's two M3 holes (70 apart),
                      turned with a hex key through the slope's windows.
  p4_multi_cover.stl  cover over a window in the stand's back wall. The MULTI
                      4-in-1 module (iRangeX IRX4+ bare board) hangs on it front
                      outwards, like its own case held it: two M2.5 x 6
                      self-tapping screws into posts, two snap hooks over its
                      bottom edge; the bind button, dial, LEDs and mini USB
                      show through the cover. Four M2.5 x 8 countersunk
                      screws, nuts in diamond pads inside the back wall.
                      Prints outer face down.

The ELRS Nano is taped to the floor inside the V. Wires run through the V's
windows and leave by the stand's open ends to the 12-pin and PH2.0 sockets.
The MULTI pocket the tray was first printed with stays (the model matches
that print), now unused. Two SMA jacks stand upright in the stand's flat top,
one near each end (the MULTI's and the Nano's antennas), their bodies inside;
the tray keeps its own SMA hole in the top wall, for later.

Board numbers come from Waveshare's dimension drawing; the ones marked
MEASURE are estimates. Check them with calipers when the board arrives and
re-run.

Tray coordinates: looking at the screen, x = right, y = up, z = towards
the viewer, origin at the glass's bottom-left corner on the tray's back
face. The drawing of the board's back is mirrored: its right edge (USB
ports) is the left wall here.

Run:  python p4_case.py   -> out/p4_tray.stl, out/p4_stand.stl, out/p4_multi_cover.stl,
      out/p4_preview.png, out/p4_assembly.html (step-by-step assembly, built
      from p4_viewer.html)
"""

import base64
import json
import os
import sys

import numpy as np
from manifold3d import CrossSection, JoinType, Manifold, OpType

from cad import OUT, box, cyl, preview, rbox, to_trimesh

# ---- printer / fit -----------------------------------------------------------
FIT = 0.4

# ---- board (Waveshare drawing) -------------------------------------------------
GW, GH = 164.28, 99.17  # cover glass outline
PCB_H = 97.0
PCB_DY = 1.0  # MEASURE: glass bottom edge to PCB bottom edge
HOLE_X = (3.35, GW - 4.35)  # standoff centres; the PH2.0 side moved 1 mm in (checked on a print)
HOLE_Y = (PCB_DY + 3.9, PCB_DY + 3.9 + 89.0)
STANDOFF = 15.0 - 8.78  # PCB back to the standoff ends: glass front to standoff ends 15 (measured)
STANDOFF_EXT = 0.0  # spacers under the standoffs, if the MULTI module ever needs more room
STACK = 8.78  # PCB back to the front of the glass (measured)
STANDOFF_HOLE = 2.9  # M2.5 clearance; countersunk screws from the back
STANDOFF_HEAD = 4.7  # M2.5 countersunk (DIN 7991): 90 degree countersink on the outside, like the stand screws (a flat counterbore printed badly)

# Left wall (the board's right edge in the drawing), centres from the glass bottom.
UART_C_Y = PCB_DY + 13.57  # USB-C "USB TO UART" (flashing, logs)
USB_C_Y = UART_C_Y + 15.28  # USB-C "USB"
USB_A_Y = USB_C_Y + 11.91 + 13.1 / 2  # USB-A OTG (the wheel), 11.91 is to its lower edge
SWITCH_Y = PCB_DY + PCB_H - 10.68 - 3.4  # power slide switch; 10.68 is to its top end (checked on a print)
# Right wall: RESET / BOOT side buttons.
BUTTONS_Y = (PCB_DY + 72.5, PCB_DY + 90.0)  # BOOT ~77.8, RESET ~86.8 (checked on a print)
# Bottom wall, x from the glass left edge.
TF_X = (70.5, 87.7)  # TF card slot
FPC_X = [(64.8, 95.7), (137.6, 154.7)]  # LCD / touch flex tails just below the glass
FPC_OUT = 1.6  # MEASURE: how far they stand below the glass
FPC_SIDE, FPC_DEEP = 3.0, 1.5  # extra room around them, along the edge and below
TF_SIDE = 4.0  # extra room each side of the TF slot
# Plug windows in the back, behind the vertical PH2.0 sockets (I2C / UART /
# CAN / RS485 along the right edge) and the two 12-pin sockets at the bottom.
PH_WIN = (150.0, PCB_DY + 9.0, GW, PCB_DY + 72.0)
PIN12_WIN = [(28.0, 59.0), (105.0, 136.0)]

# ---- tray ----------------------------------------------------------------------
WALL, WALL_B = 2.4, 5.0  # sides/top, bottom (thicker for the flex notches)
PLATE = 3.0
R = 4.0
GLASS_SINK = 0.3  # wall top this far below the glass front
X0, X1 = -FIT - WALL, GW + FIT + WALL
Y0, Y1 = -FIT - WALL_B, GH + FIT + WALL
pcb_back = PLATE + STANDOFF + STANDOFF_EXT
USBC_Z = pcb_back - 1.3  # receptacles' centre above the tray's back face (from a photo of the print: 2.3 under the old window's top)
USBC_PLUG = (12.5, 8.0)  # opening for a cable's overmould: along the wall, and deep
tray_top = pcb_back + STACK - GLASS_SINK

# ---- MULTI module (iRangeX IRX4+ board, YRFM_ARM_V1.3) -------------------------
# Board frame: u across, v down from the antenna edge, looking at the front
# (shield / dial side). Outline, holes and heights measured by the user; the
# positions of the shield and controls are from photos (MEASURE).
MB_W, MB_H, MB_T = 41.0, 55.0, 1.0
MB_HOLES = [(8.0, 2.5), (31.5, 2.5)]  # 2.7 holes; M2.5 x 6 countersunk from outside, nut on the board
MB_SINK = 1.3  # board front this far into the tray back, in a pocket: its back parts clear the P4 PCB by 0.5
MB_RELIEF = 0.8  # the pocket floor is this much lower again, for solder joints on the board's front
MB_BACK_H = 6.0  # tallest part on the back (towards the P4)
MB_SHIELD = (4.5, 7.0, 37.5, 29.5, 2.5)  # MEASURE u0, v0, u1, v1, height
MB_IPEX = (19.5, 1.5)  # MEASURE
# Across the board (u) the controls come from the module's own front cover,
# 48.35 wide, assuming the board sits centred in it; down the board (v) they
# are still from photos (MEASURE). The board lies flat on the tray back, so
# the openings fit the switch, dial and USB bodies, not just the knob and
# the button cap like the cover's holes did.
MB_COVER_OFF = (48.35 - MB_W) / 2
MB_ROW_V = 46.3 + 2.8  # bind / dial / USB centres, from the antenna edge (photo estimate, moved 2.8 after a print)
MB_BIND = (14.5 - MB_COVER_OFF, MB_ROW_V)  # cover: 14.5 from the left, button 3.2
MB_DIAL = (24.4 - MB_COVER_OFF, MB_ROW_V, 15.0)  # cover: 24.4 from the left; knob 6.8, top 15 above the PCB
MB_USB_R = 48.35 - 12.4 - MB_COVER_OFF  # cover: USB's right side 12.4 from the right
MB_USB = (MB_USB_R - 3.0, MB_ROW_V)  # vertical receptacle, MEASURE size
MB_LED_U = (18.2, 24.4)  # MEASURE (photo of the cover)
MB_LEDS = (MB_LED_U[0] - 2.2, 34.0, MB_LED_U[1] + 2.2, 39.0)  # the two light pipes, one slot
MB_KEYS = (MB_BIND[0] - 3.8, 40.0, MB_USB_R + 0.6, 53.0)  # tray's opening for the bind switch, dial body and USB, as printed
MB_HEADER = (37.0, 53.0, 4.0)  # right-angle header on the back, out past the u = MB_W edge
MB_HOOKS = (6.0, 35.0)  # lips over the bottom edge (v = MB_H): slide the board under them, then screw the top
MB_TOP = 82.0  # tray y of the antenna edge: room above for the SMA body
mb_right = GW / 2 + MB_W / 2  # tray x of u = 0; seen from the back u runs towards -x
mb_z = PLATE - MB_SINK  # board front face
mb_floor = mb_z - MB_RELIEF
# SMA bulkhead jacks: one in the tray's top wall (kept, for later), one in the
# stand's top cap (the MULTI's, see the backpack).
SMA_HOLE = 6.5  # 1/4"-36 thread, 6.2-6.3 measured
SMA_HEX = 8.0  # MEASURE: across flats
SMA_BODY = 12.0  # hex to the end of the crimp, inside
SMA_FLOOR = 0.6  # the tray back is thinned to this under the SMA body
SMA_Z = 4.8  # hex flats up and down: 0.2 mm off the floor, 0.4 mm under the P4 PCB
sma_x = mb_right - MB_IPEX[0]


def mb_box(u0, v0, u1, v1, z0, z1):
    return box(mb_right - u1, MB_TOP - v1, z0, mb_right - u0, MB_TOP - v0, z1)


def mb_xy(u, v):
    return mb_right - u, MB_TOP - v


# ---- stand ---------------------------------------------------------------------
# One profile, extruded along the stand's width (z) and printed standing on an
# end, so every wall lies in the layers. In the profile (U back, V up):
#   - a shell: the floor on the MOZA, the back wall the MULTI cover goes on,
#     the top with the two antenna jacks, the slope the tray screws to, and a
#     front panel with the speaker grille;
#   - an inverted V under the slope, a vertical leg and a diagonal from one
#     point on it down to the floor. With the floor it is a triangle, and that
#     is what holds the tray: a 2D frame check (2 mm walls, unfilled PPA) gave
#     ~150 N/mm against a press on the middle of the screen.
# The bay in front of the V takes the speaker, the 12-pin plugs behind the
# tray's bottom edge and the MOZA screws; the triangle inside the V the ELRS
# Nano; the room behind it the MULTI and the jacks' bodies.
TILT = 25.0  # screen leaned back from vertical, degrees
LIFT = 12.0  # tray's bottom-back edge above the stand's base line (TF card access)
STAND_W = 110.0
ST_T = 3.0  # walls (2 mm was too thin to print standing this tall)
TOP_T = 3.0  # the top, which the antenna jacks clamp
SLOPE_S = (24.0, 90.0)  # along the tray back, from its bottom edge: starts above the 12-pin windows (to s = 18.4)
FRONT_U = 0.0
LEG_U = 30.0  # the V's vertical leg, behind the 12-pin plugs (they reach U 26 at 20 mm out)
EDGE = 0.8  # every edge of the profile rounded this much
PAD, PAD_R = 5.6 - ST_T, 6.0  # diamond pads round the nut pockets (wall + pad 5.6, as the screws need): thick, half-diagonal
CLEAR_R, HEAD_D = 1.7, 6.4  # the tray's and the cover's holes, as printed (M3 countersunk; M2.5 screws go in them)
M25_R = 1.45  # M2.5 clearance in the stand
NUT_R = (5.0 + 0.3) / np.sqrt(3)  # M2.5 hex nut, 5 across flats: pocket's corner radius
NUT_T = 2.0
stand_x0 = GW / 2 - STAND_W / 2
SCREWS = [(x, s) for x in (stand_x0 + 10, stand_x0 + STAND_W - 10) for s in (32.0, 80.0)]  # as the tray was printed

T = np.radians(TILT)
sT, cT = np.sin(T), np.cos(T)


def side_window(x0, x1, y0, y1, z0=PLATE + 0.3, z1=None):
    """Window through a side wall, by default over the gap under the PCB."""
    return box(x0, y0, z0, x1, y1, pcb_back + 1.0 if z1 is None else z1)


def tray():
    out = rbox(X0, Y0, 0, X1 - X0, Y1 - Y0, tray_top, R)
    out -= rbox(-FIT, -FIT, PLATE, GW + 2 * FIT, GH + 2 * FIT, tray_top, 1.0)

    cut = Manifold()
    for y in (UART_C_Y, USB_C_Y):  # round the plug's overmould, centred on the receptacle
        w, h = USBC_PLUG
        cut += side_window(X0 - 1, 1, y - w / 2, y + w / 2, USBC_Z - h / 2, USBC_Z + h / 2)
    for y, h in ((USB_A_Y, 15.5), (SWITCH_Y, 10.0)):
        cut += side_window(X0 - 1, 1, y - h / 2, y + h / 2)
    cut += side_window(GW - 1, X1 + 1, *BUTTONS_Y)
    cut += box(TF_X[0] - TF_SIDE, Y0 - 1, PLATE + 1.0, TF_X[1] + TF_SIDE, 1, pcb_back + 0.3)
    for x0, x1 in FPC_X:
        cut += box(x0 - FPC_SIDE, -FIT - FPC_OUT - FPC_DEEP, pcb_back - 1.0, x1 + FPC_SIDE, 1, tray_top + 1)

    # Back: plug windows, board screws, tray -> stand screws.
    x0, y0, x1, y1 = PH_WIN
    cut += box(x0, y0, -1, x1, y1, PLATE + 1)
    for x0, x1 in PIN12_WIN:
        cut += box(x0, PCB_DY + 0.5, -1, x1, PCB_DY + 12.0, PLATE + 1)
    for x in HOLE_X:
        for y in HOLE_Y:
            cut += cyl(x, y, -1, PLATE + 1, STANDOFF_HOLE / 2)
            sink = STANDOFF_HEAD / 2 - STANDOFF_HOLE / 2
            cut += cyl(x, y, -1, sink, STANDOFF_HOLE / 2 + sink + 1, STANDOFF_HOLE / 2)
    # MULTI (now on the stand): openings for the controls, a pocket under the IPEX, the SMA hole.
    cut += mb_box(*MB_LEDS, -1, PLATE + 1)
    cut += mb_box(*MB_KEYS, -1, PLATE + 1)
    # Pocket the board drops into (room at the top to tilt it in under the
    # lips), its floor lower again, and a channel for the header's plugs.
    cut += mb_box(-0.4, -1.4, MB_W + 0.4, MB_H + 0.4, mb_z, PLATE + 1)
    cut += mb_box(0.3, 0.3, MB_W - 0.3, MB_H - 0.3, mb_floor, PLATE + 1)
    cut += mb_box(MB_W - 1, MB_HEADER[0] - 1.5, MB_W + MB_HEADER[2] + 18, MB_HEADER[1] + 1.5, mb_z, PLATE + 1)
    u0, v0, u1, v1, _ = MB_SHIELD
    cut += mb_box(u0 - 0.5, v0 - 0.5, u1 + 0.5, v1 + 0.5, -1, PLATE + 1)
    cut += mb_box(MB_IPEX[0] - 3, -6, MB_IPEX[0] + 3, MB_IPEX[1] + 3, -1, PLATE + 1)  # IPEX and its coax, through
    cut += box(sma_x - 5.0, GH + FIT - SMA_BODY - 1, SMA_FLOOR, sma_x + 5.0, GH + FIT + 0.01, PLATE + 1)
    cut += Manifold.cylinder(WALL + FIT + 2, SMA_HOLE / 2).rotate([-90, 0, 0]).translate([sma_x, GH, SMA_Z])
    sink = HEAD_D / 2 - CLEAR_R  # 90 degree countersink on the inside face
    for x, s in SCREWS:
        y = s + Y0
        cut += cyl(x, y, -1, PLATE + 1, CLEAR_R)
        cut += cyl(x, y, PLATE - sink, PLATE + 1, CLEAR_R, CLEAR_R + sink + 1)
    out -= cut

    # MULTI: full-thickness pads under the screws and the bottom edge, the
    # screws countersunk on the outside (the stand covers them), lips.
    head = 4.7  # M2.5 countersunk (DIN 7991)
    for u, v in MB_HOLES:
        x, y = mb_xy(u, v)
        out += cyl(x, y, mb_floor - 0.1, mb_z, 2.8)
        out -= cyl(x, y, -1, PLATE + 1, 1.45)
        out -= cyl(x, y, -1, head / 2 - 1.45, head / 2 + 1, 1.45)
    for u in MB_HOOKS:
        x, y = mb_xy(u, MB_H)
        z_lip = mb_z + MB_T + 0.15
        out += box(x - 2.5, y - 2.0, PLATE - 0.1, x + 2.5, y - 0.4, z_lip + 1.0)  # post, on the pocket's edge
        out += box(x - 2.5, y - 0.41, z_lip, x + 2.5, y + 0.8, z_lip + 1.0)  # lip over the edge
        out += box(x - 2.5, y, mb_floor - 0.1, x + 2.5, y + 1.8, mb_z)  # pad under the board
    return out


# ---- placing things: tray -> desk ------------------------------------------------
# World: X = x, U = depth (away from the viewer), V = up. A point s along the
# tray's back from its bottom edge and n behind it sits at
# U = s sinT + n cosT, V = LIFT + s cosT - n sinT.
def uv(s, n):
    return (s * sT + n * cT, LIFT + s * cT - n * sT)


TRAY_TO_WORLD = np.array([
    [1, 0, 0, 0],
    [0, sT, -cT, -Y0 * sT],
    [0, cT, sT, LIFT - Y0 * cT],
])
# The stand is modelled in its print frame (profile in U-V, extruded along
# z = X - stand_x0); this maps it into the world.
STAND_TO_WORLD = np.array([
    [0, 0, 1, stand_x0],
    [1, 0, 0, 0],
    [0, 1, 0, 0],
])


WORLD_TO_STAND = np.array([
    [0, 1, 0, 0],
    [0, 0, 1, 0],
    [1, 0, 0, -stand_x0],
])


# ---- backpack: the MULTI module and the ELRS Nano live inside the stand -----------
# The MULTI pocket in the tray (above) stays as printed but is unused.
# The MULTI board hangs on a cover plate screwed over a window in the stand's
# back wall, front outwards, the way its own case held it.
# Cover frame: x = u and y = v of the board, z inwards from the cover's
# outer face. The cover prints outer face down.
COVER_T = 2.5
CV_GAP = 6.5  # cover inner face to the board front (3 lower than the original's, after a print)
CV_POSTS = [(u + 1.5, v + 1.0) for u, v in MB_HOLES]  # moved after prints: 1.5 to the left seen from the posts' side (larger u), 1 down
CV_FLANGE = 7.0
CV_D0 = 28.0  # board's u = 0 edge, this far down the back wall from the top
CV_X0 = 27.5  # board's v = 0 (antenna) edge, along the stand
CV_WIN = (-1.5, -1.0, MB_W + MB_HEADER[2] + 1.0, MB_H + 3.5)  # window in the wall: the board with its header passes, and the hooks
CV_SCREWS = [(x, y) for x in (CV_WIN[0] - 3.5, CV_WIN[2] + 3.5) for y in (CV_WIN[1] - 3.5, CV_WIN[3] + 3.5)]  # M2.5 x 8 countersunk -> nuts inside the back wall
# The bind / dial / USB row as it lands on the cover, after a print: the dial
# centred across the cover, the row 0.5 higher (smaller v). The board's row
# (MB_BIND, MB_DIAL, MB_USB) stays as the tray was printed.
CV_ROW_DU = (CV_WIN[0] + CV_WIN[2]) / 2 - MB_DIAL[0]
CV_ROW_DV = -0.5
CV_USB_R = CV_POSTS[1][0] - 2.7 / 2 + 2.0  # USB's right side: the board's right hole's left edge, then 2 to the right after a fitting
CV_LED_DU = (CV_WIN[0] + CV_WIN[2]) / 2 - sum(MB_LED_U) / 2  # the two lights centred across the cover too
NANO = (12.0, 20.0)  # MEASURE: ELRS Nano RX footprint (across, along the stand), taped down inside the V

# Speaker (100 x 45 x 21 two-driver box, 2-pin PH2.0) facing forward under the
# screen, behind the grille in the front panel, like a sound bar. It slides in
# from the stand's open end at z = 0 into a slot: the panel in front, a ledge
# under its front edge, a shelf over it (the panel's top turned back), and a
# bar behind it off the V's leg, at its middle height: its back slopes in
# towards the top and bottom edges, so only the middle is a full SPK_D deep. A stop at the far end (the end on the bed);
# at the near end an M2.5 x 8 self-tapping screw with a washer in the ledge's
# end face. Its ears (rings in the corner notches) are not used.
SPK_L, SPK_W, SPK_D = 100.0, 45.0, 21.0  # along the stand, up, front to back
SPK_FIT = 0.3
PANEL_TOP = 10.5  # just under the tray's bottom-back edge (LIFT)
SPK_LIFT = 3.6  # the speaker's bottom over the floor: the M3 heads (3 high) pass under its back
SHELF = 7.0  # the shelf over the speaker and the ledge under it reach this far back from the panel
BAR_H = 8.0  # the bar behind it, this tall, centred on it
spk_top = PANEL_TOP - ST_T - SPK_FIT
spk_v = spk_top - SPK_W / 2  # speaker's middle
floor_v = spk_top - SPK_W - SPK_LIFT  # the floor's top
FOOT_H = ST_T - floor_v  # base line this high over the MOZA
spk_back = FRONT_U + ST_T + SPK_D
SPK_Z0 = 1.0  # its near end; the washer's under it
STOP_PILOT = 2.2  # M2.5 self-tapping, along z into the ledge's end
stop_uv = (FRONT_U + ST_T + SHELF / 2, floor_v + 1.4)
# Fixing to the top of the MOZA wheel base: its two M3 holes, 70 apart across
# it, under the bay. M3 x 6 socket heads, put in through the bay's open ends,
# turned with a 2.5 hex key through the slope's windows (before the tray).
MOZA_ZS = (STAND_W / 2 - 35.0, STAND_W / 2 + 35.0)
MOZA_U = 23.0
M3_R = 1.7

# The top, from the slope's top edge back to the back wall; the antenna jacks
# stand in it near the ends, their bodies inside.
top_v = uv(SLOPE_S[1], 0)[1]
sma_hex_r = SMA_HEX / np.sqrt(3)
SMA_ZS = (10.0, STAND_W - 10.0)  # the MULTI's and the Nano's antennas
SMA_U = 52.0  # a 12 mm antenna stands clear of the tray's top edge
back_u = SMA_U + sma_hex_r + 1.6 + ST_T  # the jack's hex clear of the corner's fillet
cv_p0 = np.array((back_u + COVER_T, top_v - CV_D0))  # cover's outer face, at the board's u = 0 edge
COVER_TO_STAND = np.array([
    [0, 0, -1, cv_p0[0]],
    [-1, 0, 0, cv_p0[1]],
    [0, 1, 0, CV_X0],
])
# The cover turned half round on the wall, about its middle (the window seen
# from behind flipped side to side, after a fitting): its screw pattern lands
# on itself.
_cx, _cy = (CV_WIN[0] + CV_WIN[2]) / 2, (CV_WIN[1] + CV_WIN[3]) / 2
COVER_TO_STAND = COVER_TO_STAND @ np.array([[-1, 0, 0, 2 * _cx], [0, -1, 0, 2 * _cy], [0, 0, 1, 0], [0, 0, 0, 1]])


def cv_window():
    """The window, its corners at 45 degrees at the end that prints on top, so it bridges less."""
    x0, y0, x1, y1 = CV_WIN
    c = 6.0
    poly = CrossSection([[(x0, y0), (x1, y0), (x1, y1 - c), (x1 - c, y1), (x0 + c, y1), (x0, y1 - c)]])
    return Manifold.extrude(poly, ST_T + PAD + 2).translate([0, 0, COVER_T - 0.1])


# ---- the profile -------------------------------------------------------------------
def ccw(points):
    """The points, counter-clockwise."""
    pts = [tuple(map(float, q)) for q in points]
    area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1]))
    return pts if area > 0 else pts[::-1]


def keep(p, nrm, big=400.0):
    """The half-plane {x: (x - p) . nrm >= 0}, as a big polygon."""
    p, nrm = np.asarray(p, float), np.asarray(nrm, float) / np.linalg.norm(nrm)
    d = np.array([nrm[1], -nrm[0]])
    return CrossSection([[tuple(p - d * big), tuple(p + d * big), tuple(p + d * big + nrm * big), tuple(p - d * big + nrm * big)]])


def fillet(points, radii, seg=10):
    """Polygon with corner i rounded to radii[i] (0: sharp)."""
    pts = [np.asarray(q, float) for q in points]
    out = []
    for i, (q, r) in enumerate(zip(pts, radii)):
        if r <= 0:
            out.append(tuple(q))
            continue
        a, b = pts[i - 1], pts[(i + 1) % len(pts)]
        u1, u2 = (q - a) / np.linalg.norm(q - a), (b - q) / np.linalg.norm(b - q)
        ang = np.arccos(np.clip(-u1 @ u2, -1, 1))  # the corner's angle
        d = r / np.tan(ang / 2)
        bis = (u2 - u1) / np.linalg.norm(u2 - u1)
        c = q + bis * r / np.sin(ang / 2)
        t0, t1 = q - u1 * d - c, q + u2 * d - c
        a0, a1 = np.arctan2(t0[1], t0[0]), np.arctan2(t1[1], t1[0])
        turn = (a1 - a0 + np.pi) % (2 * np.pi) - np.pi
        out += [tuple(c + r * np.array([np.cos(a0 + turn * k / seg), np.sin(a0 + turn * k / seg)])) for k in range(seg + 1)]
    return out


n_slope = np.array([cT, -sT])  # into the stand, square to the slope
d_slope = np.array([sT, cT])  # up the slope


def slope_at(u, n):
    """s where the line n (off the tray's back) reaches U = u."""
    return (u - n * cT) / sT


def v_points():
    """The V: apex on the slope's inner face over the leg, and the diagonal's
    foot on the floor, as far back as the MULTI's back parts allow."""
    apex = np.array(uv(slope_at(LEG_U, ST_T), ST_T))
    mb = multi(plugs=True).transform(COVER_TO_STAND).bounding_box()
    clear_u, clear_v = mb[0] - 1.0, mb[1]  # the MULTI's lowest, most forward corner, less 1
    foot = np.array((back_u - ST_T, floor_v))
    for _ in range(60):  # pull the foot forward until the diagonal's back face passes the MULTI
        d = (foot - apex) / np.linalg.norm(foot - apex)
        back = np.array((-d[1], d[0])) * ST_T / 2
        k = (clear_v - (apex + back)[1]) / d[1]
        if (apex + back + d * k)[0] <= clear_u:
            break
        foot[0] -= 0.2
    return apex, foot


def profile():
    """The stand's cross-section (U, V)."""
    s0, s1 = SLOPE_S
    F = -FOOT_H
    apex, foot = v_points()
    d = (foot - apex) / np.linalg.norm(foot - apex)
    n_back = np.array((-d[1], d[0]))  # off the diagonal, towards the back wall
    hull = CrossSection([ccw(fillet([(FRONT_U, F), (back_u, F), (back_u, top_v), uv(s1, 0), uv(s0, 0), (FRONT_U, PANEL_TOP)],
                                [1.5, 1.5, 4.0, 3.0, 0, 0]))])
    big = CrossSection.square([600, 600]).translate([-300, -300])
    rear = (big ^ keep(uv(0, ST_T), n_slope) ^ keep((0, top_v - TOP_T), (0, -1)) ^ keep((back_u - ST_T, 0), (-1, 0))
            ^ keep((0, floor_v), (0, 1)) ^ keep(apex + n_back * ST_T / 2, n_back))
    inner = big ^ keep((LEG_U + ST_T / 2, 0), (1, 0)) ^ keep(apex - n_back * ST_T / 2, -n_back) ^ keep((0, floor_v), (0, 1))
    # The bay: in front of the leg, under the slope, open to the front over the panel.
    leg_f = LEG_U - ST_T / 2
    bay = CrossSection([ccw([(FRONT_U + ST_T, floor_v), (leg_f, floor_v), uv(slope_at(leg_f, ST_T), ST_T), uv(s0, ST_T), uv(s0, 0),
                             uv(s0, -10), (FRONT_U - 10, PANEL_TOP), (FRONT_U + ST_T, PANEL_TOP)])])
    prof = hull - bay - rear - inner
    # The speaker's slot: shelf, ledge, and the bar behind its middle off the leg.
    f0, b0 = FRONT_U + ST_T, spk_back + SPK_FIT
    spk_bot = spk_top - SPK_W
    rect = lambda u0, v0, u1, v1: CrossSection.square([u1 - u0, v1 - v0]).translate([u0, v0])
    prof += rect(FRONT_U, PANEL_TOP - ST_T, f0 + SHELF, PANEL_TOP) + rect(f0 - 0.5, floor_v - 0.5, f0 + SHELF, spk_bot)
    prof += rect(b0, spk_v - BAR_H / 2, leg_f + 0.5, spk_v + BAR_H / 2)
    prof = prof.offset(2.0, JoinType.Round).offset(-2.0, JoinType.Round)  # fillets in every inside corner
    prof = prof.offset(-EDGE, JoinType.Round).offset(EDGE, JoinType.Round)  # and the outside edges eased
    return prof - rect(f0, spk_bot, b0, spk_top + SPK_FIT)  # but the slot's corners square


def cut_through(outline, p0, d, n, t, z0=0.0):
    """An outline drawn in a wall's own plane (along d, and along z from z0)
    cut through the wall, t thick, from its face at p0 (U, V) along n."""
    if outline.is_empty():
        return Manifold()
    p0, d, n = np.asarray(p0, float), np.asarray(d, float), np.asarray(n, float)
    m = Manifold.extrude(outline, t + 2).translate([0, 0, -1])
    if d[0] * n[1] - d[1] * n[0] > 0:  # keep the frame right-handed: come through from the other face
        p0, n = p0 + t * n, -n
    return m.transform(np.array([[d[0], 0, n[0], p0[0]], [d[1], 0, n[1], p0[1]], [0, 1, 0, z0]]))


def pointed(z0, z1, a0, a1):
    """Opening from a0 to a1 across a wall and z0 to z1 along the stand, drawn as (across, z),
    its ends pointed at 45 degrees along z (up when printed)."""
    h = (a1 - a0) / 2
    if z1 - z0 <= 2 * h + 0.01:  # too short for a straight middle: a diamond
        h = (z1 - z0) / 2
        m = (a0 + a1) / 2
        pts = [(z0, m), (z0 + h, m - h), (z1, m), (z0 + h, m + h)]
    else:
        pts = [(z0, a0 + h), (z0 + h, a0), (z1 - h, a0), (z1, a0 + h), (z1 - h, a1), (z0 + h, a1)]
    return CrossSection([ccw([(a, z) for z, a in pts])])


def row(a0, a1, size=26.0, centres=(20.0, 55.0, 90.0)):
    """Three openings along the stand, a0..a1 across, each size long (z)."""
    return CrossSection.batch_boolean([pointed(c - size / 2, c + size / 2, a0, a1) for c in centres], OpType.Add)


def speaker(z0=SPK_Z0):
    """Stand-in, facing forward against the panel's back, its near end at z0."""
    f0 = FRONT_U + ST_T
    return box(f0, spk_top - SPK_W, z0, f0 + SPK_D, spk_top, z0 + SPK_L)


def _wall_frame(p0, d, n):
    p0, d, n = np.asarray(p0, float), np.asarray(d, float), np.asarray(n, float)
    if d[0] * n[1] - d[1] * n[0] > 0:
        d = -d
    return np.array([[d[0], 0, n[0], p0[0]], [d[1], 0, n[1], p0[1]], [0, 1, 0, 0]])


def stand():
    s0, s1 = SLOPE_S
    zc = STAND_W / 2
    prof = profile()
    # The z = STAND_W end is the one on the bed, full section for the grip;
    # the other end is eased: the outline steps in 0.2 a layer for 0.6.
    out = Manifold.extrude(prof, STAND_W - 0.6).translate([0, 0, 0.6])
    for k, e in enumerate((0.6, 0.4, 0.2)):
        out += Manifold.extrude(prof.offset(-e, JoinType.Round), 0.22).translate([0, 0, k * 0.2])  # overlapping a little, so they fuse

    # Nut pads: under the slope for the tray screws, inside the back wall for the cover's.
    tray_pads = [(uv(s, ST_T), x - stand_x0) for x, s in SCREWS]
    for p, z in tray_pads:
        out += _pad(np.array(p), d_slope, n_slope, z)
    cover_pts = [(COVER_TO_STAND @ np.array([x, y, 0, 1])) for x, y in CV_SCREWS]
    for q in cover_pts:
        out += _pad(np.array((back_u - ST_T, q[1])), np.array((0.0, 1.0)), np.array((-1.0, 0.0)), q[2])

    # Openings. The slope's windows (behind the tray) let the hex key down to
    # the MOZA screws; the V's legs have two rows of diamonds each.
    apex, foot = v_points()
    s_a = slope_at(LEG_U - ST_T / 2, ST_T) - 4.0  # where the leg's fillet starts on the slope
    s_w = (38.0 + 2.0, s_a - 1.0)
    out -= cut_through(row(*s_w), uv(0, 0), d_slope, n_slope, ST_T)
    v_in = _inner_apex(apex, foot)
    for (a, b, n_dir) in ((np.array((LEG_U, floor_v)), np.array((LEG_U, v_in)), np.array((1.0, 0.0))),
                          (foot, apex + (v_in - apex[1]) / ((foot - apex)[1]) * (foot - apex), None)):
        L = np.linalg.norm(b - a)
        dd = (b - a) / L
        nn = np.array((-dd[1], dd[0])) if n_dir is None else n_dir
        mid = L / 2
        lattice = CrossSection.batch_boolean([row(m - 11.0, m + 11.0, 22.0) for m in (mid - 15.0, mid + 15.0)], OpType.Add)
        out -= cut_through(lattice, a - nn * ST_T / 2, dd, nn, ST_T)

    # Floor: the MOZA screws (teardrops, the point up as printed).
    for z in MOZA_ZS:
        out -= _teardrop(M3_R, ST_T + 2).rotate([-90, 0, 0]).translate([MOZA_U, -FOOT_H - 1, z])

    # Front panel: the grille over the speaker's face.
    gz = SPK_Z0 + SPK_L / 2
    grille = CrossSection.batch_boolean([pointed(gz - 42.0, gz + 42.0, spk_v + dv - 1.1, spk_v + dv + 1.1)
                                         for dv in np.arange(-18.0, 18.1, 4.0)], OpType.Add)
    out -= cut_through(grille, (FRONT_U, 0), (0, 1), (1, 0), ST_T)
    # The speaker's stop at the far end (on the bed), the screw's pilot at the near end.
    f0 = FRONT_U + ST_T
    out += box(f0 - 0.5, floor_v - 0.5, SPK_Z0 + SPK_L + SPK_FIT, spk_back, spk_top - SPK_W + 12.0, STAND_W)
    out -= cyl(*stop_uv, -1, 8.0, STOP_PILOT / 2)

    # Back wall: the MULTI window, the cover's M2.5 holes and nut pockets.
    wall_in = COVER_T + ST_T + PAD
    cut = cv_window()
    for x, y in CV_SCREWS:
        cut += cyl(x, y, COVER_T - 0.1, wall_in + 1, M25_R)
        cut += Manifold.cylinder(NUT_T + 0.4 + 1, NUT_R, circular_segments=6).rotate([0, 0, 90]).translate([x, y, wall_in - NUT_T - 0.4])
    out -= cut.transform(COVER_TO_STAND)

    # Antenna jacks, upright through the top (teardrops).
    for z in SMA_ZS:
        out -= _teardrop(SMA_HOLE / 2, TOP_T + 2).rotate([-90, 0, 0]).translate([SMA_U, top_v - TOP_T - 1, z])

    # Tray screws: M2.5 holes square to the slope, hex pockets for the nuts in the pads.
    for x, s in SCREWS:
        along = lambda m, n: m.rotate([0, 90, 0]).rotate([0, 0, -TILT]).translate([*uv(s, n), x - stand_x0])
        out -= along(Manifold.cylinder(ST_T + PAD + 2, M25_R), -1.0)
        out -= along(Manifold.cylinder(NUT_T + 0.4 + 1, NUT_R, circular_segments=6), ST_T + PAD - NUT_T - 0.4)
    return out


def _pad(p0, d, n, z):
    """Diamond pad on a wall's inner face at p0 (U, V), d along the wall, n off it into the room."""
    diamond = CrossSection([[(-PAD_R, z), (0, z - PAD_R), (PAD_R, z), (0, z + PAD_R)]])
    return Manifold.extrude(diamond, PAD + 0.01).transform(_wall_frame(p0 - n * 0.01, d, n))


def _inner_apex(apex, foot):
    """V where the leg's back face meets the diagonal's front face."""
    d = (foot - apex) / np.linalg.norm(foot - apex)
    n_back = np.array((-d[1], d[0]))
    q = apex - n_back * ST_T / 2
    k = (LEG_U + ST_T / 2 - q[0]) / d[0]
    return (q + d * k)[1]


def _teardrop(r, h):
    """Upright hole along z (as built), with a 45 degree point towards -y; rotated into place by the caller."""
    tip = CrossSection([[(-r * np.cos(np.pi / 4), r * np.sin(np.pi / 4)), (0, r * np.sqrt(2)), (r * np.cos(np.pi / 4), r * np.sin(np.pi / 4))]])
    return Manifold.extrude(CrossSection.circle(r, 32) + tip, h)


def cover():
    x0, y0, x1, y1 = CV_WIN
    f = CV_FLANGE
    out = rbox(x0 - f, y0 - f, 0, x1 - x0 + 2 * f, y1 - y0 + 2 * f, COVER_T, 3.0)
    top = COVER_T + CV_GAP  # board front
    # Posts for the two holes (M2.5 x 6 self-tapping), hooks and pads at the bottom edge.
    for u, v in CV_POSTS:
        out += cyl(u, v, COVER_T - 0.1, top, 2.8)
        out -= cyl(u, v, COVER_T + 0.6, top + 1, 1.05)
    for u in MB_HOOKS:
        z_lip = top + MB_T + 0.15
        out += box(u - 2.5, MB_H + 0.4, COVER_T - 0.1, u + 2.5, MB_H + 2.0, z_lip + 1.0)  # flexing post
        out += box(u - 2.5, MB_H - 0.8, z_lip, u + 2.5, MB_H + 0.41, z_lip + 1.0)  # lip over the board's back
        out += box(u - 1.0, MB_H - 2.5, COVER_T - 0.1, u + 2.5, MB_H, top)  # pad under the board, clear of the USB receptacle
    # Holes for the controls: the cover's own sizes across the board (u).
    du, dv = CV_ROW_DU, CV_ROW_DV
    cut = cyl(MB_BIND[0] + du - 0.5, MB_BIND[1] + dv, -1, COVER_T + 1, 2.3)  # bind button 3.2; 0.5 further from the dial, after a print
    cut += cyl(MB_DIAL[0] + du, MB_DIAL[1] + dv, -1, COVER_T + 1, 3.8)  # knob 6.8
    for u in MB_LED_U:
        cut += cyl(u + CV_LED_DU, 36.4, -1, COVER_T + 1, 2.0)
    row = MB_ROW_V + dv
    cut += box(CV_USB_R - 4.5, row - 4.5, -1, CV_USB_R + 1.0, row + 4.5, COVER_T + 1)  # 5.5 wide: 0.5 more on the right ("at least 2")
    sink = HEAD_D / 2 - CLEAR_R
    for x, y in CV_SCREWS:
        cut += cyl(x, y, -1, COVER_T + 1, CLEAR_R)
        cut += cyl(x, y, -1, sink, CLEAR_R + sink + 1, CLEAR_R)
    return out - cut


# ---- stand-in board, for the checks and the preview ---------------------------
def board():
    pcb = box(0.2, PCB_DY, pcb_back, GW - 0.2, PCB_DY + PCB_H, pcb_back + 1.6)
    glass = box(0, 0, pcb_back + 1.6, GW, GH, pcb_back + STACK)
    standoffs = Manifold()
    for x in HOLE_X:
        for y in HOLE_Y:
            standoffs += cyl(x, y, PLATE, pcb_back, 2.6)
    ports = Manifold()
    for y, w, h in ((UART_C_Y, 8.9, 3.2), (USB_C_Y, 8.9, 3.2), (USB_A_Y, 13.1, 5.7)):
        ports += box(-0.5, y - w / 2, pcb_back - h, 14, y + w / 2, pcb_back)
    flex = Manifold()
    for x0, x1 in FPC_X:
        flex += box(x0, -FPC_OUT, pcb_back + 1.6, x1, 0, pcb_back + 2.4)
    return pcb + glass + standoffs + ports + flex


def multi(plugs=False):
    """The MULTI board on its cover, in the cover frame; plugs: the Dupont plugs on its header."""
    f = COVER_T + CV_GAP  # front face
    b = f + MB_T
    out = box(0, 0, f, MB_W, MB_H, b)
    out += box(1, 5, b, MB_W - 1, MB_H - 2, b + MB_BACK_H)  # back components
    u0, v0, u1, v1, h = MB_SHIELD
    out += box(u0, v0, f - h, u1, v1, f)
    out += box(MB_IPEX[0] - 1.5, MB_IPEX[1] - 1.5, f - 1.3, MB_IPEX[0] + 1.5, MB_IPEX[1] + 1.5, f)
    du, dv = CV_ROW_DU, CV_ROW_DV  # where the row was found to sit on the cover
    u, v = MB_DIAL[0] + du, MB_DIAL[1] + dv
    out += box(u - 5, v - 5, f - 5, u + 5, v + 5, f)
    out += cyl(u, v, f - MB_DIAL[2], f - 5, 3.4)  # knob
    out += cyl(MB_BIND[0] + du, MB_BIND[1] + dv, f - 11, f, 1.6)  # tall tact switch, cap 11 up
    v = MB_USB[1] + dv
    out += box(CV_USB_R - 4.6, v - 4.3, f - 4, CV_USB_R, v + 4.3, f)
    for u in MB_LED_U:
        out += cyl(u + CV_LED_DU, 36.4, f - 9, f, 1.5)  # light pipes
    v0, v1, out_len = MB_HEADER
    out += box(MB_W - 2, v0, b, MB_W + out_len, v1, b + 2.5)
    if plugs:
        out += box(MB_W + out_len - 0.5, v0 + 0.5, b - 0.8, MB_W + out_len + 15, v1 - 0.5, b + 3.3)
    return out


def tray_sma():
    """The SMA jack in the tray's top wall, tray frame."""
    inner = GH + FIT
    thread = Manifold.cylinder(WALL + 8, 6.25 / 2).rotate([-90, 0, 0]).translate([sma_x, inner, SMA_Z])
    hexa = Manifold.cylinder(2.5, SMA_HEX / np.sqrt(3), circular_segments=6).rotate([-90, 0, 0]).translate([sma_x, inner - 2.5, SMA_Z])
    tail = Manifold.cylinder(SMA_BODY - 2.5, 2.5).rotate([-90, 0, 0]).translate([sma_x, inner - SMA_BODY, SMA_Z])
    return thread + hexa + tail


def sma():
    """The SMA jacks in the stand's top, stand frame (y up)."""
    out = Manifold()
    for z in SMA_ZS:
        up = lambda m, v: m.rotate([-90, 0, 0]).translate([SMA_U, v, z])
        out += up(Manifold.cylinder(TOP_T + 8, 6.25 / 2), top_v - TOP_T)
        out += up(Manifold.cylinder(2.5, sma_hex_r, circular_segments=6), top_v - TOP_T - 2.5)
        out += up(Manifold.cylinder(SMA_BODY - 2.5, 2.5), top_v - TOP_T - SMA_BODY)
    return out


def pin12_plugs(out_mm):
    """The two 12-pin plugs with their wires' bend, out_mm behind the tray's back (tray frame)."""
    return Manifold.batch_boolean([box(x0 + 1, PCB_DY + 1, -out_mm, x1 - 1, PCB_DY + 11.5, 0.5) for x0, x1 in PIN12_WIN], OpType.Add)


def nano():
    """Stand-in: the ELRS Nano taped to the floor inside the V, at the end under its antenna's jack."""
    u0 = LEG_U + ST_T / 2 + 2.0
    return box(u0, floor_v, 3.0, u0 + NANO[0], floor_v + 3.5, 3.0 + NANO[1])


def moza_screws():
    """M3 x 6 socket heads through the floor, stand frame."""
    one = Manifold.cylinder(3.0, 2.75) + Manifold.cylinder(6.0, 1.5).translate([0, 0, -6.0])
    return Manifold.batch_boolean([one.rotate([-90, 0, 0]).translate([MOZA_U, floor_v, z]) for z in MOZA_ZS], OpType.Add)


# ---- assembly page ---------------------------------------------------------------
def tris_b64(m):
    mesh = m.to_mesh()
    verts = np.asarray(mesh.vert_properties, dtype=np.float32)[:, :3]
    return base64.b64encode(verts[np.asarray(mesh.tri_verts)].astype("<f4").tobytes()).decode("ascii")


def m25_screw(length, sunk):
    """M2.5 countersunk screw pointing down -z, its head's top at z = -sunk."""
    head = Manifold.cylinder(1.1, 1.25, 2.35).translate([0, 0, -1.1])
    return (head + Manifold.cylinder(length, 1.25).translate([0, 0, -length])).translate([0, 0, -sunk])


def m25_nut(z0):
    return (Manifold.cylinder(NUT_T, 5.0 / np.sqrt(3), circular_segments=6) - Manifold.cylinder(NUT_T * 3, 1.25).translate([0, 0, -1])).translate([0, 0, z0])


def assembly_parts():
    """Every part in the world frame (x right, y away from the viewer, z up), with the
    assembly step it goes in at and where it comes from: moves [(step, offset)]."""
    n_hat = np.array([0, cT, -sT])  # into the stand, square to the slope
    world = lambda m, frame: m.transform(TRAY_TO_WORLD) if frame == "tray" else m.transform(STAND_TO_WORLD)
    cover_w = lambda m: m.transform(COVER_TO_STAND).transform(STAND_TO_WORLD)
    sunk = (HEAD_D - 4.7) / 2  # an M2.5 head sits this much lower in the M3 countersinks
    screws_t = Manifold.batch_boolean([m25_screw(10, sunk).translate([x, s + Y0, PLATE]) for x, s in SCREWS], OpType.Add)
    nuts_t = Manifold.batch_boolean([m25_nut(-(ST_T + PAD - 0.4)).translate([x, s + Y0, 0]) for x, s in SCREWS], OpType.Add)
    wall_in = COVER_T + ST_T + PAD
    screws_c = Manifold.batch_boolean([m25_screw(8, sunk).mirror([0, 0, 1]).translate([x, y, 0]) for x, y in CV_SCREWS], OpType.Add)
    nuts_c = Manifold.batch_boolean([m25_nut(wall_in - NUT_T - 0.4).translate([x, y, 0]) for x, y in CV_SCREWS], OpType.Add)
    antenna = Manifold.batch_boolean([Manifold.cylinder(100, 5.0, 4.0).rotate([-90, 0, 0]).translate([SMA_U, top_v + 8, z]) for z in SMA_ZS], OpType.Add)
    pin12 = pin12_plugs(20.0)
    usbc = Manifold()
    for y in (UART_C_Y, USB_C_Y):
        usbc += box(X0 - 22, y - 5.5, USBC_Z - 3.0, X0 - 0.3, y + 5.5, USBC_Z + 3.0)
        usbc += Manifold.cylinder(30, 1.8).rotate([0, -90, 0]).translate([X0 - 21, y, USBC_Z])
        usbc += box(X0 - 0.3, y - 4.2, USBC_Z - 1.2, X0 + WALL + 3, y + 4.2, USBC_Z + 1.2)  # the plug's tongue in the socket
    desk = box(-30, -60, -FOOT_H - 2, GW + 30, 110, -FOOT_H)
    m3 = moza_screws()
    n = lambda k: (n_hat * k).tolist()
    return [
        # name, label, mesh (world), colour, moves
        ("desk", "MOZA 底座頂面", desk, 0xc8b49a, []),
        ("stand", "底座", world(stand(), "stand"), 0x5f7389, [(0, [0, 0, 60])]),
        ("mscrews", "M3×6 內六角 ×2（固定到 MOZA）", world(m3, "stand"), 0xe8e8e8, [(1, [0, 0, 70])]),
        ("nuts", "M2.5 螺母 ×8", world(nuts_t, "tray") + cover_w(nuts_c), 0xd9d9d9, [(2, [0, 0, 0])]),
        ("tray", "螢幕托盤", world(tray(), "tray"), 0x9aa7b4, [(3, n(-55))]),
        ("screws", "M2.5 螺絲", world(screws_t, "tray"), 0xe8e8e8, [(4, n(-25))]),
        ("board", "P4 主板＋螢幕", world(board(), "tray"), 0x22303c, [(5, n(-70))]),
        ("cover", "MULTI 面板", cover_w(cover()), 0xb7c2cc, [(6, [0, 0, 0]), (7, [0, 70, 0])]),
        ("multi", "MULTI 高頻頭", cover_w(multi()), 0x2f6b4f, [(6, [0, 40, 0]), (7, [0, 70, 0])]),
        ("cscrews", "面板螺絲", cover_w(screws_c), 0xe8e8e8, [(8, [0, 25, 0])]),
        ("sma", "SMA＋天線", world(sma() + antenna, "stand"), 0x1d2228, [(9, [0, 0, 45])]),
        ("nano", "ELRS Nano", world(nano(), "stand"), 0x3a5d8f, [(10, [-80, 0, 0])]),
        ("speaker", "喇叭", world(speaker(), "stand"), 0x2a2d33, [(11, [-130, 0, 0])]),
        ("plugs", "插頭（12-pin、Type-C、MULTI 排針）", world(pin12 + usbc, "tray") + cover_w(multi(plugs=True) - multi()),
         0xd9732b, [(12, n(25))]),
    ]


def export_page(path, checks):
    """Fills p4_viewer.html with the meshes and the checks -> a standalone page."""
    parts = assembly_parts()
    data = {
        "parts": [{"name": nm, "label": lb, "tris": tris_b64(m), "color": c, "moves": mv} for nm, lb, m, c, mv in parts],
        "checks": {k: round(v, 3) for k, v in checks.items()},
        "size": {"stand": [round(v, 1) for v in (np.array(stand().bounding_box()[3:]) - stand().bounding_box()[:3])],
                 "volume": round(stand().volume() / 1000, 1)},
        "centre": [GW / 2, 30, 40],
    }
    src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "p4_viewer.html")
    with open(src, encoding="utf-8") as f:
        page = f.read().replace("/*DATA*/null", json.dumps(data))
    with open(path, "w", encoding="utf-8") as f:
        f.write(page)


def main():
    os.makedirs(OUT, exist_ok=True)
    t, st, b, sm, cv = tray(), stand(), board(), sma(), cover()
    for name, m in [("tray", t), ("stand", st), ("cover", cv)]:
        if m.is_empty() or len(m.decompose()) != 1:
            sys.exit(f"{name}: not a single solid")

    to_stand = lambda m: m.transform(COVER_TO_STAND)
    t_w, st_w, b_w = t.transform(TRAY_TO_WORLD), st.transform(STAND_TO_WORLD), b.transform(TRAY_TO_WORLD)
    cv_s, mb_s, plugs_s = to_stand(cv), to_stand(multi()), to_stand(multi(plugs=True))
    cv_w, mb_w = cv_s.transform(STAND_TO_WORLD), mb_s.transform(STAND_TO_WORLD)
    clash = {"tray x board": (t ^ b).volume(), "tray x stand": (t_w ^ st_w).volume(), "board x stand": (b_w ^ st_w).volume(),
             "stand x sma": (st ^ sm).volume(), "cover x sma": (cv_s ^ sm).volume(),
             "tray x sma": (t_w ^ sm.transform(STAND_TO_WORLD)).volume(),
             "tray x its sma": (t ^ tray_sma()).volume(), "board x tray sma": (b ^ tray_sma()).volume(),
             "stand x cover": (st ^ cv_s).volume(), "cover x multi": (cv ^ multi()).volume(),
             "stand x multi + plugs": (st ^ plugs_s).volume(), "tray x multi": (t_w ^ mb_w).volume(),
             "stand x speaker": (st ^ speaker()).volume(), "stand x M3 screws": (st ^ moza_screws()).volume(),
             "stand x Nano": (st ^ nano()).volume(), "speaker x M3 screws": (speaker() ^ moza_screws()).volume(),
             "stand x 12-pin plugs": (st_w ^ pin12_plugs(20.0).transform(TRAY_TO_WORLD)).volume(),
"speaker's way in": (st ^ (speaker(-120.0) + speaker()).hull()).volume(),
             "speaker x 12-pin plugs": (speaker().transform(STAND_TO_WORLD) ^ pin12_plugs(20.0).transform(TRAY_TO_WORLD)).volume()}
    for k, v in clash.items():
        print(f"{k}: {v:.3f} mm3")
    if max(clash.values()) > 0.01:
        sys.exit("parts overlap")
    if min(st_w.bounding_box()[2], t_w.bounding_box()[2]) < -FOOT_H - 1e-6:
        sys.exit("something is below the desk")

    to_trimesh(t).export(os.path.join(OUT, "p4_tray.stl"))
    to_trimesh(st.rotate([180, 0, 0])).export(os.path.join(OUT, "p4_stand.stl"))  # standing on its z = STAND_W end
    to_trimesh(cv).export(os.path.join(OUT, "p4_multi_cover.stl"))
    case, part, dark = (0.62, 0.68, 0.76), (0.40, 0.46, 0.55), (0.15, 0.17, 0.2)
    preview(
        [
            ("on the desk, front", [(t_w, case), (st_w, part), (b_w, dark), (sm.transform(STAND_TO_WORLD), dark)], 18, -125),
            ("on the desk, back", [(t_w, case), (st_w, part), (cv_w, case), (mb_w, dark)], 22, 35),
            ("stand, cover off", [(st, part), (mb_s, dark)], 20, 60),
            ("MULTI cover, inside", [(cv, case), (multi(), dark)], 45, -60),
        ],
        os.path.join(OUT, "p4_preview.png"),
    )
    for name, m in [("tray", t), ("stand", st), ("cover", cv)]:
        lo, hi = m.bounding_box()[:3], m.bounding_box()[3:]
        print(f"{name}: {hi[0]-lo[0]:.1f} x {hi[1]-lo[1]:.1f} x {hi[2]-lo[2]:.1f} mm, volume {m.volume()/1000:.1f} cm3")
    export_page(os.path.join(OUT, "p4_assembly.html"), clash)


if __name__ == "__main__":
    main()
