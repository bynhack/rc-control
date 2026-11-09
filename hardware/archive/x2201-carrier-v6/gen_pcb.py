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

OUT = os.path.join(HERE, "x2201-carrier-v6.kicad_pcb")
layers(4)

W, H = 46.0, 36.0
HOLES = [(2.5, 2.5), (25.5, 2.5), (2.5, H - 2.5), (W - 2.5, H - 2.5)]  # M2, unplated
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


def s3(io):
    """The brain's ESP32-S3FH4R2 (QFN56, flash + PSRAM in the package: pins 28-35 are theirs)."""
    nets = {"1": "B_RF", "2": "B_VPA", "3": "B_VPA", "4": "EN", "20": "3V3", "29": "B_VSPI", "46": "3V3",
            "53": "B_XN", "54": "B_XP", "55": "3V3", "56": "3V3", "57": "GND"}
    nets.update(io)
    return "Package_DFN_QFN", "QFN-56-1EP_7x7mm_P0.4mm_EP4x4mm", nets


ANT = ("RF_Antenna", "Johanson_2450AT18x100")
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
    # its WiFi: a chip antenna in the board's top right corner, behind Johanson's pi (tune on the board)
    ("C53", "1.0pF", two(C, "0402", "RXC_ANT", "GND")), ("L12", "3.9nH", two(L, "0402", "RXC_ANT", "RXC_FEED")),
    ("AE2", "2450AT18A100E", (ANT[0], ANT[1], {"1": "RXC_FEED"})),
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
    # -- U1: the brain, ESP32-S3FH4R2 ---------------------------------------------------------------
    ("U1", "ESP32-S3FH4R2", s3({
        "6": "VBAT_ADC", "7": "NTC", "9": "S1", "10": "S2", "11": "SDA", "12": "SCL", "13": "IMU_INT",
        "14": "LED", "23": "MSP_TX", "24": "MSP_RX", "25": "B_DM", "26": "B_DP", "38": "LIGHT_F", "39": "LIGHT_R",
        "40": "FAN", "41": "IR", "43": "CRSF_TX", "44": "CRSF_RX", "45": "RXC_EN", "47": "RXC_BOOT"})),
    ("L8", "2nH", two(L, "0402", "3V3", "B_VPA")), ("C42", "1uF", two(C, "0402", "B_VPA", "GND")),
    ("C43", "10uF", two(C, "0603", "3V3", "GND")),
    ("C44", "100nF", two(C, "0402", "3V3", "GND")), ("C56", "100nF", two(C, "0402", "3V3", "GND")),
    ("C45", "1uF", two(C, "0402", "3V3", "GND")), ("C46", "10nF", two(C, "0402", "3V3", "GND")),
    ("C49", "1uF", two(C, "0402", "B_VSPI", "GND")), ("C55", "100nF", two(C, "0402", "B_VSPI", "GND")),
    ("Y3", "40MHz", ("Crystal", XTAL, {"1": "B_XI", "2": "GND", "3": "B_XN", "4": "GND"})),
    ("L9", "24nH", two(L, "0402", "B_XI", "B_XP")),
    ("C50", "10pF", two(C, "0402", "B_XN", "GND")), ("C51", "10pF", two(C, "0402", "B_XI", "GND")),
    # its RF: Espressif's CLC at the pin, then Johanson's pi to the chip antenna on the top edge
    ("C40", "1.2pF", two(C, "0402", "B_RF", "GND")), ("L7", "3nH", two(L, "0402", "B_RF", "B_ANT")),
    ("C41", "1.2pF", two(C, "0402", "B_ANT", "GND")), ("C52", "1.0pF", two(C, "0402", "B_ANT", "GND")),
    ("L10", "3.9nH", two(L, "0402", "B_ANT", "B_FEED")),
    ("AE1", "2450AT18A100E", (ANT[0], ANT[1], {"1": "B_FEED"})),
    ("R11", "10k", two(R, "0402", "3V3", "EN")), ("C8", "1uF", two(C, "0402", "EN", "GND")),
    ("R18", "1k", two(R, "0402", "3V3", "LEDR")),
    ("D4", "green", ("LED_SMD", "LED_0603_1608Metric", {"1": "LED", "2": "LEDR"})),
    ("J9", "USB-C", ("Connector_USB", "USB_C_Receptacle_HRO_TYPE-C-31-M-12", {
        "A1": "GND", "B12": "GND", "B1": "GND", "A12": "GND", "B4": "VBUS", "A9": "VBUS", "A4": "VBUS", "B9": "VBUS",
        "A5": "CC1", "B5": "CC2", "A6": "USB_DP", "B6": "USB_DP", "A7": "USB_DM", "B7": "USB_DM", "SH": "GND"})),
    ("R40", "22", two(R, "0402", "B_DM", "USB_DM")), ("R41", "22", two(R, "0402", "B_DP", "USB_DP")),
    ("R12", "5.1k", two(R, "0402", "CC1", "GND")), ("R13", "5.1k", two(R, "0402", "CC2", "GND")),
    ("D2", "B5819WS", ("Diode_SMD", "D_SOD-323", {"1": "VIN", "2": "VBUS"})),
    # -- the IMU (I2C at 0x6A: SA0 low, CS high; its aux bus unused, tied low) --------------------------
    ("U9", "LSM6DS3TR-C", ("Package_LGA", "LGA-14_3x2.5mm_P0.5mm_LayoutBorder3x4y", {
        "1": "GND", "2": "GND", "3": "GND", "4": "IMU_INT", "5": "3V3", "6": "GND", "7": "GND", "8": "3V3",
        "12": "3V3", "13": "SCL", "14": "SDA"})),
    ("C57", "100nF", two(C, "0402", "3V3", "GND")), ("C58", "100nF", two(C, "0402", "3V3", "GND")),
    ("R42", "4.7k", two(R, "0402", "3V3", "SDA")), ("R43", "4.7k", two(R, "0402", "3V3", "SCL")),
    # -- the fan (PWM, low side, a diode across it), two lights (low side), the VTX's NTC ------------------
    ("Q5", "AO3400", ("Package_TO_SOT_SMD", SOT, {"1": "FANG", "2": "GND", "3": "FANK"})),
    ("R44", "100", two(R, "0402", "FAN", "FANG")), ("R45", "100k", two(R, "0402", "FANG", "GND")),
    ("D5", "B5819WS", ("Diode_SMD", "D_SOD-323", {"1": "5V", "2": "FANK"})),
    ("Q6", "AO3400", ("Package_TO_SOT_SMD", SOT, {"1": "LFG", "2": "GND", "3": "LFK"})),
    ("R46", "100", two(R, "0402", "LIGHT_F", "LFG")), ("R47", "100k", two(R, "0402", "LFG", "GND")),
    ("Q7", "AO3400", ("Package_TO_SOT_SMD", SOT, {"1": "LRG", "2": "GND", "3": "LRK"})),
    ("R48", "100", two(R, "0402", "LIGHT_R", "LRG")), ("R49", "100k", two(R, "0402", "LRG", "GND")),
    ("R52", "10k", two(R, "0402", "3V3", "NTC")), ("C59", "100nF", two(C, "0402", "NTC", "GND")),
    # -- plugs (v3's) --------------------------------------------------------------------------------
    ("J6", "ZH1.5 2P (battery)", (JST, "JST_ZH_B2B-ZR-SM4-TF_1x02-1MP_P1.50mm_Vertical",
                                  {"1": "VBAT", "2": "GND", "MP": "GND"})),
    ("J3", "SH1.0 4P (VTX)", (JST, "JST_SH_BM04B-SRSS-TB_1x04-1MP_P1.00mm_Vertical",
                              {"1": "VTX", "2": "GND", "3": "VTX_RX", "4": "VTX_TX", "MP": "GND"})),
    ("J4", "SH1.0 4P (fan + NTC)", (JST, "JST_SH_BM04B-SRSS-TB_1x04-1MP_P1.00mm_Vertical",
                                    {"1": "5V", "2": "FANK", "3": "NTC", "4": "GND", "MP": "GND"})),
    ("J7", "SH1.0 4P (lights)", (JST, "JST_SH_BM04B-SRSS-TB_1x04-1MP_P1.00mm_Vertical",
                                {"1": "5V", "2": "LFK", "3": "LRK", "4": "GND", "MP": "GND"})),
    ("J5", "ZH1.5 2P (IR LED)", (JST, "JST_ZH_B2B-ZR-SM4-TF_1x02-1MP_P1.50mm_Vertical",
                                 {"1": "LEDA", "2": "LEDK", "MP": "GND"})),
]

