"""Exports the assembly simulation data for viewer.html.

Writes out/viewer/<scenario>.json (every part in assembly coordinates, z up,
as base64 little-endian float32 triangle soup; JSON because the artifact host
does not serve .stl) and out/viewer/checks.json: for three ways of putting
the case together, the exact overlap volume between every pair of parts
(manifold booleans) and the alignment of every screw.

Scenarios:
  design  body.stl + plate.stl, as designed
  printed the first, mirrored body export + plate-for-mirrored-body.stl
  wrong   the first, mirrored body export + plate.stl (what happened)

Run:  python viewer_export.py   (after enclosure.py's dependencies are installed)
"""

import base64
import glob
import json
import os

import numpy as np

from manifold3d import Manifold

import enclosure as e
from enclosure import box, cyl

OUT = os.path.join(e.OUT, "viewer")
MIN_OVERLAP = 0.01  # mm3; touching faces come out as ~0


def mirror_x(m):
    return m.mirror([1, 0, 0]).translate([e.W, 0, 0])


def board_parts():
    """ESP32 devboard, USB edge at x = board_x0, plus a USB-C plug in the CH340C port."""
    x0, x1 = e.board_x0, e.board_x0 + e.BOARD_L
    y0, y1, z0 = e.board_y0, e.board_y1, e.board_z0
    zt = z0 + e.BOARD_T
    cy = e.board_cy
    board = box(x0, y0, z0, x1, y1, zt)
    board += box(x1 - 25.5, cy - 9, zt, x1, cy + 9, zt + 3.2)  # WROOM module at the far end
    for dy in (-6.5, 6.5):  # two USB-C receptacles, 0.5 proud of the edge
        board += box(x0 - 0.5, cy + dy - 4.47, zt, x0 + 6.85, cy + dy + 4.47, zt + 3.2)
    for py in (y0 + 1.27, y1 - 1.27):  # header rows: plastic spacer + pins below the board
        board += box(x0 + 1.5, py - 1.25, z0 - 2.5, x1 - 1.5, py + 1.25, z0)
        board += box(x0 + 1.5, py - 0.35, z0 - 8.5, x1 - 1.5, py + 0.35, z0 - 2.5)
    uz = zt + e.USB_STACK / 2
    plug = box(x0 - 0.5 - 22.0, cy + 6.5 - 6.2, uz - 3.25, x0 - 0.5, cy + 6.5 + 6.2, uz + 3.25)
    return board, plug


def screen_part():
    """Round GC9A01 module: glass circle + FPC bump on a round PCB, header tab to -x."""
    sx, sy = e.SCREEN_C
    g_top = e.ZT - e.TOP / 2  # glass front sits on the bezel
    g_bot = g_top - 1.5
    p_bot = g_bot - 1.6
    s = cyl(sx, sy, g_bot, g_top, e.GLASS_D / 2)
    s += box(sx - 7, sy + e.GLASS_D / 2 - e.GLASS_H, g_bot, sx + 7, sy, g_top)  # FPC bump
    s += cyl(sx, sy, p_bot, g_bot, 38.5 / 2)  # round PCB (estimated 38.5)
    s += box(sx - 19.25 - 8, sy - 10, p_bot, sx - 15, sy + 10, g_bot)  # header tab
    s += box(sx - 25.5, sy - 9, p_bot - 2.5, sx - 23, sy + 9, p_bot)  # header spacer
    s += box(sx - 24.6, sy - 9, p_bot - 8.5, sx - 23.9, sy + 9, p_bot - 2.5)  # pins
    return s


def module_part():
    """BETAFPV 1W Micro: 45 x 20 x 60 body, 53 across the rails, SMA on top, Dupont plugs on its back pins."""
    cx, y0, z0 = e.W / 2, e.D + e.FIT, e.PLATE
    m = box(cx - 22.5, y0, z0, cx + 22.5, y0 + e.MOD_T, z0 + 60)
    m += box(cx - e.MOD_W_RAILS / 2, y0, z0 + 8, cx + e.MOD_W_RAILS / 2, y0 + e.MOD_T, z0 + 52)
    m += cyl(cx, y0 + e.MOD_T / 2, z0 + 60, z0 + 72, 3.2)
    m += cyl(cx, y0 + e.MOD_T / 2, z0 + 72, z0 + 120, 5.0, 4.0)  # antenna
    dupont = box(cx - 15, e.D - 12, z0 + 5, cx - 2, y0, z0 + 18)
    return m, dupont


