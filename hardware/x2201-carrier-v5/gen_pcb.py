"""Carrier board v5: the car's control board, standalone (VHB-taped anywhere
on the chassis), parts on the top only, 4 layers. It carries the car's ELRS
receiver on the board and the car's brain; the video stays a separate module
on its plug (the Walksnail now, an OpenIPC VTX of our own later), so the
board fits any car.

    U5 ESP32-C3 + U6 SX1280 + U7 PA (ELRS) --CRSF--> U1 ESP32-C3 --PWM--> ESC
    U1 --MSP--> the VTX's UART (OSD); battery voltage on U1's ADC; IR lap code
    battery -> Q2 switch (on with the ESC's 5V) -> the VTX

Two ESP32-C3FH4 with the same periphery (Espressif's reference: 40 MHz
crystal, 24 nH on XTAL_P, 2.0 nH + 1 uF on VDD3P3, CLC at LNA_IN):
  - U5 runs ExpressLRS, wired as its "Generic C3 2400 PA" layout so stock
    firmware runs (SPI 4/5/6/7, BUSY 3, DIO1 1, RST 2, PA RXEN 18 / TXEN 19,
    UART 20/21). SX1280 -> 2450FM07D0034 -> AT2401C -> CLC -> J10, as
    AnyLeaf's elrs-hardware (MIT), with a 52 MHz crystal.
  - U1 is the car's brain (our firmware): its own USB on J9 for flashing and
    the console, WiFi on J12 for setup. It holds U5's EN and GPIO9, so it can
    put U5 in its ROM loader and pass ELRS's firmware through from J9.

Plugs, the same families and pin orders as v3 / v4, so their cables carry over:
  - J1 ZH1.5 4P: ESC, 1 S2 / 2 S1 / 3 GND / 4 5V (its BEC)
  - J3 SH1.0 4P: VTX, 1 power (switched battery) / 2 GND / 3 its RX / 4 its TX
  - J6 ZH1.5 2P: battery; J4 ZH1.5 2P: fan (5V); J5 ZH1.5 2P: IR LED
  - J9 USB-C; J10 / J11 / J12 U.FL: ELRS / U5's WiFi / U1's WiFi

Coordinates: KiCad's, the board's top-left corner at (0, 0).

Run with KiCad's Python:
  /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 gen_pcb.py
  (PLACE=1: placed only; FREEROUTING=<freerouting-1.9.0.jar>: route again; FAB=1: Gerbers, BOM, CPL)
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import pcbnew  # noqa: E402
import subprocess  # noqa: E402
import pcbgen  # noqa: E402
from pcbgen import FACE, drc, dump, fab, keepout, layers, mm, outline, place, save, track, via, zone  # noqa: E402

OUT = os.path.join(HERE, "x2201-carrier-v5.kicad_pcb")
layers(4)

W, H = 46.0, 36.0
CORNER = 1.5

R0402, C0402, L0402 = "R_0402_1005Metric", "C_0402_1005Metric", "L_0402_1005Metric"
R0603, C0603, C0805, C1206 = "R_0603_1608Metric", "C_0603_1608Metric", "C_0805_2012Metric", "C_1206_3216Metric"
SOT, QFN32 = "SOT-23", "QFN-32-1EP_5x5mm_P0.5mm_EP3.7x3.7mm"
XTAL, UFL = "Crystal_SMD_2016-4Pin_2.0x1.6mm", "U.FL_Hirose_U.FL-R-SMT-1_Vertical"



# ==== the parts: (ref, library, footprint, value, {pad: net}) ======================================
R, C, L = ("Resistor_SMD", "R_"), ("Capacitor_SMD", "C_"), ("Inductor_SMD", "L_")
SIZE = {"0402": "0402_1005Metric", "0603": "0603_1608Metric", "0805": "0805_2012Metric", "1206": "1206_3216Metric"}


def two(kind, size, a, b):
    return kind[0], kind[1] + SIZE[size], {"1": a, "2": b}


def c3(p, v33, io):
    """An ESP32-C3FH4's pads: p the prefix of its private nets, v33 its 3.3 V rail, io the GPIOs."""
    nets = {"1": p + "RF", "2": p + "VPA", "3": p + "VPA", "11": v33, "17": v33, "18": p + "VSPI",
            "29": p + "XN", "30": p + "XP", "31": v33, "32": v33, "33": "GND"}
    nets.update(io)
    return "Package_DFN_QFN", QFN32, nets


