"""Helpers for the board scripts (gen_pcb.py in each board's folder): one
board per process, built with KiCad's own Python (pcbnew).

  /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 gen_pcb.py

Coordinates are millimetres, KiCad's (y down).
"""

import csv
import os
import zipfile
import subprocess

import pcbnew

FP = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints/"
LIB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib")  # footprints KiCad doesn't ship (Espressif's)
CLI = "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
W_SIG, W_PWR = 0.3, 0.6
VIA_D, VIA_HOLE = 0.6, 0.3


def mm(v):
    return pcbnew.FromMM(v)


def pt(x, y):
    return pcbnew.VECTOR2I(mm(x), mm(y))


board = pcbnew.CreateEmptyBoard()
board.SetCopperLayerCount(2)
_ds = board.GetDesignSettings()
_ds.m_CopperEdgeClearance = mm(0.5)
_ds.m_TrackMinWidth = mm(0.15)
_ds.m_ViasMinSize = mm(0.5)
_ds.m_MinClearance = mm(0.15)

NETS = {}


def net(name):
    if name not in NETS:
        n = pcbnew.NETINFO_ITEM(board, name)
        board.Add(n)
        NETS[name] = n
    return NETS[name]


def layers(n):
    """Copper layer count (2 or 4)."""
    board.SetCopperLayerCount(n)


# A side-entry plug's rotation for its opening to face a board edge: on the
# top, and on the bottom (flipped left-right, then turned).
FACE = {"F": {"+y": 0, "+x": 90, "-y": 180, "-x": 270}, "B": {"-y": 0, "-x": 90, "+y": 180, "+x": 270}}


def place(lib, name, ref, value, x, y, rot=0.0, pads=None, side="F"):
    """A library footprint, its pads' nets from {pad number: net}; side "B"
    puts it on the bottom. Refs stay hidden: the labels are drawn where they
    help; refs are in the BOM / CPL."""
    local = os.path.join(LIB, lib + ".pretty")
    m = pcbnew.FootprintLoad(local if os.path.isdir(local) else FP + lib + ".pretty", name)
    m.SetReference(ref)
    m.SetValue(value)
    m.SetPosition(pt(x, y))
    board.Add(m)
    if side == "B":
        m.Flip(m.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    m.SetOrientationDegrees(rot)
    for p in m.Pads():
        if pads and p.GetNumber() in pads:
            p.SetNet(net(pads[p.GetNumber()]))
    m.Value().SetVisible(False)
    m.Reference().SetVisible(False)
    return m


def pad(m, n):
    p = [p for p in m.Pads() if p.GetNumber() == str(n)][0].GetPosition()
    return pcbnew.ToMM(p.x), pcbnew.ToMM(p.y)


def track(points, name, w=W_SIG, layer=pcbnew.F_Cu):
    for a, b in zip(points, points[1:]):
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(pt(*a))
        t.SetEnd(pt(*b))
        t.SetWidth(mm(w))
        t.SetLayer(layer)
        t.SetNet(net(name))
        board.Add(t)


def via(x, y, name):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(pt(x, y))
    v.SetDrill(mm(VIA_HOLE))
    v.SetWidth(mm(VIA_D))
    v.SetNet(net(name))
    board.Add(v)


def text(s, x, y, size=0.9, layer=pcbnew.F_SilkS, rot=0.0):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(s)
    t.SetMirrored(layer == pcbnew.B_SilkS)
    t.SetPosition(pt(x, y))
    t.SetLayer(layer)
    t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size)))
    t.SetTextThickness(mm(size * 0.15))
    t.SetTextAngleDegrees(rot)
    board.Add(t)


