"""Read a .kicad_pcb: the board's outline, its holes and every footprint's
outline, in KiCad's board coordinates (X right, Y DOWN, mm). Plain Python,
no KiCad needed.

KiCad's Y runs down the screen, so (X, Y) taken with z up is the board seen
from below (mirrored); turn it the right way with y = -Y (see to_car()).
"""

import math
import re

_TOKEN = re.compile(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()]+')


def parse(text):
    """S-expression -> nested lists of str (quotes stripped)."""
    stack, cur = [], []
    for t in _TOKEN.findall(text):
        if t == "(":
            stack.append(cur)
            cur = []
        elif t == ")":
            done, cur = cur, stack.pop()
            cur.append(done)
        else:
            cur.append(t[1:-1] if t.startswith('"') else t)
    return cur[0]


def kids(node, name):
    return [c for c in node[1:] if isinstance(c, list) and c and c[0] == name]


def kid(node, name):
    k = kids(node, name)
    return k[0] if k else None


def nums(node, name):
    k = kid(node, name)
    return [float(v) for v in k[1:] if not isinstance(v, list)] if k else None


def _arc(start, mid, end, n=12):
    """Points along the arc through start, mid, end."""
    (ax, ay), (bx, by), (cx, cy) = start, mid, end
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-9:
        return [start, end]
    ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay) + (cx * cx + cy * cy) * (ay - by)) / d
    uy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx) + (cx * cx + cy * cy) * (bx - ax)) / d
    r = math.hypot(ax - ux, ay - uy)
    a0, am, a1 = (math.atan2(p[1] - uy, p[0] - ux) for p in (start, mid, end))

    def ccw_span(a, b):
        return (b - a) % (2 * math.pi)

    if ccw_span(a0, am) <= ccw_span(a0, a1):
        span = ccw_span(a0, a1)
    else:
        span = -ccw_span(a1, a0)
    return [(ux + r * math.cos(a0 + span * k / n), uy + r * math.sin(a0 + span * k / n)) for k in range(n + 1)]


def shape_points(g):
    """The points of a graphic item (fp_/gr_ line, rect, circle, arc, poly)."""
    kind = g[0].split("_", 1)[1]
    if kind == "line":
        return [tuple(nums(g, "start")), tuple(nums(g, "end"))]
    if kind == "rect":
        (x0, y0), (x1, y1) = nums(g, "start"), nums(g, "end")
        return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    if kind == "circle":
        (cx, cy), (ex, ey) = nums(g, "center"), nums(g, "end")
        r = math.hypot(ex - cx, ey - cy)
        return [(cx + r * math.cos(2 * math.pi * k / 24), cy + r * math.sin(2 * math.pi * k / 24)) for k in range(24)]
    if kind == "arc":
        return _arc(tuple(nums(g, "start")), tuple(nums(g, "mid")), tuple(nums(g, "end")))
    if kind == "poly":
        return [tuple(float(v) for v in xy[1:3]) for xy in kids(kid(g, "pts"), "xy")]
    return []


def layer(g):
    k = kid(g, "layer")
    return k[1] if k else None


def place(pts, at):
    """Footprint-local points -> board points (KiCad: Y down, the angle
    counter-clockwise on screen)."""
    x, y = at[0], at[1]
    a = math.radians(at[2] if len(at) > 2 else 0.0)
    c, s = math.cos(a), math.sin(a)
    return [(x + px * c + py * s, y - px * s + py * c) for px, py in pts]


def hull(pts):
    pts = sorted(set((round(x, 4), round(y, 4)) for x, y in pts))
    if len(pts) < 3:
        return pts

    def half(ps):
        out = []
        for p in ps:
            while len(out) >= 2 and ((out[-1][0] - out[-2][0]) * (p[1] - out[-2][1])
                                     - (out[-1][1] - out[-2][1]) * (p[0] - out[-2][0])) <= 0:
                out.pop()
            out.append(p)
        return out

    lo, hi = half(pts), half(pts[::-1])
    return lo[:-1] + hi[:-1]


class Footprint:
    def __init__(self, node):
        self.name = node[1].split(":")[-1]
        self.at = nums(node, "at")
        self.side = layer(node)
        self.ref = next((p[2] for p in kids(node, "property") if p[1] == "Reference"), "?")
        self.graphics = [g for g in node[1:] if isinstance(g, list) and g and str(g[0]).startswith("fp_")
                         and g[0] != "fp_text"]
        self.pads = []
        for p in kids(node, "pad"):
            drill = kid(p, "drill")
            d = None
            if drill:
                vals = [v for v in drill[1:] if not isinstance(v, list)]
                d = float(vals[1]) if vals and vals[0] == "oval" else float(vals[0])
            self.pads.append({"kind": p[2], "at": place([tuple(nums(p, "at")[:2])], self.at)[0], "drill": d})

    def outline(self, layers=("F.Fab", "F.CrtYd", "F.SilkS")):
        """The footprint's outline on the board: the convex hull of the first
        of these layers it draws on (the body on Fab, else the courtyard,
        else the silkscreen)."""
        for lay in layers:
            pts = [p for g in self.graphics if layer(g) == lay for p in shape_points(g)]
            if len(pts) >= 3:
                return hull(place(pts, self.at)), lay
        return [], None


class Board:
    def __init__(self, path):
        with open(path, encoding="utf-8") as f:
            root = parse(f.read())
        self.footprints = [Footprint(n) for n in kids(root, "footprint")]
        edge = [g for g in root[1:] if isinstance(g, list) and g and str(g[0]).startswith("gr_")
                and layer(g) == "Edge.Cuts"]
        self.outline = _chain([shape_points(g) for g in edge])

    def ref(self, name):
        return next(f for f in self.footprints if f.ref == name)


def _chain(pieces):
    """Join the edge pieces end to end into one closed outline."""
    pieces = [list(p) for p in pieces if p]
    if not pieces:
        return []
    out = pieces.pop(0)

    def close(a, b):
        return abs(a[0] - b[0]) < 1e-3 and abs(a[1] - b[1]) < 1e-3

    while pieces:
        for i, p in enumerate(pieces):
            if close(p[0], out[-1]):
                out += p[1:]
            elif close(p[-1], out[-1]):
                out += p[::-1][1:]
            else:
                continue
            pieces.pop(i)
            break
        else:
            raise ValueError("Edge.Cuts: the outline does not close")
    return out[:-1] if close(out[0], out[-1]) else out
