#!/usr/bin/env python3
"""Generate the lap-timing transponder's schematic (transponder.kicad_sch).
gen_pcb.py has the layout, with the same net names; firmware/transponder the
code. Car number = 1 + the closed jumpers.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from schgen import write  # noqa: E402

R0603 = "Resistor_SMD:R_0603_1608Metric"
JPF = "Jumper:SolderJumper-2_P1.3mm_Open_Pad1.0x1.5mm"
PARTS = [
    ("J1", "Connector_Generic:Conn_01x03", "5V GND SWIO", "Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical",
     (30, 40), {"1": "5V", "2": "GND", "3": "SWIO"}, "the car's 5V; the WCH-LinkE when flashing"),
    ("U1", "MCU_WCH_RiscV:CH32V003JxMx", "CH32V003J4M6", "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", (80, 50),
     {"1": "NC", "2": "GND", "3": "ID2", "4": "5V", "5": "ID0", "6": "ID1", "7": "PWM", "8": "SWIO"},
     "PC4 = TIM1_CH4: 38 kHz"),
    ("C1", "Device:C", "100nF", "Capacitor_SMD:C_0603_1608Metric", (30, 75), {"1": "5V", "2": "GND"}, ""),
    ("C2", "Device:C", "10uF", "Capacitor_SMD:C_0805_2012Metric", (45, 75), {"1": "5V", "2": "GND"}, ""),
    ("JP1", "Jumper:SolderJumper_2_Open", "+1", JPF, (130, 40), {"1": "ID0", "2": "GND"}, ""),
    ("JP2", "Jumper:SolderJumper_2_Open", "+2", JPF, (130, 52), {"1": "ID1", "2": "GND"}, ""),
    ("JP3", "Jumper:SolderJumper_2_Open", "+4", JPF, (130, 64), {"1": "ID2", "2": "GND"}, ""),
    ("R2", "Device:R", "100", R0603, (80, 100), {"1": "PWM", "2": "GATE"}, ""),
    ("R3", "Device:R", "100k", R0603, (95, 115), {"1": "GATE", "2": "GND"}, ""),
    ("Q1", "Device:Q_NMOS", "AO3400", "Package_TO_SOT_SMD:SOT-23", (110, 100), {"G": "GATE", "S": "GND", "D": "LEDK"},
     "SOT-23: 1 G, 2 S, 3 D"),
    ("R1", "Device:R", "33", "Resistor_SMD:R_1206_3216Metric", (140, 85), {"1": "5V", "2": "LEDA"}, "~110 mA bursts"),
    ("D1", "Device:LED", "IR 940nm 3mm", "LED_THT:LED_D3.0mm", (140, 105), {"1": "LEDK", "2": "LEDA"}, "points up"),
    ("#FLG01", "power:PWR_FLAG", "PWR_FLAG", "", (20, 110), {"1": "5V"}, "fed by the ESC's BEC"),
    ("#FLG02", "power:PWR_FLAG", "PWR_FLAG", "", (35, 110), {"1": "GND"}, ""),
]

if __name__ == "__main__":
    write(os.path.join(HERE, "transponder.kicad_sch"), "transponder", "Lap-timing transponder", "1.0",
          "CH32V003 flashing the car number at 38 kHz on a 940 nm LED", PARTS, "6b1d3c1e-2201-4a00-9000-0000000000a1")