# ==== where they go: ref -> (x, y, rotation, side); a plug's rotation as the edge it faces ===========
F, B = "F", "B"
POS = {
    # the receiver, top right: v5's block; its WiFi now a chip antenna in the corner
    "U5": (35.40, 8.50, 180, F), "C18": (34.00, 13.60, 0, F), "C19": (32.00, 13.40, 0, F), "C29": (39.08, 10.97, 270, F),
    "L4": (40.95, 8.20, 90, F), "C30": (41.97, 7.75, 270, F), "C53": (42.97, 7.75, 270, F), "L12": (44.00, 6.40, 90, F),
    "AE2": (44.00, 2.60, 90, F), "C20": (31.20, 6.50, 90, F),
    "C21": (33.00, 3.30, 0, F), "C25": (31.40, 2.20, 0, F), "R28": (31.40, 1.10, 0, F), "Y1": (30.40, 9.60, 90, F),
    "L3": (29.70, 12.00, 0, F), "C27": (28.20, 8.90, 90, F), "C28": (28.20, 10.90, 90, F), "R26": (26.60, 6.30, 0, F),
    "C26": (26.60, 7.40, 0, F), "R27": (26.60, 8.50, 0, B), "R29": (26.60, 9.60, 0, F), "R30": (26.60, 10.70, 0, F),
    "U8": (23.40, 7.90, 0, F), "C16": (23.80, 10.50, 0, F), "C17": (24.75, 12.40, 0, F), "U6": (30.90, 17.30, 270, F),
    "Y2": (25.60, 16.50, 0, F), "L5": (30.90, 22.10, 0, F), "C31": (33.60, 21.10, 90, F), "C32": (28.00, 20.90, 90, F),
    "C33": (27.00, 20.90, 90, F), "C34": (27.40, 18.80, 270, F), "C35": (34.70, 21.10, 90, F), "FL1": (34.39, 17.10, 0, F),
    "U7": (37.40, 15.70, 0, F), "R31": (35.90, 19.70, 90, F), "R32": (37.00, 19.70, 90, F), "C36": (38.10, 19.70, 90, F),
    "C37": (39.20, 19.70, 90, F), "C38": (40.15, 17.45, 270, F), "L6": (40.15, 15.50, 90, F), "C39": (40.15, 13.50, 90, F),
    "J10": (43.30, 14.60, 0, F),
    "L2": (37.60, 2.60, 0, F), "C22": (37.60, 1.50, 0, F),
    # the brain: RF up the top edge to its chip antenna; VPA's filter left of the RF line; the crystal in a row
    "U1": (13.00, 16.00, 270, F), "AE1": (16.20, 2.60, 90, F),
    "L10": (16.20, 6.80, 90, F), "C52": (17.70, 7.80, 0, F), "C41": (17.70, 8.80, 0, F),
    "L7": (16.20, 9.90, 90, F), "C40": (17.70, 11.20, 0, F),
    "L8": (15.00, 10.50, 270, F), "C42": (13.90, 10.50, 90, F), "C43": (12.15, 8.60, 90, F),
    "L9": (18.80, 14.00, 180, F), "Y3": (21.20, 14.70, 270, F), "C50": (21.75, 17.25, 270, F), "C51": (18.80, 12.75, 180, F),
    "C45": (20.80, 12.45, 0, F), "C46": (20.80, 11.45, 0, F), "C44": (18.60, 17.40, 0, F), "C56": (7.90, 15.80, 0, F),
    "C49": (10.20, 21.40, 90, F), "C55": (11.20, 21.40, 90, F),
    "R11": (12.60, 7.30, 90, B), "C8": (13.70, 7.30, 90, B),
    "D4": (12.60, 23.60, 0, F), "R18": (15.40, 23.60, 0, F),
    "R40": (8.10, 21.60, 90, F), "R41": (9.15, 21.60, 90, F),
    # the IMU, top left
    "U9": (9.60, 5.40, 0, B), "C57": (9.35, 3.30, 0, B), "C58": (10.60, 7.60, 0, B),
    "R42": (8.40, 2.10, 0, B), "R43": (10.60, 2.10, 0, B),
    # plugs: left edge (ESC, VTX, battery), bottom edge (fan, IR, lights, NTC), USB-C on the right edge
    "J1": (4.00, 9.60, 90, F), "J3": (3.20, 19.20, 90, F), "J6": (4.00, 28.00, 90, F),
    "J5": (21.95, H - 3.99, 180, F), "J4": (30.15, H - 3.2, 180, F), "J7": (38.15, H - 3.2, 180, F), "J9": (12.5, H - 2.8, 0, F),
    "R16": (6.20, 10.20, 90, B), "R17": (7.30, 10.20, 90, B),
    "R19": (6.20, 16.80, 90, B), "R20": (7.30, 16.80, 90, B),
    "U3": (33.00, 24.80, 0, F), "C9": (35.80, 23.60, 90, F), "C10": (36.30, 26.80, 90, F),
    "D2": (27.60, 26.00, 0, F), "D3": (27.40, 23.60, 0, F), "C3": (8.30, 25.40, 90, F),
    # the bottom: the drivers, behind their plugs, clear of the QFNs' fanout
    "Q2": (7.00, 23.50, 0, B), "R2": (9.65, 22.90, 90, B), "R3": (10.75, 22.90, 90, B),
    "Q3": (7.00, 27.00, 0, B), "R4": (9.65, 26.60, 90, B), "R5": (10.75, 26.60, 90, B),
    "R14": (12.20, 22.90, 90, B), "R15": (13.30, 22.90, 90, B), "C11": (14.40, 22.90, 90, B),
    "Q5": (28.20, 26.80, 0, B), "R44": (30.80, 26.30, 90, B), "R45": (31.90, 26.30, 90, B), "D5": (28.20, 29.60, 0, B),
    "Q4": (21.50, 26.80, 0, B), "R6": (21.50, 29.80, 0, B), "R7": (24.10, 26.50, 90, B), "R8": (25.20, 26.50, 90, B),
    "Q6": (36.70, 26.60, 0, B), "R46": (39.25, 26.30, 90, B), "R47": (40.35, 26.30, 90, B),
    "Q7": (36.70, 30.40, 0, B), "R48": (39.25, 30.10, 90, B), "R49": (40.35, 30.10, 90, B),
    "R52": (33.10, 26.30, 90, B), "C59": (34.20, 26.30, 90, B),
    "R12": (18.40, 27.50, 90, F), "R13": (19.50, 27.50, 90, F),
}

