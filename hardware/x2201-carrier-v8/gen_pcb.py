"""Carrier v8 for the X2201: an ESP32-S3-MINI-1 assembled by JLC, the EP2 hand-soldered.

  EP2 2400RX --PWM--> ESC, through this board; an ESP32-S3-MINI-1 beside them for the battery and the lap IR

JLC assembles everything but the EP2, on the top side.

The EP2 drives the ESC directly, the way that already worked, and now gets its 5 V
late (Q1, C1, R1, D1). The S3 only reads the battery, flashes the lap IR and talks to
the VTX. D2 / D3 keep USB and the BEC apart.

Run with KiCad's Python:
  /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 gen_pcb.py
  (PLACE=1: placed only; FREEROUTING=<jar> or ../tools/freerouting-1.9.0.jar: route; REUSE_SES=1: keep the saved .ses; FAB=1: Gerbers, BOM)
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import pcbnew  # noqa: E402
import pcbgen  # noqa: E402
from pcbgen import drc, dump, fab, keepout, outline, place, save, text, zone, mm  # noqa: E402

OUT = os.path.join(HERE, "x2201-carrier-v8.kicad_pcb")
W, H = 46.3, 34.5
CORNER = 2.5
HOLES = [(2.5, 2.5), (W - 2.0, 2.5), (2.5, H - 2.5), (W - 2.0, H - 2.5)]

R805, C805, C1206 = "R_0805_2012Metric", "C_0805_2012Metric", "C_1206_3216Metric"
R0402, C0402 = "R_0402_1005Metric", "C_0402_1005Metric"
SOT, SOD = "SOT-23", "D_SOD-323"
ZH4 = "JST_ZH_B4B-ZR-SM4-TF_1x04-1MP_P1.50mm_Vertical"
ZH2 = "JST_ZH_B2B-ZR-SM4-TF_1x02-1MP_P1.50mm_Vertical"
SH6 = "JST_SH_BM06B-SRSS-TB_1x06-1MP_P1.00mm_Vertical"
HDR = "Connector_PinHeader_2.54mm"


def r(ref, val, x, y, rot, a, b):
    return place("Resistor_SMD", R805, ref, val, x, y, rot, {"1": a, "2": b})


def r04(ref, val, x, y, rot, a, b):
    return place("Resistor_SMD", R0402, ref, val, x, y, rot, {"1": a, "2": b})


def c(ref, val, x, y, rot, a, b, fp=C805):
    return place("Capacitor_SMD", fp, ref, val, x, y, rot, {"1": a, "2": b})


def q(ref, val, x, y, rot, g, s, d):
    return place("Package_TO_SOT_SMD", SOT, ref, val, x, y, rot, {"1": g, "2": s, "3": d})


def npth(ref, x, y, d=2.2):
    m = pcbnew.FOOTPRINT(pcbgen.board)
    m.SetReference(ref)
    m.SetValue("M2 hole")
    m.SetPosition(pcbgen.pt(x, y))
    p = pcbnew.PAD(m)
    p.SetAttribute(pcbnew.PAD_ATTRIB_NPTH)
    p.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
    p.SetSize(pcbnew.VECTOR2I(mm(d), mm(d)))
    p.SetDrillSize(pcbnew.VECTOR2I(mm(d), mm(d)))
    p.SetLayerSet(pcbnew.PAD.UnplatedHoleMask())
    m.Add(p)
    m.Reference().SetVisible(False)
    pcbgen.board.Add(m)


for i, (x, y) in enumerate(HOLES):
    npth(f"MH{i + 1}", x, y)

# ---- U1: ESP32-S3-MINI-1, antenna at the top edge ------------------------------------------
CX, CY = 21.3, 14.2
GPIO = {3: "3V3", 4: "BOOT", 13: "VBAT_ADC", 14: "MSP_RX", 15: "MSP_TX",  # left column: IO9..IO11
        19: "IR", 23: "USB_DM", 24: "USB_DP", 45: "EN"}  # bottom row: IO15, USB
U1_NETS = {str(k): v for k, v in GPIO.items()}
for n in (1, 2, 42, 43, *range(46, 66)):
    U1_NETS[str(n)] = "GND"
U1 = place("Espressif", "ESP32-S3-MINI-1", "U1", "ESP32-S3-MINI-1-N8", CX, CY, 0, U1_NETS)
c("C6", "100nF", 12.5, 7.4, 90, "3V3", "GND", C0402)
c("C10", "22uF", 11.4, 9.6, 0, "3V3", "GND")
r04("R21", "10k", 30.2, 17.6, 90, "3V3", "EN")
c("C8", "1uF", 31.4, 17.6, 90, "EN", "GND", C0402)
# the recovery pads: hold B on G while powering up to force the ROM loader
place("TestPoint", "TestPoint_Pad_1.5x1.5mm", "TP1", "BOOT", 6.0, 2.0, 0, {"1": "BOOT"})
place("TestPoint", "TestPoint_Pad_1.5x1.5mm", "TP3", "G", 8.7, 2.0, 0, {"1": "GND"})

# ---- power: BEC or USB, through a diode each, into the LDO and the EP2 ----------------------
place("Package_TO_SOT_SMD", "SOT-23-5", "U3", "AP2112K-3.3", 9.2, 12.4, 0, {"1": "VIN", "2": "GND", "3": "VIN", "5": "3V3"})
c("C9", "22uF", 12.2, 21.8, 90, "VIN", "GND")
place("Diode_SMD", SOD, "D3", "B5819WS", 37.0, 18.1, 90, {"1": "VIN", "2": "5V"})
place("Diode_SMD", SOD, "D2", "B5819WS", 14.9, 29.6, 90, {"1": "VIN", "2": "VBUS"})

# ---- USB-C under the module ----------------------------------------------------------------
place("Connector_USB", "USB_C_Receptacle_HRO_TYPE-C-31-M-12", "J9", "USB-C", CX, H - 2.8, 0, {
    "A1": "GND", "B12": "GND", "B1": "GND", "A12": "GND", "B4": "VBUS", "A9": "VBUS", "A4": "VBUS", "B9": "VBUS",
    "A5": "CC1", "B5": "CC2", "A6": "USB_DP", "B6": "USB_DP", "A7": "USB_DM", "B7": "USB_DM", "SH": "GND"})
r04("R12", "5.1k", 14.9, 24.9, 90, "CC1", "GND")
r04("R13", "5.1k", 14.9, 26.9, 90, "CC2", "GND")

# EP2 at the right, solderable either way round: a row of pads at each end
EX, EY = 34.7, 3.9
U2 = place("rc_control", "EP2_2400RX_SMD", "U2", "EP2 2400RX", EX, EY, 180, {
    "TX": "S1", "RX": "S2", "5V": "RX5V", "G": "GND"})
# The ESC holds the EP2's TX pad (ESP8285 GPIO1) low while it starts, and the EP2 hangs if it boots then:
# Q1 gives it its 5 V a moment after the BEC comes up (C1 charging through R1).
q("Q1", "AO3401", 37.0, 21.7, 0, "RXG", "5V", "RX5V")
c("C1", "10uF", 31.4, 25.7, 0, "5V", "RXG")
r04("R1", "100k", 35.1, 17.6, 90, "RXG", "GND")
place("Diode_SMD", SOD, "D1", "1N4148WS", 35.2, 25.7, 0, {"1": "RXG", "2": "GND"})

# ---- left: ESC and VTX plugs, the battery, its divider, the VTX's switch and UART -----------
J1 = place("Connector_JST", ZH4, "J1", "ZH1.5 4P (ESC)", 4.0, 9.2, 90,
           {"1": "S2", "2": "S1", "3": "GND", "4": "5V", "MP": "GND"})
J3 = place("Connector_JST", SH6, "J3", "SH1.0 6P (VTX)", 3.2, 19.9, 90,
           {"1": "VTX", "2": "GND", "3": "VTX_RX", "4": "VTX_TX", "MP": "GND"})
J6 = place("Connector_JST", ZH2, "J6", "ZH1.5 2P (battery)", 9.75, H - 3.99, 180, {"1": "VBAT", "2": "GND", "MP": "GND"})

r04("R14", "100k", 8.2, 5.0, 90, "VBAT", "VBAT_ADC")
r04("R15", "22k", 9.8, 5.0, 90, "VBAT_ADC", "GND")
c("C11", "100nF", 11.4, 5.0, 90, "VBAT_ADC", "GND", C0402)
r04("R19", "1k", 8.2, 7.2, 90, "MSP_TX", "VTX_RX")
r04("R20", "1k", 9.8, 7.2, 90, "MSP_RX", "VTX_TX")
# the VTX follows the ESC's switch: Q3 turns on with the BEC's 5 V, Q2 passes the battery
r04("R2", "100k", 12.2, 16.0, 90, "Q2G", "VBAT")
r04("R4", "1k", 12.2, 19.0, 90, "5V", "Q3G")
q("Q3", "AO3400", 9.2, 15.9, 0, "Q3G", "GND", "Q2G")
q("Q2", "AO3401", 9.2, 19.6, 0, "Q2G", "VBAT", "VTX")

# the same four signals on a plug, to wire the EP2 somewhere with better reception
J2 = place("Connector_JST", ZH4, "J2", "ZH1.5 4P (EP2)", W - 3.99, 21.8, 270,
           {"1": "S1", "2": "S2", "3": "RX5V", "4": "GND", "MP": "GND"})

# ---- right: IR and fan plugs ---------------------------------------------------------------
J5 = place("Connector_JST", ZH2, "J5", "ZH1.5 2P (IR LED)", 30.8, H - 3.99, 180,
           {"1": "LEDA", "2": "LEDK", "MP": "GND"})
J4 = place("Connector_JST", ZH2, "J4", "ZH1.5 2P (fan)", 39.0, H - 3.99, 180, {"1": "5V", "2": "GND", "MP": "GND"})
q("Q4", "AO3400", 32.0, 22.9, 0, "IR", "GND", "LEDK")
r04("R8", "100k", 33.8, 17.6, 90, "IR", "GND")
r("R6", "33", 31.4, 20.2, 0, "LEDA", "5V")

if os.environ.get("DUMP"):
    dump()
    sys.exit()
if os.environ.get("OVER"):
    bb = {}
    for m in pcbgen.board.GetFootprints():
        if m.GetReference().startswith("MH"):
            continue
        c = m.GetCourtyard(pcbnew.F_CrtYd).BBox()
        bb[m.GetReference()] = [pcbnew.ToMM(v) for v in (c.GetLeft(), c.GetTop(), c.GetRight(), c.GetBottom())]
    for a in bb:
        for b in bb:
            A, B = bb[a], bb[b]
            if a < b and A[0] < B[2] and B[0] < A[2] and A[1] < B[3] and B[1] < A[3]:
                print(a, b, [round(v, 1) for v in A], [round(v, 1) for v in B])
    sys.exit()


CLASSES = [("PWR", 0.5, 0.2, ["VBAT", "VTX"]),
           ("GROUND", 0.3, 0.15, ["GND"]),
           ("5V", 0.4, 0.15, ["5V", "VIN", "VBUS", "3V3", "RX5V"]),
           ("DRV", 0.4, 0.2, ["LEDA", "LEDK"])]


SES = OUT.replace(".kicad_pcb", ".ses")
FR = os.environ.get("FREEROUTING", os.path.join(os.path.dirname(HERE), "tools", "freerouting-1.9.0.jar"))
FR = FR if os.path.exists(FR) and not os.environ.get("REUSE_SES") else ""


def rules():
    """Net classes on the board itself: Freerouting gets its track widths from these."""
    ds = pcbgen.board.GetDesignSettings()
    ns = ds.m_NetSettings
    d = ns.GetDefaultNetclass()
    d.SetTrackWidth(mm(0.25))
    d.SetClearance(mm(0.15))
    d.SetViaDiameter(mm(0.6))
    d.SetViaDrill(mm(0.3))
    for name, w, cl, nets in CLASSES:
        nc = pcbnew.NETCLASS(name)
        nc.SetTrackWidth(mm(w))
        nc.SetClearance(mm(cl))
        nc.SetViaDiameter(mm(0.6))
        nc.SetViaDrill(mm(0.3))
        ns.SetNetclass(name, nc)
        for n in nets:
            ns.SetNetclassPatternAssignment(n, name)
    pcbgen.board.SynchronizeNetsAndNetClasses(True)


# USB: the plug's two rows cross over at the pads, so these are drawn by hand: D+ bridges A6 / B6 above the pads and
# runs straight up to the module, D- bridges B7 / A7 below them and goes under on the bottom layer.
_Y = H - 2.8  # the plug's row of pads, whatever the board's height
_P = _Y - 4.05
_T, _B, _V = _P - 1.06, _P + 1.04, _P + 1.64
USB_T = [("USB_DP", pcbnew.F_Cu, [(21.05, _P), (21.05, _T), (22.05, _T), (22.05, _P)]),
         ("USB_DP", pcbnew.F_Cu, [(22.05, _T), (22.15, _T - 0.5), (22.15, 21.2)]),
         ("USB_DM", pcbnew.F_Cu, [(20.55, _P), (20.55, _B), (21.55, _B), (21.55, _P)]),
         ("USB_DM", pcbnew.F_Cu, [(21.05, _B), (21.05, _V)]),
         ("USB_DM", pcbnew.B_Cu, [(21.05, _V), (21.05, 22.9), (21.52, 22.43), (21.52, 22.06)]),
         ("USB_DM", pcbnew.F_Cu, [(21.52, 22.06), (21.3, 21.84), (21.3, 21.2)])]
USB_V = [("USB_DM", 21.05, _V), ("USB_DM", 21.52, 22.06)]


def draw_usb():
    for t in list(pcbgen.board.GetTracks()):
        if t.GetNetname() in ("USB_DP", "USB_DM"):
            pcbgen.board.Remove(t)
    for n, layer, pts in USB_T:
        pcbgen.track(pts, n, 0.25, layer)
    for n, x, y in USB_V:
        pcbgen.via(x, y, n)


def keepout_top(x0, y0, x1, y1):
    """No tracks or vias on the top side; the pours may still fill it."""
    z = pcbnew.ZONE(pcbgen.board)
    z.SetIsRuleArea(True)
    z.SetDoNotAllowTracks(True)
    z.SetDoNotAllowVias(True)
    z.SetDoNotAllowZoneFills(False)
    z.SetDoNotAllowPads(False)
    z.SetDoNotAllowFootprints(False)
    z.SetLayer(pcbnew.F_Cu)
    o = z.Outline()
    o.NewOutline()
    for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        o.Append(mm(x), mm(y))
    pcbgen.board.Add(z)


def edge_keepout(w=0.45):
    for x0, y0, x1, y1 in ((0, 0, W, w), (0, H - w, W, H), (0, 0, w, H), (W - w, 0, W, H)):
        keepout(x0, y0, x1, y1)


def freeroute(passes):
    dsn = os.path.join(HERE, "route.dsn")
    pcbnew.ExportSpecctraDSN(pcbgen.board, dsn)
    subprocess.run(["java", "-jar", FR, "-de", dsn, "-do", SES, "-mp", str(passes), "-mt", "1"], check=True,
                   cwd=os.path.dirname(FR))
    os.remove(dsn)
    import_ses()


def import_ses():
    """KiCad stops reading at the screw holes' placement block and drops every later net: strip it."""
    s = open(SES).read()
    a, b = s.find("  (placement"), s.find("  (routes")
    if a >= 0 and b > a:
        s = s[:a] + s[b:]
    tmp = SES + ".tmp"
    open(tmp, "w").write(s)
    ok = pcbnew.ImportSpecctraSES(pcbgen.board, tmp)
    os.remove(tmp)
    if not ok:
        raise RuntimeError("SES import failed")


