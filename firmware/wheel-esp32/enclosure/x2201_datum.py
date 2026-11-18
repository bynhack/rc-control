"""X2201 reference points: the one place that says where things are in the
car and how the coordinate systems map into each other. Every enclosure
script, and the main board's layout, takes its numbers from here; nothing
else retypes them. Change a number here and re-run the scripts.

Every number says where it came from: CALIPERS (measured on the car),
SCAN (read off the 3D scan, check before relying on it), FIT (confirmed by
a test print in the car) or MEASURE (not known yet: a guess or None).

Three coordinate systems, all in mm:

CAR  (= the cage's, x2201_cage.py; the liner, the room, the FPV mount)
  x  forward; the windscreen's foot at x = 84 (x2201_cage.L)
  y  across, centred on the liner's mirror line; +y = the car's LEFT
  z  up from the chassis' top under the cab
  Tied to the real car by the liner's screw holes (LINER_* below).

CHASSIS  (x2201_hole_plate.py: the main board's mounts)
  origin  the M2 screw boss's centre, on its top
  x  forward, y = the car's left, z up (the same directions as CAR)

BOARD  (KiCad, hardware/x2201-mainboard: X, Y as KiCad shows them)
  X  across, 0 = the board's left edge in KiCad = the car's LEFT side
  Y  along, 0 = the front edge; Y runs DOWN the screen, i.e. backward
  (KiCad's Y is down, so a board drawn in (X, Y) with z up is MIRRORED:
  use board_to_chassis(), never (X, Y) as it stands.)

Where the board sits: MH1 on the M2 boss, MH2 over the locating post, so
  chassis x = MH1_Y - Y,  chassis y = MH1_X - X
and where the chassis sits in the car is CHASSIS_IN_CAR (MEASURE).
"""

import os

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD_PCB = os.path.normpath(os.path.join(HERE, "../../../hardware/x2201-mainboard/x2201-mainboard.kicad_pcb"))

# ---- the liner, in CAR (SCAN: Mesh 1111, fitted to x2201_liner.npz, 0.16 median) ----
# CHECK with calipers: front holes 40.2 apart, back tubes 44.2 apart, 109.3 front to back.
LINER_FRONT_HOLES = (88.4, 20.1)  # the front ears' screw holes, +-y; the ears' top at z 4.8
LINER_BACK_TUBES = (-20.9, 22.1)  # the back screw tubes, +-y; their top at z 6.8, down to the chassis
LINER_HOLE_D = 4.6  # all four (the scan's are 4.5 to 5.5 across, ragged)
LINER_TUBE_OD = 7.0
LINER_BAR_HOLE = (35.1, 0.0)  # the screw hole in the bar between the roof's slots, on the roof at z 23.7
LINER_BAR_HOLE_D = 2.2
LINER_SLOTS_X = (16.4, 52.8)  # the roof's two slots (the windows), corners rounded ~2.5
LINER_SLOTS_Y = (3.9, 18.9)  # |y|
LINER_ROOF_TOP = (30.9, 23.9)  # x, z: the liner's highest point, on the centre line

# ---- the chassis' board mounts, in CHASSIS ----
M2_BOSS_D = 4.95  # CALIPERS
POST_D, POST_PIN_D = 5.0, 3.5  # CALIPERS: the locating post, outside and its top pin
MOUNT_TOPS_LEVEL = True  # the M2 boss and the post are level (the user, 2026-11-17)
# The locating post the main board drops over: FIT (2026-11-17, the dummy
# with MH1 1 nearer across and both holes 6.8 forward: 27 outermost along).
POST = (22.02, -6.43)
# The hole test plate's post (CALIPERS 38 along, 12.4 across, outermost; the
# plate fitted). MEASURE: is it the same post as POST? They differ by 11 along.
PLATE_POST = (33.02, -7.43)

# ---- where the chassis sits in the car ----
# Not needed for the main board: it fixes on MH1/MH2 alone, and the trial
# fit (2026-11-17) showed it clears the liner and everything over it. Only
# for a part that must line up with both the chassis and the liner: then
# measure the M2 boss's centre in CAR (x, y; from the liner's front screw
# holes, LINER_FRONT_HOLES) and its top's z.
CHASSIS_IN_CAR = None


def board_to_chassis(X, Y, mh1):
    """A point on the board (KiCad X, Y) -> CHASSIS (x, y). mh1 = MH1's
    KiCad (X, Y), the hole over the M2 boss (kicad_board.Board.ref("MH1").at)."""
    return mh1[1] - Y, mh1[0] - X


def chassis_to_car(x, y, z=0.0):
    """CHASSIS -> CAR. Needs CHASSIS_IN_CAR measured."""
    if CHASSIS_IN_CAR is None:
        raise ValueError("CHASSIS_IN_CAR is not measured yet (x2201_datum.py)")
    cx, cy, cz = CHASSIS_IN_CAR
    return x + cx, y + cy, z + cz