M = {}
for ref, value, (lib, fp, pads) in PARTS:
    x, y, rot, side = POS[ref]
    if isinstance(rot, str):
        rot = FACE[side][rot]
    M[ref] = place(lib, fp, ref, value, x, y, rot, pads, side)


def npth(ref, x, y, d=2.2):
    """An unplated M2 hole (no copper near the antennas' screws)."""
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
# the chip antennas' clearance (no copper on any layer), with a channel for each feed line
KEEP = [(12.95, 0.0, 15.90, 5.8), (16.50, 0.0, 19.45, 5.8), (15.90, 0.0, 16.50, 3.4),   # AE1, top edge
        (39.50, 0.0, 43.70, 5.6), (44.30, 0.0, 46.00, 5.6), (43.70, 0.0, 44.30, 3.4)]   # AE2, top right
for r in KEEP:
    keepout(*r)
for g in list(M["J9"].GraphicalItems()):  # the USB-C's silk over the board's edge
    if g.GetLayer() == pcbnew.F_SilkS and max(g.GetStart().y, g.GetEnd().y) > mm(H - 1.2):
        M["J9"].Remove(g)

# ==== rules: JLCPCB 4-layer (1.6 mm, 1 oz outer); net classes by current ===========================
CLASSES = [  # name, track, clearance, nets
    ("PWR", 0.5, 0.2, ["VBAT", "VTX"]),  # the VTX's ~1 A
    ("MID", 0.35, 0.15, ["5V", "VIN", "3V3", "3V3R", "VBUS", "LEDA", "LEDK", "SX_DCC", "SX_SW"]),
    ("RF", 0.3, 0.2, ["RXC_RF", "RXC_ANT", "RXC_FEED", "SX_RF", "PA_IO", "PA_ANT", "ELRS_ANT", "B_RF", "B_ANT",
                      "B_FEED"]),
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
    # the receiver's WiFi: L4 - C30 / C53 (shunts, on the line) - L12 - the antenna
    ("RXC_ANT", "F", [(40.95, 7.715), (40.95, 7.30), (44.00, 7.30), (44.00, 6.885)]),
    ("RXC_FEED", "F", [(44.00, 5.915), (44.00, 4.05)]),
    # the brain's: pin 1 - C40 / L7 / C41 (Espressif's CLC) - C52 / L10 (Johanson's) - the antenna
    ("B_RF", "F", [(15.60, 12.55), (15.60, 11.90)], 0.2),  # inside the pin's width, clear of VDD3P3
    ("B_RF", "F", [(15.60, 11.90), (16.20, 11.30), (16.20, 10.385)]),
    ("B_RF", "F", [(16.20, 11.20), (17.22, 11.20)]),
    ("B_ANT", "F", [(16.20, 9.415), (16.20, 7.285)]),
    ("B_ANT", "F", [(16.20, 8.80), (17.22, 8.80)]),
    ("B_ANT", "F", [(16.20, 7.80), (17.22, 7.80)]),
    ("B_FEED", "F", [(16.20, 6.315), (16.20, 4.05)]),
]
RF_NETS = {r[0] for r in RF}
WIDE = RF_NETS | {"VBAT", "VTX"}  # 0.2 clearance
# the SX1280's DC-DC switch node: the shortest line, drawn by hand (0.3 mm, fixed)
SHORT = [("SX_SW", [(30.15, 19.24), (30.15, 21.75)], 0.3),
         ("3V3R", [(28.96, 18.05), (27.65, 18.05), (27.4, 18.3)], 0.25),  # U6 pin 11 to C34
         ("GND", [(29.85, 10.30), (30.95, 8.90)], 0.2),  # the receiver crystal's two GND pads, under it
         ("GND", [(24.90, 15.95), (26.30, 17.05)], 0.2),  # and the SX1280's
         ("SX_DCC", [(31.65, 15.36), (31.65, 14.25)], 0.25),  # U6 pin 2 up to its via, before anything else
         ("VBAT", [(4.70, 28.75), (7.60, 28.75), (8.30, 28.05), (8.30, 26.88)], 0.5),  # J6 to C3
         # the brain's crystal in a row: pin 54 - L9 - Y3 (XI), XN under it to Y3 and C50
         ("B_XP", [(16.45, 14.20), (18.10, 14.20), (18.315, 14.00)], 0.2),
         ("B_XI", [(19.285, 14.00), (20.65, 14.00)], 0.2),
         ("B_XI", [(19.28, 12.75), (19.285, 14.00)], 0.2),
         ("B_XN", [(16.45, 14.60), (18.80, 14.60), (18.90, 14.70), (21.25, 14.70), (21.75, 15.20), (21.75, 16.765)], 0.15),
         # VDD3P3 (pins 2, 3) straight up to L8 / C42; CHIP_PU (pin 4) to a via under C42
         ("B_VPA", [(13.90, 10.985), (15.00, 10.985), (15.00, 12.40)], 0.25),
         ("B_VPA", [(14.80, 12.55), (14.80, 12.40), (15.20, 12.40), (15.20, 12.55)], 0.2),
         ("EN", [(14.40, 12.55), (14.40, 12.00), (14.20, 11.70)], 0.15)]