GND_PA = {n: "GND" for n in ("1", "2", "3", "7", "8", "9", "11", "12", "15", "17")}
JST = "Connector_JST"
PARTS = [
    # -- U5: ELRS's C3 (top) ------------------------------------------------------------------------
    ("U5", "ESP32-C3FH4", c3("RXC_", "3V3R", {
        "5": "RX_DIO1", "6": "RX_RST", "7": "RXC_EN", "8": "RX_BUSY", "9": "RX_MOSI", "10": "RX_MISO",
        "12": "RX_SCK", "13": "RX_NSS", "14": "RXC_IO8", "15": "RXC_BOOT", "25": "PA_RXEN", "26": "PA_TXEN",
        "27": "CRSF_TX", "28": "RXC_TXD"})),
    ("C18", "1uF", two(C, "0402", "3V3R", "GND")), ("C19", "10nF", two(C, "0402", "3V3R", "GND")),
    ("L2", "2nH", two(L, "0402", "3V3R", "RXC_VPA")), ("C22", "1uF", two(C, "0402", "RXC_VPA", "GND")),
    ("C20", "10uF", two(C, "0603", "3V3R", "GND")), ("C21", "100nF", two(C, "0402", "3V3R", "GND")),
    ("C25", "1uF", two(C, "0402", "RXC_VSPI", "GND")),
    ("Y1", "40MHz", ("Crystal", XTAL, {"1": "RXC_XI", "2": "GND", "3": "RXC_XN", "4": "GND"})),
    ("L3", "24nH", two(L, "0402", "RXC_XI", "RXC_XP")),
    ("C27", "10pF", two(C, "0402", "RXC_XI", "GND")), ("C28", "10pF", two(C, "0402", "RXC_XN", "GND")),
    ("C29", "1.2pF", two(C, "0402", "RXC_RF", "GND")), ("L4", "3nH", two(L, "0402", "RXC_RF", "RXC_ANT")),
    ("C30", "1.2pF", two(C, "0402", "RXC_ANT", "GND")),
    ("J11", "U.FL (receiver WiFi)", ("Connector_Coaxial", UFL, {"1": "RXC_ANT", "2": "GND"})),
    ("R26", "10k", two(R, "0402", "3V3R", "RXC_EN")), ("C26", "1uF", two(C, "0402", "RXC_EN", "GND")),
    ("R27", "10k", two(R, "0402", "3V3R", "RX_RST")), ("R28", "10k", two(R, "0402", "3V3R", "RXC_IO8")),
    ("R29", "10k", two(R, "0402", "3V3R", "RXC_BOOT")), ("R30", "1k", two(R, "0402", "RXC_TXD", "CRSF_RX")),
    ("U8", "AP2112K-3.3", ("Package_TO_SOT_SMD", "SOT-23-5", {"1": "VIN", "2": "GND", "3": "VIN", "5": "3V3R"})),
    ("C16", "1uF", two(C, "0603", "VIN", "GND")), ("C17", "22uF", two(C, "0805", "3V3R", "GND")),
    # -- the SX1280, its filter, the PA (top) ---------------------------------------------------------
    ("U6", "SX1280IMLTRT", ("Package_DFN_QFN", "QFN-24-1EP_4x4mm_P0.5mm_EP2.6x2.6mm", {
        "1": "SX_VRPA", "2": "SX_DCC", "3": "RX_RST", "4": "SX_XA", "5": "GND", "6": "SX_XB", "7": "RX_BUSY",
        "8": "RX_DIO1", "11": "3V3R", "12": "SX_DCC", "13": "GND", "14": "SX_SW", "15": "3V3R", "16": "RX_MISO",
        "17": "RX_MOSI", "18": "RX_SCK", "19": "RX_NSS", "20": "GND", "21": "GND", "22": "SX_RF", "23": "GND",
        "24": "GND", "25": "GND"})),
    ("Y2", "52MHz", ("Crystal", XTAL, {"1": "SX_XA", "2": "GND", "3": "SX_XB", "4": "GND"})),
    ("L5", "15uH", two(L, "0805", "SX_SW", "SX_DCC")),
    ("C31", "10nF", two(C, "0402", "SX_VRPA", "GND")), ("C32", "470nF", two(C, "0402", "SX_DCC", "GND")),
    ("C33", "10nF", two(C, "0402", "SX_DCC", "GND")), ("C34", "100nF", two(C, "0402", "3V3R", "GND")),
    ("C35", "100nF", two(C, "0402", "3V3R", "GND")),
    ("FL1", "2450FM07D0034T", ("AnyLeaf", "2450FM07D0034", {"1": "SX_RF", "2": "GND", "3": "PA_IO", "4": "GND"})),
    ("U7", "AT2401C", ("Package_DFN_QFN", "QFN-16-1EP_3x3mm_P0.5mm_EP1.7x1.7mm", {
        "4": "PA_IO", "5": "PA_TXEN", "6": "PA_RXEN", "10": "PA_ANT", "14": "3V3R", "16": "3V3R", **GND_PA})),
    ("R31", "100k", two(R, "0402", "PA_TXEN", "GND")), ("R32", "100k", two(R, "0402", "PA_RXEN", "GND")),
    ("C36", "100nF", two(C, "0402", "3V3R", "GND")), ("C37", "10pF", two(C, "0402", "3V3R", "GND")),
    ("C38", "1.2pF", two(C, "0402", "PA_ANT", "GND")), ("L6", "3nH", two(L, "0402", "PA_ANT", "ELRS_ANT")),
    ("C39", "1.2pF", two(C, "0402", "ELRS_ANT", "GND")),
    ("J10", "U.FL (ELRS)", ("Connector_Coaxial", UFL, {"1": "ELRS_ANT", "2": "GND"})),
    # -- top: plugs and the small stuff -------------------------------------------------------------
    ("J1", "ZH1.5 4P (ESC)", (JST, "JST_ZH_B4B-ZR-SM4-TF_1x04-1MP_P1.50mm_Vertical",
                              {"1": "S2E", "2": "S1E", "3": "GND", "4": "5V", "MP": "GND"})),
    ("R16", "220", two(R, "0402", "S1", "S1E")), ("R17", "220", two(R, "0402", "S2", "S2E")),
    ("R19", "1k", two(R, "0402", "MSP_TX", "VTX_RX")), ("R20", "1k", two(R, "0402", "MSP_RX", "VTX_TX")),
    ("R25", "10k", two(R, "0402", "3V3", "B_IO2")),  # GPIO2, a strap: pulled up, spare
    ("Q2", "AO3401", ("Package_TO_SOT_SMD", SOT, {"1": "Q2G", "2": "VBAT", "3": "VTX"})),
    ("R2", "100k", two(R, "0402", "Q2G", "VBAT")), ("C3", "22uF 25V", two(C, "1206", "VBAT", "GND")),
    ("R3", "47k", two(R, "0402", "Q2G", "Q3D")),
    ("Q3", "AO3400", ("Package_TO_SOT_SMD", SOT, {"1": "Q3G", "2": "GND", "3": "Q3D"})),
    ("R4", "1k", two(R, "0402", "3V3", "Q3G")), ("R5", "100k", two(R, "0402", "Q3G", "GND")),
    ("R14", "100k", two(R, "0402", "VBAT", "VBAT_ADC")), ("R15", "22k", two(R, "0402", "VBAT_ADC", "GND")),
    ("C11", "100nF", two(C, "0402", "VBAT_ADC", "GND")),
    ("Q4", "AO3400", ("Package_TO_SOT_SMD", SOT, {"1": "GATE", "2": "GND", "3": "LEDK"})),
    ("R6", "33", two(R, "0805", "LEDA", "5V")), ("R7", "100", two(R, "0402", "IR", "GATE")),
    ("R8", "100k", two(R, "0402", "GATE", "GND")),
    ("D3", "B5819WS", ("Diode_SMD", "D_SOD-323", {"1": "VIN", "2": "5V"})),
    ("U3", "AP2112K-3.3", ("Package_TO_SOT_SMD", "SOT-23-5", {"1": "VIN", "2": "GND", "3": "VIN", "5": "3V3"})),
    ("C9", "1uF", two(C, "0402", "VIN", "GND")), ("C10", "22uF", two(C, "0805", "3V3", "GND")),
    # -- U1: the brain (bottom) ---------------------------------------------------------------------
    ("U1", "ESP32-C3FH4", c3("B_", "3V3", {
        "4": "S1", "5": "S2", "6": "B_IO2", "7": "EN", "8": "VBAT_ADC", "9": "MSP_TX", "10": "MSP_RX", "12": "IR",
        "13": "RXC_EN", "14": "LED", "15": "RXC_BOOT", "25": "USB_DM", "26": "USB_DP", "27": "CRSF_RX",
        "28": "CRSF_TX"})),
    ("C45", "1uF", two(C, "0402", "3V3", "GND")), ("C46", "10nF", two(C, "0402", "3V3", "GND")),
    ("L8", "2nH", two(L, "0402", "3V3", "B_VPA")), ("C42", "1uF", two(C, "0402", "B_VPA", "GND")),
    ("C43", "10uF", two(C, "0603", "3V3", "GND")), ("C44", "100nF", two(C, "0402", "3V3", "GND")),
    ("C49", "1uF", two(C, "0402", "B_VSPI", "GND")),
    ("Y3", "40MHz", ("Crystal", XTAL, {"1": "B_XI", "2": "GND", "3": "B_XN", "4": "GND"})),
    ("L9", "24nH", two(L, "0402", "B_XI", "B_XP")),
    ("C50", "10pF", two(C, "0402", "B_XN", "GND")), ("C51", "10pF", two(C, "0402", "B_XI", "GND")),
    ("C40", "1.2pF", two(C, "0402", "B_RF", "GND")), ("L7", "3nH", two(L, "0402", "B_RF", "B_ANT")),
    ("C41", "1.2pF", two(C, "0402", "B_ANT", "GND")),
    ("J12", "U.FL (brain WiFi)", ("Connector_Coaxial", UFL, {"1": "B_ANT", "2": "GND"})),
    ("R11", "10k", two(R, "0402", "3V3", "EN")), ("C8", "1uF", two(C, "0402", "EN", "GND")),
    ("R34", "10k", two(R, "0402", "3V3", "LED")), ("R18", "1k", two(R, "0402", "3V3", "LEDR")),
    ("D4", "green", ("LED_SMD", "LED_0603_1608Metric", {"1": "LED", "2": "LEDR"})),
    ("J9", "USB-C", ("Connector_USB", "USB_C_Receptacle_HRO_TYPE-C-31-M-12", {
        "A1": "GND", "B12": "GND", "B1": "GND", "A12": "GND", "B4": "VBUS", "A9": "VBUS", "A4": "VBUS", "B9": "VBUS",
        "A5": "CC1", "B5": "CC2", "A6": "USB_DP", "B6": "USB_DP", "A7": "USB_DM", "B7": "USB_DM", "SH": "GND"})),
    ("R12", "5.1k", two(R, "0402", "CC1", "GND")), ("R13", "5.1k", two(R, "0402", "CC2", "GND")),
    ("D2", "B5819WS", ("Diode_SMD", "D_SOD-323", {"1": "VIN", "2": "VBUS"})),
    # -- plugs (v3's) --------------------------------------------------------------------------------
    ("J6", "ZH1.5 2P (battery)", (JST, "JST_ZH_B2B-ZR-SM4-TF_1x02-1MP_P1.50mm_Vertical",
                                  {"1": "VBAT", "2": "GND", "MP": "GND"})),
    ("J3", "SH1.0 4P (VTX)", (JST, "JST_SH_BM04B-SRSS-TB_1x04-1MP_P1.00mm_Vertical",
                              {"1": "VTX", "2": "GND", "3": "VTX_RX", "4": "VTX_TX", "MP": "GND"})),
    ("J4", "ZH1.5 2P (fan)", (JST, "JST_ZH_B2B-ZR-SM4-TF_1x02-1MP_P1.50mm_Vertical",
                              {"1": "5V", "2": "GND", "MP": "GND"})),
    ("J5", "ZH1.5 2P (IR LED)", (JST, "JST_ZH_B2B-ZR-SM4-TF_1x02-1MP_P1.50mm_Vertical",
                                 {"1": "LEDA", "2": "LEDK", "MP": "GND"})),
]