def routed_grid(router, keep, under):
    """The router's occupancy map, filled in with what Freerouting drew: for the stitching vias."""
    P = router.pads()
    g = router.base(W, H, HOLES, keep, under, P)
    router.DRILLS[:] = [(p["x"], p["y"]) for p in P if p["th"]]
    for t in pcbgen.board.GetTracks():
        n = t.GetNetname()
        if isinstance(t, pcbnew.PCB_VIA):
            c = t.GetPosition()
            x, y = pcbnew.ToMM(c.x), pcbnew.ToMM(c.y)
            g.add(x - 0.3, y - 0.3, x + 0.3, y + 0.3, None, n)
            router.DRILLS.append((x, y))
            continue
        a, b = t.GetStart(), t.GetEnd()
        ax, ay, bx, by = pcbnew.ToMM(a.x), pcbnew.ToMM(a.y), pcbnew.ToMM(b.x), pcbnew.ToMM(b.y)
        w = pcbnew.ToMM(t.GetWidth()) / 2
        steps = max(1, int(max(abs(ax - bx), abs(ay - by)) / 0.1))
        for i in range(steps + 1):
            x, y = ax + (bx - ax) * i / steps, ay + (by - ay) * i / steps
            g.add(x - w, y - w, x + w, y + w, 0 if t.GetLayer() == pcbnew.F_Cu else 1, n)
    return g