SVIAS = [("SX_DCC", 31.65, 14.25), ("EN", 14.20, 11.70), ("GND", 7.40, 5.65), ("GND", 10.65, 3.40)]
# the IMU's strap pins (SA0, its unused aux bus: all GND), joined on the bottom and down to a via
# after routing: U9's CS (pin 12, 3V3) straight down to C58's 3V3 pad
PATCH = []
SHORT_B = [("GND", [(8.30, 5.15), (8.30, 6.15)], 0.2), ("GND", [(8.30, 5.65), (7.40, 5.65)], 0.25),
           # VDDIO (pin 5) / GND (pin 6) straight up to C57, its GND to a via
           ("3V3", [(9.10, 4.487), (9.10, 3.60), (8.87, 3.30)], 0.2),
           ("GND", [(9.60, 4.487), (9.60, 3.60), (9.83, 3.30), (10.65, 3.40)], 0.2)]
SES = os.path.join(HERE, "x2201-carrier-v6.ses")
FR = os.environ.get("FREEROUTING", "")  # path to freerouting-1.9.0.jar, to route again


def prerouted():
    for name, side, pts, *w in RF:
        track(pts, name, w[0] if w else 0.3, pcbnew.F_Cu if side == "F" else pcbnew.B_Cu)
    for name, pts, w in SHORT:
        track(pts, name, w)
    for name, pts, w in SHORT_B:
        track(pts, name, w, pcbnew.B_Cu)
    for name, x, y in SVIAS:
        d0, pcbgen.VIA_D = pcbgen.VIA_D, 0.5
        via(x, y, name)
        pcbgen.VIA_D = d0
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
               "RXC_XN", "RXC_XP", "B_XN", "B_XP", "SX_XA", "SX_XB", "VIN", "EN", ""}


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
    rf = {r[0] for r in RF}
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
    rf = {r[0] for r in RF}
    b = pcbgen.board
    tg, vg = _Owner(0.075 + 0.15), _Owner(0.25 + 0.15)
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
        ep = max(m.Pads(), key=lambda q: q.GetSize().x).GetNumber()
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
            track(pts, net, 0.15)
            vx, vy = pts[-1]
            d0, pcbgen.VIA_D = pcbgen.VIA_D, 0.5
            via(vx, vy, net)
            pcbgen.VIA_D = d0
            for s, e in zip(pts, pts[1:]):
                tg.seg(pcbnew.F_Cu, code, s[0], s[1], e[0], e[1], 0.075)
                vg.seg(pcbnew.F_Cu, code, s[0], s[1], e[0], e[1], 0.075)
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
    import_ses()


