"""Schematic for carrier v9, read from the board so the nets are the same.

  python3 gen_sch.py   (after gen_pcb.py), with KiCad's Python
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import pcbnew  # noqa: E402
from schgen import write  # noqa: E402

BOARD = os.path.join(HERE, "x2201-carrier-v9.kicad_pcb")
MOS = {"1": "G", "2": "S", "3": "D"}
SYMBOL = {
    "U1": ("RF_Module:ESP32-S3-MINI-1", None),
    "U3": ("Regulator_Linear:AP2204K-1.5", None),  # AP2112K-3.3: the same pins
    "J9": ("Connector:USB_C_Receptacle_USB2.0_16P", None),
    "TP": ("Connector:TestPoint", None),
    "D": ("Device:D_Schottky", {"1": "1", "2": "2"}),
    "Q2": ("Device:Q_PMOS", MOS),
    "Q1": ("Device:Q_NMOS", {"1": "S", "2": "S", "3": "S", "4": "G", "5": "D"}),
    "Q": ("Device:Q_NMOS", MOS),
    "U2": ("Sensor_Motion:LSM6DS3", None),
    "U4": ("Regulator_Switching:LMR51430", None),
    "W": ("Connector_Generic:Conn_01x01", None),
    "P": ("Connector_Generic:Conn_01x03", None),
    "R": ("Device:R", None), "C": ("Device:C", None), "L": ("Device:L", None),
}
PINMAP = {}
NOTES = {
    "W1": "battery +, soldered", "W2": "battery -, soldered", "W3": "ESC power +, soldered", "W4": "ESC power -, soldered",
    "Q1": "reverse guard in the battery's negative lead: on the right way round, off reversed; protects the ESC too",
    "U4": "5 V 3 A buck for the S3, EP2, servo, fan and IR: 0.6 V x (1 + 22k / 3k)",
    "P1": "the ESC's servo lead: 1 signal, 2 its BEC (open: the board makes its own 5 V), 3 GND",
    "P2": "servo: 1 signal, 2 5V, 3 GND",
    "J2": "the EP2 on a plug, CRSF: 1 its TX (to IO13), 2 its RX (from IO14), 3 5V, 4 GND",
    "J3": "VTX, 6-pin plug, 4 wires: 1 red power, 2 black GND, 3 white its RX, 4 grey its TX, 5-6 unused",
    "J4": "fan: 1 5V, 2 GND, on whenever the battery is in",
    "U1": "IO0 BOOT, IO6 VTX on, IO7 ESC, IO8 servo, IO9 VBAT, IO10 MSP RX, IO11 MSP TX, IO13 CRSF RX, IO14 CRSF TX, "
          "IO15 IR, IO16 SDA, IO17 SCL, IO18 gyro INT, IO19/20 USB",
    "U2": "gyro, I2C 0x6A (SA0 low, CS high); aux bus unused",
    "Q2": "VTX power, on when IO6 is high (Q3); off at reset",
    "D3": "the board's 5 V into VIN; D2 is USB into VIN, so the two never meet",
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
            for k in range(1, 66):
                nets.setdefault(str(k), "NC")
        if ref == "U2":
            for k in ("9", "10", "11"):
                nets.setdefault(k, "NC")
        if ref == "P1":
            nets["2"] = "NC"
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
    flags = ["5V", "GND", "VBAT", "BAT_N", "VTX", "VIN", "VBUS"]
    out += [(f"#FLG{i + 1:02d}", "power:PWR_FLAG", "PWR_FLAG", "", (60 + 15 * i, 230), {"1": n}, "") for i, n in enumerate(flags)]
    return out


if __name__ == "__main__":
    write(os.path.join(HERE, "x2201-carrier-v9.kicad_sch"), "x2201-carrier-v9", "X2201 main board v9", "9.0",
          "Main board: battery in with reverse guard, 5 V buck, ESP32-S3-MINI-1, EP2 (CRSF), servo and ESC out, gyro, lap IR, VTX",
          parts(), "6b1d3c1e-2201-4a00-9000-000000000009", paper="A3")
