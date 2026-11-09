"""Carrier v7 for the X2201: ready-made modules on a simple 2-layer board.

  EP2 2400RX --CRSF--> ESP32-S3-Zero --PWM--> ESC

Hand-soldered: the two modules sit on through-hole pads, every other part is
0805 / SOT-23 / SOD-323 on the top side.

Four jobs, nothing spare: battery voltage, lap-timing IR, the EP2 starting
reliably (the S3 sits between it and the ESC; R11 holds its TX pad high), and
wiring. D3 keeps USB out of the BEC (the S3-Zero's 5V pad IS its USB VBUS).

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

OUT = os.path.join(HERE, "x2201-carrier-v7.kicad_pcb")
W, H = 47.0, 30.0
CORNER = 2.5
HOLES = [(2.5, 2.5), (W - 2.5, 2.5), (2.5, H - 2.5), (W - 2.5, H - 2.5)]

R805, C805, C1206 = "R_0805_2012Metric", "C_0805_2012Metric", "C_1206_3216Metric"
SOT, SOD = "SOT-23", "D_SOD-323"
ZH4 = "JST_ZH_B4B-ZR-SM4-TF_1x04-1MP_P1.50mm_Vertical"
ZH2 = "JST_ZH_B2B-ZR-SM4-TF_1x02-1MP_P1.50mm_Vertical"
SH4 = "JST_SH_BM04B-SRSS-TB_1x04-1MP_P1.00mm_Vertical"
HDR = "Connector_PinHeader_2.54mm"


def r(ref, val, x, y, rot, a, b):
    return place("Resistor_SMD", R805, ref, val, x, y, rot, {"1": a, "2": b})


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

# ---- the modules: S3-Zero with its USB at the bottom edge, antenna toward the top ----------
CX, CY = 22.3, H - 11.75
U1 = place("rc_control", "ESP32-S3-Zero", "U1", "ESP32-S3-Zero", CX, CY, 180, {
    "5V": "5VM", "GND": "GND", "3V3": "3V3",
    "4": "IR", "5": "CRSF_RX", "6": "CRSF_TX",  # the board's right side
    "7": "S2", "8": "S1", "9": "VBAT_ADC", "11": "MSP_TX", "12": "MSP_RX"})  # the board's left side
# EP2 at the top right, its ceramic antenna at the top edge
EX, EY = 38.0, 13.0
U2 = place("rc_control", "EP2_2400RX", "U2", "EP2 2400RX", EX, EY, 0, {
    "TX": "CRSF_RX", "RX": "CRSF_TX", "5V": "5VM", "G": "GND"})
# The EP2 hung at power-up when its TX pad (ESP8285 GPIO1) was held low: keep it high from the first moment.
r("R11", "10k", 34.2, 17.0, 90, "3V3", "CRSF_RX")

# ---- left: ESC and VTX plugs, the battery, its divider and the VTX's switch ----------------
J1 = place("Connector_JST", ZH4, "J1", "ZH1.5 4P (ESC)", 4.0, 9.2, 90,
           {"1": "S2", "2": "S1", "3": "GND", "4": "5V", "MP": "GND"})
J3 = place("Connector_JST", SH4, "J3", "SH1.0 4P (VTX)", 3.2, 18.9, 90,
           {"1": "VTX", "2": "GND", "3": "VTX_RX", "4": "VTX_TX", "MP": "GND"})
J6 = place("Connector_JST", ZH2, "J6", "ZH1.5 2P (battery)", 7.75, H - 3.99, 180, {"1": "VBAT", "2": "GND", "MP": "GND"})

r("R14", "100k", 8.2, 5.2, 90, "VBAT", "VBAT_ADC")
r("R15", "22k", 10.5, 5.2, 90, "VBAT_ADC", "GND")
c("C11", "100nF", 10.5, 8.9, 90, "VBAT_ADC", "GND")

# the VTX follows the ESC's switch: Q3 turns on with the BEC's 5 V, Q2 passes the battery
r("R2", "100k", 8.2, 8.9, 90, "Q2G", "VBAT")
r("R4", "1k", 6.5, 2.0, 0, "5V", "Q3G")
# the VTX's UART (MSP DisplayPort OSD): the resistors keep the S3 off a powered-down VTX
r("R19", "1k", 8.2, 12.45, 90, "MSP_TX", "VTX_RX")
r("R20", "1k", 10.5, 12.45, 90, "MSP_RX", "VTX_TX")
q("Q2", "AO3401", 9.5, 19.6, 0, "Q2G", "VBAT", "VTX")
q("Q3", "AO3400", 9.5, 15.9, 0, "Q3G", "GND", "Q2G")

# ---- right: IR and fan plugs ---------------------------------------------------------------
J5 = place("Connector_JST", ZH2, "J5", "ZH1.5 2P (IR LED)", 37.0, H - 3.99, 180,
           {"1": "LEDA", "2": "LEDK", "MP": "GND"})
J4 = place("Connector_JST", ZH2, "J4", "ZH1.5 2P (fan)", H + 13.01, 18.8, 270,
           {"1": "5V", "2": "GND", "MP": "GND"})
q("Q4", "AO3400", 37.4, 20.8, 0, "IR", "GND", "LEDK")
r("R8", "100k", 36.6, 17.0, 90, "IR", "GND")
r("R6", "33", 34.2, 20.8, 90, "LEDA", "5V")
c("C10", "22uF", 45.4, 9.2, 90, "5VM", "GND")
place("Diode_SMD", SOD, "D3", "B5819WS", 42.3, 25.9, 270, {"1": "5VM", "2": "5V"})

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
           ("5V", 0.4, 0.15, ["5V", "5VM"]),
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
    for s_, x, y in [("ESC", 4.0, 14.9), ("VTX", 3.2, 23.6), ("BAT", 7.75, 22.6), ("IR", 42.4, 23.4), ("FAN", 45.2, 13.6),
                     ("TX", EX - 3.81, 14.8), ("RX", EX - 1.27, 14.8), ("5V", EX + 1.27, 14.8), ("G", EX + 3.81, 14.8),
                     ("EP2", EX, 7.5), ("S3-Zero", CX, 8.0)]:
        text(s_, x, y, 0.8)
    b = pcbnew.B_SilkS
    text("X2201 carrier v7", 40.0, 5.0, 1.0, b)


if __name__ == "__main__":
    outline(0, 0, W, H, CORNER)
    # no copper by the modules' antennas
    keepout(CX - 7.4, 0, CX + 7.4, CY - 11.75 + 3.6)
    keepout(EX - 7.0, 0, EX + 7.0, EY - 6.6)
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
    KEEP = [(CX - 7.4, 0, CX + 7.4, CY - 11.75 + 3.6), (EX - 7.0, 0, EX + 7.0, EY - 6.6)]
    UNDER = [(CX - 7.6, CY - 11.75, CX + 7.6, H)]  # the S3-Zero's exposed back pads: nothing on top, no vias
    for x0, y0, x1, y1 in UNDER:
        keepout_top(x0, y0, x1, y1)
    edge_keepout()
    if FR:
        freeroute(100)
        freeroute(100)  # again, from what the first pass left
    elif os.path.exists(SES):
        import_ses()
    else:
        raise SystemExit("no routing: set FREEROUTING=<jar>")
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
        fab(OUT, fitted="QCRDJ")
