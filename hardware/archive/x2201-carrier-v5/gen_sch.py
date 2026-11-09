"""Generate the X2201 carrier v5 schematic (x2201-carrier-v5.kicad_sch) from the
board gen_pcb.py writes: every pad's net becomes a net label on its symbol's
pin, so the schematic and the layout can't drift apart. Run gen_pcb.py first,
then this, both with KiCad's Python:

  /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 gen_sch.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import pcbnew  # noqa: E402
from schgen import write  # noqa: E402

BOARD = os.path.join(HERE, "x2201-carrier-v5.kicad_pcb")

# ref prefix or ref -> (symbol, {pad: symbol pin} or None for the same numbers)
MOS = {"1": "G", "2": "S", "3": "D"}
SYMBOL = {
    "U1": ("MCU_Espressif:ESP32-C3", None),
    "U3": ("Regulator_Linear:AP2204K-1.5", None),  # AP2112K-3.3: the same pins
    "U4": ("Regulator_Switching:LMR51430", None),
    "J9": ("Connector:USB_C_Receptacle_USB2.0_16P", None),
    "D2": ("Device:D_Schottky", None), "D3": ("Device:D_Schottky", None),
    "D4": ("Device:LED", None),
    "Q2": ("Device:Q_PMOS", MOS),
    "Q3": ("Device:Q_NMOS", MOS), "Q4": ("Device:Q_NMOS", MOS),
    "R": ("Device:R", None), "C": ("Device:C", None), "L": ("Device:L", None),
    "H": ("Mechanical:MountingHole_Pad", None),
    "U5": ("MCU_Espressif:ESP32-C3", None),
    "U6": ("rc_control:SX1280", None),
    "U7": ("rc_control:AT2401C", None),
    "U8": ("Regulator_Linear:AP2204K-1.5", None),  # AP2112K-3.3
    "FL1": ("rc_control:2450FM07D0034", None),
    "J10": ("Connector:Conn_Coaxial", None), "J11": ("Connector:Conn_Coaxial", None),
    "J12": ("Connector:Conn_Coaxial", None),
    "Y": ("Device:Crystal_GND24", None),
}
LIBS = [("R_", "Resistor_SMD"), ("C_", "Capacitor_SMD"), ("SOT", "Package_TO_SOT_SMD"), ("D_", "Diode_SMD"),
        ("LED_", "LED_SMD"), ("L_", "Inductor_SMD"), ("JST_", "Connector_JST"), ("USB_C", "Connector_USB"),
        ("ESP32", "Espressif"), ("QFN", "Package_DFN_QFN"), ("Crystal_", "Crystal"), ("U.FL", "Connector_Coaxial"),
        ("2450FM", "AnyLeaf")]
CONN = {n: f"Connector_Generic:Conn_01x{n:02d}" for n in (2, 3, 4, 6, 8)}
NOTES = {
    "U1": "the brain: GPIO0/1 S1/S2, 2 spare (strap), 3 VBAT (ADC1), 4/5 MSP (the VTX's UART), 6 IR, 7/9 U5 EN/BOOT, 8 LED, 18/19 USB, 20/21 CRSF",
    "U5": "ELRS 'Generic C3 2400 PA' pins; GPIO9 low at reset = ROM loader on U0 (CRSF pair)",
    "U6": "52 MHz crystal; DC-DC on (L5)",
    "U7": "TXEN/RXEN pulled down: off while U5 is held in reset",
    "J10": "ELRS antenna (2.4 GHz), out through the shell's window",
    "J11": "the receiver C3's WiFi (ELRS setup page)",
    "J12": "the brain's WiFi (car setup)",
    "J1": "ZERO-Z: yellow S2 / blue S1 / green GND / brown 5V",
    "J3": "VTX, same-direction cable (Walksnail Ascent Lite+): 1 red power, 2 black GND, 3 white its RX, 4 grey its TX",
    "R14": "VBAT x 22/122 to GPIO3 (ADC1)",
}


def parts():
    board = pcbnew.LoadBoard(BOARD)
    out = []
    mods = sorted(board.GetFootprints(), key=lambda m: (m.GetReference()[0], len(m.GetReference()), m.GetReference()))
    col = {}
    for m in mods:
        ref = m.GetReference()
        nets = {}
        for p in m.Pads():
            n = p.GetNumber()
            if n in ("", "MP"):
                continue
            nets.setdefault(n, p.GetNetname() or "NC")
        if ref in SYMBOL:
            sym, pinmap = SYMBOL[ref]
        elif ref[0] == "J":
            sym, pinmap = CONN[len(nets)], None
        else:
            sym, pinmap = SYMBOL[ref[0]]
        if pinmap:
            nets = {pinmap[k]: v for k, v in nets.items()}
        nets = {k: ("VBUS" if v == "VBUS_NC" else v) for k, v in nets.items()}  # one net in the symbol
        if ref in ("U3", "U8"):
            nets.setdefault("4", "NC")
        if ref in ("U1", "U5"):  # unused GPIOs, the in-package flash's pins
            for k in range(1, 34):
                nets.setdefault(str(k), "NC")
        if ref == "U7":  # pin 13 isn't in the symbol (not connected)
            nets.pop("13", None)
        if ref == "FL1":
            nets.setdefault("5", "GND")
        if ref == "U6":
            for k in ("9", "10"):
                nets.setdefault(k, "NC")
        if ref == "J9":
            for k in ("A8", "B8"):
                nets[k] = "NC"
        # an A3 grid: one column group per kind, wrapping after `rows`
        kind = "U1" if ref == "U1" else ("DQL" if ref[0] in "DQLYF" else ref[0])
        x0, dx, dy, rows = {"U1": (45, 0, 0, 1), "U": (115, 0, 33, 7), "J": (165, 30, 34, 6),
                            "DQL": (225, 20, 26, 9), "R": (262, 17, 21, 11), "C": (338, 17, 19, 12),
                            "H": (170, 18, 0, 1)}[kind]
        if kind == "H":
            y0 = 245
        else:
            y0 = 30
        i = col.setdefault(kind, [0])
        x, y = x0 + dx * (i[0] // rows), y0 + dy * (i[0] % rows)
        i[0] += 1
        x, y = {"U3": (115, 30), "U4": (115, 60), "U8": (115, 90), "U6": (115, 140), "U7": (115, 200),
                "U5": (60, 215), "U1": (45, 110)}.get(ref, (x, y))
        name = str(m.GetFPID().GetLibItemName())
        lib = next((l for pre, l in LIBS if name.startswith(pre)), "")
        out.append((ref, sym, m.GetValue(), f"{lib}:{name}" if lib else "", (x, 110 if ref == "U1" else y),
                    nets, NOTES.get(ref, "")))
    out += [("#FLG01", "power:PWR_FLAG", "PWR_FLAG", "", (60, 270), {"1": "5V"}, "fed by the ESC's BEC"),
            ("#FLG02", "power:PWR_FLAG", "PWR_FLAG", "", (75, 270), {"1": "GND"}, ""),
            ("#FLG03", "power:PWR_FLAG", "PWR_FLAG", "", (90, 270), {"1": "VBUS"}, "USB"),
            ("#FLG04", "power:PWR_FLAG", "PWR_FLAG", "", (105, 270), {"1": "VBAT"}, "battery"),
            ("#FLG05", "power:PWR_FLAG", "PWR_FLAG", "", (120, 270), {"1": "VIN"}, "D2 / D3: 5V or USB"),
            ("#FLG07", "power:PWR_FLAG", "PWR_FLAG", "", (150, 270), {"1": "VTX"}, "Q2's drain"),
            ("#FLG08", "power:PWR_FLAG", "PWR_FLAG", "", (165, 270), {"1": "RXC_VPA"}, "through L2"),
            ("#FLG09", "power:PWR_FLAG", "PWR_FLAG", "", (180, 270), {"1": "B_VPA"}, "through L8")]
    return out


if __name__ == "__main__":
    write(os.path.join(HERE, "x2201-carrier-v5.kicad_sch"), "x2201-carrier-v5", "X2201 carrier board v5", "5.0",
          "42x33 4-layer control board: ELRS RX on board (C3 + SX1280 + AT2401C), brain C3 (CRSF in, PWM out, MSP OSD to the VTX, lap IR)",
          parts(), "6b1d3c1e-2201-4a00-9000-000000000005", paper="A3")
