"""Main board v10 for the X2201 (stage 1 in ../ROADMAP.md): the battery comes in here; the board feeds an
external brushed ESC without a BEC (RZ7886 module, 7.5 A, 15 A peak) and makes the 5 V itself.

  battery --> W1/W2 --> Q1 (reverse guard) --+--> W3/W4 --> ESC (no BEC) --> 260 motor
                                             +--> U4 5 V 3 A buck, the BEC --> S3, EP2, servo, fan, IR
  EP2 --CRSF--> J2 --> ESP32-S3-MINI-1 --PWM--> P2 servo, P1 ESC signal;  LSM6DS3TR-C gyro on I2C
  J6 switch closes VBAT onto U4 EN. Open: no 5 V, so the S3 is off and the ESC gets no pulses.

P1 pin 2 is left open: the ESC has no BEC, and the board's 5 V must not go out to it. The EP2's TX pad only ever
reaches an S3 input. D2 / D3 keep USB and the 5 V apart. Parts on the top side; the wire pads and the two pin
headers are hand-soldered.

Run with KiCad's Python:
  /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 gen_pcb.py
  (PLACE=1: placed only; FREEROUTING=<jar> or ../tools/freerouting-1.9.0.jar: route; REUSE_SES=1: keep the saved .ses; FAB=1: Gerbers, BOM)
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import pcbnew  # noqa: E402
import pcbgen  # noqa: E402
from pcbgen import drc, dump, fab, keepout, outline, place, save, text, zone, mm  # noqa: E402

OUT = os.path.join(HERE, "x2201-carrier-v10.kicad_pcb")
# A long strip, 76 x 20, to fit along the car. The module sits at the left end with its antenna off that end;
# the plugs line the two long edges; the battery, the reverse guard and the buck fill the right end.
# No screw holes: the case holds the board.
W, H = 76.0, 20.0
CORNER = 2.0
HOLES = []

R805, C805, C1206 = "R_0805_2012Metric", "C_0805_2012Metric", "C_1206_3216Metric"
R0402, C0402 = "R_0402_1005Metric", "C_0402_1005Metric"
SOT, SOD = "SOT-23", "D_SOD-323"
ZH4 = "JST_ZH_B4B-ZR-SM4-TF_1x04-1MP_P1.50mm_Vertical"
ZH2 = "JST_ZH_B2B-ZR-SM4-TF_1x02-1MP_P1.50mm_Vertical"
SH6 = "JST_SH_BM06B-SRSS-TB_1x06-1MP_P1.00mm_Vertical"
HDR3 = "PinHeader_1x03_P2.54mm_Vertical"
WIRE = "SolderWire-0.75sqmm_1x01_D1.25mm_OD3.5mm"
pcbgen.LCSC[("DMN3008SFG-7", "Diodes_PowerDI3333-8")] = "C384563"
HDR = "Connector_PinHeader_2.54mm"


def r(ref, val, x, y, rot, a, b):
    return place("Resistor_SMD", R805, ref, val, x, y, rot, {"1": a, "2": b})


def r04(ref, val, x, y, rot, a, b):
    return place("Resistor_SMD", R0402, ref, val, x, y, rot, {"1": a, "2": b})


def c(ref, val, x, y, rot, a, b, fp=C805):
    return place("Capacitor_SMD", fp, ref, val, x, y, rot, {"1": a, "2": b})


def q(ref, val, x, y, rot, g, s, d):
    return place("Package_TO_SOT_SMD", SOT, ref, val, x, y, rot, {"1": g, "2": s, "3": d})


def npth(ref, x, y, d=2.2):
    m = pcbnew.FOOTPRINT(pcbgen.board)
    m.SetReference(ref)
    m.SetValue("M2 hole")
    m.SetPosition(pcbgen.pt(x, y))
    p = pcbnew.PAD(m)
    p.SetAttribute(pcbnew.PAD_ATTRIB_NPTH)
    p.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
    p.SetSize(pcbnew.VECTOR2I(mm(d), mm(d)))
    p.SetDrillSize(pcbnew.VECTOR2I(mm(d), mm(d)))
    p.SetLayerSet(pcbnew.PAD.UnplatedHoleMask())
    m.Add(p)
    m.Reference().SetVisible(False)
    pcbgen.board.Add(m)


for i, (x, y) in enumerate(HOLES):
    npth(f"MH{i + 1}", x, y)

# ---- U1: ESP32-S3-MINI-1 at the left end, turned so the antenna points off the board's left edge ----------
# Turned 90: module pads 1-15 run along the bottom (y = CY + 7), 16-30 up the right side (x = CX + 7),
# 31-45 along the top, and the ground pads 46-60 down the left side by the antenna.
CX, CY = 13.5, 10.0
ANT = CX - 13.21 + 5.6  # the copper keepout, from the left edge to just short of the module's first pads
GPIO = {3: "3V3", 4: "BOOT", 10: "VTX_EN", 11: "THR", 12: "SERVO", 13: "VBAT_ADC", 14: "MSP_RX", 15: "MSP_TX",  # IO6..IO11
        17: "CRSF_RX", 18: "CRSF_TX", 19: "IR", 20: "SDA", 21: "SCL", 22: "IMU_INT",  # IO13..IO18
        23: "USB_DM", 24: "USB_DP", 45: "EN"}
U1_NETS = {str(k): v for k, v in GPIO.items()}
for n in (1, 2, 42, 43, *range(46, 66)):
    U1_NETS[str(n)] = "GND"
U1 = place("Espressif", "ESP32-S3-MINI-1", "U1", "ESP32-S3-MINI-1-N8", CX, CY, 90, U1_NETS)
# the recovery pads, on the back under the module: hold B on G while powering up to force the ROM loader
place("TestPoint", "TestPoint_Pad_1.5x1.5mm", "TP1", "BOOT", 11.0, 7.0, 0, {"1": "BOOT"}, side="B")
place("TestPoint", "TestPoint_Pad_1.5x1.5mm", "TP3", "G", 11.0, 13.0, 0, {"1": "GND"}, side="B")
# EN's pull-up and delay, in the strip above the module, beside EN (pad 45, the top row's left end)
r04("R21", "10k", 9.2, 1.15, 0, "3V3", "EN")
c("C8", "1uF", 11.4, 1.15, 0, "EN", "GND", C0402)

# ---- top edge: the EP2, the servo, the ESC's signal, the switch ---------------------------------
# the EP2, off the board on a plug: its TX pad only ever reaches an S3 input
J2 = place("Connector_JST", ZH4, "J2", "ZH1.5 4P (EP2)", 28.2, 3.9, 0,
           {"1": "CRSF_RX", "2": "CRSF_TX", "3": "VIN", "4": "GND", "MP": "GND"})
# the ESC's servo lead: signal, its V pin (open: this ESC has no BEC), ground
P1 = place(HDR, HDR3, "P1", "2.54 3P (ESC)", 35.8, 2.4, 90, {"1": "THR", "3": "GND"})
P2 = place(HDR, HDR3, "P2", "2.54 3P (servo)", 44.6, 2.4, 90, {"1": "SERVO", "2": "5V", "3": "GND"})
# closing the switch ties EN to the battery; R16 holds it off, so the buck stays down
J6 = place("Connector_JST", ZH2, "J6", "ZH1.5 2P (switch)", 55.6, 3.9, 0, {"1": "VBAT", "2": "EN_SW", "MP": "GND"})

# ---- bottom edge: USB-C beside the module, then the IR, fan and VTX plugs --------------------
JX = 27.3
place("Connector_USB", "USB_C_Receptacle_HRO_TYPE-C-31-M-12", "J9", "USB-C", JX, H - 2.8, 0, {
    "A1": "GND", "B12": "GND", "B1": "GND", "A12": "GND", "B4": "VBUS", "A9": "VBUS", "A4": "VBUS", "B9": "VBUS",
    "A5": "CC1", "B5": "CC2", "A6": "USB_DP", "B6": "USB_DP", "A7": "USB_DM", "B7": "USB_DM", "SH": "GND"})
J5 = place("Connector_JST", ZH2, "J5", "ZH1.5 2P (IR LED)", 37.1, H - 3.99, 180,
           {"1": "LEDA", "2": "LEDK", "MP": "GND"})
J4 = place("Connector_JST", ZH2, "J4", "ZH1.5 2P (fan)", 45.4, H - 3.99, 180, {"1": "5V", "2": "GND", "MP": "GND"})
J3 = place("Connector_JST", SH6, "J3", "SH1.0 6P (VTX)", 54.6, H - 2.9, 0,
           {"1": "VTX", "2": "GND", "3": "VTX_RX", "4": "VTX_TX", "MP": "GND"})

# ---- between J2 and J9: the 3V3 LDO, the two diodes that keep USB and the 5 V apart -----------
place("Package_TO_SOT_SMD", "SOT-23-5", "U3", "AP2112K-3.3", 25.0, 9.45, 0, {"1": "VIN", "2": "GND", "3": "VIN", "5": "3V3"})
c("C9", "22uF", 28.4, 9.45, 90, "VIN", "GND")
place("Diode_SMD", SOD, "D3", "B5819WS", 30.6, 9.45, 90, {"1": "VIN", "2": "5V"})
place("Diode_SMD", SOD, "D2", "B5819WS", 32.65, 9.45, 90, {"1": "VIN", "2": "VBUS"})

# ---- middle: CC resistors, the gyro, 3V3 decoupling, IR driver, the battery divider ----------
r04("R12", "5.1k", 34.4, 8.0, 90, "CC1", "GND")
r04("R13", "5.1k", 34.4, 10.1, 90, "CC2", "GND")
# the gyro (I2C 0x6A: SA0 low, CS high; aux bus unused). Its caps and pull-ups sit where v10 had them.
GX, GY = 38.7, 8.5
place("Package_LGA", "LGA-14_3x2.5mm_P0.5mm_LayoutBorder3x4y", "U2", "LSM6DS3TR-C", GX, GY, 0, {
    "1": "GND", "2": "GND", "3": "GND", "4": "IMU_INT", "5": "3V3", "6": "GND", "7": "GND", "8": "3V3",
    "12": "3V3", "13": "SCL", "14": "SDA"})
c("C12", "100nF", GX - 2.9, GY - 1.0, 90, "3V3", "GND", C0402)
c("C13", "100nF", GX - 2.9, GY + 1.2, 90, "3V3", "GND", C0402)
r04("R9", "4.7k", GX + 3.1, GY - 1.0, 90, "3V3", "SDA")
r04("R10", "4.7k", GX + 4.2, GY - 1.0, 90, "3V3", "SCL")
c("C14", "22uF", 47.8, 6.4, 90, "5V", "GND")  # the servo's surges, by its plug
c("C10", "22uF", 43.0, 10.8, 90, "3V3", "GND")
c("C6", "100nF", 41.3, 10.8, 90, "3V3", "GND", C0402)
r04("R11", "10k", 36.6, 5.0, 0, "THR", "GND")  # holds the ESC's signal low while the S3 restarts
q("Q4", "AO3400", 46.0, 10.4, 0, "IR", "GND", "LEDK")
r04("R8", "100k", 45.6, 7.9, 0, "IR", "GND")
r("R6", "33", 49.0, 10.4, 90, "LEDA", "5V")
r04("R14", "100k", 50.9, 5.4, 90, "VBAT", "VBAT_ADC")
r04("R15", "22k", 50.9, 7.5, 90, "VBAT_ADC", "GND")
c("C11", "100nF", 50.9, 9.6, 90, "VBAT_ADC", "GND", C0402)

# ---- between J6 and J3: the VTX's switch and UART, the module's EN ---------------------------
# the VTX on the S3's word: VTX_EN high turns Q3 on, Q3 pulls Q2's gate down, Q2 passes the battery; off at reset
q("Q3", "AO3400", 53.6, 9.0, 0, "Q3G", "GND", "Q2G")
q("Q2", "AO3401", 57.6, 9.0, 0, "Q2G", "VBAT", "VTX")
r04("R2", "100k", 52.2, 12.5, 90, "Q2G", "VBAT")
r04("R7", "100k", 53.3, 12.5, 90, "Q3G", "GND")
r04("R4", "1k", 54.4, 12.5, 90, "VTX_EN", "Q3G")
r04("R19", "1k", 55.5, 12.5, 90, "MSP_TX", "VTX_RX")
r04("R20", "1k", 56.6, 12.5, 90, "MSP_RX", "VTX_TX")


# ---- the 5 V buck, a column beside the wire pads -------------------------------------------
# LMR51430: 1 GND, 2 SW, 3 VIN, 4 FB, 5 EN, 6 CB; 5.0 V = 0.6 V x (1 + 22k / 3k). Turned 180: VIN, SW, GND
# down the right side, FB, EN, CB down the left. U4, C5 and L1 keep v10's spacing, so its hand routes carry over.
UX, UY = 62.9, 4.25
c("C1", "10uF", 63.4, 1.45, 180, "VBAT", "GND")
place("Package_TO_SOT_SMD", "SOT-23-6", "U4", "LMR51430XDDCR", UX, UY, 180,
      {"1": "GND", "2": "SW", "3": "VBAT", "4": "FB", "5": "EN_SW", "6": "CB"})
# the FB ends of the two meet in the middle, level with U4's FB pin; R3's 5 V end faces down, to its via
r04("R5", "3k", 60.25, 2.6, 90, "FB", "GND")
r04("R3", "22k", 60.25, 4.6, 90, "5V", "FB")
r04("R16", "100k", 59.9, 12.9, 90, "EN_SW", "GND")
c("C5", "100nF", UX - 0.7, UY + 2.35, 0, "CB", "SW", C0402)
place("Inductor_SMD", "L_Changjiang_FXL0420", "L1", "4.7uH", 63.0, 9.5, 0, {"1": "SW", "2": "5V"})
c("C3", "22uF", 62.9, 13.05, 180, "5V", "GND")
c("C4", "22uF", 62.9, 15.15, 180, "5V", "GND")

# ---- right end: the battery in, the reverse guard, the ESC's power out ----------------------
# wires soldered through: the ESC's on the inner column, the battery's on the outer one, between the holes
place("Connector_Wire", WIRE, "W3", "ESC+", 68.3, 4.6, 0, {"1": "VBAT"})
place("Connector_Wire", WIRE, "W4", "ESC-", 68.3, 15.0, 0, {"1": "GND"})
place("Connector_Wire", WIRE, "W1", "BAT+", 73.5, 7.5, 0, {"1": "VBAT"})
place("Connector_Wire", WIRE, "W2", "BAT-", 73.5, 12.5, 0, {"1": "BAT_N"})
# low-side guard, drain to the battery's negative, source to the board's ground. The right way round, the body
# diode carries the first current, GND sits a diode above BAT- and Vgs = VBAT turns Q1 hard on. Reversed, the
# body diode is reverse-biased and the gate sits at the source: off. Protects the ESC as well as this board.
# DMN3008SFG: 1-3 source, 4 gate, 5 (the tab) drain. Turned 90: the tab faces up, the sources face W4 below.
place("Package_SON", "Diodes_PowerDI3333-8", "Q1", "DMN3008SFG-7", 68.3, 10.2, 90,
      {"1": "GND", "2": "GND", "3": "GND", "4": "Q1G", "5": "BAT_N"})
r04("R1", "10k", 67.0, 7.45, 0, "VBAT", "Q1G")

if os.environ.get("DUMP"):
    dump()
    sys.exit()
if os.environ.get("OVER"):
    bb = {}
    for m in pcbgen.board.GetFootprints():
        if m.GetReference().startswith("MH"):
            continue
        c = m.GetCourtyard(pcbnew.F_CrtYd).BBox()
        bb[m.GetReference()] = [pcbnew.ToMM(v) for v in (c.GetLeft(), c.GetTop(), c.GetRight(), c.GetBottom())]
    for a in bb:
        for b in bb:
            A, B = bb[a], bb[b]
            if a < b and A[0] < B[2] and B[0] < A[2] and A[1] < B[3] and B[1] < A[3]:
                print(a, b, [round(v, 1) for v in A], [round(v, 1) for v in B])
    for m in pcbgen.board.GetFootprints():
        if m.GetReference() in ("Q1", "U4", "C1", "C5", "L1", "R1"):
            print(m.GetReference(), {p.GetNumber(): tuple(round(pcbnew.ToMM(v), 2) for v in (p.GetPosition().x, p.GetPosition().y)) for p in m.Pads()})
    sys.exit()


CLASSES = [("PWR", 0.5, 0.2, ["VBAT", "VTX", "BAT_N", "SW", "5V"]),
           ("GROUND", 0.3, 0.15, ["GND"]),
           ("5V", 0.4, 0.15, ["VIN", "VBUS", "3V3"]),
           ("DRV", 0.4, 0.2, ["LEDA", "LEDK"])]


SES = OUT.replace(".kicad_pcb", ".ses")
FR = os.environ.get("FREEROUTING", os.path.join(os.path.dirname(HERE), "tools", "freerouting-1.9.0.jar"))
FR = FR if os.path.exists(FR) and not os.environ.get("REUSE_SES") else ""


def rules():
    """Net classes on the board itself: Freerouting gets its track widths from these."""
    ds = pcbgen.board.GetDesignSettings()
    ns = ds.m_NetSettings
    d = ns.GetDefaultNetclass()
    d.SetTrackWidth(mm(0.25))
    d.SetClearance(mm(0.15))
    d.SetViaDiameter(mm(0.6))
    d.SetViaDrill(mm(0.3))
    for name, w, cl, nets in CLASSES:
        nc = pcbnew.NETCLASS(name)
        nc.SetTrackWidth(mm(w))
        nc.SetClearance(mm(cl))
        nc.SetViaDiameter(mm(0.6))
        nc.SetViaDrill(mm(0.3))
        ns.SetNetclass(name, nc)
        for n in nets:
            ns.SetNetclassPatternAssignment(n, name)
    pcbgen.board.SynchronizeNetsAndNetClasses(True)


# Hand-drawn where the pins are too tight for the router.
# USB: the plug's two rows cross over at the pads. D+ bridges A6 / B6 above the pads, D- bridges B7 / A7 below them
# and drops to a via; the router takes both on to the module.
_P = H - 2.8 - 4.05  # the plug's row of pads
_T, _B, _V = _P - 1.06, _P + 1.04, _P + 1.64
# U4 (SOT-23-6, turned 180): GND drops to a via under the body; SW leaves sideways and comes round below to C5
# and L1; CB straight down to C5. U2 (LGA-14): the three 3V3 pins (5, 8, 12) joined round the outside, SDA out
# the top and over, SCL between them and down to a via. Q1's gate is boxed in by the drain and the sources: it
# leaves on a via and runs under to R1.
GX0, GY0 = GX - 8.5, GY - 30.0  # the gyro routes were drawn with U2 at (8.5, 30)


def _g(pts):
    return [(x + GX0, y + GY0) for x, y in pts]


HAND_T = [("USB_DP", pcbnew.F_Cu, [(JX - 0.25, _P), (JX - 0.25, _T), (JX + 0.75, _T), (JX + 0.75, _P)], 0.25),
          ("USB_DM", pcbnew.F_Cu, [(JX - 0.75, _P), (JX - 0.75, _B), (JX + 0.25, _B), (JX + 0.25, _P)], 0.25),
          ("USB_DM", pcbnew.F_Cu, [(JX - 0.25, _B), (JX - 0.25, _V)], 0.25),
          ("GND", pcbnew.F_Cu, [(UX + 0.48, UY + 0.95), (UX, UY + 1.05)], 0.25),
          ("SW", pcbnew.F_Cu, [(UX + 1.8, UY), (UX + 2.3, UY), (UX + 2.3, UY + 3.1), (61.15, UY + 3.1), (61.15, 8.5)], 0.4),
          ("SW", pcbnew.F_Cu, [(UX - 0.22, UY + 2.35), (UX - 0.22, UY + 3.1)], 0.3),
          # VBAT for the switch, the VTX and the divider: on the back along the top edge from the battery pour
          ("VBAT", pcbnew.B_Cu, [(65.9, 1.0), (55.4, 1.0), (54.85, 1.55), (54.85, 2.7)], 0.5),
          ("VBAT", pcbnew.F_Cu, [(54.85, 2.7), (54.85, 4.6)], 0.5),
          ("FB", pcbnew.F_Cu, [(60.25, 3.11), (60.25, 4.09)], 0.2),
          # R3's 5 V: a via below it, under L1 on the back, up beside C3's 5 V pad
          ("5V", pcbnew.F_Cu, [(60.25, 5.11), (60.25, 6.4)], 0.3),
          ("5V", pcbnew.B_Cu, [(60.25, 6.4), (60.25, 8.0), (64.25, 12.0), (64.9, 12.0)], 0.3),
          ("5V", pcbnew.F_Cu, [(64.9, 12.0), (64.35, 12.55)], 0.3),
          # EN's RC above the module: EN along under the pull-up, the pull-up's 3V3 out to a via by the antenna
          ("EN", pcbnew.F_Cu, [(7.55, 3.0), (7.55, 2.2), (9.4, 2.2), (9.71, 1.89), (9.71, 1.15)], 0.25),
          ("3V3", pcbnew.F_Cu, [(8.69, 1.15), (6.6, 1.15)], 0.25),
          ("FB", pcbnew.F_Cu, [(60.25, 3.3), (UX - 1.14, 3.3)], 0.2),
          ("CB", pcbnew.F_Cu, [(UX - 1.14, UY + 1.25), (UX - 1.18, UY + 2.35)], 0.25),
          ("Q1G", pcbnew.F_Cu, [(67.51, 7.45), (67.9, 7.45)], 0.25),
          ("Q1G", pcbnew.B_Cu, [(67.9, 7.45), (66.4, 8.95), (66.4, 12.55), (69.4, 12.55)], 0.25),
          ("Q1G", pcbnew.F_Cu, [(69.4, 12.55), (69.28, 11.7)], 0.25),
          ("3V3", pcbnew.F_Cu, _g([(8.0, 31.22), (8.0, 31.6), (10.3, 31.6), (10.3, 28.4), (9.0, 28.4), (9.0, 28.78)]), 0.2),
          ("3V3", pcbnew.F_Cu, _g([(9.97, 30.75), (10.3, 30.75)]), 0.2),
          ("3V3", pcbnew.F_Cu, _g([(10.3, 29.51), (11.6, 29.51)]), 0.25),
          ("SDA", pcbnew.F_Cu, _g([(8.0, 29.09), (8.0, 28.7), (7.6, 28.3), (7.6, 27.2), (11.6, 27.2), (11.6, 28.49)]), 0.25),
          ("SCL", pcbnew.F_Cu, _g([(8.5, 29.09), (8.5, 27.9)]), 0.2),
          ("SCL", pcbnew.B_Cu, _g([(8.5, 27.9), (8.5, 29.1), (13.5, 29.1)]), 0.25),
          ("SCL", pcbnew.F_Cu, _g([(13.5, 29.1), (12.7, 28.49)]), 0.25)]
HAND_V = [("USB_DM", JX - 0.25, _V), ("VBAT", 54.85, 2.7), ("5V", 60.25, 6.4), ("5V", 64.9, 12.0), ("3V3", 6.6, 1.15), ("GND", UX, UY + 1.05), ("Q1G", 67.9, 7.45), ("Q1G", 69.4, 12.55),
          *[(n, x + GX0, y + GY0) for n, x, y in (("3V3", 10.3, 28.4), ("SCL", 8.5, 27.9), ("SCL", 13.5, 29.1))]]


def draw_hand():
    have = {(t.GetNetname(), t.GetStart().x, t.GetStart().y, t.GetEnd().x, t.GetEnd().y) for t in pcbgen.board.GetTracks()}
    for n, layer, pts, w in HAND_T:
        for a, b in zip(pts, pts[1:]):
            A, B = pcbgen.pt(*a), pcbgen.pt(*b)
            if (n, A.x, A.y, B.x, B.y) not in have and (n, B.x, B.y, A.x, A.y) not in have:
                pcbgen.track([a, b], n, w, layer)
    # the router hands the hand vias back a hair off where they were drawn: compare to 0.01 mm
    vias = {(round(pcbnew.ToMM(t.GetPosition().x), 2), round(pcbnew.ToMM(t.GetPosition().y), 2))
            for t in pcbgen.board.GetTracks() if isinstance(t, pcbnew.PCB_VIA)}
    for n, x, y in HAND_V:
        if (round(x, 2), round(y, 2)) not in vias:
            pcbgen.via(x, y, n)


def keepout_top(x0, y0, x1, y1):
    """No tracks or vias on the top side; the pours may still fill it."""
    z = pcbnew.ZONE(pcbgen.board)
    z.SetIsRuleArea(True)
    z.SetDoNotAllowTracks(True)
    z.SetDoNotAllowVias(True)
    z.SetDoNotAllowZoneFills(False)
    z.SetDoNotAllowPads(False)
    z.SetDoNotAllowFootprints(False)
    z.SetLayer(pcbnew.F_Cu)
    o = z.Outline()
    o.NewOutline()
    for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        o.Append(mm(x), mm(y))
    pcbgen.board.Add(z)


def edge_keepout(w=0.45):
    for x0, y0, x1, y1 in ((0, 0, W, w), (0, H - w, W, H), (0, 0, w, H), (W - w, 0, W, H)):
        keepout(x0, y0, x1, y1)


def freeroute(passes):
    dsn = os.path.join(HERE, "route.dsn")
    pcbnew.ExportSpecctraDSN(pcbgen.board, dsn)
    subprocess.run(["java", "-jar", FR, "-de", dsn, "-do", SES, "-mp", str(passes), "-mt", "1"], check=True,
                   cwd=os.path.dirname(FR))
    os.remove(dsn)
    import_ses()


def import_ses():
    """KiCad stops reading at the screw holes' placement block and drops every later net: strip it."""
    s = open(SES).read()
    a, b = s.find("  (placement"), s.find("  (routes")
    if a >= 0 and b > a:
        s = s[:a] + s[b:]
    tmp = SES + ".tmp"
    open(tmp, "w").write(s)
    ok = pcbnew.ImportSpecctraSES(pcbgen.board, tmp)
    os.remove(tmp)
    if not ok:
        raise RuntimeError("SES import failed")


