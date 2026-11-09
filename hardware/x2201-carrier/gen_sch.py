#!/usr/bin/env python3
"""Generate the X2201 carrier board schematic (x2201-carrier.kicad_sch).

The board is the FPV mount's base (gen_pcb.py has the layout): the ZERO-Z
ESC's receiver cable, the EP2 receiver with its 5V delayed (it hangs if it
boots while the ESC holds its TX pad low), and the VTX's battery power
switched on by the ESC's BEC, so the ESC's switch turns everything on, and
the lap-timing transponder (firmware/transponder).
Each part's pins get net labels; the net names match gen_pcb.py.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from schgen import write  # noqa: E402

# ref, lib_id, value, footprint, (x, y), {pin: net}, note
ZH4 = "Connector_JST:JST_ZH_B4B-ZR-SM4-TF_1x04-1MP_P1.50mm_Vertical"
SOT = "Package_TO_SOT_SMD:SOT-23"
R0603 = "Resistor_SMD:R_0603_1608Metric"
C0805 = "Capacitor_SMD:C_0805_2012Metric"
TP15 = "TestPoint:TestPoint_Pad_1.5x1.5mm"
TP20 = "TestPoint:TestPoint_Pad_2.0x2.0mm"
MOS = "SOT-23: 1 G, 2 S, 3 D"
PARTS = [
    # The ESC's receiver cable: its BEC's 5V, and the two signals.
    ("J1", "Connector_Generic:Conn_01x04", "ESC RX port (ZH1.5 4P)", ZH4, (30, 40),
     {"1": "S2", "2": "S1", "3": "GND", "4": "5V"},
     "ZERO-Z: yellow S2 / blue S1 / green GND / brown 5V"),
    ("C2", "Device:C", "22uF", C0805, (30, 75), {"1": "5V", "2": "GND"}, ""),
    # EP2 receiver, its 5V delayed by Q1: C1 charges through R1, Q1 opens
    # 0.5..1 s after the BEC. D1 empties C1 at power-off.
    ("Q1", "Device:Q_PMOS", "AO3401", SOT, (85, 40), {"S": "5V", "G": "RXG", "D": "RX5V"}, MOS),
    ("C1", "Device:C", "10uF", C0805, (65, 60), {"1": "5V", "2": "RXG"}, "5V side to Q1's source"),
    ("R1", "Device:R", "100k", R0603, (85, 75), {"1": "RXG", "2": "GND"}, ""),
    ("D1", "Device:D", "1N4148WS", "Diode_SMD:D_SOD-323", (105, 75), {"1": "RXG", "2": "GND"}, "K to the gate"),
    ("J2", "Connector_Generic:Conn_01x04", "EP2 (ZH1.5 4P)", "Connector_JST:JST_ZH_B4B-ZR-SM4-TF_1x04-1MP_P1.50mm_Vertical",
     (145, 30), {"1": "S2", "2": "S1", "3": "GND", "4": "RX5V"}, "EP2 cable: 1 RX pad, 2 TX pad, 3 GND, 4 5V"),
    # VTX on the battery while the BEC is up: Q3 pulls Q2's gate down;
    # R2 / R3 hold Vgs at -VBAT x 100/147.
    ("J6", "Connector_Generic:Conn_01x02", "Battery (ZH1.5 2P)", "Connector_JST:JST_ZH_B2B-ZR-SM4-TF_1x02-1MP_P1.50mm_Vertical", (35, 120), {"1": "VBAT", "2": "GND"},
     "a thin branch off the ESC's battery lead"),
    ("C3", "Device:C", "22uF 25V", "Capacitor_SMD:C_1206_3216Metric", (60, 140), {"1": "VBAT", "2": "GND"}, ""),
    ("Q2", "Device:Q_PMOS", "AO3401", SOT, (110, 115), {"S": "VBAT", "G": "Q2G", "D": "VTX"}, MOS),
    ("R2", "Device:R", "100k", R0603, (85, 105), {"1": "Q2G", "2": "VBAT"}, ""),
    ("R3", "Device:R", "47k", R0603, (85, 135), {"1": "Q2G", "2": "Q3D"}, ""),
    ("Q3", "Device:Q_NMOS", "AO3400", SOT, (110, 150), {"D": "Q3D", "G": "Q3G", "S": "GND"}, MOS),
    ("R4", "Device:R", "1k", R0603, (130, 165), {"1": "5V", "2": "Q3G"}, ""),
    ("R5", "Device:R", "100k", R0603, (85, 165), {"1": "Q3G", "2": "GND"}, ""),
    ("J3", "Connector_Generic:Conn_01x04", "VTX (SH1.0 4P)", "Connector_JST:JST_SH_BM04B-SRSS-TB_1x04-1MP_P1.00mm_Vertical",
     (155, 110), {"1": "VTX", "2": "GND", "3": "NC", "4": "NC"}, "Ascent Lite+ cable, same-direction: 1 red, 2 black, 3/4 UART unused"),
    ("J4", "Connector_Generic:Conn_01x02", "Fan (ZH1.5 2P)", "Connector_JST:JST_ZH_B2B-ZR-SM4-TF_1x02-1MP_P1.50mm_Vertical", (155, 140), {"1": "5V", "2": "GND"}, "25 mm fan, 5 V"),
    # Lap-timing transponder (firmware/transponder): car number = 1 + JP4..6.
    ("U2", "MCU_WCH_RiscV:CH32V003JxMx", "CH32V003J4M6", "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", (200, 110),
     {"1": "NC", "2": "GND", "3": "ID2", "4": "5V", "5": "ID0", "6": "ID1", "7": "PWM", "8": "SWIO"},
     "PC4 = TIM1_CH4: 38 kHz"),
    ("C4", "Device:C", "100nF", "Capacitor_SMD:C_0603_1608Metric", (230, 95), {"1": "5V", "2": "GND"}, ""),
    ("JP1", "Jumper:SolderJumper_2_Open", "+1", "Jumper:SolderJumper-2_P1.3mm_Open_Pad1.0x1.5mm", (240, 115),
     {"1": "ID0", "2": "GND"}, ""),
    ("JP2", "Jumper:SolderJumper_2_Open", "+2", "Jumper:SolderJumper-2_P1.3mm_Open_Pad1.0x1.5mm", (240, 125),
     {"1": "ID1", "2": "GND"}, ""),
    ("JP3", "Jumper:SolderJumper_2_Open", "+4", "Jumper:SolderJumper-2_P1.3mm_Open_Pad1.0x1.5mm", (240, 135),
     {"1": "ID2", "2": "GND"}, ""),
    ("TP11", "Connector:TestPoint", "SWIO", TP15, (200, 140), {"1": "SWIO"}, "WCH-LinkE; its GND on a nut"),
    ("R7", "Device:R", "100", R0603, (200, 160), {"1": "PWM", "2": "GATE"}, ""),
    ("R8", "Device:R", "100k", R0603, (215, 175), {"1": "GATE", "2": "GND"}, ""),
    ("Q4", "Device:Q_NMOS", "AO3400", SOT, (230, 160), {"G": "GATE", "S": "GND", "D": "LEDK"}, MOS),
    ("R6", "Device:R", "33", "Resistor_SMD:R_1206_3216Metric", (255, 150), {"1": "5V", "2": "LEDA"}, "~110 mA bursts"),
    ("J5", "Connector_Generic:Conn_01x02", "IR LED (ZH1.5 2P)", "Connector_JST:JST_ZH_B2B-ZR-SM4-TF_1x02-1MP_P1.50mm_Vertical", (262, 175), {"1": "LEDA", "2": "LEDK"},
     "940 nm LED on its cable, at the rear window"),
    ("H1", "Mechanical:MountingHole_Pad", "M2 SMT nut", "", (170, 30), {"1": "GND"}, "the printed frame's screws"),
    ("H2", "Mechanical:MountingHole_Pad", "M2 SMT nut", "", (185, 30), {"1": "GND"}, ""),
    ("H3", "Mechanical:MountingHole_Pad", "M2 SMT nut", "", (200, 30), {"1": "GND"}, ""),
    ("H4", "Mechanical:MountingHole_Pad", "M2 SMT nut", "", (215, 30), {"1": "GND"}, ""),
    ("#FLG01", "power:PWR_FLAG", "PWR_FLAG", "", (260, 30), {"1": "5V"}, "fed by the ESC's BEC"),
    ("#FLG02", "power:PWR_FLAG", "PWR_FLAG", "", (275, 30), {"1": "GND"}, ""),
]

if __name__ == "__main__":
    write(os.path.join(HERE, "x2201-carrier.kicad_sch"), "x2201-carrier", "X2201 carrier board", "3.0",
          "FPV mount base, all plugs: ZERO-Z cable, EP2 with delayed 5V, VTX switched by the BEC, lap transponder",
          PARTS, "6b1d3c1e-2201-4a00-9000-000000000000")