# ==== where they go: ref -> (x, y, rotation, side); a plug's rotation as the edge it faces ===========
F, B = "F", "B"
POS = {
    # the receiver, top right: placed (and its RF lines drawn) as one block
    "U5": (35.40, 8.50, 180, F), "C18": (34.00, 13.60, 0, F), "C19": (32.00, 13.60, 0, F), "C29": (39.08, 10.97, 270, F),
    "L4": (40.95, 8.20, 90, F), "C30": (40.95, 5.50, 90, F), "J11": (44.10, 6.50, 0, F), "C20": (31.20, 6.50, 90, F),
    "C21": (33.00, 3.30, 0, F), "C25": (31.40, 2.20, 0, F), "R28": (31.40, 1.10, 0, F), "Y1": (30.40, 9.60, 90, F),
    "L3": (29.70, 12.00, 0, F), "C27": (28.20, 8.90, 90, F), "C28": (28.20, 10.90, 90, F), "R26": (26.60, 6.30, 0, F),
    "C26": (26.60, 7.40, 0, F), "R27": (26.60, 8.50, 0, F), "R29": (26.60, 9.60, 0, F), "R30": (26.60, 10.70, 0, F),
    "U8": (23.40, 7.90, 0, F), "C16": (23.80, 10.50, 0, F), "C17": (24.75, 12.40, 0, F), "U6": (30.90, 17.30, 270, F),
    "Y2": (25.60, 16.50, 0, F), "L5": (30.90, 22.10, 0, F), "C31": (33.60, 21.10, 90, F), "C32": (28.00, 20.90, 90, F),
    "C33": (27.00, 20.90, 90, F), "C34": (27.40, 18.80, 270, F), "C35": (34.70, 21.10, 90, F), "FL1": (34.39, 17.10, 0, F),
    "U7": (37.40, 15.70, 0, F), "R31": (35.90, 19.70, 90, F), "R32": (37.00, 19.70, 90, F), "C36": (38.10, 19.70, 90, F),
    "C37": (39.20, 19.70, 90, F), "C38": (40.15, 17.45, 270, F), "L6": (40.15, 15.50, 90, F), "C39": (40.15, 13.50, 90, F),
    "J10": (43.30, 14.60, 0, F),
    "L2": (37.60, 2.60, 0, F), "C22": (37.60, 1.50, 0, F),
    # the brain, left of it; its WiFi U.FL on the top edge
    "U1": (12.50, 12.10, 270, F), "J12": (14.00, 3.70, 90, F), "L7": (14.25, 7.80, 90, F),
    "C40": (15.80, 8.40, 0, F), "C41": (15.90, 7.10, 0, F),
    "L8": (9.40, 7.70, 90, F), "C42": (8.30, 7.70, 90, F), "C43": (10.00, 4.60, 90, F), "C44": (10.20, 17.60, 90, F),
    "C45": (19.30, 9.60, 0, F), "C46": (19.30, 8.60, 0, F), "C49": (11.20, 17.60, 90, F),
    "Y3": (19.70, 11.95, 270, F), "L9": (17.30, 11.25, 180, F), "C50": (22.00, 12.65, 0, F), "C51": (17.30, 10.00, 180, F),
    "R11": (12.40, 20.20, 90, F), "C8": (13.50, 20.20, 90, F), "R34": (14.60, 20.20, 90, F), "R25": (15.70, 20.20, 90, F),
    "D4": (12.60, 23.20, 0, F), "R18": (15.40, 23.20, 0, F),
    # plugs: left edge (ESC, VTX, battery), bottom edge (fan, IR, USB-C)
    "J1": (4.0, 6.1, 90, F), "J3": (3.20, 17.55, 90, F), "J6": (4.00, 27.60, 90, F),
    "J4": (13.0, H - 3.99, 180, F), "J5": (22.0, H - 3.99, 180, F), "J9": (34.5, H - 2.8, 0, F),
    "R16": (8.0, 2.0, 90, F), "R17": (9.1, 2.0, 90, F),
    "R19": (7.60, 13.90, 90, F), "R20": (7.60, 16.00, 90, F),
    # the VTX switch, the divider, the IR driver, 3V3 / VIN, USB's CC
    "Q2": (10.60, 26.40, 0, F), "R2": (9.20, 23.30, 90, F), "C3": (20.80, 26.20, 90, F), "R3": (10.30, 23.30, 90, F),
    "Q3": (14.80, 26.40, 0, F), "R4": (17.40, 26.00, 90, F), "R5": (18.50, 26.00, 90, F),
    "R14": (18.10, 1.50, 90, F), "R15": (19.20, 1.50, 90, F), "C11": (20.30, 1.50, 90, F),
    "Q4": (22.80, 2.40, 0, F), "R6": (26.60, 2.00, 0, F), "R7": (26.40, 3.90, 0, F), "R8": (22.00, 4.65, 0, F),
    "U3": (33.00, 24.80, 0, F), "C9": (36.00, 23.60, 90, F), "C10": (37.80, 24.20, 90, F),
    "D2": (27.60, 26.00, 0, F), "D3": (27.40, 23.60, 0, F),
    "R12": (40.00, 24.20, 90, F), "R13": (41.10, 24.20, 90, F),
}

M = {}
for ref, value, (lib, fp, pads) in PARTS:
    x, y, rot, side = POS[ref]
    if isinstance(rot, str):
        rot = FACE[side][rot]
    M[ref] = place(lib, fp, ref, value, x, y, rot, pads, side)
for g in list(M["J9"].GraphicalItems()):  # the USB-C's silk over the board's edge
    if g.GetLayer() == pcbnew.F_SilkS and max(g.GetStart().y, g.GetEnd().y) > mm(H - 1.2):
        M["J9"].Remove(g)

# ==== rules: JLCPCB 4-layer (1.6 mm, 1 oz outer); net classes by current ===========================
CLASSES = [  # name, track, clearance, nets
    ("PWR", 0.5, 0.2, ["VBAT", "VTX"]),  # the VTX's ~1 A
    ("MID", 0.35, 0.15, ["5V", "VIN", "3V3", "3V3R", "VBUS", "LEDA", "LEDK", "SX_DCC", "SX_SW"]),
    ("RF", 0.3, 0.2, ["RXC_RF", "RXC_ANT", "SX_RF", "PA_IO", "PA_ANT", "ELRS_ANT", "B_RF", "B_ANT"]),
]


def rules():
    ds = pcbgen.board.GetDesignSettings()
    ds.m_TrackMinWidth = mm(0.15)
    ds.m_MinClearance = mm(0.15)
    ds.m_ViasMinSize = mm(0.45)
    ds.m_CopperEdgeClearance = mm(0.3)
    ns = ds.m_NetSettings
    d = ns.GetDefaultNetclass()
    d.SetTrackWidth(mm(0.2))
    d.SetClearance(mm(0.15))
    d.SetViaDiameter(mm(0.5))
    d.SetViaDrill(mm(0.3))
    for name, w, cl, nets in CLASSES:
        nc = pcbnew.NETCLASS(name)
        nc.SetTrackWidth(mm(w))
        nc.SetClearance(mm(cl))
        nc.SetViaDiameter(mm(0.6 if name == "PWR" else 0.5))
        nc.SetViaDrill(mm(0.3))
        ns.SetNetclass(name, nc)
        for n in nets:
            ns.SetNetclassPatternAssignment(n, name)
    pcbgen.board.SynchronizeNetsAndNetClasses(True)


# ==== the RF lines, drawn by hand and locked (50 ohm on the top over In1's ground: 0.3 mm) ==========
RF = [  # net, layer, points
    ("SX_RF", "F", [(32.84, 17.05), (33.79, 17.10)]),
    ("PA_IO", "F", [(34.99, 17.10), (35.50, 16.45), (35.94, 16.45)]),
    ("PA_ANT", "F", [(38.86, 15.95), (40.15, 15.99), (40.15, 16.97)]),
    ("ELRS_ANT", "F", [(40.15, 13.98), (40.15, 14.60), (41.78, 14.60)]),
    ("ELRS_ANT", "F", [(40.15, 14.60), (40.15, 15.02)]),
    ("RXC_RF", "F", [(37.85, 10.25), (40.95, 10.25), (40.95, 8.68)]),
    ("RXC_RF", "F", [(39.08, 10.25), (39.08, 10.49)]),
    ("RXC_ANT", "F", [(40.95, 7.72), (40.95, 6.50), (42.58, 6.50)]),
    ("RXC_ANT", "F", [(40.95, 6.50), (40.95, 5.98)]),
    ("B_RF", "F", [(14.25, 9.65), (14.25, 8.28)]),
    ("B_RF", "F", [(14.25, 8.90), (15.32, 8.90), (15.32, 8.40)]),
    ("B_ANT", "F", [(14.25, 7.32), (14.25, 6.10), (14.00, 5.22)]),
    ("B_ANT", "F", [(14.25, 7.10), (15.42, 7.10)]),
]
RF_NETS = {n for n, _, _ in RF}
# the SX1280's DC-DC switch node: the shortest line, drawn by hand (0.3 mm, fixed)
SHORT = [("SX_SW", [(30.15, 19.24), (30.15, 21.75)], 0.3),
         # the brain's crystal in a row: pin 30 - L9 - Y3 (XI), XN under it to Y3 and C50
         ("3V3R", [(28.96, 18.05), (27.65, 18.05), (27.4, 18.3)], 0.25),  # U6 pin 11 to C34
         ("B_XP", [(14.95, 11.35), (16.6, 11.35), (16.815, 11.25)], 0.2),
         ("B_XI", [(16.815 + 0.97, 11.25), (19.15, 11.25)], 0.2),
         ("B_XI", [(17.78, 10.0), (17.785, 11.25)], 0.2),
         ("B_XN", [(14.95, 11.85), (17.3, 11.85), (17.4, 11.95), (19.75, 11.95), (20.25, 12.45), (20.25, 12.65),
                   (21.52, 12.65)], 0.15)]
SES = os.path.join(HERE, "x2201-carrier-v5.ses")
FR = os.environ.get("FREEROUTING", "")  # path to freerouting-1.9.0.jar, to route again


def prerouted():
    for name, side, pts in RF:
        track(pts, name, 0.3, pcbnew.F_Cu if side == "F" else pcbnew.B_Cu)
    for name, pts, w in SHORT:
        track(pts, name, w)
    for m in pcbgen.board.GetFootprints():  # a QFN's GND pins: straight in to its exposed pad
        if m.GetReference() not in ("U6", "U7"):
            continue
        cx, cy = pcbnew.ToMM(m.GetPosition().x), pcbnew.ToMM(m.GetPosition().y)
        ep = max(m.Pads(), key=lambda q: q.GetSize().x)
        h = pcbnew.ToMM(ep.GetSize().x) / 2 - 0.1
        for q in m.Pads():
            if q is ep or q.GetNetname() != "GND":
                continue
            px, py = pcbnew.ToMM(q.GetPosition().x), pcbnew.ToMM(q.GetPosition().y)
            if abs(px - cx) > abs(py - cy):
                end = (cx + (h if px > cx else -h), py)
            else:
                end = (px, cy + (h if py > cy else -h))
            track([(px, py), end], "GND", 0.2)
    for t in pcbgen.board.GetTracks():
        t.SetLocked(True)


FANOUT_SKIP = {"GND", "3V3", "3V3R", "RXC_VPA", "B_VPA", "RXC_VSPI", "B_VSPI", "SX_VRPA", "SX_DCC", "SX_SW",
               "RXC_XN", "RXC_XP", "B_XN", "B_XP", "SX_XA", "SX_XB", "VIN", ""}