def import_ses():
    """Read Freerouting's wiring back. Its placement section goes first: KiCad stops reading at
    the screw holes (footprints with no library), and drops every net after that point."""
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


def redraw_rf():
    """Freerouting may touch the RF nets: put back exactly the hand-drawn lines."""
    rf = {r[0] for r in RF}
    for t in list(pcbgen.board.GetTracks()):
        if t.GetNetname() in rf:
            pcbgen.board.Remove(t)
    for name, side, pts, *w in RF:
        track(pts, name, w[0] if w else 0.3, pcbnew.F_Cu if side == "F" else pcbnew.B_Cu)


def _clear(shape, net, layers, cl=0.2):
    r = shape.BBox()
    x0, y0, x1, y1 = (pcbnew.ToMM(v) for v in (r.GetLeft(), r.GetTop(), r.GetRight(), r.GetBottom()))
    for k in KEEP:  # nothing in the antennas' clearance
        if x1 > k[0] - cl and x0 < k[2] + cl and y1 > k[1] - cl and y0 < k[3] + cl:
            return False
    for hx, hy in HOLES:  # the screws' holes: 0.25 from copper
        dx, dy = max(x0 - hx, 0, hx - x1), max(y0 - hy, 0, hy - y1)
        if dx * dx + dy * dy < (1.1 + 0.3) ** 2:
            return False
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


