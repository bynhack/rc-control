"""Exports the assembly simulation data for viewer.html.

Writes out/viewer/design.json (every part in assembly coordinates, z up, as
base64 little-endian float32 triangle soup; JSON because the artifact host
does not serve .stl) and out/viewer/checks.json: the exact overlap volume
between every pair of parts (manifold booleans) and the alignment of every
screw.

The parts other than the case are stand-ins drawn from spec sheets and
product photos: right sizes and positions, simplified shapes.

Run:  python viewer_export.py   (after enclosure.py's dependencies are installed)
"""

import base64
import glob
import json
import os
from itertools import combinations

import numpy as np
from manifold3d import Manifold

import enclosure as e
from enclosure import box, cyl

OUT = os.path.join(e.OUT, "viewer")
MIN_OVERLAP = 0.01  # mm3; touching faces come out as ~0


def board_parts():
    """ESP32 devboard, USB end against the front wall, plus a USB-C plug in one port."""
    x0, x1, y0, y1, z0 = e.board_x0, e.board_x1, e.board_y0, e.board_y1, e.board_z0
    zt = z0 + e.BOARD_T
    cx = e.board_cx
    b = box(x0, y0, z0, x1, y1, zt)
    b += box(cx - 9, y1 - 25.5, zt, cx + 9, y1, zt + 3.2)  # WROOM module at the far end
    for dx in (-6.5, 6.5):  # two USB-C receptacles, 0.5 proud of the edge
        b += box(cx + dx - 4.47, y0 - 0.5, zt, cx + dx + 4.47, y0 + 6.85, zt + 3.2)
    for px in (x0 + 1.27, x1 - 1.27):  # header rows: plastic spacer + pins below the board
        b += box(px - 1.25, y0 + 1.5, z0 - 2.5, px + 1.25, y1 - 1.5, z0)
        b += box(px - 0.35, y0 + 1.5, z0 - 8.5, px + 0.35, y1 - 1.5, z0 - 2.5)
    uz = zt + e.USB_STACK / 2
    plug = box(cx + 6.5 - 6.2, y0 - 0.5 - 22.0, uz - 3.25, cx + 6.5 + 6.2, y0 - 0.5, uz + 3.25)
    return b, plug


def screen_part():
    """Round GC9A01 module, taped under the top: glass in the recess, header tab to -x."""
    sx, sy = e.SCREEN_C
    recess = max(e.GLASS_T - e.TAPE_T, 0.3)
    g_top = e.ZT - e.TOP + recess
    g_bot = g_top - e.GLASS_T
    p_bot = g_bot - 1.6
    s = cyl(sx, sy, g_bot, g_top, e.GLASS_D / 2)
    s += box(sx + e.GLASS_D / 2 - e.GLASS_SPAN, sy - 13, g_bot, sx, sy + 13, g_top)  # FPC fold
    s += cyl(sx, sy, p_bot, g_bot, 38.5 / 2)  # round PCB (estimated 38.5)
    s += box(sx - 19.25 - 8, sy - 10, p_bot, sx - 15, sy + 10, g_bot)  # header tab
    s += box(sx - 25.5, sy - 9, p_bot - 2.5, sx - 23, sy + 9, p_bot)  # header spacer
    s += box(sx - 24.6, sy - 9, p_bot - 8.5, sx - 23.9, sy + 9, p_bot - 2.5)  # pins
    s += box(sx - 25.6, sy - 9.5, p_bot - 8.5 - 14, sx - 22.9, sy + 9.5, p_bot - 8.5)  # Dupont housings
    return s


def module_part():
    """BETAFPV 1W Micro, pushed fully into the bay: body, latches, SMA, antenna."""
    cx, y0, y1, z0 = e.CX, e.bay_y0 + e.BAY_FIT, e.D - e.BAY_FIT, e.Z0 + e.BAY_FIT
    m = box(cx - e.MOD_W / 2, y0, z0, cx + e.MOD_W / 2, y1, z0 + e.MOD_H)
    lz0, lz1 = e.LATCH_Z
    m += box(cx - e.MOD_W_LATCH / 2, y0 + 4, z0 + lz0, cx + e.MOD_W_LATCH / 2, y1 - 4, z0 + lz1)
    ym = (y0 + y1) / 2
    m += box(cx - 5, ym - 5, z0 + e.MOD_H, cx + 5, ym + 5, z0 + e.MOD_H + 3)  # SMA boss
    m += cyl(cx, ym, z0 + e.MOD_H + 3, z0 + e.MOD_H + 12, 3.2)
    m += cyl(cx, ym, z0 + e.MOD_H + 12, z0 + e.MOD_H + 60, 5.0, 4.0)  # antenna
    sx0, sx1 = e.socket_x
    m -= box(sx0, y0 - 1, e.Z0 + e.SOCKET_Z[0], sx1, y0 + 6, e.Z0 + e.SOCKET_Z[1])  # back socket
    return m