def tent():
    for t in pcbgen.board.GetTracks():
        if isinstance(t, pcbnew.PCB_VIA):
            t.SetFrontTentingMode(pcbnew.TENTING_MODE_TENTED)
            t.SetBackTentingMode(pcbnew.TENTING_MODE_TENTED)


# JLC's part models sit turned from KiCad's footprints; checked against JLC's SMT preview.
CPL_TURN = {"Q2": 180, "Q3": 180, "Q4": 180, "U3": 270, "D2": 180, "D3": 180, "J1": 180, "J3": 180, "J2": 180, "Q1": 180, "D1": 180}
CPL_MOVE_Y = {"J9": 1.5}  # mm toward the top of the board: JLC's model has its origin elsewhere than KiCad's footprint


def cpl_rotation():
    import csv
    path = os.path.join(HERE, "cpl.csv")
    rows = list(csv.reader(open(path)))
    for row in rows[1:]:
        row[4] = str((int(float(row[4])) + CPL_TURN.get(row[0], 0)) % 360)
        if row[0] in CPL_MOVE_Y:
            row[2] = f"{float(row[2].replace('mm', '')) + CPL_MOVE_Y[row[0]]:.3f}mm"
    with open(path, "w", newline="") as f:
        csv.writer(f).writerows(rows)


