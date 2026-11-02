#!/usr/bin/env python3
"""Generate the X2201 carrier board schematic (x2201-carrier.kicad_sch).

A passive board: no chips, only pads and connectors so the Lite RX, the
ZERO-Z ESC, the servo, the lights and the FPV power meet in one place
instead of a nest of wires. Each part's pins get net labels; the board
layout is drawn later, once the real parts are measured.
"""
import os
import re
import uuid

LIB = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "x2201-carrier.kicad_sch")

ns = uuid.UUID("6b1d3c1e-2201-4a00-9000-000000000000")
def uid(*k):
    return str(uuid.uuid5(ns, "/".join(map(str, k))))
ROOT = uid("root")

def block(text, start):
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    raise ValueError("unbalanced")

_libs = {}
def lib_symbol(lib_id):
    lib, name = lib_id.split(":")
    if lib not in _libs:
        _libs[lib] = open(os.path.join(LIB, lib + ".kicad_sym")).read()
    text = _libs[lib]
    m = re.search(r'^\t\(symbol "%s"' % re.escape(name), text, re.M)
    body = block(text, m.start() + 1)
    if "(extends" in body:
        raise ValueError(lib_id + " extends another symbol")
    pins = {}
    for p in re.finditer(r"\(pin \w+ \w+", body):
        pb = block(body, p.start())
        at = re.search(r"\(at ([-\d.]+) ([-\d.]+) ([-\d.]+)\)", pb)
        num = re.search(r'\(number "([^"]+)"', pb).group(1)
        pins[num] = tuple(float(v) for v in at.groups())
    body = body.replace('(symbol "%s"' % name, '(symbol "%s"' % lib_id, 1)
    return body, pins

# ref, lib_id, value, footprint, (x, y), {pin: net}, note
ZH4 = "Connector_JST:JST_ZH_B4B-ZR_1x04_P1.50mm_Vertical"
ZH3 = "Connector_JST:JST_ZH_B3B-ZR_1x03_P1.50mm_Vertical"
H2 = "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical"
H3 = "Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical"
H4 = "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical"
PH2 = "Connector_JST:JST_PH_B2B-PH-K_1x02_P2.00mm_Vertical"
PARTS = [
    ("J1", "Connector_Generic:Conn_01x04", "ESC RX port (ZH1.5 4P)", ZH4, (40, 50),
     {"1": "S2_THR", "2": "S1_STEER", "3": "GND", "4": "+5V"},
     "ZERO-Z order: S2 / S1 / GND / 5V"),
    ("J2", "Connector_Generic:Conn_01x04", "Lite RX pads", H4, (110, 50),
     {"1": "+5V", "2": "GND", "3": "S1_STEER", "4": "S2_THR"},
     "TX = CH1 steering, RX = CH2 throttle; footprint TBD after measuring"),
    ("C1", "Device:C_Polarized", "220uF 10V", "Capacitor_Tantalum_SMD:CP_EIA-7343-20_Kemet-V_HandSolder",
     (150, 45), {"1": "+5V", "2": "GND"}, "bulk cap for servo current spikes"),
    ("C2", "Device:C", "100nF", "Capacitor_SMD:C_0805_2012Metric_Pad1.18x1.45mm_HandSolder",
     (165, 45), {"1": "+5V", "2": "GND"}, ""),
    ("J3", "Connector_Generic:Conn_01x03", "Servo (2.54 3P)", H3, (40, 88),
     {"1": "SERVO", "2": "+5V", "3": "GND"}, "standard servo plug: signal / + / -"),
    ("J4", "Connector_Generic:Conn_01x03", "ESC servo port (ZH1.5 3P)", ZH3, (110, 88),
     {"1": "SERVO", "2": "+5V", "3": "GND"}, "pin order TBD on arrival"),
    ("J5", "Connector_Generic:Conn_01x02", "ESC light out", H2, (40, 125),
     {"1": "LED+", "2": "LED-"}, ""),
    ("R1", "Device:R", "0R", "Resistor_SMD:R_0805_2012Metric_Pad1.20x1.40mm_HandSolder",
     (80, 120), {"1": "LED+", "2": "LED_F"}, "front LED series resistor, 0R if the ESC limits current"),
    ("R2", "Device:R", "0R", "Resistor_SMD:R_0805_2012Metric_Pad1.20x1.40mm_HandSolder",
     (95, 120), {"1": "LED+", "2": "LED_R"}, "rear LED series resistor"),
    ("J6", "Connector_Generic:Conn_01x02", "Front lights", H2, (130, 125),
     {"1": "LED_F", "2": "LED-"}, ""),
    ("J7", "Connector_Generic:Conn_01x02", "Rear lights", H2, (165, 125),
     {"1": "LED_R", "2": "LED-"}, ""),
    ("JP1", "Jumper:SolderJumper_3_Open", "FPV power select", "Jumper:SolderJumper-3_P1.3mm_Open_Pad1.0x1.5mm",
     (95, 157), {"1": "VBAT", "2": "FPV_V", "3": "+5V"}, "bridge 1-2 for VBAT, 2-3 for 5V"),
    ("J9", "Connector_Generic:Conn_01x02", "FPV power out", H2, (150, 160),
     {"1": "FPV_V", "2": "GND"}, ""),
    # battery -> car power switch -> ESC; the ESC drives the motor
    ("J8", "Connector_Generic:Conn_01x02", "Battery in", PH2, (205, 45),
     {"1": "BAT_IN", "2": "GND"}, "connector TBD: match the battery lead"),
    ("J10", "Connector_Generic:Conn_01x02", "Power switch (PH2.0)", PH2, (245, 45),
     {"1": "BAT_IN", "2": "VBAT"}, "the car's own switch, in series with battery +"),
    ("J12", "Connector_Generic:Conn_01x02", "ESC power pads", H2, (205, 80),
     {"1": "VBAT", "2": "GND"}, "ESC B+ / B- wires"),
    ("J11", "Connector_Generic:Conn_01x02", "ESC motor pads", H2, (205, 115),
     {"1": "MOT_A", "2": "MOT_B"}, "ESC M+ / M- wires"),
    ("J13", "Connector_Generic:Conn_01x02", "Motor (PH2.0)", PH2, (245, 115),
     {"1": "MOT_A", "2": "MOT_B"}, "the car's motor plug"),
    ("H1", "Mechanical:MountingHole", "M2", "MountingHole:MountingHole_2.2mm_M2_Pad", (240, 80), {}, ""),
    ("H2", "Mechanical:MountingHole", "M2", "MountingHole:MountingHole_2.2mm_M2_Pad", (255, 80), {}, ""),
]