def routed_grid(router, keep, under):
    """The router's occupancy map, filled in with what Freerouting drew: for the stitching vias."""
    P = router.pads()
    g = router.base(W, H, HOLES, keep, under, P)
    router.DRILLS[:] = [(p["x"], p["y"]) for p in P if p["th"]]
    for t in pcbgen.board.GetTracks():
        n = t.GetNetname()
        if isinstance(t, pcbnew.PCB_VIA):
            c = t.GetPosition()
            x, y = pcbnew.ToMM(c.x), pcbnew.ToMM(c.y)
            g.add(x - 0.3, y - 0.3, x + 0.3, y + 0.3, None, n)
            router.DRILLS.append((x, y))
            continue
        a, b = t.GetStart(), t.GetEnd()
        ax, ay, bx, by = pcbnew.ToMM(a.x), pcbnew.ToMM(a.y), pcbnew.ToMM(b.x), pcbnew.ToMM(b.y)
        w = pcbnew.ToMM(t.GetWidth()) / 2
        steps = max(1, int(max(abs(ax - bx), abs(ay - by)) / 0.1))
        for i in range(steps + 1):
            x, y = ax + (bx - ax) * i / steps, ay + (by - ay) * i / steps
            g.add(x - w, y - w, x + w, y + w, 0 if t.GetLayer() == pcbnew.F_Cu else 1, n)
    return g