def prune():
    """Dangling stubs the router leaves where a branch starts."""
    import json
    rpt = OUT + ".json"
    for _ in range(6):
        subprocess.run([pcbgen.CLI, "pcb", "drc", "--refill-zones", "--format", "json", "--severity-all", "-o", rpt, OUT],
                       capture_output=True)
        dead = {i["uuid"] for v in json.load(open(rpt))["violations"] if v["type"] == "track_dangling" for i in v["items"]}
        if not dead:
            break
        for t in list(pcbgen.board.GetTracks()):
            if t.m_Uuid.AsString() in dead:
                pcbgen.board.Remove(t)
        pcbnew.ZONE_FILLER(pcbgen.board).Fill(pcbgen.board.Zones())
        save(OUT)
    os.remove(rpt)


def labels():
    for s_, x, y in [("B", 6.0, 3.75), ("G", 8.7, 3.75), ("ESC", 4.0, 14.9), ("VTX", 3.2, 25.4), ("BAT", 7.5, H - 7.6),
                     ("IR", 27.8, H - 7.6), ("FAN", 37.7, H - 7.6), ("EP2 wire", W - 3.6, 15.4),
                     ("G", EX - 3.6, 1.4), ("5V", EX - 1.2, 1.4), ("RX", EX + 1.2, 1.4), ("TX", EX + 3.6, 1.4),
                     ("TX", EX - 3.6, 16.0), ("RX", EX - 1.2, 16.0), ("5V", EX + 1.2, 16.0), ("G", EX + 3.6, 16.0),
                     ("EP2", EX, 8.6)]:
        text(s_, x, y, 0.8)
    text("X2201 carrier v8", 36.0, 32.2, 1.0, pcbnew.B_SilkS)


