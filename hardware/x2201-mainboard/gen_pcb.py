"""The X2201 main board (the plan: ../PLAN.md): 40 x 40, everything on one board, the brushed ESC
included. The battery comes in here and nowhere else.

  battery --> W1/W2 --> Q1 (reverse guard) --+--> U5 DRV8874 (ESC, 4.9 A limit) --> J7 ZH2.0 --> 260 motor
                                             +--> U4 5 V 3 A buck, the BEC --> SuperMini, EP2, servo, fan, IR
  EP2 --CRSF--> J2 --> ESP32-S3 SuperMini --PWM--> P2 servo;  IO7 / IO4 --> U5 forward / reverse
  J6 power button: press on (D4 lifts EN, the S3 holds it with TX through D5); press again, the S3 lets go: off.

The SuperMini is hand-soldered on header pins, its USB-C off the left edge, with low parts underneath it. Every
plug is a side-entry ZH1.5 (the motor's a ZH2.0, off the right end), its mouth on an edge, so nothing stands up.
The EP2's TX pad only ever reaches an S3 input. JLC places the SMD parts on the top; the module and the two
battery wires are hand-soldered.

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

OUT = os.path.join(HERE, "x2201-mainboard.kicad_pcb")
# 40 x 40, inside the 40 x 60 room on the chassis (40 along the car, 60 across). X runs across the car, Y along
# it: Y = 0 is the front edge, Y = 40 the rear, seen from above. The M2 hole on the front suspension block's boss,
# the locating post toward the front, 22.02 along and 6.43 across from it, both confirmed by a printed dummy in the
# car (2026-11-17; cad/x2201_datum.py POST). The M2 screw is the only fixing; the post's 3.5 mm tip only locates.
W, H = 40.0, 40.0
CORNER = 2.0
M2_HOLE = (22.28, 29.71)    # M2 clearance, 2.4; the boss under it is 4.95 across
POST_HOLE = (28.71, 7.68)   # the post's 3.5 tip goes in, 3.6; the post under it is 5.0 across
HOLES = []

R805, C805, C1206 = "R_0805_2012Metric", "C_0805_2012Metric", "C_1206_3216Metric"
R0402, C0402 = "R_0402_1005Metric", "C_0402_1005Metric"
SOT, SOD = "SOT-23", "D_SOD-323"
ZH4 = "JST_ZH_B4B-ZR-SM4-TF_1x04-1MP_P1.50mm_Vertical"
ZH2 = "JST_ZH_B2B-ZR-SM4-TF_1x02-1MP_P1.50mm_Vertical"
SH6 = "JST_SH_BM06B-SRSS-TB_1x06-1MP_P1.00mm_Vertical"
HDR3 = "PinHeader_1x03_P2.54mm_Vertical"
WIRE = "SolderWire-0.5sqmm_1x01_D0.9mm_OD2.1mm"  # 20 AWG
ZH4S = "JST_ZH_S4B-ZR-SM4A-TF_1x04-1MP_P1.50mm_Horizontal"
ZH2S = "JST_ZH_S2B-ZR-SM4A-TF_1x02-1MP_P1.50mm_Horizontal"
ZH3S = "JST_ZH_S3B-ZR-SM4A-TF_1x03-1MP_P1.50mm_Horizontal"
PH2S = "JST_PH_S2B-PH-SM4-TB_1x02-1MP_P2.00mm_Horizontal"
HTSSOP = "HTSSOP-16-1EP_4.4x5mm_P0.65mm_EP3.4x5mm_Mask2.46x2.31mm"  # thermal vias added by hand, 0.3 mm
SH6S = "JST_SH_SM06B-SRSS-TB_1x06-1MP_P1.00mm_Horizontal"
HDR3H = "PinHeader_1x03_P2.54mm_Horizontal"
pcbgen.LCSC[("DMN3008SFG-7", "Diodes_PowerDI3333-8")] = "C384563"
# side-entry plugs, JST, checked on lcsc.com 2026-11-16
for _v in ("fan", "button"):
    pcbgen.LCSC[(f"ZH1.5 2P side ({_v})", "JST_ZH_S2B-ZR-SM4A-TF_1x02-1MP_P1.50mm_Horizontal")] = "C265329"
pcbgen.LCSC[("ZH1.5 4P side (EP2)", "JST_ZH_S4B-ZR-SM4A-TF_1x04-1MP_P1.50mm_Horizontal")] = "C485354"
pcbgen.LCSC[("ZH1.5 4P side (VTX)", "JST_ZH_S4B-ZR-SM4A-TF_1x04-1MP_P1.50mm_Horizontal")] = "C485354"
pcbgen.LCSC[("ZH1.5 3P side (servo)", "JST_ZH_S3B-ZR-SM4A-TF_1x03-1MP_P1.50mm_Horizontal")] = "C72591"
pcbgen.LCSC[("ZH2.0 2P side (motor)", "JST_PH_S2B-PH-SM4-TB_1x02-1MP_P2.00mm_Horizontal")] = "C295747"
pcbgen.LCSC[("DRV8874PWPR", "HTSSOP-16-1EP_4.4x5mm_P0.65mm_EP3.4x5mm_Mask2.46x2.31mm")] = "C1855818"
pcbgen.LCSC[("22nF", "C_0402_1005Metric")] = "C1532"    # 50 V X7R, the DRV8874's flying cap
pcbgen.LCSC[("1.5k", "R_0402_1005Metric")] = "C25867"   # the DRV8874's IPROPI
pcbgen.LCSC[("IR 940nm 3mm", "LED_D3.0mm")] = "C60099"
pcbgen.LCSC[("LSM6DSV16X", "LGA-14_3x2.5mm_P0.5mm_LayoutBorder3x4y")] = "C5267406"  # ST LSM6DSV16XTR  # Everlight IR204/H60: 940 nm, 3 mm, 100 mA, 1 A pulsed
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


npth("MH1", *M2_HOLE, d=2.4)
npth("MH2", *POST_HOLE, d=3.6)

# ---- U1: an ESP32-S3 SuperMini, hand-soldered through its two rows of 9 holes ---------------------
# 23.5 x 18, 2.54 pitch, standing on header pins (about 2.5 mm): low parts sit under it. Each castellated pad
# has a hole on the module's edge and one 1.27 in; the header goes through the inner ones, so the rows are
# 18 - 2 x 1.27 = 15.46 apart (the maker's drawing, 2025-10). The S3-Zero's are 1.38 in (15.24): it still fits.
# Along the car on the left, its USB-C off the rear edge. Seen from above with the USB end down, its top row
# (5V GND 3V3 13 12 11 10 9 8, from the USB end) is on the left, the bottom row (TX RX 1-7) on the right.
# Its chip antenna is at the front end, toward the bottom row: no copper under that.
MXL = 0.5                                          # the module's left edge
MROW = (MXL + 1.27, MXL + 18.0 - 1.27)             # the two rows
MPY = [H - 1.59 - 2.54 * k for k in range(9)]      # pin k from the USB end
MFRONT = H - 23.5                                  # the module's front end
ANT = (MXL + 7.3, MFRONT - 1.5, MXL + 15.3, MFRONT + 3.1)
# the VTX's UART on the right row, beside its plug; the gyro's I2C on the left, the gyro being under the module
TOP_ROW = ["VIN", "GND", "3V3", "CRSF_RX", "CRSF_TX", "SDA", "SCL", "VBAT_ADC", "SERVO"]      # 5V GND 3V3 13 12 11 10 9 8
BOT_ROW = ["HOLD", "BTN_SENSE", "MSP_TX", "MSP_RX", "IMU_INT", "M_REV", "IR", "VTX_EN", "M_FWD"]  # TX RX 1 2 3 4 5 6 7


def supermini(ref, nets):
    m = pcbnew.FOOTPRINT(pcbgen.board)
    m.SetReference(ref)
    m.SetValue("ESP32-S3 SuperMini")
    m.SetPosition(pcbgen.pt(MXL, MFRONT))
    pcbgen.board.Add(m)
    for k, (x, y) in enumerate([(MROW[0], py) for py in MPY] + [(MROW[1], py) for py in MPY]):
        p = pcbnew.PAD(m)
        p.SetNumber(str(k + 1))
        p.SetAttribute(pcbnew.PAD_ATTRIB_PTH)
        p.SetShape(pcbnew.PAD_SHAPE_RECTANGLE if k == 0 else pcbnew.PAD_SHAPE_CIRCLE)
        p.SetSize(pcbnew.VECTOR2I(mm(1.7), mm(1.7)))
        p.SetDrillSize(pcbnew.VECTOR2I(mm(1.0), mm(1.0)))
        p.SetLayerSet(pcbnew.PAD.PTHMask())
        p.SetPosition(pcbgen.pt(x, y))
        m.Add(p)
        if nets[k]:
            p.SetNet(pcbgen.net(nets[k]))
    # outline on the silk only: low parts sit under the module, so it has no courtyard of its own
    x0, y0, x1, y1 = MXL, MFRONT, MXL + 18.0, H
    for a_, b_ in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
        sh = pcbnew.PCB_SHAPE(m)
        sh.SetShape(pcbnew.SHAPE_T_SEGMENT)
        sh.SetStart(pcbgen.pt(*a_))
        sh.SetEnd(pcbgen.pt(*b_))
        sh.SetLayer(pcbnew.F_SilkS)
        sh.SetWidth(mm(0.12))
        m.Add(sh)
    m.Reference().SetVisible(False)
    m.Value().SetVisible(False)
    return m


U1 = supermini("U1", TOP_ROW + BOT_ROW)

# ---- under the SuperMini, between its rows and behind the antenna ------------------------------------
GX, GY = 10.5, 30.0  # the gyro (I2C 0x6A: SA0 low, CS high; aux bus unused); caps and pull-ups keep the old spacing
# LSM6DSV16X (ST, C5267406), the LSM6DS3TR-C's successor on the same LGA-14 2.5 x 3 and pin-out (DS13510 table 2):
# 1 SA0 low (I2C 0x6A), 2 3 to GND (analog hub / Qvar off), 4 INT1, 5 VDDIO, 6 7 GND, 8 VDD, 9 INT2 open, 10 11 open,
# 12 CS high for I2C, 13 SCL, 14 SDA. 2.8 mdps/rtHz. JLC Standard assembly only, like every part of this family
place("Package_LGA", "LGA-14_3x2.5mm_P0.5mm_LayoutBorder3x4y", "U2", "LSM6DSV16X", GX, GY, 0, {
    "1": "GND", "2": "GND", "3": "GND", "4": "IMU_INT", "5": "3V3", "6": "GND", "7": "GND", "8": "3V3",
    "12": "3V3", "13": "SCL", "14": "SDA"})
c("C12", "100nF", GX - 2.9, GY - 1.0, 90, "3V3", "GND", C0402)
c("C13", "100nF", GX - 2.9, GY + 1.2, 90, "3V3", "GND", C0402)
r04("R9", "4.7k", GX + 3.1, GY - 1.0, 90, "3V3", "SDA")
r04("R10", "4.7k", GX + 4.2, GY - 1.0, 90, "3V3", "SCL")
r04("R14", "100k", 3.6, 22.5, 90, "VBAT", "VBAT_ADC")
r04("R15", "22k", 4.75, 22.5, 90, "VBAT_ADC", "GND")
c("C11", "100nF", 5.9, 22.5, 90, "VBAT_ADC", "GND", C0402)
# the board's 5 V into the module's 5V pin (and the EP2), through D3: with USB in, VBUS stays on the module's side
place("Diode_SMD", SOD, "D3", "B5819WS", 5.5, 36.5, 0, {"1": "VIN", "2": "5V"})


# ---- right edge, plugs facing out: the servo, the EP2, the VTX. All ZH1.5 side-entry -----------------------
# turned 90: the mouth on the right edge, the pads facing in
P2 = place("Connector_JST", ZH3S, "P2", "ZH1.5 3P side (servo)", W - 4.0, 4.8, 90, {"1": "SERVO", "2": "5V", "3": "GND", "MP": "GND"})
J2 = place("Connector_JST", ZH4S, "J2", "ZH1.5 4P side (EP2)", W - 4.0, 15.3, 90,
           {"1": "CRSF_RX", "2": "CRSF_TX", "3": "VIN", "4": "GND", "MP": "GND"})
J3 = place("Connector_JST", ZH4S, "J3", "ZH1.5 4P side (VTX)", W - 4.0, 26.3, 90,
           {"1": "VTX", "2": "GND", "3": "VTX_RX", "4": "VTX_TX", "MP": "GND"})

# ---- left edge, front of the module, plugs facing out: the fan, the power button -----------------------
J4 = place("Connector_JST", ZH2S, "J4", "ZH1.5 2P side (fan)", 4.0, 4.5, 270, {"1": "5V", "2": "GND", "MP": "GND"})
# the power button, momentary, between the battery and BTN
J6 = place("Connector_JST", ZH2S, "J6", "ZH1.5 2P side (button)", 4.0, 12.3, 270, {"1": "VBAT", "2": "BTN", "MP": "GND"})

# ---- front edge: the battery pads, the reverse guard, the motor plug -----------------------------------
place("Connector_Wire", WIRE, "W1", "BAT+", 14.5, 2.0, 0, {"1": "VBAT"})
place("Connector_Wire", WIRE, "W2", "BAT-", 9.5, 2.0, 0, {"1": "BAT_N"})
# low-side guard, drain to the battery's negative, source to the board's ground. The right way round, the body
# diode carries the first current, GND sits a diode above BAT- and Vgs = VBAT turns Q1 hard on. Reversed, the
# body diode is reverse-biased and the gate sits at the source: off. DMN3008SFG: 1-3 source, 4 gate, 5 (the tab)
# drain.
place("Package_SON", "Diodes_PowerDI3333-8", "Q1", "DMN3008SFG-7", 11.5, 5.9, 180,
      {"1": "GND", "2": "GND", "3": "GND", "4": "Q1G", "5": "BAT_N"})
r04("R1", "10k", 14.2, 4.6, 90, "VBAT", "Q1G")
# the motor on a ZH2.0 (PH) plug facing off the front edge
J7 = place("Connector_JST", PH2S, "J7", "ZH2.0 2P side (motor)", 21.0, 5.14, 180,
           {"1": "MOT_A", "2": "MOT_B", "MP": "GND"})

# ---- the brushed ESC: DRV8874, PWM mode, current limited ------------------------------------------
# PMODE high: IN1 / IN2 = 10 forward, 01 reverse, 11 brake, 00 coast; both inputs have internal pull-downs,
# so a restarting S3 coasts. nSLEEP on 3V3: asleep whenever the board is off. IMODE on GND: fixed off-time
# chopping, retries after a fault. ITRIP = VREF / (450 uA/A x RIPROPI) = 3.3 / (450e-6 x 1.5k) = 4.9 A.
# Turned 180, behind the motor plug: OUT1 at the right column's top, OUT2 the left column's second; VM, VCP, CPH,
# CPL down the left column, the inputs up the right.
DX, DY = 21.0, 13.5
place("Package_SO", HTSSOP, "U5", "DRV8874PWPR", DX, DY, 180, {
    "1": "M_FWD", "2": "M_REV", "3": "3V3", "5": "3V3", "6": "IPROPI", "7": "GND", "8": "MOT_A",
    "9": "GND", "10": "MOT_B", "11": "VBAT", "12": "VCP", "13": "CPH", "14": "CPL", "15": "GND", "16": "3V3",
    "17": "GND"})
c("C15", "22uF 25V", 13.6, 12.53, 180, "VBAT", "GND", C1206)   # bulk, VM
c("C16", "100nF", 13.7, 10.3, 0, "VBAT", "GND", C0402)       # VM bypass
c("C18", "100nF", 14.9, 14.5, 0, "VBAT", "VCP", C0402)       # charge pump: VCP to VM
c("C19", "22nF", 16.4, 15.4, 90, "CPL", "CPH", C0402)        # charge pump flying cap, 50 V
r04("R26", "1.5k", DX + 5.0, DY - 0.97, 0, "IPROPI", "GND")

# ---- the power button: press for on, press again for off ----------------------------------------------
#   On:  the button puts the battery on EN through D4; the buck starts, the S3 boots and its TX (IO43, high
#        while idle, through boot and restarts) holds EN up through D5. Let go, it stays on.
#   Off: Q6 turns the button into a low on RX (IO44); the S3 sees the second press and drives TX low.
#        Once the button is let go, R16 pulls EN down. C20 keeps TX's boot-log pulses off EN.
q("Q6", "AO3400", 21.5, 22.5, 0, "BTN", "GND", "BTN_SENSE")
r04("R28", "10k", 24.3, 22.5, 90, "BTN", "GND")  # 10k: D4's leakage stays far under Q6's threshold
# RX's pull-up is the S3's own (about 45k), set in the firmware
# D4 a 1N4148WS, not a Schottky: with the board on, TX holds EN at about 3 V and D4 sits reverse-biased; a B5819WS
# leaks 4 uA at 25 C, about 40 uA hot, enough through R28 to lift BTN past Q6's threshold and read as an off press
place("Diode_SMD", SOD, "D4", "1N4148WS", 20.0, 18.5, 90, {"1": "EN_SW", "2": "BTN"})
place("Diode_SMD", SOD, "D5", "B5819WS", 22.5, 18.5, 90, {"1": "EN_SW", "2": "HOLD"})
r04("R16", "100k", 24.1, 18.5, 90, "EN_SW", "GND")
c("C20", "100nF", 25.2, 18.5, 90, "EN_SW", "GND", C0402)

# ---- the 5 V buck ------------------------------------------------------------------------------------
# LMR51430: 1 GND, 2 SW, 3 VIN, 4 FB, 5 EN, 6 CB; 5.0 V = 0.6 V x (1 + 22k / 3k). Turned 180: VIN, SW, GND
# down the right side, FB, EN, CB down the left. U4, C1, C5, L1 keep the earlier boards' spacing, so its hand
# routes carry over.
UX, UY = 29.0, 20.0
c("C1", "10uF", UX + 0.5, UY - 2.8, 180, "VBAT", "GND")
place("Package_TO_SOT_SMD", "SOT-23-6", "U4", "LMR51430XDDCR", UX, UY, 180,
      {"1": "GND", "2": "SW", "3": "VBAT", "4": "FB", "5": "EN_SW", "6": "CB"})
r04("R5", "3k", UX - 2.65, UY - 1.65, 90, "FB", "GND")
r04("R3", "22k", UX - 2.65, UY + 0.35, 90, "5V", "FB")
c("C5", "100nF", UX - 0.7, UY + 2.35, 0, "CB", "SW", C0402)
place("Inductor_SMD", "L_Changjiang_FXL0420", "L1", "4.7uH", UX + 0.1, UY + 5.25, 0, {"1": "SW", "2": "5V"})
c("C3", "22uF", 28.5, 29.4, 0, "5V", "GND")
c("C4", "22uF", 28.5, 31.5, 0, "5V", "GND")

# ---- under the module, behind the antenna: the VTX's switch, by IO6 ------------------------------------
# the VTX on the S3's word: VTX_EN high turns Q3 on, Q3 pulls Q2's gate down, Q2 passes the battery; off at reset
# Q2's gate (pin 1) top left, its drain right; Q3 turned 180, its drain left facing Q2, its gate bottom right
q("Q2", "AO3401", 10.3, 22.0, 0, "Q2G", "VBAT", "VTX")
q("Q3", "AO3400", 14.4, 22.0, 180, "Q3G", "GND", "Q2G")
r04("R2", "100k", 7.3, 22.0, 270, "Q2G", "VBAT")
r04("R7", "100k", 13.8, 24.4, 180, "Q3G", "GND")
r04("R4", "1k", 15.34, 24.75, 90, "VTX_EN", "Q3G")
# the VTX's UART resistors, beside the module's IO1 / IO2, behind the M2 hole
r04("R19", "1k", 19.2, 34.2, 270, "MSP_TX", "VTX_RX")
r04("R20", "1k", 20.4, 34.2, 270, "MSP_RX", "VTX_TX")

# ---- the lap transponder's IR LED, on the board by the rear edge -----------------------------------------
# a 3 mm 940 nm LED, soldered by JLC (THT assembly), upright to shine up through the shell; bend it over if needed
D6 = place("LED_THT", "LED_D3.0mm", "D6", "IR 940nm 3mm", 22.25, 36.3, 0, {"1": "LEDK", "2": "LEDA"})
# its driver under the module's rear end
q("Q4", "AO3400", 11.0, 35.0, 0, "IR", "GND", "LEDK")
r04("R8", "100k", 11.0, 37.8, 0, "IR", "GND")
r("R6", "33", 14.5, 35.0, 90, "LEDA", "5V")

# ---- the EP2 soldered on straight, at the rear edge: four holes on 2.54, the EP2 out past the edge ----------
# the same signals as J2 (either, not both). The EP2's pads, parts side up, read RX TX 5V GND from the left with
# the pads nearest you; laid parts side up with its pads toward the board, they run GND 5V TX RX left to right
J8 = place(HDR, "PinHeader_1x04_P2.54mm_Vertical", "J8", "EP2 pads", 29.5, 38.4, 90,
           {"1": "GND", "2": "VIN", "3": "CRSF_RX", "4": "CRSF_TX"})

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
            if os.environ["OVER"] == "2": print(a, [round(v, 2) for v in A]) if a < b else None
            if a < b and A[0] < B[2] and B[0] < A[2] and A[1] < B[3] and B[1] < A[3]:
                print(a, b, [round(v, 1) for v in A], [round(v, 1) for v in B])
    for m in pcbgen.board.GetFootprints():
        if m.GetReference() in ("Q1", "J7", "U5", "W1", "W2", "R1"):
            print(m.GetReference(), {p.GetNumber(): tuple(round(pcbnew.ToMM(v), 2) for v in (p.GetPosition().x, p.GetPosition().y)) for p in m.Pads()})
    sys.exit()


CLASSES = [("PWR", 0.5, 0.2, ["VBAT", "VTX", "BAT_N", "SW", "5V"]),
           ("MOTOR", 0.4, 0.2, ["MOT_A", "MOT_B"]),
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
# U4 (SOT-23-6, turned 180): GND drops to a via under the body; SW leaves sideways and comes round below to C5
# and L1; CB straight down to C5; FB joins R5 / R3 to the pin. U2 (LGA-14): the three 3V3 pins (5, 8, 12) joined
# round the outside, SDA out the top and over, SCL between them and down to a via. Q1's gate is boxed in by the
# drain and the sources: it leaves on a via and runs under to R1.
GX0, GY0 = GX - 8.5, GY - 30.0  # the gyro routes were drawn with U2 at (8.5, 30)


def _g(pts):
    return [(x + GX0, y + GY0) for x, y in pts]


HAND_T = [("GND", pcbnew.F_Cu, [(UX + 0.48, UY + 0.95), (UX, UY + 1.05)], 0.25),
          ("SW", pcbnew.F_Cu, [(UX + 1.8, UY), (UX + 2.3, UY), (UX + 2.3, UY + 3.1), (UX - 1.75, UY + 3.1), (UX - 1.75, UY + 4.25)], 0.4),
          ("SW", pcbnew.F_Cu, [(UX - 0.22, UY + 2.35), (UX - 0.22, UY + 3.1)], 0.3),
          ("CB", pcbnew.F_Cu, [(UX - 1.14, UY + 1.25), (UX - 1.18, UY + 2.35)], 0.25),
          ("FB", pcbnew.F_Cu, [(UX - 2.65, UY - 1.14), (UX - 2.65, UY - 0.16)], 0.2),
          ("FB", pcbnew.F_Cu, [(UX - 2.65, UY - 0.95), (UX - 1.14, UY - 0.95)], 0.2),
          # R3's 5 V: a via below it, under U4 on the back, up beside L1's 5 V pad
          ("5V", pcbnew.F_Cu, [(UX - 2.65, UY + 0.86), (UX - 2.65, UY + 2.15)], 0.3),
          ("5V", pcbnew.B_Cu, [(UX - 2.65, UY + 2.15), (UX - 2.65, UY + 2.6), (UX + 2.8, UY + 2.6), (UX + 2.8, UY + 5.25)], 0.3),
          ("5V", pcbnew.F_Cu, [(UX + 2.8, UY + 5.25), (UX + 1.95, UY + 5.25)], 0.3),
          # DRV8874, turned 180. OUT1 (pin 8, right column top) straight up to the plug's right pin; OUT2 (pin 10,
          # left column) out to the left and up round to the plug's left pin. Narrow at the pins, wide after.
          ("MOT_A", pcbnew.F_Cu, [(DX + 2.3, DY - 2.28), (DX + 2.3, DY - 2.9)], 0.4),
          ("MOT_A", pcbnew.F_Cu, [(DX + 2.3, DY - 2.9), (DX + 1.0, DY - 4.2), (DX + 1.0, 8.6)], 0.8),
          ("MOT_B", pcbnew.F_Cu, [(DX - 3.5, DY - 1.62), (DX - 4.2, DY - 1.62), (DX - 4.2, DY - 2.9)], 0.4),
          ("MOT_B", pcbnew.F_Cu, [(DX - 4.2, DY - 2.9), (DX - 4.2, 9.4), (DX - 3.3, 8.5), (DX - 1.0, 8.5)], 0.8),
          # VM (pin 11) left to the bulk cap; the battery's + down the left of the motor plug to it
          ("VBAT", pcbnew.F_Cu, [(DX - 3.5, DY - 0.97), (DX - 4.5, DY - 0.97)], 0.4),
          ("VBAT", pcbnew.F_Cu, [(DX - 4.5, DY - 0.97), (15.58, DY - 0.97)], 0.5),
          # the charge pump: VCP (12) to C18, CPH (13) and CPL (14) round to C19
          ("VCP", pcbnew.F_Cu, [(DX - 3.64, DY - 0.33), (16.2, DY - 0.33), (15.38, DY + 0.49), (15.38, 14.5)], 0.2),
          ("VBAT", pcbnew.F_Cu, [(14.42, 14.5), (14.42, 13.9), (14.9, 13.4)], 0.3),
          ("CPH", pcbnew.F_Cu, [(DX - 3.64, DY + 0.32), (16.9, DY + 0.32), (16.4, DY + 0.82), (16.4, 14.92)], 0.2),
          ("CPL", pcbnew.F_Cu, [(DX - 3.64, DY + 0.97), (17.05, DY + 0.97), (17.05, 15.88), (16.4, 15.88)], 0.2),
          ("VBAT", pcbnew.F_Cu, [(14.5, 2.0), (15.4, 2.9), (15.4, 12.0)], 1.0),
          ("VBAT", pcbnew.F_Cu, [(14.2, 5.11), (15.4, 5.11)], 0.3),
          # the buck's 5 V across the front to the left (the fan, D3): under the motor plug between its pads, above
          # the post's keepout, into the servo plug; down past the VBAT stub on the back, across on the top to J6's side
          ("5V", pcbnew.F_Cu, [(16.6, 4.45), (31.0, 4.45), (31.35, 4.8), (34.35, 4.8)], 0.5),
          ("5V", pcbnew.B_Cu, [(16.6, 4.45), (16.6, 5.9), (13.3, 9.2)], 0.5),
          ("5V", pcbnew.F_Cu, [(13.3, 9.2), (13.1, 9.0), (7.9, 9.0)], 0.5),
          # the battery's + to the buck and the VTX switch: along the front edge on the back, up the right side
          ("VBAT", pcbnew.B_Cu, [(14.5, 2.0), (15.3, 1.2), (32.4, 1.2), (33.2, 2.0), (33.2, 12.0), (32.0, 13.2), (32.0, 16.8)], 0.6),
          ("VBAT", pcbnew.F_Cu, [(32.0, 16.8), (31.6, 17.2), (30.45, 17.2)], 0.5),
          # the VTX's power from Q2 under the module to its plug: on the back between IO4 and IO3, over the M2 keepout
          # the VTX switch's own nets, short and on the top
          ("Q2G", pcbnew.F_Cu, [(13.46, 22.0), (12.5, 21.04), (12.5, 20.1), (9.36, 20.1), (9.36, 21.05)], 0.25),
          ("Q2G", pcbnew.F_Cu, [(7.3, 21.49), (7.3, 21.05), (9.36, 21.05)], 0.25),
          ("VBAT", pcbnew.F_Cu, [(7.3, 22.51), (7.74, 22.95), (9.36, 22.95)], 0.3),
          ("Q3G", pcbnew.F_Cu, [(15.34, 22.95), (15.34, 24.24)], 0.25),
          ("Q3G", pcbnew.F_Cu, [(14.31, 24.4), (14.47, 24.24), (15.34, 24.24)], 0.25),
          # IO6 to R4 on the back, beside the module's right row
          ("VTX_EN", pcbnew.B_Cu, [(15.34, 26.1), (15.9, 25.54), (15.9, 21.36), (MROW[1], MPY[7])], 0.25),
          ("VTX_EN", pcbnew.F_Cu, [(15.34, 25.26), (15.34, 26.1)], 0.25),
          ("VTX", pcbnew.F_Cu, [(11.24, 22.0), (11.6, 22.36), (11.6, 24.1), (12.3, 24.8)], 0.4),
          ("VTX", pcbnew.B_Cu, [(12.3, 24.8), (14.48, 26.98), (18.4, 26.98), (18.88, 26.5), (26.0, 26.5), (28.05, 28.55),
                                (32.4, 28.55)], 0.4),
          ("VTX", pcbnew.F_Cu, [(32.4, 28.55), (34.35, 28.55)], 0.4),
          # IO5 to the IR driver under the module's rear: down beside the M2 keepout, back in between IO2 and IO1
          ("IR", pcbnew.F_Cu, [(MROW[1], MPY[6]), (18.7, 24.64), (18.7, 31.6), (18.24, 32.06), (11.5, 32.06),
                               (10.06, 33.5), (10.06, 34.05)], 0.25),
          # the EP2's TX (into IO13) across on the back: from beside its plug, over the motor driver, down to the module
          ("CRSF_TX", pcbnew.B_Cu, [(30.32, 15.67), (28.54, 13.88), (24.89, 13.88), (23.1, 15.68), (17.95, 15.68),
                                    (16.1, 17.52), (16.1, 19.75), (9.08, 26.78), (7.8, 26.78)], 0.25),
          # IO8 round the module's front end, past the antenna keepout, across on the back to the servo plug
          ("SERVO", pcbnew.F_Cu, [(MROW[0], MPY[8]), (3.2, 16.8), (7.0, 16.8), (7.6, 16.2), (7.6, 14.6)], 0.25),
          ("SERVO", pcbnew.B_Cu, [(7.6, 14.6), (11.4, 10.8), (31.5, 10.8), (32.3, 10.0), (32.3, 7.3)], 0.25),
          ("SERVO", pcbnew.F_Cu, [(32.3, 7.3), (33.0, 6.6), (34.35, 6.3)], 0.25),
          # PGND (9), GND (15) and IMODE (7) into the thermal pad; nSLEEP (3) and VREF (5) joined outside the pins
          ("GND", pcbnew.F_Cu, [(DX - 2.07, DY - 2.27), (DX - 1.2, DY - 2.27)], 0.3),
          ("GND", pcbnew.F_Cu, [(DX - 2.07, DY + 1.62), (DX - 1.2, DY + 1.62)], 0.3),
          ("GND", pcbnew.F_Cu, [(DX + 2.07, DY - 1.62), (DX + 1.2, DY - 1.62)], 0.3),
          ("3V3", pcbnew.F_Cu, [(DX + 3.64, DY + 0.97), (DX + 4.1, DY + 0.97), (DX + 4.1, DY - 0.33), (DX + 3.64, DY - 0.33)], 0.25),
          ("IPROPI", pcbnew.F_Cu, [(DX + 3.64, DY - 0.97), (DX + 4.49, DY - 0.97)], 0.25),
          ("3V3", pcbnew.F_Cu, _g([(8.0, 31.22), (8.0, 31.6), (10.3, 31.6), (10.3, 28.4), (9.0, 28.4), (9.0, 28.78)]), 0.2),
          ("3V3", pcbnew.F_Cu, _g([(9.97, 30.75), (10.3, 30.75)]), 0.2),
          ("3V3", pcbnew.F_Cu, _g([(10.3, 29.51), (11.6, 29.51)]), 0.25),
          ("SDA", pcbnew.F_Cu, _g([(8.0, 29.09), (8.0, 28.7), (7.6, 28.3), (7.6, 27.2), (11.6, 27.2), (11.6, 28.49)]), 0.25),
          ("SCL", pcbnew.F_Cu, _g([(8.5, 29.09), (8.5, 27.9)]), 0.2),
          ("SCL", pcbnew.B_Cu, _g([(8.5, 27.9), (8.5, 29.1), (13.5, 29.1)]), 0.25),
          ("SCL", pcbnew.F_Cu, _g([(13.5, 29.1), (12.7, 28.49)]), 0.25)]
# six 0.3 mm vias under the DRV8874's thermal pad, into the ground pour on the back; four by Q1's sources,
# the motor's return to the battery down through the back
HAND_V = [*[("GND", DX + dx, DY + dy) for dx in (-0.75, 0.75) for dy in (-1.6, 0.0, 1.6)],
          *[("GND", 14.0, y) for y in (6.0, 7.0)], *[("GND", 13.0, y) for y in (8.2,)],
          ("GND", 6.8, 0.95), ("SERVO", 7.6, 14.6), ("5V", 16.6, 4.45), ("5V", 13.3, 9.2), ("5V", 7.9, 9.0), ("VBAT", 32.0, 16.8), ("CRSF_TX", 30.32, 15.67), ("CRSF_TX", 7.8, 26.78), ("VTX", 12.3, 24.8), ("VTX_EN", 15.34, 26.1), ("VTX", 32.4, 28.55), ("SERVO", 32.3, 7.3),  # stitches the front-left corner's ground to the rest
          ("5V", UX - 2.65, UY + 2.15), ("5V", UX + 2.8, UY + 5.25), ("GND", UX, UY + 1.05),
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


# JLC's part models sit turned from KiCad's footprints. By footprint, not by ref: the refs were reused across boards
# and a ref-keyed table turned the wrong parts. SOT-23 and SOD-323 were checked against JLC's SMT preview on the v8
# board. The rest from JLC's 3D preview of this board (2026-11-17): the DRV8874 (HTSSOP) and the LMR51430 (SOT-23-6)
# and the DMN3008SFG (PowerDI3333) came out a quarter turn off, their pin-1 dot a corner away from the silkscreen's
# triangle; the ZH 4P side plug (C485354) faced inward, unlike the 3P and 2P ones (other makers' models).
CPL_TURN = {"SOT-23": 180, "D_SOD-323": 180, "HTSSOP-16-1EP_4.4x5mm_P0.65mm_EP3.4x5mm_Mask2.46x2.31mm": 270,
            "SOT-23-6": 270, "Diodes_PowerDI3333-8": 270, "JST_ZH_S4B-ZR-SM4A-TF_1x04-1MP_P1.50mm_Horizontal": 180,
            # the IR LED: JLC's model has its + (anode) where KiCad's pin 1 (cathode) is, and its origin at the body's
            # centre, not at pin 1 (CPL_CENTRE)
            "LED_D3.0mm": 180}
# by value, before the footprint: a part whose JLC model differs from others in the same footprint. The 1N4148WS (D4,
# C2128) came out reversed against the B5819WS's 180 in the preview
CPL_TURN_VALUE = {"1N4148WS": 0}
CPL_CENTRE = {"LED_D3.0mm"}  # placed by the middle of the pads
# mm on the board (KiCad X, Y), as turned here: JLC's model sits off the footprint's centre. Q1's body came out 0.58 to
# the left of its pads in JLC's preview
CPL_SHIFT = {"Diodes_PowerDI3333-8": (0.58, 0.0)}
CPL_MOVE_Y = {}  # mm toward the top of the board: JLC's model has its origin elsewhere than KiCad's footprint


def cpl_rotation():
    import csv
    path = os.path.join(HERE, "cpl.csv")
    rows = list(csv.reader(open(path)))
    mods = {m.GetReference(): m for m in pcbgen.board.GetFootprints()}
    fp = {r: m.GetFPID().GetLibItemName().wx_str() for r, m in mods.items()}
    for row in rows[1:]:
        val = mods[row[0]].GetValue()
        turn = CPL_TURN_VALUE[val] if val in CPL_TURN_VALUE else CPL_TURN.get(fp[row[0]], 0)
        row[4] = str((int(float(row[4])) + turn) % 360)
        if fp[row[0]] in CPL_SHIFT:
            dx, dy = CPL_SHIFT[fp[row[0]]]
            row[1] = f"{float(row[1].replace('mm', '')) + dx:.3f}mm"
            row[2] = f"{float(row[2].replace('mm', '')) - dy:.3f}mm"
        if fp[row[0]] in CPL_CENTRE:
            ps = list(mods[row[0]].Pads())
            row[1] = f"{sum(pcbnew.ToMM(p.GetPosition().x) for p in ps) / len(ps):.3f}mm"
            row[2] = f"{-sum(pcbnew.ToMM(p.GetPosition().y) for p in ps) / len(ps):.3f}mm"
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
    """What plugs in where, on the back (no parts there to collide with); the battery pads on both sides."""
    B = pcbnew.B_SilkS
    for s_, x, y in [("SERVO", 35.5, 4.8), ("EP2", 35.5, 15.3), ("VTX", 35.5, 26.3), ("IR LED", 23.5, 39.1),
                     ("FAN", 4.0, 4.5), ("BTN", 4.0, 12.3), ("MOTOR", 21.0, 1.2), ("S3 SuperMini", 9.5, 34.0),
                     ("X2201 main board", 9.5, 37.0)]:
        text(s_, x, y, 0.8, B)
    for layer in (pcbnew.F_SilkS, B):
        # the EP2's holes, named as on the EP2: GND, 5V, its TX, its RX
        for k, s_ in enumerate(("-", "+", "T", "R")):
            text(s_, 29.5 + 2.54 * k, 35.9, 0.9, layer)
        text("EP2", 33.3, 34.6, 0.8, layer)
        for s_, x, y in [("+", 12.9, 2.0), ("-", 11.1, 2.0)]:
            text(s_, x, y, 1.0, layer)


if __name__ == "__main__":
    outline(0, 0, W, H, CORNER)
    # no copper under the module's antenna
    keepout(*ANT)
    if os.environ.get("PLACE"):
        pcbgen.project(OUT, CLASSES)
        save(OUT)
        for line in drc(OUT):
            print(line)
        sys.exit()
    labels()
    rules()
    # copper to the edge: 0.25 (JLC routes to 0.2); the straight edges keep 0.45 (edge_keepout), the corners' arcs
    # don't, and a via in the right-rear one sits 0.295 off it
    pcbgen.project(OUT, CLASSES, default=(0.25, 0.15), rules={"min_copper_edge_clearance": 0.25})
    import router
    # The battery's - and Q1's tab, on the top. The + runs as a 1 mm track (HAND_T); the return from the
    # DRV8874 to Q1's sources is the ground pour, on the back mostly.
    POWER = [
        ("BAT_N", (8.2, 0.5, 11.9, 7.6), True),
    ]
    # no copper round the two holes: the M2 boss (4.95), the post (5.0); both tops level
    HOLE_KEEP = [(x - 2.7, y - 2.7, x + 2.7, y + 2.7) for x, y in (M2_HOLE, POST_HOLE)]
    # octagons round the holes, 2.7 to the flats: the boss and the post are round, the corners are free
    t = 2.7 * 0.4142
    for x, y in (M2_HOLE, POST_HOLE):
        keepout(0, 0, 0, 0, pts=[(x + dx, y + dy) for dx, dy in
                                 ((t, -2.7), (2.7, -t), (2.7, t), (t, 2.7), (-t, 2.7), (-2.7, t), (-2.7, -t), (-t, -2.7))])
    KEEP = [ANT, *HOLE_KEEP, *[b for _, b, _ in POWER]]
    UNDER = []
    edge_keepout()
    draw_hand()
    if FR:
        freeroute(100)
        freeroute(100)  # again, from what the first pass left
        freeroute(200)  # and once more: the last net or two often finds its way here
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
        zone("GND", l, 0.3, 0.3, W - 0.3, H - 0.3, chamfer=1.0)
    pcbnew.ZONE_FILLER(pcbgen.board).Fill(pcbgen.board.Zones())
    save(OUT)
    prune()
    for line in drc(OUT):
        print(line)
    if os.environ.get("FAB"):
        fab(OUT, fitted="QCRDJULP", tht=("D6",))  # P2 is the servo's ZH plug, JLC places it
        cpl_rotation()