def outline(x0, y0, x1, y1, r):
    """A rounded rectangle on Edge.Cuts."""
    segs = [((x0 + r, y0), (x1 - r, y0)), ((x1, y0 + r), (x1, y1 - r)), ((x1 - r, y1), (x0 + r, y1)),
            ((x0, y1 - r), (x0, y0 + r))]
    for a, b in segs:
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(pt(*a))
        s.SetEnd(pt(*b))
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(mm(0.1))
        board.Add(s)
    for cx, cy, sx, sy in ((x0 + r, y0 + r, -1, 0), (x1 - r, y0 + r, 0, -1), (x1 - r, y1 - r, 1, 0),
                           (x0 + r, y1 - r, 0, 1)):
        a = pcbnew.PCB_SHAPE(board)
        a.SetShape(pcbnew.SHAPE_T_ARC)
        a.SetCenter(pt(cx, cy))
        a.SetStart(pt(cx + sx * r, cy + sy * r))
        a.SetArcAngleAndEnd(pcbnew.EDA_ANGLE(90, pcbnew.DEGREES_T), True)
        a.SetLayer(pcbnew.Edge_Cuts)
        a.SetWidth(mm(0.1))
        board.Add(a)


def nut(ref, x, y, d=4.4, hole=2.4, name="GND", paste=True, value="M2 SMT nut"):
    """An SMT nut (e.g. Wurth 9774020151R, M2 x 2): a round pad with paste,
    the screw's hole through it."""
    m = pcbnew.FOOTPRINT(board)
    m.SetReference(ref)
    m.SetValue(value)
    m.SetPosition(pt(x, y))
    p = pcbnew.PAD(m)
    p.SetAttribute(pcbnew.PAD_ATTRIB_PTH)
    p.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
    p.SetSize(pcbnew.VECTOR2I(mm(d), mm(d)))
    p.SetDrillSize(pcbnew.VECTOR2I(mm(hole), mm(hole)))
    ls = pcbnew.PAD.PTHMask()
    if paste:
        ls.AddLayer(pcbnew.F_Paste)  # the nut is reflowed on
    p.SetLayerSet(ls)
    p.SetNumber("1")
    p.SetPosition(pt(x, y))
    m.Add(p)
    p.SetNet(net(name))
    m.Reference().SetVisible(False)
    m.Value().SetVisible(False)
    board.Add(m)
    return m


def mhole(ref, x, y, hole=2.2, d=3.8, name="GND"):
    """A plated mounting hole for the stack's M2 screws."""
    return nut(ref, x, y, d=d, hole=hole, name=name, paste=False, value="M2 hole")


def zone(name, layer, x0, y0, x1, y1, chamfer=0.0):
    """A pour; chamfer cuts its corners (inside a rounded board outline)."""
    z = pcbnew.ZONE(board)
    z.SetLayer(layer)
    z.SetNet(net(name))
    o = z.Outline()
    o.NewOutline()
    c = chamfer
    pts = ((x0, y0), (x1, y0), (x1, y1), (x0, y1)) if not c else (
        (x0 + c, y0), (x1 - c, y0), (x1, y0 + c), (x1, y1 - c), (x1 - c, y1), (x0 + c, y1), (x0, y1 - c), (x0, y0 + c))
    for x, y in pts:
        o.Append(mm(x), mm(y))
    z.SetLocalClearance(mm(0.3))
    z.SetMinThickness(mm(0.25))
    z.SetThermalReliefGap(mm(0.3))
    z.SetThermalReliefSpokeWidth(mm(0.4))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)  # small pads in tight spots: no thermal spokes to starve
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)  # no floating copper
    board.Add(z)
    return z


def keepout(x0, y0, x1, y1):
    """No copper at all (tracks, vias, pours), every copper layer: an antenna."""
    z = pcbnew.ZONE(board)
    z.SetIsRuleArea(True)
    z.SetDoNotAllowTracks(True)
    z.SetDoNotAllowVias(True)
    z.SetDoNotAllowZoneFills(True)
    z.SetDoNotAllowPads(False)
    z.SetDoNotAllowFootprints(False)
    ls = pcbnew.LSET()
    for l in ((pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu) if board.GetCopperLayerCount() == 4
              else (pcbnew.F_Cu, pcbnew.B_Cu)):
        ls.AddLayer(l)
    z.SetLayerSet(ls)
    o = z.Outline()
    o.NewOutline()
    for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        o.Append(mm(x), mm(y))
    board.Add(z)
    return z