def tent():
    for t in pcbgen.board.GetTracks():
        if isinstance(t, pcbnew.PCB_VIA):
            t.SetFrontTentingMode(pcbnew.TENTING_MODE_TENTED)
            t.SetBackTentingMode(pcbnew.TENTING_MODE_TENTED)


# JLC's part models sit turned from KiCad's footprints; checked against JLC's SMT preview.
CPL_TURN = {"Q2": 180, "Q3": 180, "Q4": 180, "U3": 270, "D2": 180, "D3": 180, "J3": 180, "J2": 180, "J6": 180}
CPL_MOVE_Y = {"J9": 1.5}  # mm toward the top of the board: JLC's model has its origin elsewhere than KiCad's footprint


def cpl_rotation():
    import csv
    path = os.path.join(HERE, "cpl.csv")
    rows = list(csv.reader(open(path)))
    for row in rows[1:]:
        row[4] = str((int(float(row[4])) + CPL_TURN.get(row[0], 0)) % 360)
        if row[0] in CPL_MOVE_Y:
            row[2] = f"{float(row[2].replace('mm', '')) + CPL_MOVE_Y[row[0]]:.3f}mm"
    with open(path, "w", newline="") as f:
        csv.writer(f).writerows(rows)


def prune():
    """Dangling stubs the router leaves where a branch starts, and stitching vias no pour reached."""
    import json
    rpt = OUT + ".json"
    for _ in range(6):
        subprocess.run([pcbgen.CLI, "pcb", "drc", "--refill-zones", "--format", "json", "--severity-all", "-o", rpt, OUT],
                       capture_output=True)
        dead = {i["uuid"] for v in json.load(open(rpt))["violations"] if v["type"] in ("track_dangling", "via_dangling") for i in v["items"]}
        if not dead:
            break
        for t in list(pcbgen.board.GetTracks()):
            if t.m_Uuid.AsString() in dead:
                pcbgen.board.Remove(t)
        pcbnew.ZONE_FILLER(pcbgen.board).Fill(pcbgen.board.Zones())
        save(OUT)
    os.remove(rpt)