def _fan(tg, vg, ban, code, starts, limit=4.0):
    """Dijkstra on the top from a pad's cells to the nearest cell where a via fits."""
    import heapq
    L = (pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.B_Cu)
    nx, ny = tg.nx, tg.ny
    D = [(1, 0, 1), (-1, 0, 1), (0, 1, 1), (0, -1, 1), (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414)]
    best, prev, q = {}, {}, []
    for s in starts:
        best[s] = 0
        heapq.heappush(q, (0, s))
    lim = limit / RES
    while q:
        cost, s = heapq.heappop(q)
        if cost > best.get(s, 1e18) or cost > lim:
            continue
        x, y = s
        i = y * nx + x
        if s not in starts and cost > 0.55 / RES and not ban[i] and all(vg.ok(l, i, code) for l in L):
            path = [s]
            while s in prev:
                s = prev[s]
                path.append(s)
            return [(px * RES, py * RES) for px, py in path[::-1]]
        for dx, dy, w in D:
            u, v = x + dx, y + dy
            if 0 <= u < nx and 0 <= v < ny and tg.ok(pcbnew.F_Cu, v * nx + u, code):
                nc = cost + w
                if nc < best.get((u, v), 1e18):
                    best[(u, v)] = nc
                    prev[(u, v)] = s
                    heapq.heappush(q, (nc, (u, v)))
    return None


def _normal(m, p):
    """A QFN pad's outward direction, its tip (the outer end), and its slot along the side."""
    cx, cy = pcbnew.ToMM(m.GetPosition().x), pcbnew.ToMM(m.GetPosition().y)
    px, py = pcbnew.ToMM(p.GetPosition().x), pcbnew.ToMM(p.GetPosition().y)
    bb = p.GetBoundingBox()
    hx, hy = pcbnew.ToMM(bb.GetWidth()) / 2, pcbnew.ToMM(bb.GetHeight()) / 2
    if abs(px - cx) > abs(py - cy):
        n = (1 if px > cx else -1, 0)
        tip, off = (px + n[0] * hx, py), py - cy
    else:
        n = (0, 1 if py > cy else -1)
        tip, off = (px, py + n[1] * hy), px - cx
    return n, tip, (px, py), int(round(off / 0.5 + 0.5))


DOG = (0.55, 1.35, 2.15)  # pad tip to via: neighbours differ by a step, the far track passes between the near vias
RES_LEN = 1.0  # the corridor kept for a power / crystal / RF pin


def dogbones(refs=("U1", "U5", "U6")):
    """The textbook QFN fanout: each signal pin straight out to a via, near and far by turns along a
    side, so no via ever boxes a neighbour in. The power and crystal pins keep a corridor out on the
    top (reserved, not drawn). Returns the pads done; the rest go to the searching fanout()."""
    rf = {n for n, _, _ in RF}
    b = pcbgen.board
    gt, gv = _Owner(0.075 + 0.15), _Owner(0.25 + 0.15)
    vias = [(pcbnew.ToMM(v.GetPosition().x), pcbnew.ToMM(v.GetPosition().y)) for v in b.GetTracks() if v.Type() == pcbnew.PCB_VIA_T]
    vias += [(pcbnew.ToMM(q.GetPosition().x), pcbnew.ToMM(q.GetPosition().y)) for m in b.GetFootprints() for q in m.Pads()
             if q.GetDrillSize().x > 0]
    ban = _ban(vias)
    L3 = (pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.B_Cu)
    mods = {m.GetReference(): m for m in b.GetFootprints()}
    RESERVE.clear()
    for ref in refs:  # the corridors the power / crystal pins need
        m = mods[ref]
        ep = "25" if ref == "U6" else "33"
        for p in m.Pads():
            net = p.GetNetname()
            if p.GetNumber() == ep or net in ("", ) or net in rf or net not in FANOUT_SKIP:
                continue
            n, (tx, ty), _, _ = _normal(m, p)
            seg = (p.GetNetCode(), tx, ty, tx + n[0] * RES_LEN, ty + n[1] * RES_LEN, 0.175)
            RESERVE.append(seg)
            for g in (gt, gv):
                g.seg(pcbnew.F_Cu, *seg)
    done = set()
    for ref in refs:
        m = mods[ref]
        ep = "25" if ref == "U6" else "33"
        plan, sides = [], {}
        for p in m.Pads():
            if p.GetNumber() == ep or not p.GetNetname():
                continue
            n, tip, pos, k = _normal(m, p)
            sides.setdefault(n, {})[k] = (p, tip, pos)
        for n, pins in sides.items():
          failed = set()
          for _try in range(4):
            side_plan = []
            prev = None  # the previous slot's distance (None: no via there, "R": a corridor)
            fixed = lambda q: q.GetNetname() in FANOUT_SKIP or q.GetNetname() in rf or q.GetNumber() in failed
            new_fail = False
            for k in sorted(pins):
                p, (tx, ty), (px, py) = pins[k]
                net = p.GetNetname()
                if net in FANOUT_SKIP or net in rf or net.startswith("unconnected") or p.GetNumber() in failed:
                    prev = "R"
                    continue
                nxt = pins.get(k + 1)
                beside = prev == "R" or (nxt and fixed(nxt[0]))
                code = p.GetNetCode()
                got = None
                for d in DOG:
                    if beside and d < 1.35:
                        continue
                    if isinstance(prev, float) and abs(prev - d) < 0.79:
                        continue
                    vx, vy = tx + n[0] * d, ty + n[1] * d
                    i = int(round(vy / RES)) * gv.nx + int(round(vx / RES))
                    steps = max(1, int(d / RES))
                    if not ban[i] and all(gv.ok(l, i, code) for l in L3) and \
                            all(gt.ok(pcbnew.F_Cu, int(round((ty + n[1] * d * j / steps) / RES)) * gt.nx
                                      + int(round((tx + n[0] * d * j / steps) / RES)), code) for j in range(1, steps + 1)):
                        got = d
                        side_plan.append((p, net, code, px, py, vx, vy))
                        break
                if got is None:
                    failed.add(p.GetNumber())
                    new_fail = True
                    prev = "R"
                else:
                    prev = got
            if not new_fail:
                break
          plan += side_plan
          for k, (p, (tx, ty), _) in pins.items():
              if p.GetNumber() in failed:
                  RESERVE.append((p.GetNetCode(), tx, ty, tx + n[0] * RES_LEN, ty + n[1] * RES_LEN, 0.075))
        for p, net, code, px, py, vx, vy in plan:
            track([(px, py), (vx, vy)], net, 0.15)
            d0, pcbgen.VIA_D = pcbgen.VIA_D, 0.5  # 0.5 / 0.3: the far track passes 0.175 off it
            via(vx, vy, net)
            pcbgen.VIA_D = d0
            for g in (gt, gv):
                g.seg(pcbnew.F_Cu, code, px, py, vx, vy, 0.075)
                for l in L3:
                    g.seg(l, code, vx, vy, vx, vy, 0.25)
            _ban_add(ban, gt.nx, gt.ny, vx, vy)
            done.add((ref, p.GetNumber()))
    return done


RESERVE = []  # (code, x0, y0, x1, y1, half width): kept free on the top for the power / crystal pins


def fanout(refs=("U1", "U5", "U6"), done=()):
    """From each signal pin of the QFNs, a short track on the top to a via (found by search, so
    it goes round the passives): the router then never boxes a pin in, it meets the vias on
    In2 / B.Cu. Done before routing, when the top is still empty."""
    rf = {n for n, _, _ in RF}
    b = pcbgen.board
    tg, vg = _Owner(0.2 + 0.1), _Owner(0.2 + 0.25)
    vias = [(pcbnew.ToMM(v.GetPosition().x), pcbnew.ToMM(v.GetPosition().y)) for v in b.GetTracks() if v.Type() == pcbnew.PCB_VIA_T]
    vias += [(pcbnew.ToMM(p.GetPosition().x), pcbnew.ToMM(p.GetPosition().y)) for m in b.GetFootprints() for p in m.Pads()
             if p.GetDrillSize().x > 0]
    ban = _ban(vias)
    for seg in RESERVE:
        tg.seg(pcbnew.F_Cu, *seg)
        vg.seg(pcbnew.F_Cu, *seg)
    for m in b.GetFootprints():
        if m.GetReference() in ("J10", "J11", "J12", "FL1", "J9"):
            r = m.GetCourtyard(pcbnew.F_CrtYd).BBox()
            for y in range(int(pcbnew.ToMM(r.GetTop()) / RES), int(pcbnew.ToMM(r.GetBottom()) / RES) + 2):
                for x in range(int(pcbnew.ToMM(r.GetLeft()) / RES), int(pcbnew.ToMM(r.GetRight()) / RES) + 2):
                    if 0 <= x < tg.nx and 0 <= y < tg.ny:
                        ban[y * tg.nx + x] = 1
    n = 0
    for ref in refs:
        m = [m for m in b.GetFootprints() if m.GetReference() == ref][0]
        ep = "25" if ref == "U6" else "33"
        for p in sorted(m.Pads(), key=lambda p: int(p.GetNumber()) if p.GetNumber().isdigit() else 0):
            net = p.GetNetname()
            if net in FANOUT_SKIP or net in rf or p.GetNumber() == ep or (ref, p.GetNumber()) in done:
                continue
            code = p.GetNetCode()
            starts = {(x, y) for x, y, _ in _cells(p, 0)}
            path = _fan(tg, vg, ban, code, starts)
            if not path:
                continue
            pts = _simplify(path)
            track(pts, net, 0.2)
            vx, vy = pts[-1]
            via(vx, vy, net)
            for s, e in zip(pts, pts[1:]):
                tg.seg(pcbnew.F_Cu, code, s[0], s[1], e[0], e[1], 0.1)
                vg.seg(pcbnew.F_Cu, code, s[0], s[1], e[0], e[1], 0.1)
            for l in (pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.B_Cu):
                tg.seg(l, code, vx, vy, vx, vy, 0.25)
                vg.seg(l, code, vx, vy, vx, vy, 0.25)
            _ban_add(ban, tg.nx, tg.ny, vx, vy)
            n += 1
    for t in b.GetTracks():
        t.SetLocked(True)
    return n