def header_part():
    """1x5 male header glued in the bay window, mating with the module's back socket."""
    x0, x1 = e.socket_x
    xc = (x0 + x1) / 2
    zb, zt = e.Z0 + e.SOCKET_Z[0], e.Z0 + e.SOCKET_Z[1]
    # Plastic spacer in the window, long pins into the module socket, short pins
    # plus solder joints into the case.
    h = box(xc - 1.25, e.bay_y0 - 2.5, zb, xc + 1.25, e.bay_y0, zt)
    h += box(xc - 0.35, e.bay_y0 - 2.5 - 3.0, zb + 0.5, xc + 0.35, e.bay_y0 + 5.0, zt - 0.5)
    h += box(xc - 1.0, e.bay_y0 - 2.5 - 4.5, zb + 0.5, xc + 1.0, e.bay_y0 - 2.5 - 1.0, zt - 0.5)
    return h


def power_parts():
    """MB102 on its pedestal, DC jack and mini-USB at the right wall, plus a DC plug."""
    x0, x1, y0, y1, z0 = e.pwr_x0, e.pwr_x1, e.pwr_y0, e.pwr_y1, e.pwr_z0
    zt = z0 + e.PWR_T
    p = box(x0, y0, z0, x1, y1, zt)
    jy = y0 + e.PWR_JACK_Y
    p += box(x1 - 10, jy - 4.5, zt, x1 + e.PWR_JACK_OUT, jy + 4.5, zt + 11)  # DC jack
    uy = y0 + e.PWR_USB_Y
    p += box(x1 - 9, uy - 3.9, zt, x1 + 0.3, uy + 3.9, zt + 4)  # mini-USB
    for cx_, cy_ in ((x0 + 10, y0 + 18), (x0 + 22, y0 + 34)):  # electrolytics
        p += cyl(cx_, cy_, zt, zt + 9, 3.2)
    for yy in (y0 + 1, y1 - 9):  # breadboard pin blocks under both ends
        p += box(x0 + 3, yy, z0 - 8.5, x0 + 11, yy + 8, z0)
        p += box(x1 - 11, yy, z0 - 8.5, x1 - 3, yy + 8, z0)
    jz = zt + 5.5
    dc_plug = cyl(0, 0, 0, 30, 4.75).rotate([0, 90, 0]).translate([x1 + e.PWR_JACK_OUT, jy, jz])
    return p, dc_plug


def usba_part():
    """USB-A female breakout glued behind the left-wall opening."""
    yc, zc = e.USBA_C
    xw = e.WALL
    a = box(xw - 0.3, yc - 6.55, zc - 2.85, xw + 14, yc + 6.55, zc + 2.85)
    a += box(xw + 1, yc - 9, zc - 2.85 - 1.6, xw + 16, yc + 9, zc - 2.85)
    return a


LABELS = {
    "body": "外殼本體", "plate": "底板", "board": "ESP32 板", "plug": "USB-C 插頭",
    "screen": "圓屏", "module": "BETAFPV 高頻頭", "header": "模組排針", "power": "MB102 電源",
    "dcplug": "DC 插頭", "usba": "USB-A 母座",
}


def triangles_b64(m):
    mesh = m.to_mesh()
    verts = np.asarray(mesh.vert_properties, dtype=np.float32)[:, :3]
    tris = verts[np.asarray(mesh.tri_verts)].astype("<f4")
    return base64.b64encode(tris.tobytes()).decode("ascii")


def screws():
    holes = e.bosses  # the plate's holes are drilled at the same list
    return [{"x": round(x, 1), "y": round(y, 1), "offset": round(min(((x - hx) ** 2 + (y - hy) ** 2) ** 0.5 for hx, hy in holes), 2)} for x, y in e.bosses]


def main():
    os.makedirs(OUT, exist_ok=True)
    for old in glob.glob(os.path.join(OUT, "*")):
        os.remove(old)
    board, plug = board_parts()
    power, dcplug = power_parts()
    parts = {
        "body": e.body(), "plate": e.plate(), "board": board, "plug": plug, "screen": screen_part(),
        "module": module_part(), "header": header_part(), "power": power, "dcplug": dcplug, "usba": usba_part(),
    }
    meshes = {k: triangles_b64(m) for k, m in parts.items()}
    checks, hits = [], Manifold()
    for a, b in combinations(parts, 2):
        x = parts[a] ^ parts[b]
        vol = sum(max(p.volume(), 0) for p in x.decompose())
        entry = {"a": a, "b": b, "overlap": round(vol, 2)}
        if vol > MIN_OVERLAP:
            lo, hi = x.bounding_box()[:3], x.bounding_box()[3:]
            entry["where"] = [round(v, 1) for v in (*lo, *hi)]
            hits += x
        checks.append(entry)
    if not hits.is_empty():
        meshes["overlap"] = triangles_b64(hits)
    with open(os.path.join(OUT, "design.json"), "w") as f:
        json.dump(meshes, f)
    report = {
        "scenarios": {"design": {"parts": list(parts), "checks": checks, "screws": screws()}},
        "labels": LABELS,
        "dims": {"W": e.W, "D": e.D, "H": e.H, "PLATE": e.PLATE},
    }
    with open(os.path.join(OUT, "checks.json"), "w") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    bad = [c for c in checks if c["overlap"] > MIN_OVERLAP]
    print(f"{len(checks)} pairs, {len(bad)} colliding")
    for c in bad:
        print("  ", LABELS[c["a"]], "x", LABELS[c["b"]], c["overlap"], "mm3 at", c["where"])


if __name__ == "__main__":
    main()