def _junction(v):
    """The track ends of the via's net that land on its copper but not at its centre."""
    c, r = v.GetPosition(), v.GetWidth(pcbnew.F_Cu) / 2
    out = []
    for t in pcbgen.board.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T or t.GetNetname() != v.GetNetname():
            continue
        for e in (t.GetStart(), t.GetEnd()):
            d = ((e.x - c.x) ** 2 + (e.y - c.y) ** 2) ** 0.5
            if 1000 < d <= r + t.GetWidth() / 2:
                out.append((e, t.GetLayer()))
    return out


def prune(path):
    """Take out what DRC finds dangling (Freerouting's stubs, fanout vias the routes didn't use)."""
    import json
    kept = []  # first: a via on top of another of its net (a link ending on a via) goes
    for v in [t for t in pcbgen.board.GetTracks() if t.Type() == pcbnew.PCB_VIA_T]:
        x, y = pcbnew.ToMM(v.GetPosition().x), pcbnew.ToMM(v.GetPosition().y)
        if any(n == v.GetNetname() and (x - a) ** 2 + (y - c) ** 2 < 0.56 ** 2 for n, a, c in kept):
            pcbgen.board.Remove(v)
        else:
            kept.append((v.GetNetname(), x, y))
    pcbnew.ZONE_FILLER(pcbgen.board).Fill(pcbgen.board.Zones())
    save(path)
    for _ in range(6):
        rpt = path.replace(".kicad_pcb", "-drc.json")
        subprocess.run([pcbgen.CLI, "pcb", "drc", "--format", "json", "-o", rpt, path], capture_output=True)
        d = json.load(open(rpt))
        os.remove(rpt)
        ids = {v["items"][0]["uuid"] for v in d["violations"] if v["type"] in ("via_dangling", "track_dangling")}
        if not ids:
            return
        gone = 0
        for t in list(pcbgen.board.GetTracks()):  # by its id: never a neighbour that merely shares a point
            if t.m_Uuid.AsString() in ids and t.Type() == pcbnew.PCB_VIA_T and _junction(t):
                # a track ends on its copper, off its centre: the via joins them on one layer, so a
                # short track from its centre to that end does the same job without the drill
                for e, layer in _junction(t):
                    track([(pcbnew.ToMM(t.GetPosition().x), pcbnew.ToMM(t.GetPosition().y)),
                           (pcbnew.ToMM(e.x), pcbnew.ToMM(e.y))], t.GetNetname(), 0.15, layer)
                pcbgen.board.Remove(t)
                gone += 1
                continue
            if t.m_Uuid.AsString() in ids and t.GetNetname() not in RF_NETS:
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
                if _clear(via_s, "GND", cu) and _clear(seg, "GND", [_side(p)]) and _via_room(vx, vy, 0.56):
                    ok = (vx, vy)
                    break
            if ok:
                track([(px, py), ok], "GND", 0.25, _side(p))
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
    tg, vg = _Owner(0.075 + 0.18), _Owner(0.25 + 0.18)
    vias = [(pcbnew.ToMM(v.GetPosition().x), pcbnew.ToMM(v.GetPosition().y)) for v in b.GetTracks() if v.Type() == pcbnew.PCB_VIA_T]
    vias += [(pcbnew.ToMM(q.GetPosition().x), pcbnew.ToMM(q.GetPosition().y)) for m in b.GetFootprints() for q in m.Pads()
             if q.GetDrillSize().x > 0]
    ban = _ban(vias)
    code = b.FindNet("GND").GetNetCode()
    pads = [q for m in b.GetFootprints() for q in m.Pads() if q.GetNetname() == "GND"]
    done = 0
    for x, y in points:
        p = min(pads, key=lambda q: (pcbnew.ToMM(q.GetPosition().x) - x) ** 2 + (pcbnew.ToMM(q.GetPosition().y) - y) ** 2)
        starts = _cells(p, 2 if _side(p) == pcbnew.B_Cu else 0)
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


