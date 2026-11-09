"""Generate the X2201 carrier v4 schematic (x2201-carrier-v4.kicad_sch) from the
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

BOARD = os.path.join(HERE, "x2201-carrier-v4.kicad_pcb")

# ref prefix or ref -> (symbol, {pad: symbol pin} or None for the same numbers)
MOS = {"1": "G", "2": "S", "3": "D"}
SYMBOL = {
    "U1": ("RF_Module:ESP32-S3-MINI-1", None),
    "U3": ("Regulator_Linear:AP2204K-1.5", None),  # AP2112K-3.3: the same pins
    "J9": ("Connector:USB_C_Receptacle_USB2.0_16P", None),
    "D2": ("Device:D_Schottky", None), "D3": ("Device:D_Schottky", None),
    "D4": ("Device:LED", None),
    "Q2": ("Device:Q_PMOS", MOS),
    "Q3": ("Device:Q_NMOS", MOS), "Q4": ("Device:Q_NMOS", MOS),
    "R": ("Device:R", None), "C": ("Device:C", None),
    "H": ("Mechanical:MountingHole_Pad", None),
}
LIBS = [("R_", "Resistor_SMD"), ("C_", "Capacitor_SMD"), ("SOT", "Package_TO_SOT_SMD"), ("D_", "Diode_SMD"),
        ("LED_", "LED_SMD"), ("JST_", "Connector_JST"), ("USB_C", "Connector_USB"), ("ESP32", "Espressif")]
CONN = {2: "Connector_Generic:Conn_01x02", 3: "Connector_Generic:Conn_01x03", 4: "Connector_Generic:Conn_01x04"}
NOTES = {
    "U1": "IO4 S1, IO5 S2, IO6 LED, IO7 IR, IO8/9 CRSF, IO10/11 MSP, IO17 VBAT (ADC2)",
    "J1": "ZERO-Z: yellow S2 / blue S1 / green GND / brown 5V",
    "J2": "EP2 as a CRSF receiver: 1 its RX pad, 2 its TX pad",
    "J3": "Ascent Lite+ cable, same-direction: 1 red, 2 black, 3 white (VTX RX), 4 grey (VTX TX)",
    "J9": "A4/B9 open: VBUS through B4/A9",
    "R14": "VBAT x 22/122 to IO17",
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
        if ref == "U1":  # the module's unused pins
            for k in range(1, 66):
                nets.setdefault(str(k), "NC")
        if ref == "U3":
            nets.setdefault("4", "NC")
        if ref == "J9":
            for k in ("A8", "B8"):
                nets[k] = "NC"
        # a grid: one column per kind, the module on its own
        kind = "U1" if ref == "U1" else ref[0]
        i = col.setdefault(kind, [0])
        x0 = {"U1": 60, "U": 130, "J": 175, "D": 215, "Q": 245, "R": 275, "C": 305, "H": 335}[kind]
        y = 30 + i[0] * (22 if kind in "RCH" else 30)
        if kind == "R" and y > 260:
            x0, y = 290, y - 230
        i[0] += 1
        name = str(m.GetFPID().GetLibItemName())
        lib = next((l for pre, l in LIBS if name.startswith(pre)), "")
        out.append((ref, sym, m.GetValue(), f"{lib}:{name}" if lib else "", (x0, 100 if ref == "U1" else y),
                    nets, NOTES.get(ref, "")))
    out += [("#FLG01", "power:PWR_FLAG", "PWR_FLAG", "", (360, 30), {"1": "5V"}, "fed by the ESC's BEC"),
            ("#FLG02", "power:PWR_FLAG", "PWR_FLAG", "", (375, 30), {"1": "GND"}, ""),
            ("#FLG03", "power:PWR_FLAG", "PWR_FLAG", "", (390, 30), {"1": "VBUS"}, "USB"),
            ("#FLG04", "power:PWR_FLAG", "PWR_FLAG", "", (405, 30), {"1": "VBAT"}, "battery tap"),
            ("#FLG05", "power:PWR_FLAG", "PWR_FLAG", "", (420, 30), {"1": "VIN"}, "D2 / D3: 5V or USB")]
    return out


if __name__ == "__main__":
    write(os.path.join(HERE, "x2201-carrier-v4.kicad_sch"), "x2201-carrier-v4", "X2201 carrier board v4", "4.0",
          "FPV mount base with an ESP32-S3: CRSF in, PWM out to the ESC, VTX OSD, battery telemetry, lap transponder",
          parts(), "6b1d3c1e-2201-4a00-9000-000000000004")
