"""A small grid router, enough for this 2-layer board: A* over (x, y, layer), net by net, with restarts in
another net order when one fails. GND isn't routed: every GND pad gets a via to the bottom pour."""
import heapq
import math
import random

import pcbnew
import pcbgen
from pcbgen import track, via as _via

G = 0.2
FIXED = []


def via(x, y, name):
    _via(x, y, name)
    for t in pcbgen.board.GetTracks():
        if isinstance(t, pcbnew.PCB_VIA):
            t.SetFrontTentingMode(pcbnew.TENTING_MODE_TENTED)
            t.SetBackTentingMode(pcbnew.TENTING_MODE_TENTED)
MARGIN = 0.05  # diagonals against corners
VIA_R = 0.3
DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]


class Grid:
    def __init__(s, W, H):
        s.nx, s.ny = int(W / G) + 1, int(H / G) + 1
        s.shapes = []  # (x0, y0, x1, y1, layer or None, net)

    def add(s, x0, y0, x1, y1, layer, net):
        s.shapes.append((x0, y0, x1, y1, layer, net))

    def blocked(s, net, r, layer):
        """Cells a track of half-clearance r can't take on this layer."""
        b = bytearray(s.nx * s.ny)
        for x0, y0, x1, y1, l, n in s.shapes:
            if n == net or (l is not None and l != layer):
                continue
            ix0, ix1 = max(0, int(math.ceil((x0 - r) / G))), min(s.nx - 1, int((x1 + r) / G))
            iy0, iy1 = max(0, int(math.ceil((y0 - r) / G))), min(s.ny - 1, int((y1 + r) / G))
            if ix1 < ix0:
                continue
            for j in range(iy0, iy1 + 1):
                b[j * s.nx + ix0:j * s.nx + ix1 + 1] = b"\1" * (ix1 - ix0 + 1)
        return b


def smd_block(g, P):
    """No via on or against any SMD pad, whatever its net: solder would drain down it."""
    b = bytearray(g.nx * g.ny)
    r = VIA_R + 0.05  # tented, and clear of the pad
    for p in P:
        if p["th"] or p["npth"]:
            continue
        x0, y0, x1, y1 = p["box"]
        ix0, ix1 = max(0, int(math.ceil((x0 - r) / G))), min(g.nx - 1, int((x1 + r) / G))
        iy0, iy1 = max(0, int(math.ceil((y0 - r) / G))), min(g.ny - 1, int((y1 + r) / G))
        for j in range(iy0, iy1 + 1):
            b[j * g.nx + ix0:j * g.nx + ix1 + 1] = b"\1" * (ix1 - ix0 + 1)
    return b


def pads():
    out = []
    for m in pcbgen.board.GetFootprints():
        for p in m.Pads():
            bb = p.GetBoundingBox()
            x0, y0, x1, y1 = (pcbnew.ToMM(v) for v in (bb.GetLeft(), bb.GetTop(), bb.GetRight(), bb.GetBottom()))
            c = p.GetPosition()
            out.append(dict(ref=m.GetReference(), num=p.GetNumber(), net=p.GetNetname(), x=pcbnew.ToMM(c.x),
                            y=pcbnew.ToMM(c.y), box=(x0, y0, x1, y1), th=p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH,
                            npth=p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH))
    return out


def astar(g, starts, goals, block, vblock, w_b=2.5):
    nx, ny = g.nx, g.ny
    idx = lambda i, j, l: (j * nx + i) * 2 + l
    tx = sum(a[0] for a in goals) / len(goals)
    ty = sum(a[1] for a in goals) / len(goals)
    goalset = {idx(*a) for a in goals}
    dist, prev, pq = {}, {}, []
    for a in starts:
        k = idx(*a)
        dist[k] = 0
        heapq.heappush(pq, (0, k, a))
    while pq:
        _, k, (i, j, l) = heapq.heappop(pq)
        if k in goalset:
            path = [(i, j, l)]
            while k in prev:
                k, st = prev[k]
                path.append(st)
            return path[::-1]
        d0 = dist[k]
        cost = 1.0 if l == 0 else w_b
        for dx, dy in DIRS:
            a, b = i + dx, j + dy
            if not (0 <= a < nx and 0 <= b < ny) or block[l][b * nx + a]:
                continue
            if dx and dy and (block[l][j * nx + a] or block[l][b * nx + i]):
                continue
            n = idx(a, b, l)
            nd = d0 + cost * (1.414 if dx and dy else 1.0)
            if nd < dist.get(n, 1e18):
                dist[n] = nd
                prev[n] = (k, (i, j, l))
                heapq.heappush(pq, (nd + math.hypot(a - tx / 1, b - ty / 1) * 0.5, n, (a, b, l)))
        if not vblock[j * nx + i]:
            m = 1 - l
            n = idx(i, j, m)
            nd = d0 + 18
            if nd < dist.get(n, 1e18):
                dist[n] = nd
                prev[n] = (k, (i, j, l))
                heapq.heappush(pq, (nd + 0, n, (i, j, m)))
    return None