def save(path):
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(path)
    lock = os.path.join(os.path.dirname(path), "~" + os.path.basename(path).replace(".kicad_pcb", ".kicad_pro.lck"))
    if os.path.exists(lock):
        os.remove(lock)
    print("saved", path)


# LCSC numbers for JLCPCB assembly, by (value, footprint). Blank: let JLC's BOM tool match it.
LCSC = {
    ("10uF", "C_0805_2012Metric"): "C15850",
    ("22uF", "C_0805_2012Metric"): "C45783",
    ("22uF 25V", "C_1206_3216Metric"): "C12891",
    ("100nF", "C_0603_1608Metric"): "C14663",
    ("1N4148WS", "D_SOD-323"): "C2128",
    ("AO3401", "SOT-23"): "C15127",
    ("AO3400", "SOT-23"): "C20917",
    ("47k", "R_0603_1608Metric"): "C25819",
    ("1k", "R_0603_1608Metric"): "C21190",
    ("100", "R_0603_1608Metric"): "C22775",
    ("100k", "R_0603_1608Metric"): "C25803",
    ("CH32V003J4M6", "SOIC-8_3.9x4.9mm_P1.27mm"): "C5299908",
    ("ZH1.5 4P (ESC)", "JST_ZH_B4B-ZR-SM4-TF_1x04-1MP_P1.50mm_Vertical"): "C265083",
    ("ZH1.5 4P (EP2)", "JST_ZH_B4B-ZR-SM4-TF_1x04-1MP_P1.50mm_Vertical"): "C265083",
    ("SH1.0 4P (VTX)", "JST_SH_BM04B-SRSS-TB_1x04-1MP_P1.00mm_Vertical"): "C160390",
}
LCSC.update({  # v4
    ("ESP32-S3-MINI-1-N8", "ESP32-S3-MINI-1"): "C2913206",
    ("AP2112K-3.3", "SOT-23-5"): "C51118",
    ("USB-C", "USB_C_Receptacle_HRO_TYPE-C-31-M-12"): "C165948",
    ("B5819W", "D_SOD-123"): "C8598",
    ("green", "LED_0603_1608Metric"): "C72043",
    ("10k", "R_0603_1608Metric"): "C25804",
    ("5.1k", "R_0603_1608Metric"): "C23186",
    ("22k", "R_0603_1608Metric"): "C31850",
    ("220", "R_0603_1608Metric"): "C22962",
    ("1uF", "C_0603_1608Metric"): "C15849",
    ("10uF", "C_0603_1608Metric"): "C19702",
    ("22uF", "C_0805_2012Metric"): "C45783",
})
LCSC.update({  # v5
    ("LMR51430XDDCR", "SOT-23-6"): "C5185863",
    ("4.7uH", "L_7.3x7.3_H3.5"): "C207840",  # Sunltech SLO0630H4R7MTT, 6.6 x 7.1, 5.5 A
    ("3k", "R_0603_1608Metric"): "C4211",
    ("SH1.0 6P (Thinker power)", "JST_SH_BM06B-SRSS-TB_1x06-1MP_P1.00mm_Vertical"): "C160392",
    ("SH1.0 4P (Thinker USB)", "JST_SH_BM04B-SRSS-TB_1x04-1MP_P1.00mm_Vertical"): "C160390",
    ("ZH1.5 8P (WiFi)", "JST_ZH_B8B-ZR-SM4-TF_1x08-1MP_P1.50mm_Vertical"): "C265368",
    ("PH2.0 2P (battery)", "JST_PH_B2B-PH-SM4-TB_1x02-1MP_P2.00mm_Vertical"): "C160352",
    # v5's ELRS receiver
    ("ESP32-C3FH4", "QFN-32-1EP_5x5mm_P0.5mm_EP3.7x3.7mm"): "C2858491",
    ("SX1280IMLTRT", "QFN-24-1EP_4x4mm_P0.5mm_EP2.6x2.6mm"): "C125969",
    ("AT2401C", "QFN-16-1EP_3x3mm_P0.5mm_EP1.7x1.7mm"): "C783588",
    ("2450FM07D0034T", "2450FM07D0034"): "C2651081",
    ("40MHz", "Crystal_SMD_2016-4Pin_2.0x1.6mm"): "C49158179",  # JLYE Y201640MDBCX, 9 pF, +-10 ppm
    ("52MHz", "Crystal_SMD_2016-4Pin_2.0x1.6mm"): "C841202",  # as the F722 board's SX1280
    ("U.FL (ELRS)", "U.FL_Hirose_U.FL-R-SMT-1_Vertical"): "C88374",
    ("U.FL (receiver WiFi)", "U.FL_Hirose_U.FL-R-SMT-1_Vertical"): "C88374",
    ("2nH", "L_0402_1005Metric"): "C43365",  # 300 mA (Espressif prefers >= 500 mA)
    ("3nH", "L_0402_1005Metric"): "C269824",
    ("24nH", "L_0402_1005Metric"): "C74301",
    ("15uH", "L_0805_2012Metric"): "C486333",
    ("1.2pF", "C_0402_1005Metric"): "C327292",
    ("10pF", "C_0402_1005Metric"): "C32949",
    ("10nF", "C_0402_1005Metric"): "C15195",
    ("470nF", "C_0402_1005Metric"): "C47339",
    # v5, the 30 x 34 stack board: 0402 passives, side-entry plugs
    ("1uF", "C_0402_1005Metric"): "C52923",
    ("100nF", "C_0402_1005Metric"): "C1525",
    ("10k", "R_0402_1005Metric"): "C25744",
    ("100k", "R_0402_1005Metric"): "C25741",
    ("1k", "R_0402_1005Metric"): "C11702",
    ("3k", "R_0402_1005Metric"): "C25784",
    ("100", "R_0402_1005Metric"): "C25076",
    ("5.1k", "R_0402_1005Metric"): "C25905",
    ("22k", "R_0402_1005Metric"): "C25768",
    ("220", "R_0402_1005Metric"): "C25091",
    ("47k", "R_0402_1005Metric"): "C25792",
    ("33", "R_0805_2012Metric"): "C17634",
    ("B5819WS", "D_SOD-323"): "C7420331",
    ("4.7uH", "L_Changjiang_FXL0420"): "C167208",
    ("ZH1.5 4P (ESC)", "JST_ZH_S4B-ZR-SM4A-TF_1x04-1MP_P1.50mm_Horizontal"): "C485354",
    ("SH1.0 6P (Thinker power)", "JST_SH_SM06B-SRSS-TB_1x06-1MP_P1.00mm_Horizontal"): "C160405",
    ("SH1.0 8P (WiFi)", "JST_SH_SM08B-SRSS-TB_1x08-1MP_P1.00mm_Horizontal"): "C160407",
    ("SH1.0 4P (Thinker USB)", "JST_SH_SM04B-SRSS-TB_1x04-1MP_P1.00mm_Horizontal"): "C160404",
    ("SH1.0 2P (fan)", "JST_SH_SM02B-SRSS-TB_1x02-1MP_P1.00mm_Horizontal"): "C160402",
    ("SH1.0 2P (IR LED)", "JST_SH_SM02B-SRSS-TB_1x02-1MP_P1.00mm_Horizontal"): "C160402",
    ("PH2.0 2P (battery)", "JST_PH_S2B-PH-SM4-TB_1x02-1MP_P2.00mm_Horizontal"): "C295747",
    ("U.FL (brain WiFi)", "U.FL_Hirose_U.FL-R-SMT-1_Vertical"): "C88374",
})
LCSC.update({  # v7, 0805 for hand soldering; numbers checked on szlcsc 2026-11-09
    ("0", "R_0805_2012Metric"): "C17477",
    ("33", "R_0805_2012Metric"): "C17634",
    ("100", "R_0805_2012Metric"): "C17408",
    ("220", "R_0805_2012Metric"): "C17557",
    ("1k", "R_0805_2012Metric"): "C17513",
    ("10k", "R_0805_2012Metric"): "C17414",
    ("22k", "R_0805_2012Metric"): "C17560",
    ("47k", "R_0805_2012Metric"): "C17713",
    ("100k", "R_0805_2012Metric"): "C149504",
    ("100nF", "C_0805_2012Metric"): "C49678",
    ("ZH1.5 2P (battery)", "JST_ZH_B2B-ZR-SM4-TF_1x02-1MP_P1.50mm_Vertical"): "C265284",
    ("ZH1.5 2P (IR LED)", "JST_ZH_B2B-ZR-SM4-TF_1x02-1MP_P1.50mm_Vertical"): "C265284",
    ("SH1.0 4P (fan + NTC)", "JST_SH_BM04B-SRSS-TB_1x04-1MP_P1.00mm_Vertical"): "C160390",
    ("SH1.0 4P (lights)", "JST_SH_BM04B-SRSS-TB_1x04-1MP_P1.00mm_Vertical"): "C160390",
    ("B5819WS", "D_SOD-323"): "C7420331",
})
LCSC.update({("SH1.0 4P (EP2)", "JST_SH_BM04B-SRSS-TB_1x04-1MP_P1.00mm_Vertical"): "C160390"})
LCSC.update({("SH1.0 6P (VTX)", "JST_SH_BM06B-SRSS-TB_1x06-1MP_P1.00mm_Vertical"): "C160392"})
LCSC.update({  # v6
    ("ESP32-S3FH4R2", "QFN-56-1EP_7x7mm_P0.4mm_EP4x4mm"): "C3013940",
    ("LSM6DS3TR-C", "LGA-14_3x2.5mm_P0.5mm_LayoutBorder3x4y"): "C967633",
    ("2450AT18A100E", "Johanson_2450AT18x100"): "C89334",
    ("3.9nH", "L_0402_1005Metric"): "C5452416",
    ("1.0pF", "C_0402_1005Metric"): "C1550",
    ("22", "R_0402_1005Metric"): "C25092",
    ("4.7k", "R_0402_1005Metric"): "C25900",
    ("SH1.0 4P (fan + NTC)", "JST_SH_BM04B-SRSS-TB_1x04-1MP_P1.00mm_Vertical"): "C160390",
    ("SH1.0 4P (lights)", "JST_SH_BM04B-SRSS-TB_1x04-1MP_P1.00mm_Vertical"): "C160390",
})
for _v in ("fan", "IR LED", "battery", "front light", "rear light", "NTC"):
    LCSC[(f"ZH1.5 2P ({_v})", "JST_ZH_B2B-ZR-SM4-TF_1x02-1MP_P1.50mm_Vertical")] = "C265284"