if __name__ == "__main__":
    outline(0, 0, W, H, CORNER)
    # no copper by the modules' antennas
    keepout(CX - 8.0, 0, CX + 8.0, CY - 7.6)
    keepout(EX - 4.0, EY + 1.2, EX + 5.2, EY + 8.8)  # between the two rows of pads: under its antenna either way round
    if os.environ.get("PLACE"):
        pcbgen.project(OUT, CLASSES)
        save(OUT)
        for line in drc(OUT):
            print(line)
        sys.exit()
    labels()
    rules()
    pcbgen.project(OUT, CLASSES, default=(0.25, 0.15))
    import router
    KEEP = [(CX - 8.0, 0, CX + 8.0, CY - 7.6), (EX - 4.0, EY + 1.2, EX + 5.2, EY + 8.8)]
    UNDER = []
    edge_keepout()
    draw_usb()
    if FR:
        freeroute(100)
        freeroute(100)  # again, from what the first pass left
    elif os.path.exists(SES):
        import_ses()
    else:
        raise SystemExit("no routing: set FREEROUTING=<jar>")
    draw_usb()
    grid = routed_grid(router, KEEP, UNDER)
    router.stitch(grid, W, H, UNDER, router.pads())
    tent()
    for l in (pcbnew.F_Cu, pcbnew.B_Cu):
        zone("GND", l, 0.3, 0.3, W - 0.3, H - 0.3, chamfer=1.2)
    pcbnew.ZONE_FILLER(pcbgen.board).Fill(pcbgen.board.Zones())
    save(OUT)
    prune()
    for line in drc(OUT):
        print(line)
    if os.environ.get("FAB"):
        fab(OUT, fitted="QCRDJU")
        cpl_rotation()
