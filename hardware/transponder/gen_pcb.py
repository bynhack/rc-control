"""Lap-timing transponder board (firmware/transponder): one per car, for
the cars without the X2201 carrier board. A CH32V003J4M6 flashes the car's
number on a 940 nm IR LED at 38 kHz; the LED points up through a window or
a thin plastic shell, at the finish-line arch.

  - J1: 5V, GND, SWIO, 2.54 mm. The car's 5V (any servo plug's + and -)
    goes here, and the WCH-LinkE does too when flashing.
  - JP1..JP3: the car number, 1 + the closed jumpers (bit 0..2).
  - D1: a 3 mm IR LED, in the board or on two wires. Q1 drives it, about
    110 mA in the bursts through R1 (33 ohm), ~10 mA on average.

The schematic is gen_sch.py's, with the same net names.

Run with KiCad's Python:
  /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 gen_pcb.py
  -> transponder.kicad_pcb; with FAB=1 also gerber/, bom.csv and cpl.csv for JLCPCB
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import pcbnew  # noqa: E402
from pcbgen import W_PWR, drc, dump, fab, outline, pad, place, save, text, track, via, zone  # noqa: E402

OUT = os.path.join(HERE, "transponder.kicad_pcb")
W, H = 15.0, 22.0

J1 = place("Connector_PinHeader_2.54mm", "PinHeader_1x03_P2.54mm_Vertical", "J1", "5V GND SWIO", 5.0, 1.9, 90,
           {"1": "5V", "2": "GND", "3": "SWIO"})
U1 = place("Package_SO", "SOIC-8_3.9x4.9mm_P1.27mm", "U1", "CH32V003J4M6", 7.5, 7.6, 0,
           {"2": "GND", "3": "ID2", "4": "5V", "5": "ID0", "6": "ID1", "7": "PWM", "8": "SWIO"})
C1 = place("Capacitor_SMD", "C_0603_1608Metric", "C1", "100nF", 2.6, 8.2, 270, {"1": "GND", "2": "5V"})
JP = [place("Jumper", "SolderJumper-2_P1.3mm_Open_Pad1.0x1.5mm", "JP" + str(i + 1), "ID" + str(i), 12.9, y, 0,
            {"1": "ID" + str(i), "2": "GND"}) for i, y in enumerate((10.9, 8.3, 13.5))]
D1 = place("LED_THT", "LED_D3.0mm", "D1", "IR 940nm 3mm", 8.77, 19.5, 180, {"1": "LEDK", "2": "LEDA"})
R1 = place("Resistor_SMD", "R_1206_3216Metric", "R1", "33", 2.0, 18.0, 90, {"1": "LEDA", "2": "5V"})
Q1 = place("Package_TO_SOT_SMD", "SOT-23", "Q1", "AO3400", 12.6, 19.6, 0, {"1": "GATE", "2": "GND", "3": "LEDK"})
R2 = place("Resistor_SMD", "R_0603_1608Metric", "R2", "100", 10.3, 15.6, 270, {"1": "PWM", "2": "GATE"})
R3 = place("Resistor_SMD", "R_0603_1608Metric", "R3", "100k", 12.75, 15.9, 0, {"1": "GATE", "2": "GND"})
C2 = place("Capacitor_SMD", "C_0805_2012Metric", "C2", "10uF", 5.5, 13.4, 0, {"1": "5V", "2": "GND"})

B = pcbnew.B_Cu
# 5V down the left edge: U1, C1, C2, R1.
track([pad(J1, 1), (5.0, 3.4), (1.2, 3.4), (1.2, 16.54), pad(R1, 2)], "5V", W_PWR)
track([(1.2, 9.51), pad(U1, 4)], "5V", W_PWR)
track([pad(C1, 2), (2.6, 9.51)], "5V")
track([(1.2, 13.4), pad(C2, 1)], "5V", W_PWR)
track([pad(U1, 2), (3.6, 6.96), pad(C1, 1)], "GND")
via(3.6, 6.2, "GND")
track([(3.6, 6.96), (3.6, 6.2)], "GND")
track([pad(J1, 3), (10.08, 4.4), pad(U1, 8)], "SWIO")
# Car number jumpers on the right; ID2 under the chip and along the bottom.
track([pad(U1, 6), (11.3, 8.3), pad(JP[1], 1)], "ID1")
track([pad(U1, 5), (11.2, 9.51), (11.2, 10.9), pad(JP[0], 1)], "ID0")
track([pad(U1, 3), (7.5, 8.23)], "ID2")
via(7.5, 8.23, "ID2")
via(12.25, 14.9, "ID2")
track([(7.5, 8.23), (7.5, 14.9), (12.25, 14.9)], "ID2", layer=B)
track([(12.25, 14.9), pad(JP[2], 1)], "ID2")
# PWM on the bottom to R2, the gate, the LED.
track([pad(U1, 7), (11.4, 6.96)], "PWM")
via(11.4, 6.96, "PWM")
via(10.3, 13.4, "PWM")
track([(11.4, 6.96), (11.4, 12.3), (10.3, 13.4)], "PWM", layer=B)
track([(10.3, 13.4), pad(R2, 1)], "PWM")
track([pad(R2, 2), (11.66, 16.42), pad(Q1, 1)], "GATE")
track([pad(R3, 1), (11.66, 16.42)], "GATE")
track([pad(R1, 1), pad(D1, 2)], "LEDA", W_PWR)
# The LED's cathode to Q1's drain on the bottom, under Q1's source.
track([pad(Q1, 3), (13.54, 20.75)], "LEDK", W_PWR)
via(13.54, 20.75, "LEDK")
track([(13.54, 20.75), (8.77, 20.75), pad(D1, 1)], "LEDK", W_PWR, B)
for v in ((7.54, 4.2), (3.6, 12.0), (8.6, 11.6)):
    via(*v, "GND")

# ---- silkscreen ---------------------------------------------------------------------------
# Labels on the back: the front has no room between the parts.
BS = pcbnew.B_SilkS
for n, lab in ((1, "5V"), (2, "G"), (3, "SW")):
    x, y = pad(J1, n)
    text(lab, x, y + 2.0, 0.8, BS)
for j, lab in zip(JP, ("+1", "+2", "+4")):
    x, y = pad(j, 1)
    text(lab, x + 0.65, y, 0.8, BS)
text("CAR = 1 +", 7.0, 11.0, 0.8, BS)
text("IR LED", 7.5, 16.4, 0.8, BS)
text("LAP v1", 7.5, 7.0, 0.8, BS)

outline(0, 0, W, H, 1.5)
zone("GND", pcbnew.F_Cu, 0.3, 0.3, W - 0.3, H - 0.3)
zone("GND", B, 0.3, 0.3, W - 0.3, H - 0.3)

if __name__ == "__main__":
    if os.environ.get("DUMP"):
        dump()
    else:
        save(OUT)
        for line in drc(OUT):
            print(line)
        if os.environ.get("FAB"):
            fab(OUT)