def labels():
    """What plugs in where, on the back (no parts there to collide with); the wire pads on both sides."""
    B = pcbnew.B_SilkS
    for s_, x, y in [("B", 13.0, 7.0), ("G", 13.0, 13.0), ("EP2", 28.2, 6.2), ("ESC", 38.3, 4.4), ("SERVO", 47.1, 4.4),
                     ("SW", 55.6, 6.2), ("USB", JX, 11.2), ("IR", 37.1, 13.4), ("FAN", 45.4, 13.4), ("VTX", 54.6, 13.8),
                     ("IMU", GX, 11.2)]:
        text(s_, x, y, 0.8, B)
    for layer in (pcbnew.F_SilkS, B):
        for s_, x, y in [("ESC+", 68.3, 1.55), ("ESC-", 68.3, 17.5), ("BAT+", 73.5, 5.2), ("BAT-", 73.5, 14.8)]:
            text(s_, x, y, 0.8, layer)
    text("X2201 main board v10", 48.0, 11.6, 0.8, B)


if __name__ == "__main__":
    outline(0, 0, W, H, CORNER)
    # no copper by the module's antenna
    keepout(0, 0, ANT, H)
    if os.environ.get("PLACE"):
        pcbgen.project(OUT, CLASSES)
        save(OUT)
        for line in drc(OUT):
            print(line)
        sys.exit()
    labels()
    rules()
    pcbgen.project(OUT, CLASSES, default=(0.25, 0.15))
    import router
    # Pours for the battery's current, filled after routing: battery to the ESC pads and the buck's input,
    # and the reverse guard's drain back to BAT-. GND (Q1's sources to W4) is the ground pour.
    POWER = [
        ("VBAT", (63.6, 0.5, 65.9, 3.62), True),    # C1 and U4 VIN, stops short of SW; SMD pads only: top
        ("VBAT", (65.75, 0.5, 75.55, 6.9), False),  # over to W3
        ("VBAT", (65.75, 6.5, 66.95, 7.95), False),  # down to R1
        ("VBAT", (71.4, 6.8, 75.55, 9.4), False),   # round W1
        ("BAT_N", (69.0, 8.6, 71.1, 11.0), True),  # Q1's tab, top only
        ("BAT_N", (70.4, 9.7, 75.55, 15.6), False),  # over to W2
    ]
    KEEP = [(0, 0, ANT, H), *[b for _, b, _ in POWER], (65.6, 12.15, 71.0, 17.9)]  # + Q1's sources down to W4
    keepout_top(66.7, 12.1, 69.05, 13.6)  # the router leaves Q1's sources a clear run to W4
    UNDER = []
    edge_keepout()
    draw_hand()
    if FR:
        freeroute(100)
        freeroute(100)  # again, from what the first pass left
    elif os.path.exists(SES):
        import_ses()
    else:
        raise SystemExit("no routing: set FREEROUTING=<jar>")
    draw_hand()
    grid = routed_grid(router, KEEP, UNDER)
    router.stitch(grid, W, H, UNDER, router.pads())
    tent()
    for l in (pcbnew.F_Cu, pcbnew.B_Cu):
        for i, (n, box, top_only) in enumerate(POWER):
            if l == pcbnew.B_Cu and top_only:
                continue
            zone(n, l, *box).SetAssignedPriority(i + 1)
        zone("GND", l, ANT, 0.3, W - 0.3, H - 0.3, chamfer=1.0)
    pcbnew.ZONE_FILLER(pcbgen.board).Fill(pcbgen.board.Zones())
    save(OUT)
    prune()
    for line in drc(OUT):
        print(line)
    if os.environ.get("FAB"):
        fab(OUT, fitted="QCRDJUL")
        cpl_rotation()