def r(v):
    return round(v, 3)

def main():
    libs, out = {}, []
    g = lambda v: r(round(v / 2.54) * 2.54)
    for ref, lib_id, value, fp, (x, y), nets, note in PARTS:
        x, y = g(x), g(y)
        if lib_id not in libs:
            libs[lib_id] = lib_symbol(lib_id)
        _, pins = libs[lib_id]
        props = [("Reference", ref, 0, -1), ("Value", value, 0, 1),
                 ("Footprint", fp, 0, 2), ("Datasheet", "", 0, 3)]
        if note:
            props.append(("Note", note, 0, 4))
        p = "\n".join(
            '\t\t(property "%s" "%s" (at %s %s 0) (effects (font (size 1.27 1.27))%s))'
            % (k, v, r(x + 8), r(y + 3 * dy + (-6 if dy < 0 else 6)),
               "" if k in ("Reference", "Value") else " (hide yes)")
            for k, v, _, dy in props)
        pin_uuids = "\n".join('\t\t(pin "%s" (uuid "%s"))' % (n, uid(ref, n)) for n in pins)
        out.append(
            '\t(symbol (lib_id "%s") (at %s %s 0) (unit 1) (exclude_from_sim no) (in_bom yes) '
            '(on_board yes) (dnp no) (uuid "%s")\n%s\n%s\n'
            '\t\t(instances (project "x2201-carrier" (path "/%s" (reference "%s") (unit 1))))\n\t)'
            % (lib_id, x, y, uid(ref), p, pin_uuids, ROOT, ref))
        for num, net in nets.items():
            px, py, ang = pins[num]
            lx, ly = r(x + px), r(y - py)
            # the label sits on the pin end, facing away from the body
            la = {0: 180, 180: 0, 90: 270, 270: 90}[int(ang)]
            just = "right" if la == 180 else "left"
            out.append('\t(label "%s" (at %s %s %d) (effects (font (size 1.27 1.27)) (justify %s bottom)) (uuid "%s"))'
                       % (net, lx, ly, la if la in (0, 180) else la, just, uid(ref, num, "label")))
    text = ['(kicad_sch (version 20250114) (generator "gen_sch.py") (generator_version "10.0")',
            '\t(uuid "%s")' % ROOT, '\t(paper "A4")',
            '\t(title_block (title "X2201 carrier board") (rev "0.1") (comment 1 "passive: power, Lite RX, ZERO-Z, motor, servo, lights, FPV"))',
            "\t(lib_symbols"]
    text += ["\t\t" + body.replace("\n", "\n\t") for body, _ in libs.values()]
    text.append("\t)")
    text += out
    text.append('\t(sheet_instances (path "/" (page "1")))')
    text.append(")")
    with open(OUT, "w") as f:
        f.write("\n".join(text) + "\n")
    print("wrote", OUT)

if __name__ == "__main__":
    main()
