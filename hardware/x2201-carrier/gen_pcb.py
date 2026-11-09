"""Carrier board layout for the Geeks X2201 (the schematic is gen_sch.py's,
with the same net names): the base of the driver's-view FPV mount and the
car's low-current wiring in one. The printed frame that screws onto it is
firmware/wheel-esp32/enclosure/x2201_carrier_frame.py.

It takes the printed mount's plate's place: 44 x 52, on 1 mm 3M VHB tape on
the chassis' two flat strips either side of the middle channel. Parts are on
the top only, beside the VTX; the underside is flat (a ground pour). The
printed frame (posts, fan pads, camera cheeks) screws onto four M2 SMT nuts.

Circuit (the ZERO-Z ESC's BEC gives 5V; its switch is the car's only switch):
  - EP2 receiver, delayed: Q1 (P-MOS) gives the EP2 its 5V 0.5..1 s after the
    BEC comes up (C1 charging through R1). The EP2's GPIO1 (TX pad) is held
    low by the ESC while the ESC starts, and the EP2 hangs if it boots then.
    D1 empties C1 at power-off, so a quick off-on still waits.
  - VTX switched by the BEC: Q3 (N-MOS) pulls Q2's (P-MOS) gate down while
    5V is there, so the VTX gets the battery only while the ESC is on.
    R2/R3 keep Q2's gate at -VBAT x 100/147 (2S: -5.7 V, 3S: -8.6 V, its
    limit is 12 V).
  - J1: the ESC's receiver cable, ZH1.5 4P. EP2 TX pad = CH1 = signal 1
    (steering, the ESC's gyro passes it to the servo), RX pad = CH2 =
    signal 2 (throttle).
  - Pads: battery in (thin wires from the ESC's battery input), VTX out
    (the Ascent Lite+'s red/black power wires; white/grey UART unused),
    fan 5V (25 mm, 5 V), EP2 (5V, GND, TX, RX on short wires).

Coordinates: x forward, as in the enclosure scripts (enclosure/x2201_cage.py: the cage's
back end = 0); the board's y points to the car's right (KiCad's y is down,
seen from above with the front to the right).

Run with KiCad's Python:
  /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 gen_pcb.py
  -> x2201-carrier.kicad_pcb; with FAB=1 also gerber/, bom.csv and cpl.csv for JLCPCB
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import pcbnew  # noqa: E402
from pcbgen import W_PWR, drc, dump, fab, nut, outline, pad, place, save, text, track, via, zone  # noqa: E402

OUT = os.path.join(HERE, "x2201-carrier.kicad_pcb")

# ---- outline: the printed mount's plate (x2201_fpv_mount.py) -----------------------
X0, X1 = 3.6, 57.8  # back, front: the mount's plate (13.6 to 57.8) and 10 mm more for the plugs
BACK = 8.6  # the plug row along the back edge, under the rear window
HW = 26.0  # half width (RAIL_Y[1])
CORNER = 2.5

# ---- the printed frame's footprint on the board -----------------------------------------
NUTS = [(17.6, -18.6), (17.6, 18.6), (35.7, -18.6), (35.7, 18.6)]  # M2 SMT nuts, under the frame's ears


# ---- parts ---------------------------------------------------------------------------------
# Top (the car's left, y < 0): the ESC cable, the EP2 pads and its delay.
J1 = place("Connector_JST", "JST_ZH_B4B-ZR-SM4-TF_1x04-1MP_P1.50mm_Vertical", "J1", "ZH1.5 4P (ESC)", 51.5, -22.5, 180,
           {"1": "S2", "2": "S1", "3": "GND", "4": "5V", "MP": "GND"})
Q1 = place("Package_TO_SOT_SMD", "SOT-23", "Q1", "AO3401", 43.0, -17.5, 0, {"1": "RXG", "2": "5V", "3": "RX5V"})
C1 = place("Capacitor_SMD", "C_0805_2012Metric", "C1", "10uF", 41.0, -21.5, 90, {"1": "5V", "2": "RXG"})
R1 = place("Resistor_SMD", "R_0603_1608Metric", "R1", "100k", 41.0, -14.5, 90, {"1": "RXG", "2": "GND"})
D1 = place("Diode_SMD", "D_SOD-323", "D1", "1N4148WS", 43.6, -24.4, 0, {"1": "RXG", "2": "GND"})
C2 = place("Capacitor_SMD", "C_0805_2012Metric", "C2", "22uF", 47.5, -17.0, 270, {"1": "5V", "2": "GND"})

# Bottom (the car's right, y > 0): battery in, the VTX switch, VTX and fan pads.
Q2 = place("Package_TO_SOT_SMD", "SOT-23", "Q2", "AO3401", 50.5, 15.0, 0, {"1": "Q2G", "2": "VBAT", "3": "VTX"})
Q3 = place("Package_TO_SOT_SMD", "SOT-23", "Q3", "AO3400", 45.0, 15.0, 0, {"1": "Q3G", "2": "GND", "3": "Q3D"})
R2 = place("Resistor_SMD", "R_0603_1608Metric", "R2", "100k", 50.5, 11.5, 0, {"1": "Q2G", "2": "VBAT"})
R3 = place("Resistor_SMD", "R_0603_1608Metric", "R3", "47k", 47.5, 12.0, 90, {"1": "Q2G", "2": "Q3D"})
R4 = place("Resistor_SMD", "R_0603_1608Metric", "R4", "1k", 42.0, 12.0, 0, {"1": "5V", "2": "Q3G"})
R5 = place("Resistor_SMD", "R_0603_1608Metric", "R5", "100k", 42.0, 17.0, 90, {"1": "Q3G", "2": "GND"})
C3 = place("Capacitor_SMD", "C_1206_3216Metric", "C3", "22uF 25V", 50.5, 22.0, 90, {"1": "VBAT", "2": "GND"})

NUT = [nut("H" + str(i + 1), x, y) for i, (x, y) in enumerate(NUTS)]

# The plug row along the back edge: everything that leaves the board plugs in,
# nothing is soldered to it. The VTX is set on the board and the frame lowered
# over it, so the row doesn't block its way in.
ZH2 = "JST_ZH_B2B-ZR-SM4-TF_1x02-1MP_P1.50mm_Vertical"
J5 = place("Connector_JST", ZH2, "J5", "ZH1.5 2P (IR LED)", BACK, -21.0, 270, {"1": "LEDA", "2": "LEDK", "MP": "GND"})
J2 = place("Connector_JST", "JST_ZH_B4B-ZR-SM4-TF_1x04-1MP_P1.50mm_Vertical", "J2", "ZH1.5 4P (EP2)", BACK, -8.5, 270,
           {"1": "S2", "2": "S1", "3": "GND", "4": "RX5V", "MP": "GND"})
J3 = place("Connector_JST", "JST_SH_BM04B-SRSS-TB_1x04-1MP_P1.00mm_Vertical", "J3", "SH1.0 4P (VTX)", BACK, 2.5, 270,
           {"1": "VTX", "2": "GND", "MP": "GND"})
J4 = place("Connector_JST", ZH2, "J4", "ZH1.5 2P (fan)", BACK, 12.0, 270, {"1": "5V", "2": "GND", "MP": "GND"})
J6 = place("Connector_JST", ZH2, "J6", "ZH1.5 2P (battery)", BACK, 21.0, 270, {"1": "VBAT", "2": "GND", "MP": "GND"})


# ---- tracks -----------------------------------------------------------------------------
B = pcbnew.B_Cu
# ESC signals and the EP2's delayed 5V to the back, on the bottom along the
# left edge (the 5V trunk is in the way on top), up again by J2.
track([pad(J1, 1), (53.75, -17.8)], "S2")
track([pad(J1, 2), (52.25, -17.8)], "S1")
for v, n in (((53.75, -17.8), "S2"), ((52.25, -17.8), "S1"), ((45.6, -22.4), "RX5V"), ((12.4, -15.5), "S2"),
             ((13.4, -15.5), "S1"), ((14.4, -15.5), "RX5V")):
    via(*v, n)
track([(53.75, -17.8), (53.75, -24.0), (12.4, -24.0), (12.4, -15.5)], "S2", layer=B)
track([(52.25, -17.8), (52.25, -23.2), (13.4, -23.2), (13.4, -15.5)], "S1", layer=B)
track([(45.6, -22.4), (14.4, -22.4), (14.4, -15.5)], "RX5V", W_PWR, B)
track([(12.4, -15.5), (12.4, -10.75), pad(J2, 1)], "S2")
track([(13.4, -15.5), (13.4, -9.25), pad(J2, 2)], "S1")
track([(14.4, -15.5), (14.4, -6.25), pad(J2, 4)], "RX5V", W_PWR)
# 5V: J1 -> C2 on top, then a trunk on the bottom to Q1, C1, R4 and the fan.
track([pad(J1, 4), (49.25, -19.0), (47.5, -19.0), pad(C2, 1)], "5V", W_PWR)
for v in ((49.25, -19.0), (42.5, -20.55), (42.06, -15.45), (40.3, 12.0)):
    via(*v, "5V")
track([(49.25, -19.0), (42.5, -19.0), (42.5, -20.55)], "5V", W_PWR, B)
track([(42.5, -19.0), (42.5, -15.45), (42.06, -15.45)], "5V", W_PWR, B)
track([(42.5, -15.45), (40.3, -13.25), (40.3, 15.7)], "5V", W_PWR, B)
track([pad(C1, 1), (42.5, -20.55)], "5V", W_PWR)
track([pad(Q1, 2), (42.06, -15.45)], "5V", W_PWR)
track([(40.3, 12.0), pad(R4, 1)], "5V")
# Q1's gate: C1, R1, D1, round the left.
track([pad(Q1, 1), (39.6, -18.45), (39.6, -22.45), pad(C1, 2)], "RXG")
track([pad(C1, 2), (42.55, -22.45), pad(D1, 1)], "RXG")
track([(39.6, -18.45), (39.6, -13.68), pad(R1, 1)], "RXG")
track([pad(Q1, 3), (45.5, -17.5), (45.6, -22.4)], "RX5V", W_PWR)
# Battery: J6 at the back, under the VTX on the bottom, to R2, Q2's source and C3.
track([pad(J6, 1), (13.6, 20.25), (13.6, 10.0)], "VBAT", W_PWR)
track([(13.6, 10.0), (33.0, 10.0)], "VBAT", W_PWR, B)
track([(33.0, 10.0), (51.8, 10.0), (52.2, 10.4), (52.2, 12.9)], "VBAT", W_PWR)
track([pad(R2, 2), (52.2, 11.5)], "VBAT", W_PWR)
for v in ((13.6, 10.0), (33.0, 10.0), (52.2, 12.9), (48.3, 17.0), (48.3, 23.48)):
    via(*v, "VBAT")
track([(52.2, 12.9), (48.3, 17.0), (48.3, 23.48)], "VBAT", W_PWR, B)
track([(48.3, 17.0), pad(Q2, 2)], "VBAT", W_PWR)
track([(48.3, 23.48), pad(C3, 1)], "VBAT", W_PWR)
# The VTX's battery feed to J3, the same way.
track([pad(Q2, 3), (53.0, 15.0), (53.0, 8.8), (32.0, 8.8)], "VTX", W_PWR)
track([(32.0, 8.8), (12.5, 8.8), (12.5, 1.0)], "VTX", W_PWR, B)
track([(12.5, 1.0), pad(J3, 1)], "VTX", W_PWR)
for v in ((32.0, 8.8), (12.5, 1.0)):
    via(*v, "VTX")
# The fan's 5V: the bottom branch on to J4.
track([(21.3, 15.7), (12.4, 15.7)], "5V", W_PWR, B)
via(12.4, 15.7, "5V")
track([(12.4, 15.7), (12.4, 11.25), pad(J4, 1)], "5V", W_PWR)
track([pad(Q2, 1), (49.6, 12.82), pad(R2, 1)], "Q2G")
track([(49.6, 12.82), pad(R3, 1)], "Q2G")
track([pad(R3, 2), (46.5, 11.18), (46.5, 14.75), pad(Q3, 3)], "Q3D")
track([pad(R4, 2), (43.5, 12.7), (43.5, 14.05), pad(Q3, 1)], "Q3G")
track([pad(Q3, 1), (42.9, 14.05), (42.9, 17.82), pad(R5, 1)], "Q3G")
# Ground: both layers poured, stitched.
for v in ((50.75, -19.6), (48.5, -14.0), (44.0, -21.2), (40.4, -16.2), (44.06, 17.2), (41.2, 15.0),
          (55.0, 17.75), (55.0, 25.0), (52.3, 20.5), (43.5, 24.5), (36.5, 0.0), (16.0, 0.0), (5.0, -16.0), (5.0, 7.0), (5.0, 16.5), (33.5, 24.6), (23.5, 0.0), (29.5, 0.0),
          (29.5, -12.0), (23.5, 12.0)):
    via(*v, "GND")
track([pad(R1, 2), (40.4, -16.2)], "GND")
track([pad(J1, 3), (50.75, -19.6)], "GND")

# ---- lap-timing transponder (firmware/transponder) -------------------------------------------
# The chip and the car-number jumpers on the right, between the frame's ears;
# the LED's driver and pads on the left. PWM crosses under the VTX on top, 5V
# comes from the trunk on the bottom.
U2 = place("Package_SO", "SOIC-8_3.9x4.9mm_P1.27mm", "U2", "CH32V003J4M6", 26.5, 20.0, 0,
           {"2": "GND", "3": "ID2", "4": "5V", "5": "ID0", "6": "ID1", "7": "PWM", "8": "SWIO"})
C4 = place("Capacitor_SMD", "C_0603_1608Metric", "C4", "100nF", 21.6, 20.6, 270, {"1": "GND", "2": "5V"})
JP = {n: place("Jumper", "SolderJumper-2_P1.3mm_Open_Pad1.0x1.5mm", "JP" + str(i + 1), n, x, 24.3, 0, {"1": n, "2": "GND"})
      for i, (n, x) in enumerate((("ID0", 26.5), ("ID1", 30.2), ("ID2", 23.0)))}
# SWIO for the WCH-LinkE; its GND goes on a nut (H4) while the frame is off.
SWIO = place("TestPoint", "TestPoint_Pad_1.5x1.5mm", "TP11", "SWIO", 31.6, 17.6, 0, {"1": "SWIO"})
Q4 = place("Package_TO_SOT_SMD", "SOT-23", "Q4", "AO3400", 27.5, -20.5, 0, {"1": "GATE", "2": "GND", "3": "LEDK"})
R6 = place("Resistor_SMD", "R_1206_3216Metric", "R6", "33", 31.0, -19.5, 270, {"1": "LEDA", "2": "5V"})
R7 = place("Resistor_SMD", "R_0603_1608Metric", "R7", "100", 24.5, -18.0, 90, {"1": "PWM", "2": "GATE"})
R8 = place("Resistor_SMD", "R_0603_1608Metric", "R8", "100k", 22.8, -21.45, 0, {"1": "GND", "2": "GATE"})

track([(40.3, 15.7), (21.3, 15.7), (21.3, 22.75), (24.03, 22.75)], "5V", W_PWR, B)
for v in ((21.3, 22.0), (24.03, 22.75)):
    via(*v, "5V")
track([pad(C4, 2), (21.3, 22.0)], "5V")
track([(24.03, 22.75), pad(U2, 4)], "5V")
track([pad(C4, 1), (22.0, 19.37), pad(U2, 2)], "GND")
track([pad(U2, 3), (22.55, 20.63), (22.55, 23.4), pad(JP["ID2"], 1)], "ID2")
track([pad(U2, 5), (28.97, 23.0), (25.85, 23.0), pad(JP["ID0"], 1)], "ID0")
track([pad(U2, 6), (30.4, 20.63), (30.4, 22.6), pad(JP["ID1"], 1)], "ID1")
via(28.35, 24.6, "GND")  # JP1's ground pad is fenced in by the ID tracks
track([pad(JP["ID0"], 2), (28.35, 24.6)], "GND")
track([pad(U2, 8), (31.6, 18.1)], "SWIO")
# PWM: under the chip to the bottom, up again past the 5V branch, across on top.
track([pad(U2, 7), (26.5, 19.37)], "PWM")
via(26.5, 19.37, "PWM")
via(26.5, 16.6, "PWM")
track([(26.5, 19.37), (26.5, 16.6)], "PWM", layer=B)
track([(26.5, 16.6), (26.5, -16.0), (24.5, -16.6), pad(R7, 1)], "PWM")
track([pad(R7, 2), (24.5, -21.45), pad(Q4, 1)], "GATE")
track([pad(R8, 2), (24.5, -21.45)], "GATE")
track([(40.3, -13.25), (31.0, -13.25), (31.0, -16.9)], "5V", W_PWR, B)
via(31.0, -16.9, "5V")
track([(31.0, -16.9), pad(R6, 2)], "5V", W_PWR)
# The LED's pair to J5 along the left edge.
track([pad(R6, 1), (31.0, -24.4), (11.8, -24.4), (11.8, -21.75), pad(J5, 1)], "LEDA", W_PWR)
track([pad(Q4, 3), (28.44, -22.8), (13.0, -22.8), (13.0, -20.25), pad(J5, 2)], "LEDK", W_PWR)
# Labels: the front has no room by the chip, so the jumpers' are on the back.
BS = pcbnew.B_SilkS
for name, m in JP.items():
    x, y = pad(m, 1)
    text({"ID0": "+1", "ID1": "+2", "ID2": "+4"}[name], x + 0.65, y, 0.8, BS)
text("CAR = 1 +", 26.5, 22.0, 0.8, BS)
text("SW", 31.6, 15.9, 0.8, BS)
for m in JP.values():
    for p_ in m.Pads():
        p_.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)  # the footprint asks for spokes; these pads are small

# ---- silkscreen ---------------------------------------------------------------------------
for n, lab in ((1, "S2"), (2, "S1"), (3, "G"), (4, "5V")):
    x, _ = pad(J1, n)
    text(lab, x, -18.1, 0.8, rot=90)
text("Br G B Y", 51.5, -16.2, 0.8)  # the cable's colours: brown 5V, green GND, blue S1, yellow S2
# The plug row: what plugs in where, along the back edge.
for m, lab in ((J5, "IR"), (J2, "EP2"), (J3, "VTX"), (J4, "FAN"), (J6, "BAT")):
    x, y = pad(m, 1)
    text(lab, X0 + 1.0, (y + pad(m, 2)[1]) / 2, 0.8, rot=90)
text("X2201 carrier v3", 26.65, -1.5, 1.2)
text("VTX here", 26.65, 1.0, 1.0)

outline(X0, -HW, X1, HW, CORNER)
zone("GND", pcbnew.F_Cu, X0 + 0.4, -HW + 0.4, X1 - 0.4, HW - 0.4)
zone("GND", B, X0 + 0.4, -HW + 0.4, X1 - 0.4, HW - 0.4)



if __name__ == "__main__":
    if os.environ.get("DUMP"):
        dump()
    else:
        save(OUT)
        drc(OUT)
        if os.environ.get("FAB"):
            fab(OUT)