def simplify(path):
    out = [path[0]]
    for a, b in zip(path[1:], path[2:]):
        p = out[-1]
        if a[2] == p[2] == b[2] and (a[0] - p[0]) * (b[1] - a[1]) == (a[1] - p[1]) * (b[0] - a[0]):
            continue
        out.append(a)
    out.append(path[-1])
    return out


def base(W, H, holes, keep, under, P):
    g = Grid(W, H)
    # the board's edge
    e = 0.5
    g.add(-1, -1, W + 1, e - 0.25, None, "#"), g.add(-1, H - e + 0.25, W + 1, H + 1, None, "#")
    g.add(-1, -1, e - 0.25, H + 1, None, "#"), g.add(W - e + 0.25, -1, W + 1, H + 1, None, "#")
    for x, y in holes:
        g.add(x - 1.1, y - 1.1, x + 1.1, y + 1.1, None, "#")
    for x, y in ((0, 0), (W - 1.4, 0), (0, H - 1.4), (W - 1.4, H - 1.4)):  # the rounded corners
        g.add(x, y, x + 1.4, y + 1.4, None, "#")
    for k in keep:
        g.add(*k, None, "#")
    for (x0, y0), (x1, y1), w_ in FIXED:  # hand-drawn stubs, reserved before anything is routed
        g.add(min(x0, x1) - w_ / 2, min(y0, y1) - w_ / 2, max(x0, x1) + w_ / 2, max(y0, y1) + w_ / 2, 0, "GND")
    for u in under:
        g.add(*u, 0, "#")  # top side
    for p in P:
        if p["npth"]:
            continue
        g.add(*p["box"], None if p["th"] else 0, p["net"] or "#nc")
    return g