def pours():
    for layer in (pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.B_Cu):
        zone("GND", layer, 0.3, 0.3, W - 0.3, H - 0.3, chamfer=1.2)


def edge_keepout(w=0.45):
    """No tracks or vias within w of the edge (JLC's copper-to-edge, with margin)."""
    for x0, y0, x1, y1 in ((0, 0, W, w), (0, H - w, W, H), (0, 0, w, H), (W - w, 0, W, H)):
        keepout(x0, y0, x1, y1)


def freeroute(passes):
    """Export the board as it stands, let Freerouting route what's missing, read it back."""
    dsn = os.path.join(HERE, "route.dsn")
    pcbnew.ExportSpecctraDSN(pcbgen.board, dsn)
    # In1 is the ground plane: a "power" layer to Freerouting, so it routes no signals there
    d = open(dsn).read()
    i = d.index("(layer In1.Cu")
    d = d[:i] + d[i:].replace("(type signal)", "(type power)", 1)
    open(dsn, "w").write(d)
    subprocess.run(["java", "-jar", FR, "-de", dsn, "-do", SES, "-mp", str(passes), "-mt", "1"], check=True,
                   cwd=os.path.dirname(FR))
    os.remove(dsn)
    pcbnew.ImportSpecctraSES(pcbgen.board, SES)


def redraw_rf():
    """Freerouting may touch the RF nets: put back exactly the hand-drawn lines."""
    rf = {n for n, _, _ in RF}
    for t in list(pcbgen.board.GetTracks()):
        if t.GetNetname() in rf:
            pcbgen.board.Remove(t)
    for name, side, pts in RF:
        track(pts, name, 0.3, pcbnew.F_Cu if side == "F" else pcbnew.B_Cu)


def _clear(shape, net, layers, cl=0.2):
    b = pcbgen.board
    for t in b.GetTracks():
        if t.GetNetname() == net:
            continue
        for l in layers:
            if (t.Type() == pcbnew.PCB_VIA_T or t.GetLayer() == l) and t.GetEffectiveShape(l).Collide(shape, mm(cl)):
                return False
    for m in b.GetFootprints():
        for p in m.Pads():
            if p.GetNetname() == net:
                continue
            for l in layers:
                if p.IsOnLayer(l) and p.GetEffectiveShape(l).Collide(shape, mm(cl)):
                    return False
    return True


def prune(path):
    """Take out what DRC finds dangling (Freerouting's stubs, fanout vias the routes didn't use)."""
    import json
    kept = []  # first: a via on top of another of its net (a link ending on a via) goes
    for v in [t for t in pcbgen.board.GetTracks() if t.Type() == pcbnew.PCB_VIA_T]:
        x, y = pcbnew.ToMM(v.GetPosition().x), pcbnew.ToMM(v.GetPosition().y)
        if any(n == v.GetNetname() and (x - a) ** 2 + (y - c) ** 2 < 0.2 ** 2 for n, a, c in kept):
            pcbgen.board.Remove(v)
        else:
            kept.append((v.GetNetname(), x, y))
    for _ in range(3):
        rpt = path.replace(".kicad_pcb", "-drc.json")
        subprocess.run([pcbgen.CLI, "pcb", "drc", "--format", "json", "-o", rpt, path], capture_output=True)
        d = json.load(open(rpt))
        os.remove(rpt)
        pts = [(v["items"][0]["pos"]["x"], v["items"][0]["pos"]["y"]) for v in d["violations"]
               if v["type"] in ("via_dangling", "track_dangling")]
        if not pts:
            return
        gone = 0
        for t in list(pcbgen.board.GetTracks()):
            if t.GetNetname() in RF_NETS:
                continue
            if t.Type() == pcbnew.PCB_VIA_T:
                c = [t.GetPosition()]
            else:
                c = [t.GetStart(), t.GetEnd(), (t.GetStart() + t.GetEnd()) / 2]
            if any(abs(pcbnew.ToMM(q.x) - x) < 0.01 and abs(pcbnew.ToMM(q.y) - y) < 0.01 for q in c for x, y in pts):
                pcbgen.board.Remove(t)
                gone += 1
        pcbnew.ZONE_FILLER(pcbgen.board).Fill(pcbgen.board.Zones())
        save(path)
        if not gone:
            return


def stitch_gnd(points):
    """A via to the ground plane beside each unconnected GND pad (at points, from DRC)."""
    import math
    cu = [pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]
    pads = [p for m in pcbgen.board.GetFootprints() for p in m.Pads() if p.GetNetname() == "GND"]
    done = 0
    seen = set()
    for x, y in points:
        p = min(pads, key=lambda q: (pcbnew.ToMM(q.GetPosition().x) - x) ** 2 + (pcbnew.ToMM(q.GetPosition().y) - y) ** 2)
        px, py = pcbnew.ToMM(p.GetPosition().x), pcbnew.ToMM(p.GetPosition().y)
        if (px - x) ** 2 + (py - y) ** 2 > 0.01 or (px, py) in seen:  # not a pad (a pour's island), or done
            continue
        seen.add((px, py))
        for r in (0.6, 0.8, 1.0, 1.2, 1.5, 1.8):
            ok = None
            for k in range(24):
                a = 2 * math.pi * k / 24
                vx, vy = px + r * math.cos(a), py + r * math.sin(a)
                if not (0.8 < vx < W - 0.8 and 0.8 < vy < H - 0.8):
                    continue
                via_s = pcbnew.SHAPE_CIRCLE(pcbnew.VECTOR2I(mm(vx), mm(vy)), mm(0.25))
                seg = pcbnew.SHAPE_SEGMENT(p.GetPosition(), pcbnew.VECTOR2I(mm(vx), mm(vy)), mm(0.25))
                if _clear(via_s, "GND", cu) and _clear(seg, "GND", [pcbnew.F_Cu]):
                    ok = (vx, vy)
                    break
            if ok:
                track([(px, py), ok], "GND", 0.25)
                via(*ok, "GND")
                done += 1
                break
    return done


def stitch_grid(step=2.0):
    """GND vias on a grid wherever there's room: they tie the four layers' ground together."""
    cu = [pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]
    n = 0
    y = 1.2
    while y < H - 1.0:
        x = 1.2
        while x < W - 1.0:
            s = pcbnew.SHAPE_CIRCLE(pcbnew.VECTOR2I(mm(x), mm(y)), mm(0.25))
            if _clear(s, "GND", cu, 0.25) and _clear_courtyards(x, y) and _via_room(x, y):
                via(x, y, "GND")
                n += 1
            x += step
        y += step
    return n


def _via_room(x, y, d=0.8):
    """No other via (any net, GND included) within d: drills keep their distance."""
    for v in pcbgen.board.GetTracks():
        if v.Type() == pcbnew.PCB_VIA_T and (pcbnew.ToMM(v.GetPosition().x) - x) ** 2 + \
                (pcbnew.ToMM(v.GetPosition().y) - y) ** 2 < d * d:
            return False
    return True


def _clear_courtyards(x, y):
    """Not under a connector or the RF parts' bodies (a via under a plug's body is fine, but
    not under a U.FL or the filter)."""
    for m in pcbgen.board.GetFootprints():
        if m.GetReference()[:2] in ("J1", "FL") or m.GetReference() in ("J10", "J11", "J12", "J9"):
            r = m.GetCourtyard(pcbnew.F_CrtYd).BBox()
            if pcbnew.ToMM(r.GetLeft()) - 0.3 < x < pcbnew.ToMM(r.GetRight()) + 0.3 and \
                    pcbnew.ToMM(r.GetTop()) - 0.3 < y < pcbnew.ToMM(r.GetBottom()) + 0.3:
                return False
    return True


def stitch_islands():
    """A GND via into every piece of the outer / In2 pours that has none (after a fill)."""
    pcbnew.ZONE_FILLER(pcbgen.board).Fill(pcbgen.board.Zones())
    cu = [pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]
    vias = [v.GetPosition() for v in pcbgen.board.GetTracks() if v.Type() == pcbnew.PCB_VIA_T and v.GetNetname() == "GND"]
    n = 0
    gpads = [p for m in pcbgen.board.GetFootprints() for p in m.Pads() if p.GetNetname() == "GND"]
    lone = []  # GND pads in a piece too small for a via of its own
    for z in pcbgen.board.Zones():
        if z.GetIsRuleArea() or z.GetNetname() != "GND" or z.GetLayer() == pcbnew.In1_Cu:
            continue
        polys = z.GetFilledPolysList(z.GetLayer())
        for i in range(polys.OutlineCount()):
            ol = polys.Outline(i)
            if any(ol.PointInside(v) for v in vias):
                continue
            bb = ol.BBox()
            x0, y0, x1, y1 = (pcbnew.ToMM(v) for v in (bb.GetLeft(), bb.GetTop(), bb.GetRight(), bb.GetBottom()))
            placed = False
            y = y0 + 0.3
            while y < y1 - 0.3 and not placed:
                x = x0 + 0.3
                while x < x1 - 0.3 and not placed:
                    c = pcbnew.VECTOR2I(mm(x), mm(y))
                    if all(ol.PointInside(c + pcbnew.VECTOR2I(mm(dx), mm(dy)))
                           for dx, dy in ((0, 0), (0.3, 0), (-0.3, 0), (0, 0.3), (0, -0.3))) and \
                            _clear(pcbnew.SHAPE_CIRCLE(c, mm(0.25)), "GND", cu, 0.2) and _via_room(x, y):
                        via(x, y, "GND")
                        vias.append(c)
                        n += 1
                        placed = True
                    x += 0.1
                y += 0.1
            if not placed:
                lone += [(pcbnew.ToMM(p.GetPosition().x), pcbnew.ToMM(p.GetPosition().y)) for p in gpads
                         if p.IsOnLayer(z.GetLayer()) and ol.PointInside(p.GetPosition())]
    if lone:
        k = stitch_gnd(lone)
        if k < len(lone):
            k += gnd_link(lone)
        n += k
    return n