def _side(p):
    """The copper layer an SMD pad is on (the bottom's parts: B.Cu)."""
    return pcbnew.B_Cu if p.IsOnLayer(pcbnew.B_Cu) and not p.IsOnLayer(pcbnew.F_Cu) else pcbnew.F_Cu


def _escape(px, py, net, away=None, layer=pcbnew.F_Cu):
    """A via spot near (px, py) for `net`, joined to it on `layer`: (vx, vy) or None."""
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
                    _clear(pcbnew.SHAPE_SEGMENT(pcbnew.VECTOR2I(mm(px), mm(py)), c, mm(0.25)), net, [layer], 0.22) and \
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
            for r in KEEP:  # grown like any copper: a via's centre stays its radius out
                g = self.grow
                self.box(l, -2, r[0] - g, r[1] - g, r[2] + g, r[3] + g)
            for hx, hy in HOLES:
                self.box(l, -2, hx - 1.35, hy - 1.35, hx + 1.35, hy + 1.35)
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
                x = 0.05 if p.GetNetname() in WIDE else 0.0
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
        x = 0.05 if t.GetNetname() in WIDE else 0.0  # the RF / PWR classes want 0.2, not 0.15
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


SNAP = []  # every track / via drawn before Freerouting
LINKS = []  # bottom pads joined to their net's nearest fanout via, before routing


def links():
    """An L of track from each LINKS pad to the nearest via of its net, on the pad's side."""
    b = pcbgen.board
    for ref, num in LINKS:
        p = [q for q in b.FindFootprintByReference(ref).Pads() if q.GetNumber() == num][0]
        net, layer = p.GetNetname(), _side(p)
        px, py = pcbnew.ToMM(p.GetPosition().x), pcbnew.ToMM(p.GetPosition().y)
        vs = sorted(((pcbnew.ToMM(v.GetPosition().x), pcbnew.ToMM(v.GetPosition().y)) for v in b.GetTracks()
                     if v.Type() == pcbnew.PCB_VIA_T and v.GetNetname() == net),
                    key=lambda v: (v[0] - px) ** 2 + (v[1] - py) ** 2)
        done = False
        for vx, vy in vs[:3]:
            for pts in ([(vx, vy), (vx, py), (px, py)], [(vx, vy), (px, vy), (px, py)]):
                if all(_clear(pcbnew.SHAPE_SEGMENT(pcbnew.VECTOR2I(mm(a[0]), mm(a[1])), pcbnew.VECTOR2I(mm(c[0]), mm(c[1])),
                                                   mm(0.2)), net, [layer], 0.15) for a, c in zip(pts, pts[1:])):
                    track(pts, net, 0.2, layer)
                    done = True
                    break
            if done:
                break
        print("link", ref, num, "ok" if done else "FAILED")


def _fits(path, net):
    """A routed path (cells) as tracks and vias, checked against the board with KiCad's shapes."""
    cl = 0.2 if net in WIDE else 0.15
    for (x0, y0, l0), (x1, y1, l1) in zip(path, path[1:]):
        a, c = pcbnew.VECTOR2I(mm(x0), mm(y0)), pcbnew.VECTOR2I(mm(x1), mm(y1))
        if l0 != l1:
            if not _clear(pcbnew.SHAPE_CIRCLE(a, mm(0.25)), net, [pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.B_Cu], cl):
                return False
        elif not _clear(pcbnew.SHAPE_SEGMENT(a, c, mm(0.15)), net, [l0], cl):
            if os.environ.get("FITDBG"):
                print("fits: segment", (x0, y0), (x1, y1), pcbgen.board.GetLayerName(l0))
            return False
    return True