def fab(path, fitted="QCRDJHULYF"):
    """Gerbers, drill, BOM and placement for JLCPCB (SMT assembly on the top):
    only the parts whose refs start with one of `fitted`, not the bare pads."""
    out = os.path.dirname(path)
    g = os.path.join(out, "gerber")
    os.makedirs(g, exist_ok=True)
    cu = "F.Cu,In1.Cu,In2.Cu,B.Cu" if board.GetCopperLayerCount() == 4 else "F.Cu,B.Cu"
    subprocess.run([CLI, "pcb", "export", "gerbers", "--layers", cu + ",F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts",
                    "-o", g + "/", path], check=True, capture_output=True)
    subprocess.run([CLI, "pcb", "export", "drill", "--excellon-separate-th", "-o", g + "/", path], check=True,
                   capture_output=True)
    parts = [m for m in board.GetFootprints() if m.GetReference()[0] in fitted
             and (m.GetAttributes() & pcbnew.FP_SMD or m.GetValue() == "M2 SMT nut")]
    with open(os.path.join(out, "cpl.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for m in parts:
            p = m.GetPosition()
            w.writerow([m.GetReference(), f"{pcbnew.ToMM(p.x):.3f}mm", f"{-pcbnew.ToMM(p.y):.3f}mm",
                        "Bottom" if m.IsFlipped() else "Top",
                        f"{m.GetOrientationDegrees() % 360:.0f}"])
    rows = {}
    for m in parts:
        rows.setdefault((m.GetValue(), m.GetFPID().GetLibItemName().wx_str()), []).append(m.GetReference())
    with open(os.path.join(out, "bom.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Comment", "Designator", "Footprint", "Qty", "LCSC Part #"])
        for (val, fp), refs in sorted(rows.items(), key=lambda r: r[1][0]):
            w.writerow([val, ",".join(sorted(refs)), fp, len(refs), LCSC.get((val, fp), "")])
    name = os.path.basename(path).replace(".kicad_pcb", "")
    zp = os.path.join(out, name + "-gerber.zip")
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        for fn in sorted(os.listdir(g)):
            z.write(os.path.join(g, fn), fn)
    print("fab files in", out)


def project(path, classes, default=(0.2, 0.15), rules=None):
    """Write the board's .kicad_pro: KiCad keeps net classes and design rules
    there, not in the .kicad_pcb, so DRC (and anyone opening the board) uses
    the same rules the routing did. classes: [(name, track, clearance, [nets])]."""
    import json
    r = {"min_clearance": 0.15, "min_track_width": 0.15, "min_via_diameter": 0.45, "min_via_annular_width": 0.1,
         "min_through_hole_diameter": 0.3, "min_copper_edge_clearance": 0.3, "min_hole_clearance": 0.25,
         "min_hole_to_hole": 0.25, "solder_mask_to_copper_clearance": 0.0, "min_silk_clearance": 0.0}
    r.update(rules or {})

    def nc(name, w, cl):
        return {"name": name, "track_width": w, "clearance": cl, "via_diameter": 0.6 if w >= 0.5 else 0.5,
                "via_drill": 0.3, "microvia_diameter": 0.3, "microvia_drill": 0.1, "diff_pair_width": 0.2,
                "diff_pair_gap": 0.25, "diff_pair_via_gap": 0.25, "wire_width": 6, "bus_width": 12,
                "line_style": 0, "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)",
                "priority": 2147483647 if name == "Default" else 0}
    pro = {
        "board": {"design_settings": {"rules": r, "defaults": {}, "rule_severities": {}}},
        "net_settings": {
            "classes": [nc("Default", *default)] + [nc(n, w, cl) for n, w, cl, _ in classes],
            "meta": {"version": 4},
            "netclass_patterns": [{"netclass": n, "pattern": net} for n, _, _, nets in classes for net in nets],
        },
        "meta": {"filename": os.path.basename(path).replace(".kicad_pcb", ".kicad_pro"), "version": 3},
    }
    with open(path.replace(".kicad_pcb", ".kicad_pro"), "w") as f:
        json.dump(pro, f, indent=2)


def drc(path):
    rpt = path.replace(".kicad_pcb", "-drc.rpt")
    subprocess.run([CLI, "pcb", "drc", "--refill-zones", "-o", rpt, path], capture_output=True)
    lines = open(rpt).read().splitlines()
    os.remove(rpt)
    found = [l for l in lines if l.startswith("** Found")]
    print("\n".join(found))
    return [l for l in lines if l.startswith("[")]


def dump():
    for m in board.GetFootprints():
        for p in m.Pads():
            x, y = pcbnew.ToMM(p.GetPosition().x), pcbnew.ToMM(p.GetPosition().y)
            print(f"{m.GetReference():4} {p.GetNumber():3} {p.GetNetname():6} {x:7.2f} {y:7.2f}  "
                  f"{pcbnew.ToMM(p.GetBoundingBox().GetWidth()):.2f}x{pcbnew.ToMM(p.GetBoundingBox().GetHeight()):.2f}")