def gnd_link(points):
    """A track (and vias if it must) from each GND pad at points to a GND via near it: for pads
    in a piece of pour too small, and too crowded round, for a via of their own."""
    b = pcbgen.board
    gv = [v for v in b.GetTracks() if v.Type() == pcbnew.PCB_VIA_T and v.GetNetname() == "GND"]
    tg, vg = _Owner(0.075 + 0.15), _Owner(0.25 + 0.15)
    vias = [(pcbnew.ToMM(v.GetPosition().x), pcbnew.ToMM(v.GetPosition().y)) for v in b.GetTracks() if v.Type() == pcbnew.PCB_VIA_T]
    vias += [(pcbnew.ToMM(q.GetPosition().x), pcbnew.ToMM(q.GetPosition().y)) for m in b.GetFootprints() for q in m.Pads()
             if q.GetDrillSize().x > 0]
    ban = _ban(vias)
    code = b.FindNet("GND").GetNetCode()
    pads = [q for m in b.GetFootprints() for q in m.Pads() if q.GetNetname() == "GND"]
    done = 0
    for x, y in points:
        p = min(pads, key=lambda q: (pcbnew.ToMM(q.GetPosition().x) - x) ** 2 + (pcbnew.ToMM(q.GetPosition().y) - y) ** 2)
        starts = _cells(p, 0)
        near = sorted(gv, key=lambda v: (pcbnew.ToMM(v.GetPosition().x) - x) ** 2 + (pcbnew.ToMM(v.GetPosition().y) - y) ** 2)
        for v in near[:6]:
            vx, vy = pcbnew.ToMM(v.GetPosition().x), pcbnew.ToMM(v.GetPosition().y)
            targets = {(int(round(vx / RES)) + dx, int(round(vy / RES)) + dy, li)
                       for dx in (-2, -1, 0, 1, 2) for dy in (-2, -1, 0, 1, 2) for li in range(3)}
            path = _route3(tg, vg, ban, code, starts, targets)
            if path:
                for pts, layer in _lay(path, "GND"):
                    for a, c in zip(pts, pts[1:]):
                        tg.seg(layer, code, a[0], a[1], c[0], c[1], 0.075)
                        vg.seg(layer, code, a[0], a[1], c[0], c[1], 0.075)
                done += 1
                break
    return done


# ---- finishing what Freerouting leaves: escape vias + a grid router on In2 / B.Cu ---------------
RES = 0.05  # grid, mm


class _Grid:
    """A flat occupancy grid over the board, RES mm a cell."""

    def __init__(self):
        self.nx, self.ny = int(W / RES) + 1, int(H / RES) + 1
        self.c = bytearray(self.nx * self.ny)

    def get(self, x, y):
        return self.c[y * self.nx + x]

    def rect(self, x0, y0, x1, y1, v=1):
        for y in range(max(0, int(y0 / RES)), min(self.ny, int(y1 / RES) + 2)):
            i = y * self.nx
            lo, hi = max(0, int(x0 / RES)), min(self.nx, int(x1 / RES) + 2)
            self.c[i + lo:i + hi] = bytes([v]) * (hi - lo)

    def seg(self, ax, ay, cx, cy, r):
        dx, dy = cx - ax, cy - ay
        L2 = dx * dx + dy * dy or 1e-9
        for y in range(max(0, int((min(ay, cy) - r) / RES)), min(self.ny, int((max(ay, cy) + r) / RES) + 2)):
            py = y * RES
            for x in range(max(0, int((min(ax, cx) - r) / RES)), min(self.nx, int((max(ax, cx) + r) / RES) + 2)):
                px = x * RES
                u = min(1, max(0, ((px - ax) * dx + (py - ay) * dy) / L2))
                if (px - ax - u * dx) ** 2 + (py - ay - u * dy) ** 2 <= r * r:
                    self.c[y * self.nx + x] = 1


def _obstacles(layer, net, half):
    """Where a track of `net` (half width `half`) may not go on `layer`."""
    g = _Grid()
    e = 0.45 + half  # the edge keep-out
    g.rect(0, 0, W, e)
    g.rect(0, H - e, W, H)
    g.rect(0, 0, e, H)
    g.rect(W - e, 0, W, H)
    cl = 0.2 + half

    def box(bb, grow):
        x0, y0, x1, y1 = (pcbnew.ToMM(v) for v in (bb.GetLeft(), bb.GetTop(), bb.GetRight(), bb.GetBottom()))
        g.rect(x0 - grow, y0 - grow, x1 + grow, y1 + grow)

    b = pcbgen.board
    for t in b.GetTracks():
        if t.GetNetname() == net:
            continue
        if t.Type() == pcbnew.PCB_VIA_T:
            box(t.GetBoundingBox(), cl)
        elif t.GetLayer() == layer:
            a, c = t.GetStart(), t.GetEnd()
            g.seg(pcbnew.ToMM(a.x), pcbnew.ToMM(a.y), pcbnew.ToMM(c.x), pcbnew.ToMM(c.y),
                  pcbnew.ToMM(t.GetWidth()) / 2 + cl)
    for m in b.GetFootprints():
        for p in m.Pads():
            if p.GetNetname() != net and p.IsOnLayer(layer):
                box(p.GetBoundingBox(), cl)
    return g


def _astar(g, a, c):
    import heapq
    nx, ny = g.nx, g.ny
    sx, sy, tx, ty = int(round(a[0] / RES)), int(round(a[1] / RES)), int(round(c[0] / RES)), int(round(c[1] / RES))
    for x, y in ((sx, sy), (tx, ty)):  # the end vias sit on their own cleared spots
        g.rect((x - 6) * RES, (y - 6) * RES, (x + 6) * RES, (y + 6) * RES, 0)
    D = [(1, 0, 1), (-1, 0, 1), (0, 1, 1), (0, -1, 1), (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414)]
    best = {(sx, sy): 0}
    prev = {}
    q = [(0, sx, sy)]
    while q:
        f, x, y = heapq.heappop(q)
        if (x, y) == (tx, ty):
            path = [(x, y)]
            while (x, y) in prev:
                x, y = prev[(x, y)]
                path.append((x, y))
            return [(px * RES, py * RES) for px, py in path[::-1]]
        cost = best[(x, y)]
        if f - ((x - tx) ** 2 + (y - ty) ** 2) ** 0.5 > cost + 1e-9:
            continue
        pd = (x - prev[(x, y)][0], y - prev[(x, y)][1]) if (x, y) in prev else None
        for dx, dy, w in D:
            u, v = x + dx, y + dy
            if 0 <= u < nx and 0 <= v < ny and not g.c[v * nx + u]:
                nc = cost + w + (0.5 if pd and pd != (dx, dy) else 0)
                if nc < best.get((u, v), 1e18):
                    best[(u, v)] = nc
                    prev[(u, v)] = (x, y)
                    heapq.heappush(q, (nc + ((u - tx) ** 2 + (v - ty) ** 2) ** 0.5, u, v))
    return None


def _simplify(path):
    out = [path[0]]
    for i in range(1, len(path) - 1):
        a, b, c = out[-1], path[i], path[i + 1]
        if abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])) > 1e-6:
            out.append(b)
    out.append(path[-1])
    return out


def _escape(px, py, net, away=None):
    """A via spot near (px, py) for `net`, joined to it on the top: (vx, vy) or None."""
    import math
    cu = [pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]
    for r in (0.6, 0.8, 1.0, 1.2, 1.5, 1.8, 2.2, 2.6, 3.0):
        for k in range(32):
            a = 2 * math.pi * k / 32
            vx, vy = px + r * math.cos(a), py + r * math.sin(a)
            if not (0.9 < vx < W - 0.9 and 0.9 < vy < H - 0.9):
                continue
            c = pcbnew.VECTOR2I(mm(vx), mm(vy))
            if _clear(pcbnew.SHAPE_CIRCLE(c, mm(0.25)), net, cu, 0.25) and _via_room(vx, vy) and \
                    _clear(pcbnew.SHAPE_SEGMENT(pcbnew.VECTOR2I(mm(px), mm(py)), c, mm(0.25)), net, [pcbnew.F_Cu], 0.22) and \
                    _clear_courtyards(vx, vy):
                return vx, vy
    return None