def usba_part():
    """USB-A female breakout glued behind the right-wall opening."""
    yc, zc = e.USBA_C
    xw = e.W - e.WALL
    a = box(xw - 14, yc - 6.55, zc - 2.85, xw + 0.3, yc + 6.55, zc + 2.85)
    a += box(xw - 16, yc - 9, zc - 2.85 - 1.6, xw - 1, yc + 9, zc - 2.85)
    return a


def scenarios():
    body, plate = e.body(), e.plate()
    board, plug = board_parts()
    screen = screen_part()
    module, dupont = module_part()
    usba = usba_part()
    design = {
        "body": body, "plate": plate, "board": board, "plug": plug,
        "screen": screen, "module": module, "dupont": dupont, "usba": usba,
    }
    printed_body = mirror_x(body)
    # Physical parts don't mirror, but the board, plug and USB-A move to the other
    # walls; the screen keeps tab-left / FPC-front; the module and its plugs are symmetric enough.
    printed = dict(design, body=printed_body, plate=mirror_x(plate), board=mirror_x(board),
                   plug=mirror_x(plug), usba=mirror_x(usba), dupont=mirror_x(dupont))
    wrong = dict(design, body=printed_body)  # parts placed by the unmirrored plate
    return {"design": design, "printed": printed, "wrong": wrong}


LABELS = {
    "body": "外殼本體", "plate": "底板", "board": "ESP32 板", "plug": "USB-C 插頭",
    "screen": "圓屏", "module": "BETAFPV 高頻頭", "dupont": "高頻頭杜邦頭", "usba": "USB-A 母座",
}
PAIRS = [
    ("body", "plate"), ("body", "board"), ("plate", "board"), ("body", "plug"),
    ("body", "screen"), ("body", "module"), ("plate", "module"), ("body", "dupont"),
    ("plate", "dupont"), ("body", "usba"), ("plate", "usba"), ("board", "usba"),
    ("screen", "board"), ("screen", "usba"),
]


def screws(body_is_mirrored, plate_is_mirrored):
    def place(pts, mirrored):
        return [(e.W - x, y) if mirrored else (x, y) for x, y in pts]

    columns = place(e.bosses + e.bay_bosses, body_is_mirrored)
    holes = place(e.bosses + e.bay_bosses, plate_is_mirrored)
    out = []
    for cx, cy in columns:
        d = min(((cx - hx) ** 2 + (cy - hy) ** 2) ** 0.5 for hx, hy in holes)
        out.append({"x": round(cx, 1), "y": round(cy, 1), "offset": round(d, 2)})
    return out


def triangles_b64(m):
    mesh = m.to_mesh()
    verts = np.asarray(mesh.vert_properties, dtype=np.float32)[:, :3]
    tris = verts[np.asarray(mesh.tri_verts)].astype("<f4")
    return base64.b64encode(tris.tobytes()).decode("ascii")


def main():
    os.makedirs(OUT, exist_ok=True)
    for old in glob.glob(os.path.join(OUT, "*.stl")):
        os.remove(old)
    report = {"scenarios": {}, "labels": LABELS, "dims": {"W": e.W, "D": e.D, "H": e.H, "PLATE": e.PLATE}}
    mirrored = {"design": (False, False), "printed": (True, True), "wrong": (True, False)}
    for name, parts in scenarios().items():
        meshes = {part: triangles_b64(m) for part, m in parts.items()}
        checks, hits = [], Manifold()
        for a, b in PAIRS:
            x = parts[a] ^ parts[b]
            vol = sum(max(p.volume(), 0) for p in x.decompose())
            entry = {"a": a, "b": b, "overlap": round(vol, 2)}
            if vol > MIN_OVERLAP:
                lo, hi = x.bounding_box()[:3], x.bounding_box()[3:]
                entry["where"] = [round(v, 1) for v in (*lo, *hi)]
                hits += x
            checks.append(entry)
        has_hits = not hits.is_empty()
        if has_hits:
            meshes["overlap"] = triangles_b64(hits)
        with open(os.path.join(OUT, f"{name}.json"), "w") as f:
            json.dump(meshes, f)
        report["scenarios"][name] = {
            "parts": list(parts),
            "checks": checks,
            "screws": screws(*mirrored[name]),
            "overlapMesh": has_hits,
        }
        bad = [c for c in checks if c["overlap"] > MIN_OVERLAP]
        print(f"{name}: {len(bad)} colliding pair(s)", [(c['a'], c['b'], c['overlap']) for c in bad])
    with open(os.path.join(OUT, "checks.json"), "w") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