def restore_fixed():
    """Put back what Freerouting dropped of the hand-drawn lines and the fanout (it may treat a
    stub inside a pad as redundant, and then its own wire stops short of the fanout's via)."""
    b = pcbgen.board
    have = {_key(t) for t in b.GetTracks()}
    n = 0
    for is_via, net, layer, a, c, w, key in SNAP:
        if key in have:
            continue
        if is_via:
            v = pcbnew.PCB_VIA(b)
            v.SetPosition(a)
            v.SetDrill(mm(0.3))
            v.SetWidth(w)
            v.SetNet(b.FindNet(net))
            b.Add(v)
        else:
            t = pcbnew.PCB_TRACK(b)
            t.SetStart(a)
            t.SetEnd(c)
            t.SetWidth(w)
            t.SetLayer(layer)
            t.SetNet(b.FindNet(net))
            b.Add(t)
        n += 1
    print("restored", n, "fixed items")


RIPS = [0]
MAX_RIPS = int(os.environ.get("RIPS", "12"))
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
            if net in ("", "GND", "VBAT", "VTX") or len(its) < 2:  # power: Freerouting's, at its width
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
            if not p and not ripped and RIPS[0] < MAX_RIPS:
                # rip-up: through the fewest other nets, which are torn out and routed again next round
                p = _route3(tg, vg, ban, code, sa, sb, soft=_Owner(0.075 + 0.15, locked_only=True))
                hit = set()
                for x, y, l in p or []:
                    c = tg.g[l][int(round(y / RES)) * tg.nx + int(round(x / RES))]
                    if c >= 0 and c != code:
                        hit.add(c)
                bad = [c for c in hit if pcbgen.board.GetNetInfo().GetNetItem(c).GetNetname() in ("",) or
                       pcbgen.board.GetNetInfo().GetNetItem(c).GetNetname() in {r[0] for r in RF}]
                bad += [c for c in hit if RIPPED.get(c, 0) >= 2]
                keep = (FANOUT_SKIP | WIDE | set(CLASSES[1][3])) - {"GND"}  # power, crystals, RF: never torn out
                # (GND may go: the stitching that follows ties every GND pad down again)
                bad += [c for c in hit if pcbgen.board.GetNetInfo().GetNetItem(c).GetNetname() in keep]
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
            if not _fits(p, net):  # the grid rounds: KiCad's own geometry has the last word
                print("finish: rounding clash for", net)
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
            v = _escape(px, py, "GND", layer=_side(p))
            if v:
                track([(px, py), v], "GND", 0.25, _side(p))
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
    dog = dogbones(("U5", "U6"))
    print("dogbones:", len(dog), "fanout:", fanout(done=dog), "pins")
    links()
    if os.environ.get("FANOUT"):
        save(OUT)
        sys.exit()
    gnd_vias()  # a GND via by every GND pad while the board is still empty: Freerouting goes round them
    FIXED.update(_key(t) for t in pcbgen.board.GetTracks())
    SNAP[:] = [(t.Type() == pcbnew.PCB_VIA_T, t.GetNetname(), t.GetLayer(), t.GetStart(), t.GetEnd(), t.GetWidth(pcbnew.F_Cu)
                if t.Type() == pcbnew.PCB_VIA_T else t.GetWidth(), _key(t)) for t in pcbgen.board.GetTracks()]
    edge_keepout()
    zone("GND", pcbnew.In1_Cu, 0.3, 0.3, W - 0.3, H - 0.3, chamfer=1.2)  # the ground plane
    if FR:
        freeroute(100)
        freeroute(100)  # again, from what the first pass left: it finishes what it can
    elif os.path.exists(SES):
        import_ses()
    redraw_rf()
    restore_fixed()
    for t in pcbgen.board.GetTracks():  # only the RF lines and the fanout stay fixed for the finisher
        t.SetLocked(_key(t) in FIXED)
    save(OUT)
    finish(OUT)
    for name, pts, w, layer in PATCH:  # what the routers leave, drawn before the ground goes in
        track(pts, name, w, layer)
    prune(OUT)
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
    for _ in range(2):  # what the pruning cut off: pour pieces to stitch again
        if not stitch_islands():
            break
        save(OUT)
        prune(OUT)
    for line in drc(OUT):
        print(line)
    if os.environ.get("FAB"):
        fab(OUT, fitted="QCRDJULYFA")