def _anchor(net, x, y, is_pad):
    """Where an unconnected item can be reached: a pad (escaped to a via) or a point on a track."""
    b = pcbgen.board
    if is_pad:
        pads = [p for m in b.GetFootprints() for p in m.Pads() if p.GetNetname() == net]
        p = min(pads, key=lambda q: (pcbnew.ToMM(q.GetPosition().x) - x) ** 2 + (pcbnew.ToMM(q.GetPosition().y) - y) ** 2)
        px, py = pcbnew.ToMM(p.GetPosition().x), pcbnew.ToMM(p.GetPosition().y)
        v = _escape(px, py, net)
        return (px, py, v) if v else None
    tr = [t for t in b.GetTracks() if t.GetNetname() == net and t.Type() != pcbnew.PCB_VIA_T]
    if not tr:
        return None
    t = min(tr, key=lambda t: min((pcbnew.ToMM(e.x) - x) ** 2 + (pcbnew.ToMM(e.y) - y) ** 2 for e in (t.GetStart(), t.GetEnd())))
    ends = [t.GetStart(), t.GetEnd()]
    layer = t.GetLayer()
    for e in ends:
        ex, ey = pcbnew.ToMM(e.x), pcbnew.ToMM(e.y)
        if _clear(pcbnew.SHAPE_CIRCLE(e, mm(0.25)), net, [pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.B_Cu], 0.2):
            return (ex, ey, (ex, ey))
    if layer == pcbnew.F_Cu:
        ex, ey = pcbnew.ToMM(ends[0].x), pcbnew.ToMM(ends[0].y)
        v = _escape(ex, ey, net)
        return (ex, ey, v) if v else None
    return None


class _Owner:
    """Per-layer grids of which net owns each cell (copper grown by a clearance): -1 free,
    a net code, or -2 for two nets (or the edge)."""

    def __init__(self, grow, locked_only=False):
        self.nx, self.ny = int(W / RES) + 1, int(H / RES) + 1
        self.grow = grow
        from array import array
        self.g = {l: array("i", [-1]) * (self.nx * self.ny) for l in (pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.B_Cu)}
        e = 0.45 + grow
        for l in self.g:
            self.box(l, -2, 0, 0, W, e)
            self.box(l, -2, 0, H - e, W, H)
            self.box(l, -2, 0, 0, e, H)
            self.box(l, -2, W - e, 0, W, H)
        b = pcbgen.board
        for t in b.GetTracks():
            if not locked_only or t.IsLocked():
                self.add(t)
        for m in b.GetFootprints():
            for p in m.Pads():
                bb = p.GetBoundingBox()
                x = 0.05 if p.GetNetname() in RF_NETS else 0.0
                for l in self.g:
                    if p.IsOnLayer(l):
                        x0, y0, x1, y1 = (pcbnew.ToMM(v) for v in (bb.GetLeft(), bb.GetTop(), bb.GetRight(), bb.GetBottom()))
                        self.box(l, p.GetNetCode(), x0 - x, y0 - x, x1 + x, y1 + x)

    def _mark(self, l, i, code):
        g = self.g[l]
        v = g[i]
        if v == -1 or code == -2:
            g[i] = code
        elif v != code:
            g[i] = -2

    def box(self, l, code, x0, y0, x1, y1):
        import math
        r = self.grow if code != -2 else 0
        # the cells whose centres fall inside (no rounding outwards: corridors between QFN pins are a cell wide)
        for y in range(max(0, math.ceil((y0 - r) / RES - 1e-6)), min(self.ny, math.floor((y1 + r) / RES + 1e-6) + 1)):
            for x in range(max(0, math.ceil((x0 - r) / RES - 1e-6)), min(self.nx, math.floor((x1 + r) / RES + 1e-6) + 1)):
                self._mark(l, y * self.nx + x, code)

    def seg(self, l, code, ax, ay, cx, cy, hw):
        r = hw + self.grow
        dx, dy = cx - ax, cy - ay
        L2 = dx * dx + dy * dy or 1e-9
        for y in range(max(0, int((min(ay, cy) - r) / RES)), min(self.ny, int((max(ay, cy) + r) / RES) + 2)):
            py = y * RES
            for x in range(max(0, int((min(ax, cx) - r) / RES)), min(self.nx, int((max(ax, cx) + r) / RES) + 2)):
                px = x * RES
                u = min(1, max(0, ((px - ax) * dx + (py - ay) * dy) / L2))
                if (px - ax - u * dx) ** 2 + (py - ay - u * dy) ** 2 <= r * r:
                    self._mark(l, y * self.nx + x, code)

    def add(self, t):
        code = t.GetNetCode()
        x = 0.05 if t.GetNetname() in RF_NETS else 0.0  # the RF class wants 0.2, not 0.15
        if t.Type() == pcbnew.PCB_VIA_T:
            c = t.GetPosition()
            for l in self.g:
                self.seg(l, code, pcbnew.ToMM(c.x), pcbnew.ToMM(c.y), pcbnew.ToMM(c.x), pcbnew.ToMM(c.y),
                         pcbnew.ToMM(t.GetWidth(pcbnew.F_Cu)) / 2 + x)
        elif t.GetLayer() in self.g:
            a, c = t.GetStart(), t.GetEnd()
            self.seg(t.GetLayer(), code, pcbnew.ToMM(a.x), pcbnew.ToMM(a.y), pcbnew.ToMM(c.x), pcbnew.ToMM(c.y),
                     pcbnew.ToMM(t.GetWidth()) / 2 + x)

    def ok(self, l, i, code):
        v = self.g[l][i]
        return v == -1 or v == code


def _route3(tg, vg, ban, code, starts, targets, soft=False):
    """A* over F / In2 / B from any of `starts` to any of `targets` (sets of (x, y, layer index));
    via moves where a via fits on all three layers and no other drill is near (ban).
    Returns [(x, y, layer)] or None."""
    import heapq
    L = (pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.B_Cu)
    nx, ny = tg.nx, tg.ny
    tx = sum(x for x, _, _ in targets) / len(targets)
    ty = sum(y for _, y, _ in targets) / len(targets)
    D = [(1, 0, 1), (-1, 0, 1), (0, 1, 1), (0, -1, 1), (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414)]
    best, prev, q = {}, {}, []
    for s in starts:
        best[s] = 0
        heapq.heappush(q, (0, 0, s))
    n = 0
    while q and n < 800000:
        f, cost, s = heapq.heappop(q)
        if cost > best.get(s, 1e18):
            continue
        n += 1
        if s in targets:
            path = [s]
            while s in prev:
                s = prev[s]
                path.append(s)
            return [(px * RES, py * RES, L[pl]) for px, py, pl in path[::-1]]
        x, y, li = s
        i = y * nx + x
        moves = [(x + dx, y + dy, li, w) for dx, dy, w in D]
        if not ban[i] and all(vg.ok(l, i, code) for l in L):
            moves += [(x, y, lj, 14) for lj in range(3) if lj != li]
        for u, v, lj, w in moves:
            if not (0 <= u < nx and 0 <= v < ny):
                continue
            if not tg.ok(L[lj], v * nx + u, code):
                if not soft or not soft.ok(L[lj], v * nx + u, code):  # a pad or locked copper: never
                    continue
                w += 30  # through another net's copper: ripped up if this path is taken
            ns = (u, v, lj)
            nc = cost + w
            if nc < best.get(ns, 1e18):
                best[ns] = nc
                prev[ns] = s
                heapq.heappush(q, (nc + ((u - tx) ** 2 + (v - ty) ** 2) ** 0.5, nc, ns))
    return None


def _cells(item, layer_index):
    """The grid cells on an item's copper: a pad's box or a track's centre line."""
    out = set()
    if isinstance(item, pcbnew.PAD):
        bb = item.GetBoundingBox()
        x0, y0, x1, y1 = (pcbnew.ToMM(v) for v in (bb.GetLeft(), bb.GetTop(), bb.GetRight(), bb.GetBottom()))
        for y in range(int(y0 / RES) + 1, int(y1 / RES) + 1):
            for x in range(int(x0 / RES) + 1, int(x1 / RES) + 1):
                out.add((x, y, layer_index))
    else:
        a, c = item.GetStart(), item.GetEnd()
        ax, ay, cx, cy = (pcbnew.ToMM(v) for v in (a.x, a.y, c.x, c.y))
        n = max(1, int(((cx - ax) ** 2 + (cy - ay) ** 2) ** 0.5 / RES))
        for k in range(n + 1):
            out.add((int(round((ax + (cx - ax) * k / n) / RES)), int(round((ay + (cy - ay) * k / n) / RES)), layer_index))
    return out


def _ban(vias, d=0.8):
    """Cells no new via may sit on: within d of any via."""
    nx, ny = int(W / RES) + 1, int(H / RES) + 1
    g = bytearray(nx * ny)
    for vx, vy in vias:
        _ban_add(g, nx, ny, vx, vy, d)
    return g


def _ban_add(g, nx, ny, vx, vy, d=0.8):
    r = int(d / RES) + 1
    cx, cy = int(round(vx / RES)), int(round(vy / RES))
    for y in range(max(0, cy - r), min(ny, cy + r + 1)):
        for x in range(max(0, cx - r), min(nx, cx + r + 1)):
            if ((x - cx) ** 2 + (y - cy) ** 2) * RES * RES <= d * d:
                g[y * nx + x] = 1


def _lay(path, net):
    """Tracks and vias for a routed path."""
    runs = [[path[0]]]
    for p in path[1:]:
        if p[2] != runs[-1][-1][2]:
            d0, pcbgen.VIA_D = pcbgen.VIA_D, 0.5
            via(p[0], p[1], net)
            pcbgen.VIA_D = d0
            runs.append([p])
        else:
            runs[-1].append(p)
    out = []
    for r in runs:
        pts = _simplify([(x, y) for x, y, _ in r])
        if len(pts) > 1:
            track(pts, net, 0.15, r[0][2])
            out.append((pts, r[0][2]))
    return out