def attempt(W, H, holes, keep, under, width, clear, order, P, plan):
    g = base(W, H, holes, keep, under, P)
    add_plan(g, plan)
    done = []
    smd = smd_block(g, P)
    for n in order:
        ps = [p for p in P if p["net"] == n]
        w = width.get(n, 0.25)
        cl = clear.get(n, 0.15)
        r = w / 2 + cl + MARGIN
        block = [g.blocked(n, r, 0), g.blocked(n, r, 1)]
        rv = VIA_R + cl + MARGIN
        vb0, vb1 = g.blocked(n, rv, 0), g.blocked(n, rv, 1)
        ub = bytearray(g.nx * g.ny)
        for x0, y0, x1, y1 in under:
            for j in range(int(y0 / G), min(g.ny, int(y1 / G) + 2)):
                ub[j * g.nx + int(x0 / G):j * g.nx + int(x1 / G) + 2] = b"\1" * (int(x1 / G) - int(x0 / G) + 2)
        vblock = bytes(a | b | c | d for a, b, c, d in zip(vb0, vb1, ub, smd))

        def cells(p):
            i, j = round(p["x"] / G), round(p["y"] / G)
            ls = [0, 1] if p["th"] else [0]
            for l in ls:  # the pad's own centre is always usable
                block[l][j * g.nx + i] = 0
            return [(i, j, l) for l in ls]
        tree = cells(ps[0])
        pts = [ps[0]]
        for p in ps[1:]:
            pass
        rest = ps[1:]
        routed_cells = list(tree)
        while rest:
            rest.sort(key=lambda p: min(math.hypot(p["x"] - q["x"], p["y"] - q["y"]) for q in pts))
            p = rest.pop(0)
            goal = cells(p)
            path = astar(g, routed_cells, goal, block, vblock)
            if not path:
                return n, done
            path = simplify(path)
            done.append((n, w, p, path))
            routed_cells += [c for c in path]
            # densify so later branches can start anywhere along it
            for a, b in zip(path, path[1:]):
                s = max(abs(a[0] - b[0]), abs(a[1] - b[1]))
                if a[2] == b[2] and s:
                    routed_cells += [(a[0] + (b[0] - a[0]) * t // s, a[1] + (b[1] - a[1]) * t // s, a[2])
                                     for t in range(1, s)]
                if a[2] != b[2]:
                    g.add(a[0] * G - VIA_R, a[1] * G - VIA_R, a[0] * G + VIA_R, a[1] * G + VIA_R, None, n)
            for a, b in zip(path, path[1:]):
                if a[2] == b[2]:
                    s = max(abs(a[0] - b[0]), abs(a[1] - b[1]))
                    for t in range(0, s + 1):
                        x, y = (a[0] + (b[0] - a[0]) * t / s) * G if s else a[0] * G, (a[1] + (b[1] - a[1]) * t / s) * G if s else a[1] * G
                        g.add(x - w / 2, y - w / 2, x + w / 2, y + w / 2, a[2], n)
            pts.append(p)
    return None, (done, g)


def emit(done, P):
    def xy(c):
        return c[0] * G, c[1] * G
    seen = set()
    for n, w, p, path in done:
        for a, b in zip(path, path[1:]):
            if a[2] != b[2]:
                if (a[0], a[1], n) not in seen:
                    seen.add((a[0], a[1], n))
                    via(a[0] * G, a[1] * G, n)
            else:
                track([xy(a), xy(b)], n, w, pcbnew.F_Cu if a[2] == 0 else pcbnew.B_Cu)
    # the off-grid stub from every pad's true centre to its grid cell
    for p in P:
        if p["net"] in ("", "GND") or p["npth"]:
            continue
        i, j = round(p["x"] / G), round(p["y"] / G)
        for n, w, q, path in done:
            if n == p["net"]:
                ends = [c for c in path if c[0] == i and c[1] == j]
                if ends:
                    if abs(i * G - p["x"]) > 1e-6 or abs(j * G - p["y"]) > 1e-6:
                        track([(p["x"], p["y"]), (i * G, j * G)], n, min(w, 0.25), pcbnew.F_Cu)
                    break


# ground pads hemmed in by the signals: their vias go in first
PRE = {("C11", "2"), ("R15", "2"), ("C17", "2"), ("J1", "3"), ("J1", "MP"), ("J5", "MP"), ("J6", "2"), ("R5", "2"), ("R8", "2")}
DRILLS = []


def x0_in(p, x, y):
    x0, y0, x1, y1 = p["box"]
    return x0 - 0.1 <= x <= x1 + 0.1 and y0 - 0.1 <= y <= y1 + 0.1


def clear_line(p, x, y, b0, nx):
    x0, y0, x1, y1 = p["box"]
    for t in range(1, 30):
        cx = int(round((p["x"] + (x - p["x"]) * t / 30) / G))
        cy = int(round((p["y"] + (y - p["y"]) * t / 30) / G))
        if b0[cy * nx + cx] and not (x0 - 0.3 <= cx * G <= x1 + 0.3 and y0 - 0.3 <= cy * G <= y1 + 0.3):
            return False
    return True


def far(x, y, d=0.9):
    return all(math.hypot(x - a, y - b) >= d for a, b in DRILLS)


def gnd_plan(g, P, under, only=None, skip=()):
    """Before any signal: a via beside every top-side GND pad, on an otherwise empty board."""
    nx = g.nx
    r = VIA_R + 0.15 + MARGIN
    smd = smd_block(g, P)
    if not DRILLS:
        DRILLS[:] = [(p["x"], p["y"]) for p in P if p["th"]]
    plan = []
    block_via = lambda: bytes(a | b | c for a, b, c in zip(g.blocked("GND", r, 0), g.blocked("GND", r, 1), smd))
    vb = block_via()
    b0 = g.blocked("GND", 0.125 + 0.15 + MARGIN, 0)
    for p in P:
        if p["net"] != "GND" or p["th"] or p["npth"]:
            continue
        key = (p["ref"], p["num"], round(p["x"], 1))
        if key in skip or (only is not None and (p["ref"], p["num"]) not in only):
            continue
        if only is None and p["num"] == "MP":  # a connector's tabs: normally the top pour takes them
            continue
        i0, j0 = round(p["x"] / G), round(p["y"] / G)
        best = None
        for rad in range(3, 40):
            for a in range(0, 360, 10):
                i = i0 + round(rad * math.cos(math.radians(a)))
                j = j0 + round(rad * math.sin(math.radians(a)))
                if not (0 <= i < g.nx and 0 <= j < g.ny) or vb[j * nx + i]:
                    continue
                x, y = i * G, j * G
                if not far(x, y) or x0_in(p, x, y) or any(
                        u[0] - 0.4 <= x <= u[2] + 0.4 and u[1] - 0.4 <= y <= u[3] + 0.4 for u in under):
                    continue
                if clear_line(p, x, y, b0, nx):
                    best = (x, y)
                    break
            if best:
                break
        if not best:
            print("no via for", p["ref"], p["num"])
            continue
        plan.append(((p["x"], p["y"]), best))
        DRILLS.append(best)
        g.add(best[0] - VIA_R, best[1] - VIA_R, best[0] + VIA_R, best[1] + VIA_R, None, "GND")
        vb = block_via()
    return plan


def add_plan(g, plan):
    for (x0, y0), (x1, y1) in plan:
        g.add(x1 - VIA_R, y1 - VIA_R, x1 + VIA_R, y1 + VIA_R, None, "GND")
        n = 10
        for t in range(n + 1):
            x, y = x0 + (x1 - x0) * t / n, y0 + (y1 - y0) * t / n
            g.add(x - 0.125, y - 0.125, x + 0.125, y + 0.125, 0, "GND")


def ub_under(g, under):
    ub = bytearray(g.nx * g.ny)
    for x0, y0, x1, y1 in under:
        for j in range(int(y0 / G), min(g.ny, int(y1 / G) + 2)):
            ub[j * g.nx + int(x0 / G):j * g.nx + int(x1 / G) + 2] = b"\1" * (int(x1 / G) - int(x0 / G) + 2)
    return ub


def stitch(g, W, H, under, P):
    """Ties the two ground pours together wherever there's room."""
    r = VIA_R + 0.2 + MARGIN
    smd = smd_block(g, P)
    vb = bytes(a | b | c for a, b, c in zip(g.blocked("GND", r, 0), g.blocked("GND", r, 1), smd))
    n = 0
    for x in [1.5 + 2.4 * i for i in range(30)]:
        for y in [1.5 + 2.4 * j for j in range(16)]:
            if x > W - 1 or y > H - 1:
                continue
            i, j = round(x / G), round(y / G)
            if vb[j * g.nx + i]:
                continue
            X, Y = i * G, j * G
            if not far(X, Y):
                continue
            if any(u[0] - 0.4 <= X <= u[2] + 0.4 and u[1] - 0.4 <= Y <= u[3] + 0.4 for u in under):
                continue
            via(X, Y, "GND")
            DRILLS.append((X, Y))
            n += 1
    print("stitching vias:", n)


def route(W, H, holes, keep, under, width, clear, seed=1):
    P = pads()
    pre = gnd_plan(base(W, H, holes, keep, under, P), P, under, only=PRE)
    plan = pre
    nets = sorted({p["net"] for p in P if p["net"] and p["net"] != "GND"})
    nets = [n for n in nets if sum(p["net"] == n for p in P) > 1]
    rnd = random.Random(seed)
    span = lambda n: sum(abs(p["x"] - q["x"]) + abs(p["y"] - q["y"]) for p in P if p["net"] == n for q in P if q["net"] == n)
    order = sorted(nets, key=lambda n: (width.get(n, 0) < 0.45, span(n)))
    failed = {}
    for t in range(70):
        bad, res = attempt(W, H, holes, keep, under, width, clear, order, P, plan)
        if bad is None:
            done, g = res
            print(f"routed {len(nets)} nets on try {t + 1}")
            emit(done, P)
            taken = {(p["ref"], p["num"], round(p["x"], 1)) for p in P if p["net"] == "GND" and
                     any(abs(p["x"] - q[0]) < 1e-6 and abs(p["y"] - q[1]) < 1e-6 for q, _ in pre)}
            plan = pre + gnd_plan(g, P, under, skip=taken)
            for q, v in plan:
                track([q, v], "GND", 0.25, pcbnew.F_Cu)
                via(v[0], v[1], "GND")
            print("GND vias:", len(plan))
            stitch(g, W, H, under, P)
            return
        failed[bad] = failed.get(bad, 0) + 1
        print("try", t + 1, "stuck on", bad, "after", len({d[0] for d in res}), "nets")
        order.remove(bad)
        order.insert(rnd.randint(0, min(3, len(order))), bad)
    raise RuntimeError(f"no route: {failed}")
