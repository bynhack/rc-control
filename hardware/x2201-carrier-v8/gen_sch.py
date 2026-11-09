"""Schematic for carrier v7, read from the board so the nets are the same.

  python3 gen_sch.py   (after gen_pcb.py), with KiCad's Python
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import pcbnew  # noqa: E402
from schgen import write  # noqa: E402

BOARD = os.path.join(HERE, "x2201-carrier-v8.kicad_pcb")
MOS = {"1": "G", "2": "S", "3": "D"}
SYMBOL = {
    "U1": ("RF_Module:ESP32-S3-MINI-1", None),
    "U3": ("Regulator_Linear:AP2204K-1.5", None),  # AP2112K-3.3: the same pins
    "J9": ("Connector:USB_C_Receptacle_USB2.0_16P", None),
    "TP": ("Connector:TestPoint", None),
    "D": ("Device:D_Schottky", {"1": "1", "2": "2"}),
    "Q2": ("Device:Q_PMOS", MOS),
    "Q": ("Device:Q_NMOS", MOS),
    "R": ("Device:R", None), "C": ("Device:C", None),
}
PINMAP = {"U2": {"TX": "1", "RX": "2", "5V": "3", "G": "4"}}
NOTES = {
    "J1": "ZERO-Z: yellow S2 / blue S1 / green GND / brown 5V",
    "J2": "the EP2 on wires: 1 its TX (S1), 2 its RX (S2), 3 delayed 5V, 4 GND",
    "J3": "VTX, 6-pin plug, 4 wires: 1 red power, 2 black GND, 3 white its RX, 4 grey its TX, 5-6 unused",
    "J4": "fan: 1 5V, 2 GND, on whenever the ESC is on",
    "Q1": "the EP2's 5V, late: C1 charges through R1 after the BEC comes up, so the ESC has let go of its TX pad",
    "U1": "IO0 BOOT, IO9 VBAT, IO10 MSP RX, IO11 MSP TX, IO15 IR, IO19/20 USB; not in the control path",
    "U2": "EP2 2400RX in PWM mode: TX pad = CH1 steering (S1), RX pad = CH2 throttle (S2)",
    "D3": "BEC into VIN; D2 is USB into VIN, so the two never meet",
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
        kind = ref[0] if ref[0] in "UJT" else ("DQ" if ref[0] in "DQ" else ref[0])
        x0, dx, dy, rows = {"U": (50, 70, 80, 3), "T": (100, 20, 0, 1), "J": (130, 32, 30, 6), "DQ": (170, 22, 26, 7), "R": (225, 17, 21, 9),
                            "C": (300, 17, 21, 9)}[kind]
        i = col.setdefault(kind, [0])
        x, y = x0 + dx * (i[0] // rows), 40 + dy * (i[0] % rows)
        i[0] += 1
        out.append((ref, sym, m.GetValue(), "", (x, y), nets, NOTES.get(ref, "")))
    flags = ["5V", "GND", "VBAT", "VTX", "VIN", "VBUS"]
    out += [(f"#FLG{i + 1:02d}", "power:PWR_FLAG", "PWR_FLAG", "", (60 + 15 * i, 230), {"1": n}, "") for i, n in enumerate(flags)]
    return out


if __name__ == "__main__":
    write(os.path.join(HERE, "x2201-carrier-v8.kicad_sch"), "x2201-carrier-v8", "X2201 carrier board v8", "8.0",
          "ESP32-S3-MINI-1 + EP2 2400RX on a 2-layer board: CRSF in, PWM out, battery voltage, lap IR, VTX UART, wiring",
          parts(), "6b1d3c1e-2201-4a00-9000-000000000008", paper="A3")