RIPS = [0]
RIPPED = {}
FIXED = set()


def _key(t):
    a, c = t.GetStart(), t.GetEnd()
    return (t.GetNetname(), round(pcbnew.ToMM(a.x), 2), round(pcbnew.ToMM(a.y), 2), round(pcbnew.ToMM(c.x), 2), round(pcbnew.ToMM(c.y), 2))


def finish(path, rounds=16):
    """Connect what DRC still finds unconnected (not GND: the plane does that)."""
    import json
    import re
    LI = {pcbnew.F_Cu: 0, pcbnew.In2_Cu: 1, pcbnew.B_Cu: 2}
    for _ in range(rounds):
        rpt = path.replace(".kicad_pcb", "-drc.json")
        subprocess.run([pcbgen.CLI, "pcb", "drc", "--refill-zones", "--format", "json", "-o", rpt, path],
                       capture_output=True)
        d = json.load(open(rpt))
        os.remove(rpt)
        b = pcbgen.board
        pads = {}
        for m in b.GetFootprints():
            for p in m.Pads():
                pads.setdefault(p.GetNetname(), []).append(p)
        todo = []
        for u in d.get("unconnected_items", []):
            its = u["items"]
            m = re.search(r"\[([^\]]+)\]", its[0]["description"])
            net = m.group(1) if m else ""
            if net in ("", "GND") or len(its) < 2:
                continue
            ends = []
            for it in its[:2]:
                x, y = it["pos"]["x"], it["pos"]["y"]
                if it["description"].startswith("走線") or it["description"].lower().startswith("track"):
                    tr = [t for t in b.GetTracks() if t.GetNetname() == net and t.Type() != pcbnew.PCB_VIA_T
                          and t.GetLayer() in LI]
                    t = min(tr, key=lambda t: min((pcbnew.ToMM(e.x) - x) ** 2 + (pcbnew.ToMM(e.y) - y) ** 2
                                                  for e in (t.GetStart(), t.GetEnd())))
                    ends.append(_cells(t, LI[t.GetLayer()]))
                else:
                    p = min(pads[net], key=lambda q: (pcbnew.ToMM(q.GetPosition().x) - x) ** 2 + (pcbnew.ToMM(q.GetPosition().y) - y) ** 2)
                    s = set()
                    for l, i in LI.items():
                        if p.IsOnLayer(l):
                            s |= _cells(p, i)
                    ends.append(s)
            if all(ends):
                todo.append((net, ends))
        if not todo:
            return
        tg, vg = _Owner(0.075 + 0.15), _Owner(0.25 + 0.15)
        vias = [(pcbnew.ToMM(v.GetPosition().x), pcbnew.ToMM(v.GetPosition().y)) for v in b.GetTracks() if v.Type() == pcbnew.PCB_VIA_T]
        for m in b.GetFootprints():  # the plugs' and U.FLs' holes, and no vias under the U.FLs / the filter
            for p in m.Pads():
                if p.GetDrillSize().x > 0:
                    vias.append((pcbnew.ToMM(p.GetPosition().x), pcbnew.ToMM(p.GetPosition().y)))
        ban = _ban(vias)
        for m in b.GetFootprints():
            if m.GetReference() in ("J10", "J11", "J12", "FL1"):
                r = m.GetCourtyard(pcbnew.F_CrtYd).BBox()
                for y in range(int(pcbnew.ToMM(r.GetTop()) / RES), int(pcbnew.ToMM(r.GetBottom()) / RES) + 2):
                    for x in range(int(pcbnew.ToMM(r.GetLeft()) / RES), int(pcbnew.ToMM(r.GetRight()) / RES) + 2):
                        if 0 <= x < tg.nx and 0 <= y < tg.ny:
                            ban[y * tg.nx + x] = 1
        done = 0
        ripped = False
        for net, (sa, sb) in todo:
            code = b.FindNet(net).GetNetCode()
            p = _route3(tg, vg, ban, code, sa, sb)
            if not p and not ripped and RIPS[0] < 12:
                # rip-up: through the fewest other nets, which are torn out and routed again next round
                p = _route3(tg, vg, ban, code, sa, sb, soft=_Owner(0.075 + 0.15, locked_only=True))
                hit = set()
                for x, y, l in p or []:
                    c = tg.g[l][int(round(y / RES)) * tg.nx + int(round(x / RES))]
                    if c >= 0 and c != code:
                        hit.add(c)
                bad = [c for c in hit if pcbgen.board.GetNetInfo().GetNetItem(c).GetNetname() in ("",) or
                       pcbgen.board.GetNetInfo().GetNetItem(c).GetNetname() in {n for n, _, _ in RF}]
                bad += [c for c in hit if RIPPED.get(c, 0) >= 2]
                if not p or bad or len(hit) > 3:
                    print("no rip-up for", net, ":", "no path" if not p else sorted(
                        pcbgen.board.GetNetInfo().GetNetItem(c).GetNetname() for c in hit))
                    p = None
                else:
                    gone = [t for t in b.GetTracks() if t.GetNetCode() in hit and not t.IsLocked()]
                    for t in gone:
                        b.Remove(t)
                    RIPS[0] += 1
                    for c in hit:
                        RIPPED[c] = RIPPED.get(c, 0) + 1
                    ripped = True
                    print("rip-up for", net, ":", sorted(pcbgen.board.GetNetInfo().GetNetItem(c).GetNetname() for c in hit))
            if not p:
                continue
            for pts, layer in _lay(p, net):
                for s, e in zip(pts, pts[1:]):
                    tg.seg(layer, code, s[0], s[1], e[0], e[1], 0.075)
                    vg.seg(layer, code, s[0], s[1], e[0], e[1], 0.075)
            for (x0, y0, l0), (x1, y1, l1) in zip(p, p[1:]):
                if l0 != l1:  # a via: on every layer, and no drill beside it from now on
                    for l in (pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.B_Cu):
                        tg.seg(l, code, x0, y0, x0, y0, 0.25)
                        vg.seg(l, code, x0, y0, x0, y0, 0.25)
                    _ban_add(ban, tg.nx, tg.ny, x0, y0)
            done += 1
        save(path)
        print("finish: connected", done, "of", len(todo))
        if not done and not ripped:
            return


def gnd_vias():
    """A GND via within reach of every GND pad on the top (beside the pours, a sure way down)."""
    vias = [(pcbnew.ToMM(v.GetPosition().x), pcbnew.ToMM(v.GetPosition().y)) for v in pcbgen.board.GetTracks()
            if v.Type() == pcbnew.PCB_VIA_T and v.GetNetname() == "GND"]
    for m in pcbgen.board.GetFootprints():
        for p in m.Pads():
            if p.GetNetname() != "GND" or p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
                continue
            px, py = pcbnew.ToMM(p.GetPosition().x), pcbnew.ToMM(p.GetPosition().y)
            if any((vx - px) ** 2 + (vy - py) ** 2 < 1.3 ** 2 for vx, vy in vias):
                continue
            v = _escape(px, py, "GND")
            if v:
                track([(px, py), v], "GND", 0.25)
                via(*v, "GND")
                vias.append(v)


def unconnected(path):
    """DRC's unconnected items: [(net, x, y)] of the first item of each."""
    import json
    import re
    rpt = path.replace(".kicad_pcb", "-drc.json")
    subprocess.run([pcbgen.CLI, "pcb", "drc", "--refill-zones", "--format", "json", "-o", rpt, path], capture_output=True)
    d = json.load(open(rpt))
    os.remove(rpt)
    out = []
    for u in d.get("unconnected_items", []):
        for it in u["items"]:
            m = re.search(r"\[([^\]]+)\]", it["description"])
            out.append((m.group(1) if m else "", it["pos"]["x"], it["pos"]["y"]))
    return out


if __name__ == "__main__":
    if os.environ.get("DUMP"):
        dump()
        sys.exit()
    outline(0, 0, W, H, CORNER)
    if os.environ.get("PLACE"):
        save(OUT)
        sys.exit()
    rules()
    pcbgen.project(OUT, CLASSES)
    prerouted()
    dog = dogbones()
    print("dogbones:", len(dog), "fanout:", fanout(done=dog), "pins")
    if os.environ.get("FANOUT"):
        save(OUT)
        sys.exit()
    FIXED.update(_key(t) for t in pcbgen.board.GetTracks())
    edge_keepout()
    zone("GND", pcbnew.In1_Cu, 0.3, 0.3, W - 0.3, H - 0.3, chamfer=1.2)  # the ground plane
    if FR:
        freeroute(100)
        freeroute(100)  # again, from what the first pass left: it finishes what it can
    elif os.path.exists(SES):
        pcbnew.ImportSpecctraSES(pcbgen.board, SES)
    redraw_rf()
    for t in pcbgen.board.GetTracks():  # only the RF lines and the fanout stay fixed for the finisher
        t.SetLocked(_key(t) in FIXED)
    save(OUT)
    finish(OUT)
    gnd_vias()
    stitch_grid()
    pours()
    for _ in range(2):
        if not stitch_islands():
            break
    save(OUT)
    for _ in range(3):  # stitch GND pads the pours left alone to the plane
        gnd = [(x, y) for n, x, y in unconnected(OUT) if n == "GND"]
        if not gnd or not stitch_gnd(gnd):
            break
        save(OUT)
    prune(OUT)
    for line in drc(OUT):
        print(line)
    if os.environ.get("FAB"):
        fab(OUT)
