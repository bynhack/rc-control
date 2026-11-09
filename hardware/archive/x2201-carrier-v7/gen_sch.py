"""Schematic for carrier v7, read from the board so the nets are the same.

  python3 gen_sch.py   (after gen_pcb.py), with KiCad's Python
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import pcbnew  # noqa: E402
from schgen import write  # noqa: E402

BOARD = os.path.join(HERE, "x2201-carrier-v7.kicad_pcb")
MOS = {"1": "G", "2": "S", "3": "D"}
SYMBOL = {
    "D": ("Device:D_Schottky", {"1": "1", "2": "2"}),
    "Q2": ("Device:Q_PMOS", MOS),
    "Q": ("Device:Q_NMOS", MOS),
    "R": ("Device:R", None), "C": ("Device:C", None),
}
ZERO = ["5V", "GND", "3V3", "1", "2", "3", "4", "5", "6", "TX", "RX", "13", "12", "11", "10", "9", "8", "7"]
PINMAP = {"U1": {n: str(i + 1) for i, n in enumerate(ZERO)},
          "U2": {"TX": "1", "RX": "2", "5V": "3", "G": "4"}}
NOTES = {
    "J1": "ZERO-Z: yellow S2 / blue S1 / green GND / brown 5V",
    "J3": "VTX, same-direction cable: 1 red power, 2 black GND, 3 white its RX, 4 grey its TX",
    "J4": "fan: 1 5V, 2 GND, on whenever the ESC is on",
    "R11": "holds the EP2's TX pad high at power-up",
    "U1": "ESP32-S3-Zero; pins in order: 5V GND 3V3 IO1-6, TX(43) RX(44) IO13-7. Its 5V pad is USB VBUS",
    "U2": "EP2 2400RX: CRSF; set to serial, not PWM",
    "D3": "keeps USB off the BEC",
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
        if ref in PINMAP:
            n = len(PINMAP[ref])
            sym, pm = f"Connector_Generic:Conn_01x{n:02d}", PINMAP[ref]
        elif ref[0] == "J":
            sym, pm = f"Connector_Generic:Conn_01x{len(nets):02d}", None
        else:
            sym, pm = SYMBOL.get(ref, SYMBOL[ref[0]])
        if pm:
            nets = {pm[k]: v for k, v in nets.items()}
        kind = ref[0] if ref[0] in "UJ" else ("DQ" if ref[0] in "DQ" else ref[0])
        x0, dx, dy, rows = {"U": (50, 0, 80, 3), "J": (100, 30, 30, 6), "DQ": (170, 22, 26, 7), "R": (225, 17, 21, 9),
                            "C": (300, 17, 21, 9)}[kind]
        i = col.setdefault(kind, [0])
        x, y = x0 + dx * (i[0] // rows), 40 + dy * (i[0] % rows)
        i[0] += 1
        out.append((ref, sym, m.GetValue(), "", (x, y), nets, NOTES.get(ref, "")))
    flags = ["5V", "GND", "VBAT", "VTX", "5VM", "3V3"]
    out += [(f"#FLG{i + 1:02d}", "power:PWR_FLAG", "PWR_FLAG", "", (60 + 15 * i, 230), {"1": n}, "") for i, n in enumerate(flags)]
    return out


if __name__ == "__main__":
    write(os.path.join(HERE, "x2201-carrier-v7.kicad_sch"), "x2201-carrier-v7", "X2201 carrier board v7", "7.0",
          "ESP32-S3-Zero + EP2 2400RX on a 2-layer board: CRSF in, PWM out, battery voltage, lap IR, VTX UART, wiring",
          parts(), "6b1d3c1e-2201-4a00-9000-000000000007", paper="A3")
