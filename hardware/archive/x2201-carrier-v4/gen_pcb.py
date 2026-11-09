"""Carrier board v4 for the Geeks X2201 (the schematic is gen_sch.py's, with
the same net names): the base of the driver's-view FPV mount, the car's
wiring, and now its brain, an ESP32-S3.

Same nuts and plug row as v3 (x2201-carrier), so the printed frame
(firmware/wheel-esp32/enclosure/x2201_carrier_frame.py) and every cable
carry over; the board is 4 mm longer at the front, for the module's
antenna. What changed:
  - U1 ESP32-S3-MINI-1 at the front right, beside the camera, its antenna
    at the front edge over a copper keep-out. It takes over from the
    CH32V003 and sits between the receiver and the ESC:
      EP2 --CRSF (UART)--> U1 --PWM--> ESC (S1 steering, S2 throttle)
    so U1 owns the failsafe (throttle to neutral when CRSF stops), sends
    the battery voltage back as CRSF telemetry, draws an OSD on the VTX
    (MSP DisplayPort on the VTX cable's UART pins), and flashes the
    lap-timing IR code (RMT, 38 kHz).
  - The EP2's 5V delay (v3's Q1, C1, R1, D1) is gone: the ESC no longer
    touches the EP2's pins, so nothing holds its TX pad low at boot.
  - J9 USB-C on the front edge, under the camera: flashing and the serial
    console (the S3's own USB), and power for U1 alone (D2 / D3 keep USB
    off the 5V rail).
  - Battery voltage on U1's ADC (R14 / R15 by the battery plug; IO17 is on
    ADC2, read with the WiFi off, i.e. whenever the car drives), a status
    LED.
  - WiFi only to set the car up (car number, trims), with the car still:
    it shares 2.4 GHz with ELRS.

The frame's camera cheeks stand on the board at |y| 7.3 .. 9.3 from x 40.3
to 57.8, with a relief underneath (x2201_carrier_frame.py) for the low
parts there (U1's decoupling).

Coordinates: x forward, as in the enclosure scripts (the cage's back end =
0); KiCad's y (down), so y < 0 is the car's left.

Run with KiCad's Python:
  /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 gen_pcb.py
  -> x2201-carrier-v4.kicad_pcb; with FAB=1 also gerber/, bom.csv and cpl.csv for JLCPCB
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import pcbnew  # noqa: E402
from pcbgen import (W_PWR, drc, dump, fab, keepout, nut, outline, pad, place, save, text, track,  # noqa: E402
                    via, zone)

OUT = os.path.join(HERE, "x2201-carrier-v4.kicad_pcb")
B = pcbnew.B_Cu
W_USB, W3, WS = 0.2, 0.4, 0.25

# ---- outline, nuts, plug row ---------------------------------------------------------------
X0, X1 = 3.6, 61.8  # v3's 57.8 + 4: the antenna
BACK = 8.6
HW = 26.0
CORNER = 2.5
NUTS = [(17.6, -18.6), (17.6, 18.6), (35.7, -18.6), (35.7, 18.6)]

R0603, C0603, C0805 = "R_0603_1608Metric", "C_0603_1608Metric", "C_0805_2012Metric"
SOT, ZH2 = "SOT-23", "JST_ZH_B2B-ZR-SM4-TF_1x02-1MP_P1.50mm_Vertical"


def r(ref, val, x, y, rot, a, b, fp=R0603):
    return place("Resistor_SMD", fp, ref, val, x, y, rot, {"1": a, "2": b})


def c(ref, val, x, y, rot, a, b, fp=C0603):
    return place("Capacitor_SMD", fp, ref, val, x, y, rot, {"1": a, "2": b})


# ---- U1: ESP32-S3-MINI-1, front right, antenna forward -----------------------------------------
# Turned 270: its left column (IO0..IO11) faces the board's middle, its
# bottom row (IO12..IO21, USB) the back, its right column (EN) the right edge.
UX, UY = 48.8, 17.5
GPIO = {
    3: "3V3", 45: "EN",
    8: "S1", 9: "S2", 10: "LED",  # IO4, IO5, IO6: to the ESC (front left) and the LED
    11: "IR", 12: "CRSF_TX", 13: "CRSF_RX", 14: "MSP_TX", 15: "MSP_RX",  # IO7..IO11: to the back
    21: "VBAT_ADC",  # IO17, ADC2_CH6
    23: "USB_DM", 24: "USB_DP"}
U1_NETS = {str(k): v for k, v in GPIO.items()}
for n in (1, 2, 42, 43, *range(46, 66)):
    U1_NETS[str(n)] = "GND"
U1 = place("Espressif", "ESP32-S3-MINI-1", "U1", "ESP32-S3-MINI-1-N8", UX, UY, 270, U1_NETS)
keepout(UX + 7.7, UY - 8.5, X1 + 1, HW + 1)  # under the antenna, both layers
# Its decoupling, under the cheek's relief (<= 1 mm high).
C6 = c("C6", "100nF", 53.05, 7.9, 90, "3V3", "GND")
C5 = c("C5", "10uF", 54.6, 7.9, 90, "3V3", "GND")

# ---- USB-C, front edge under the camera ---------------------------------------------------------
USBX, USBY = 59.0, 0.5
J9 = place("Connector_USB", "USB_C_Receptacle_HRO_TYPE-C-31-M-12", "J9", "USB-C", USBX, USBY, 90,
           {"A1": "GND", "B12": "GND", "B1": "GND", "A12": "GND", "B4": "VBUS", "A9": "VBUS",
            "A4": "VBUS_NC", "B9": "VBUS_NC", "A5": "CC1", "B5": "CC2", "A6": "USB_DP", "B6": "USB_DP",
            "A7": "USB_DM", "B7": "USB_DM", "SH": "GND"})
# A4/B9, the VBUS contact on the module's side, is left open (the D- pair
# runs past it): the plug's VBUS reaches B4/A9 either way round, and the S3
# draws well under one contact's rating.
R12 = r("R12", "5.1k", 51.0, 1.75, 180, "CC1", "GND")
R13 = r("R13", "5.1k", 51.0, -1.25, 180, "CC2", "GND")
R18 = r("R18", "1k", 47.1, 4.6, 90, "LED", "LEDR")
D4 = place("LED_SMD", "LED_0603_1608Metric", "D4", "green", 47.1, 1.6, 270, {"1": "GND", "2": "LEDR"})

# ---- front left: the ESC's plug, power ---------------------------------------------------------
J1 = place("Connector_JST", "JST_ZH_B4B-ZR-SM4-TF_1x04-1MP_P1.50mm_Vertical", "J1", "ZH1.5 4P (ESC)", 50.25, -22.5, 0,
           {"1": "S2E", "2": "S1E", "3": "GND", "4": "5V", "MP": "GND"})
R17 = r("R17", "220", 48.0, -16.6, 90, "S2", "S2E")
R16 = r("R16", "220", 49.6, -16.6, 90, "S1", "S1E")
D2 = place("Diode_SMD", "D_SOD-123", "D2", "B5819W", 55.2, -11.6, 180, {"1": "VIN", "2": "VBUS"})
U3 = place("Package_TO_SOT_SMD", "SOT-23-5", "U3", "AP2112K-3.3", 55.2, -15.0, 0,
           {"1": "VIN", "2": "GND", "3": "VIN", "5": "3V3"})
D3 = place("Diode_SMD", "D_SOD-123", "D3", "B5819W", 55.2, -18.1, 180, {"1": "VIN", "2": "5V"})
C9 = c("C9", "1uF", 51.8, -15.0, 90, "VIN", "GND")
C10 = c("C10", "22uF", 58.4, -15.0, 270, "3V3", "GND", C0805)
C2 = c("C2", "22uF", 58.4, -21.6, 90, "5V", "GND", C0805)

# ---- right front corner, behind U1: EN ----------------------------------------------------------
R11 = r("R11", "10k", 38.0, 24.5, 180, "3V3", "EN")
C8 = c("C8", "1uF", 35.0, 24.5, 180, "EN", "GND")

# ---- between the right ears (2 mm under the frame): the VTX switch -----------------------------
Q2 = place("Package_TO_SOT_SMD", SOT, "Q2", "AO3401", 24.5, 21.3, 0, {"1": "Q2G", "2": "VBAT", "3": "VTX"})
R2 = r("R2", "100k", 21.6, 21.3, 270, "Q2G", "VBAT")
C3 = c("C3", "22uF 25V", 22.3, 24.4, 180, "VBAT", "GND", "C_1206_3216Metric")
R3 = r("R3", "47k", 26.8, 18.4, 0, "Q2G", "Q3D")
Q3 = place("Package_TO_SOT_SMD", SOT, "Q3", "AO3400", 28.8, 21.8, 180, {"1": "Q3G", "2": "GND", "3": "Q3D"})
R4 = r("R4", "1k", 31.7, 19.4, 270, "3V3", "Q3G")
R5 = r("R5", "100k", 31.7, 23.2, 270, "Q3G", "GND")

# ---- by the battery plug: its divider -------------------------------------------------------
R14 = r("R14", "100k", 13.35, 23.4, 90, "VBAT", "VBAT_ADC")
C11 = c("C11", "100nF", 13.35, 20.4, 90, "GND", "VBAT_ADC")
R15 = r("R15", "22k", 13.35, 17.4, 90, "GND", "VBAT_ADC")

NUT = [nut("H" + str(i + 1), x, y) for i, (x, y) in enumerate(NUTS)]

# ---- the plug row, as v3; J2 and J3 now carry UARTs ---------------------------------------
J5 = place("Connector_JST", ZH2, "J5", "ZH1.5 2P (IR LED)", BACK, -21.0, 270, {"1": "LEDA", "2": "LEDK", "MP": "GND"})
J2 = place("Connector_JST", "JST_ZH_B4B-ZR-SM4-TF_1x04-1MP_P1.50mm_Vertical", "J2", "ZH1.5 4P (EP2)", BACK, -8.5, 270,
           {"1": "CRSF_TX", "2": "CRSF_RX", "3": "GND", "4": "5V", "MP": "GND"})
J3 = place("Connector_JST", "JST_SH_BM04B-SRSS-TB_1x04-1MP_P1.00mm_Vertical", "J3", "SH1.0 4P (VTX)", BACK, 2.5, 270,
           {"1": "VTX", "2": "GND", "3": "MSP_TX", "4": "MSP_RX", "MP": "GND"})
J4 = place("Connector_JST", ZH2, "J4", "ZH1.5 2P (fan)", BACK, 12.0, 270, {"1": "5V", "2": "GND", "MP": "GND"})
J6 = place("Connector_JST", ZH2, "J6", "ZH1.5 2P (battery)", BACK, 21.0, 270, {"1": "VBAT", "2": "GND", "MP": "GND"})

# The IR LED's driver, as v3, between the left ears.
Q4 = place("Package_TO_SOT_SMD", SOT, "Q4", "AO3400", 27.5, -20.5, 0, {"1": "GATE", "2": "GND", "3": "LEDK"})
R6 = r("R6", "33", 31.0, -19.5, 270, "LEDA", "5V", "R_1206_3216Metric")
R7 = r("R7", "100", 24.5, -18.0, 90, "IR", "GATE")
R8 = r("R8", "100k", 22.8, -21.45, 0, "GND", "GATE")

if os.environ.get("DUMP"):
    dump()
    sys.exit()
if os.environ.get("PLACE"):
    outline(X0, -HW, X1, HW, CORNER)
    save(OUT)
    sys.exit()

# ==== tracks =====================================================================================
P = pad
# -- U1's 3V3: C6 / C5 under the cheek, fed from below -------------------------------------------
track([P(U1, 3), P(C6, 1), P(C5, 1)], "3V3", W3)
via(52.1, 5.0, "3V3")
track([(52.1, 5.0), (52.1, 8.675), P(C6, 1)], "3V3", W3)
# -- IO4..IO6 down through the middle: the ESC's signals, the LED ----------------------------------
track([P(U1, 8), (48.8, -14.6), P(R16, 1)], "S1", WS)
track([P(U1, 9), (47.95, -14.6), P(R17, 1)], "S2", WS)
track([P(R17, 2), P(J1, 1)], "S2E", WS)
track([P(R16, 2), (49.5, -18.6), P(J1, 2)], "S1E", WS)
track([P(U1, 10), P(R18, 1)], "LED", WS)
track([P(R18, 2), P(D4, 2)], "LEDR", WS)
# -- IO7..IO11 to the back, under the VTX: a nested bundle -----------------------------------------
BUNDLE = [(15, 9.3, 12.6, (4.0, J3, 4)), (14, 8.85, 13.4, (3.0, J3, 3)), (13, 8.4, 14.2, (-9.25, J2, 2)),
          (12, 7.95, 15.0, (-10.75, J2, 1))]
for n, yb, xt, (yd, m, pn) in BUNDLE:
    x = P(U1, n)[0]
    track([P(U1, n), (x, yb), (xt, yb), (xt, yd), P(m, pn)], GPIO[n], WS)
track([P(U1, 11), (46.25, 7.5), (30.0, 7.5), (30.0, -14.0), (24.5, -15.5), P(R7, 1)], "IR", WS)
track([P(R7, 2), (24.5, -21.45), P(Q4, 1)], "GATE")
track([P(R8, 2), (24.5, -21.45)], "GATE")
# -- battery voltage: the divider by J6, along y 15.8 to IO17 ---------------------------------------
track([P(U1, 21), (14.25, 15.8), (14.25, 22.575), P(R14, 2)], "VBAT_ADC", WS)
track([(14.25, 16.575), P(R15, 2)], "VBAT_ADC", WS)
track([(14.25, 19.575), P(C11, 2)], "VBAT_ADC", WS)
# -- USB: D+ round the back of the pads, D- through vias under the shell; both on the bottom --------
track([P(J9, "B6"), (53.8, -0.25), (53.8, 0.75), P(J9, "A6")], "USB_DP", W_USB)
track([(53.8, 0.25), (53.1, 0.25)], "USB_DP", W_USB)
via(53.1, 0.25, "USB_DP")
for y in (0.25, 1.25):
    via(56.15, y, "USB_DM")
track([P(J9, "A7"), (56.15, 0.25)], "USB_DM", W_USB)
track([P(J9, "B7"), (56.15, 1.25)], "USB_DM", W_USB)
track([(56.15, 0.25), (56.15, 1.25), (57.3, 1.25), (57.3, 6.6), (40.7, 6.6), (40.7, 17.5)], "USB_DM", W_USB, B)
via(40.7, 17.5, "USB_DM")
track([(40.7, 17.5), P(U1, 23)], "USB_DM", W_USB)
track([(53.1, 0.25), (53.1, 6.2), (40.0, 6.2), (40.0, 18.35)], "USB_DP", W_USB, B)
via(40.0, 18.35, "USB_DP")
track([(40.0, 18.35), P(U1, 24)], "USB_DP", W_USB)
track([P(J9, "A5"), P(R12, 1)], "CC1", W_USB)
track([P(J9, "B5"), P(R13, 1)], "CC2", W_USB)
track([P(J9, "B4"), (53.3, -1.95), (53.3, -11.0), P(D2, 2)], "VBUS", W3)
track([(55.2, -2.75), (55.2, -3.6)], "GND")
track([(55.2, 3.75), (55.2, 4.6)], "GND")
# -- VIN, 3V3 ----------------------------------------------------------------------------------
track([P(D2, 1), (56.85, -12.8), (53.0, -12.8), (53.0, -15.95), P(U3, 1)], "VIN", W3)
track([(53.0, -14.05), P(U3, 3)], "VIN", W3)
track([P(C9, 1), (53.0, -14.225)], "VIN", W3)
track([P(D3, 1), (56.85, -16.9), (53.0, -16.9), (53.0, -15.95)], "VIN", W3)
track([P(U3, 5), P(C10, 1), (58.4, -17.2)], "3V3", W3)
via(58.4, -17.2, "3V3")
track([(58.4, -17.2), (52.1, -17.2), (52.1, 5.0)], "3V3", W3, B)
track([(52.1, -5.0), (38.3, -5.0), (38.3, 23.5)], "3V3", W3, B)
via(38.3, 23.5, "3V3")
track([(38.3, 23.5), P(R11, 1)], "3V3", W3)
track([(38.3, 16.0), (31.7, 16.0), (31.7, 17.6)], "3V3", W3, B)
via(31.7, 17.6, "3V3")
track([(31.7, 17.6), P(R4, 1)], "3V3")
# EN: along the right edge from pin 45 to R11 / C8.
track([P(U1, 45), (54.75, 25.35), (36.5, 25.35), (36.5, 24.5), P(R11, 2)], "EN", WS)
track([(36.5, 24.5), P(C8, 1)], "EN", WS)
# -- 5V: J1 -> D3, C2; a trunk on the bottom to R6, the EP2 and the fan -----------------------------
track([P(J1, 4), (52.5, -20.3), (58.4, -20.3), P(C2, 1)], "5V", W_PWR)
track([(52.5, -20.3), (52.5, -19.95), P(D3, 2)], "5V", W_PWR)
track([(52.5, -20.3), (52.0, -19.4)], "5V", W_PWR)
via(52.0, -19.4, "5V")
track([(52.0, -19.4), (50.0, -23.2), (5.0, -23.2)], "5V", W_PWR, B)
via(5.0, -23.2, "5V")
track([(33.0, -23.2), (33.0, -16.8)], "5V", W_PWR, B)
via(33.0, -16.8, "5V")
track([(33.0, -16.8), (31.0, -17.2), P(R6, 2)], "5V", W_PWR)
track([(5.0, -23.2), (5.0, 11.25), P(J4, 1)], "5V", W_PWR)  # along the back edge
track([(5.0, -6.25), P(J2, 4)], "5V", W_PWR)
# -- the IR LED's pair to J5 along the left edge, as v3 ---------------------------------------
track([P(R6, 1), (31.0, -24.4), (11.8, -24.4), (11.8, -21.75), P(J5, 1)], "LEDA", W_PWR)
track([P(Q4, 3), (28.44, -22.8), (13.0, -22.8), (13.0, -20.25), P(J5, 2)], "LEDK", W_PWR)
# -- the battery: J6 -> the bottom -> the VTX switch and R14 -------------------------------------
via(11.6, 20.25, "VBAT")
track([P(J6, 1), (11.6, 20.25)], "VBAT", W_PWR)
track([(11.6, 20.25), (11.6, 25.1), (24.9, 25.1)], "VBAT", W_PWR, B)
via(14.3, 25.1, "VBAT")
track([(14.3, 25.1), P(R14, 1)], "VBAT")
via(24.9, 25.1, "VBAT")
track([(24.9, 25.1), P(C3, 1), (23.56, 23.0), P(Q2, 2), P(R2, 2)], "VBAT", W_PWR)
# -- the VTX switch ---------------------------------------------------------------------------
track([P(R2, 1), P(Q2, 1)], "Q2G")
track([P(Q2, 1), (23.56, 19.3), P(R3, 1)], "Q2G")
track([P(R3, 2), (27.86, 18.6), P(Q3, 3)], "Q3D")
track([P(Q3, 1), (31.0, 22.75), P(R5, 1)], "Q3G")
track([P(R5, 1), P(R4, 2)], "Q3G")
track([P(Q2, 3), (26.4, 21.3), (26.4, 20.3)], "VTX", W_PWR)
via(26.4, 20.3, "VTX")
track([(26.4, 20.3), (26.4, 8.8), (12.5, 8.8), (12.5, 1.0)], "VTX", W_PWR, B)
via(12.5, 1.0, "VTX")
track([(12.5, 1.0), P(J3, 1)], "VTX", W_PWR)
# -- ground: both layers poured; vias in the module's pad and about the board -----------------
for dx in (-1.65, 1.65):
    for dy in (-1.65, 1.65):
        via(UX + dx, UY + dy, "GND")
via(UX, UY, "GND")
for v in ((30.6, 20.3), (50.0, 0.25), (47.1, -0.3), (36.5, 0.0), (23.5, 0.0), (29.0, 3.0), (20.0, 3.0),
          (23.5, -6.0), (5.0, 16.5), (19.4, 23.6), (20.5, -21.4), (12.45, 21.6), (12.0, 16.5), (57.8, -12.4),
          (54.9, -15.0), (50.8, -18.3), (59.8, -22.8), (33.0, 25.2), (45.0, 4.0), (45.0, -8.0),
          (56.0, -8.0), (58.0, 8.0)):
    via(*v, "GND")

# ---- silkscreen ---------------------------------------------------------------------------
for n, lab in ((1, "S2"), (2, "S1"), (3, "G"), (4, "5V")):
    x, _ = P(J1, n)
    text(lab, x, -18.6, 0.8, rot=90)
for m, lab in ((J5, "IR"), (J2, "EP2"), (J3, "VTX"), (J4, "FAN"), (J6, "BAT")):
    x, y = P(m, 1)
    text(lab, X0 + 1.0, (y + P(m, 2)[1]) / 2, 0.8, rot=90)
text("X2201 carrier v4", 26.65, -1.5, 1.2)
text("VTX here", 26.65, 1.0, 1.0)

for m in (U1, J9):  # footprint silk past the outline
    for g in list(m.GraphicalItems()):
        if g.GetLayer() == pcbnew.F_SilkS:
            bb = g.GetBoundingBox()
            if pcbnew.ToMM(bb.GetLeft()) < X0 + 0.3 or pcbnew.ToMM(bb.GetRight()) > X1 - 0.3 or \
                    pcbnew.ToMM(bb.GetTop()) < -HW + 0.3 or pcbnew.ToMM(bb.GetBottom()) > HW - 0.3:
                m.Remove(g)

outline(X0, -HW, X1, HW, CORNER)
zone("GND", pcbnew.F_Cu, X0 + 0.4, -HW + 0.4, X1 - 0.4, HW - 0.4)
zone("GND", B, X0 + 0.4, -HW + 0.4, X1 - 0.4, HW - 0.4)

if __name__ == "__main__":
    save(OUT)
    for l in drc(OUT):
        print(l)
    if os.environ.get("FAB"):
        fab(OUT)
