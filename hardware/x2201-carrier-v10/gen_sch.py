"""Schematic for main board v10, read from the board so the nets are the same.

  python3 gen_sch.py   (after gen_pcb.py), with KiCad's Python
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import pcbnew  # noqa: E402
from schgen import write  # noqa: E402

BOARD = os.path.join(HERE, "x2201-carrier-v10.kicad_pcb")
MOS = {"1": "G", "2": "S", "3": "D"}
SYMBOL = {
    "U1": ("Connector_Generic:Conn_01x18", None),  # the SuperMini, on its two rows of 9
    "U3": ("Regulator_Linear:AP2204K-1.5", None),  # AP2112K-3.3: the same pins
    "J9": ("Connector:USB_C_Receptacle_USB2.0_16P", None),
    "TP": ("Connector:TestPoint", None),
    "D": ("Device:D_Schottky", {"1": "1", "2": "2"}),
    "Q2": ("Device:Q_PMOS", MOS),
    "Q1": ("Device:Q_NMOS", {"1": "S", "2": "S", "3": "S", "4": "G", "5": "D"}),
    "Q": ("Device:Q_NMOS", MOS),
    "U2": ("Sensor_Motion:LSM6DS3", None),
    "U4": ("Regulator_Switching:LMR51430", None),
    "U5": ("rc_control:DRV8874", None),
    "W": ("Connector_Generic:Conn_01x01", None),
    "P": ("Connector_Generic:Conn_01x03", None),
    "J7": ("Connector_Generic:Conn_01x02", None),
    "R": ("Device:R", None), "C": ("Device:C", None), "L": ("Device:L", None),
}
PINMAP = {}
NOTES = {
    "W1": "battery +, soldered", "W2": "battery -, soldered",
    "Q1": "reverse guard in the battery's negative lead, drain to BAT-, source to GND: on the right way round, "
          "off reversed. Protects the whole board, the motor driver included",
    "U4": "5 V 3 A buck, the BEC: 0.6 V x (1 + 22k / 3k). EN from the button (D4) or the S3's TX (D5), held off by R16",
    "U5": "onboard brushed ESC, PWM mode (PMODE high): IN1/IN2 = IO7/IO4. 10 forward, 01 reverse, 11 brake, 00 coast. "
          "ITRIP = 3.3 V / (450 uA/A x 1.5k) = 4.9 A, fixed off-time, auto retry (IMODE low). Asleep when 3V3 is off",
    "J7": "motor, ZH2.0 (PH) 2P side entry: 1 OUT1, 2 OUT2",
    "J6": "power button, momentary, ZH1.5 2P: 1 battery, 2 BTN. Press: on (D4 lifts EN, the S3 boots and holds EN "
          "with TX). Press again: Q6 pulls RX low, the S3 drops TX, off on release",
    "P2": "servo, ZH1.5 3P: 1 signal, 2 5V, 3 GND",
    "J2": "the EP2, ZH1.5 4P: 1 its TX (to IO13), 2 its RX (from IO12), 3 5V, 4 GND",
    "J3": "VTX, ZH1.5 4P: 1 power (battery, switched by Q2), 2 GND, 3 its RX, 4 its TX",
    "J4": "fan: 1 5V, 2 GND, on whenever the board is on",
    "U1": "ESP32-S3 SuperMini, hand-soldered on header pins. Pins 1-9 (top row from the USB end): 5V GND 3V3 IO13 IO12 "
          "IO11 IO10 IO9 IO8; 10-18: TX RX IO1-IO7. IO13/12 CRSF RX/TX, IO11/10 MSP TX/RX, IO9 VBAT, IO8 servo, "
          "IO7/IO4 motor forward/reverse, IO6 VTX on, IO5 IR, IO1/2/3 SDA/SCL/gyro INT, TX (IO43) power hold, "
          "RX (IO44) button",
    "U2": "gyro, I2C 0x6A (SA0 low, CS high); aux bus unused",
    "Q2": "VTX power, on when IO6 is high (Q3); off at reset",
    "D3": "the board's 5 V into the SuperMini's 5V pin and the EP2; with USB in, VBUS stays on the module's side",
}


def parts():
    board = pcbnew.LoadBoard(BOARD)
    out, col = [], {}
    mods = sorted(board.GetFootprints(), key=lambda m: (m.GetReference()[0], len(m.GetReference()), m.GetReference()))
    for m in mods:
        ref = m.GetReference()
        if ref.startswith("MH"):
            continue
        nets = {}
        for p in m.Pads():
            if p.GetNumber() in ("", "MP"):
                continue
            nets.setdefault(p.GetNumber(), p.GetNetname() or "NC")
        if ref == "U1":
            for k in range(1, 19):
                nets.setdefault(str(k), "NC")
        if ref == "U2":
            for k in ("9", "10", "11"):
                nets.setdefault(k, "NC")
        if ref == "U3":
            nets.setdefault("4", "NC")
        if ref == "J9":
            for k in ("A8", "B8"):
                nets[k] = "NC"
        if ref in PINMAP:
            n = len(PINMAP[ref])
            sym, pm = f"Connector_Generic:Conn_01x{n:02d}", PINMAP[ref]
        elif ref[0] == "J" and ref not in SYMBOL:
            sym, pm = f"Connector_Generic:Conn_01x{len(nets):02d}", None
        elif ref.startswith("TP"):
            sym, pm = SYMBOL["TP"]
        else:
            sym, pm = SYMBOL[ref] if ref in SYMBOL else SYMBOL[ref[0]]
        if pm:
            nets = {pm[k]: v for k, v in nets.items()}
        kind = "J" if ref[0] in "JWP" else ("C" if ref[0] == "L" else (ref[0] if ref[0] in "UT" else ("DQ" if ref[0] in "DQ" else ref[0])))
        x0, dx, dy, rows = {"U": (50, 70, 80, 3), "T": (100, 20, 0, 1), "J": (130, 32, 30, 6), "DQ": (170, 22, 26, 7), "R": (225, 17, 21, 9),
                            "C": (300, 17, 21, 9)}[kind]
        i = col.setdefault(kind, [0])
        x, y = x0 + dx * (i[0] // rows), 40 + dy * (i[0] % rows)
        i[0] += 1
        out.append((ref, sym, m.GetValue(), "", (x, y), nets, NOTES.get(ref, "")))
    flags = ["5V", "GND", "VBAT", "BAT_N", "VTX", "VIN", "3V3"]  # 3V3 comes from the SuperMini's own LDO
    out += [(f"#FLG{i + 1:02d}", "power:PWR_FLAG", "PWR_FLAG", "", (60 + 15 * i, 230), {"1": n}, "") for i, n in enumerate(flags)]
    return out


if __name__ == "__main__":
    write(os.path.join(HERE, "x2201-carrier-v10.kicad_sch"), "x2201-carrier-v10", "X2201 main board v10", "10.0",
          "76 x 20. External brushed ESC (no BEC), onboard 5 V 3 A BEC, ESP32-S3-MINI-1, EP2, servo, gyro, lap IR, VTX",
          parts(), "6b1d3c1e-2201-4a00-9000-000000000010", paper="A2")
