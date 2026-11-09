"""Writes a KiCad 10 schematic from a parts list (gen_sch.py in each board's
folder): each part's pins get net labels, no wires. The net names match the
board's gen_pcb.py.

PARTS: (ref, lib_id, value, footprint, (x, y), {pin: net}, note); net "NC" is a
no-connect flag. Add power:PWR_FLAG parts on the nets the board is fed on.
"""
import os
import re
import uuid

LIB = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols"
LOCAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib")


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
        local = os.path.join(LOCAL, lib + ".kicad_sym")  # hardware/lib first
        _libs[lib] = open(local if os.path.exists(local) else os.path.join(LIB, lib + ".kicad_sym")).read()
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

def r(v):
    return round(v, 3)

def write(path, project, title, rev, comment, parts, seed, paper="A4"):
    ns = uuid.UUID(seed)
    uid = lambda *k: str(uuid.uuid5(ns, "/".join(map(str, k))))
    ROOT = uid("root")
    libs, out = {}, []
    g = lambda v: r(round(v / 2.54) * 2.54)
    for ref, lib_id, value, fp, (x, y), nets, note in parts:
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
            '\t\t(instances (project "%s" (path "/%s" (reference "%s") (unit 1))))\n\t)'
            % (lib_id, x, y, uid(ref), p, pin_uuids, project, ROOT, ref))
        for num, net in nets.items():
            px, py, ang = pins[num]
            lx, ly = r(x + px), r(y - py)
            if net == "NC":
                out.append('\t(no_connect (at %s %s) (uuid "%s"))' % (lx, ly, uid(ref, num, "nc")))
                continue
            # the label sits on the pin end, facing away from the body
            la = {0: 180, 180: 0, 90: 270, 270: 90}[int(ang)]
            just = "right" if la == 180 else "left"
            out.append('\t(label "%s" (at %s %s %d) (effects (font (size 1.27 1.27)) (justify %s bottom)) (uuid "%s"))'
                       % (net, lx, ly, la if la in (0, 180) else la, just, uid(ref, num, "label")))
    text = ['(kicad_sch (version 20250114) (generator "gen_sch.py") (generator_version "10.0")',
            '\t(uuid "%s")' % ROOT, '\t(paper "%s")' % paper,
            '\t(title_block (title "%s") (rev "%s") (comment 1 "%s"))' % (title, rev, comment),
            "\t(lib_symbols"]
    text += ["\t\t" + body.replace("\n", "\n\t") for body, _ in libs.values()]
    text.append("\t)")
    text += out
    text.append('\t(sheet_instances (path "/" (page "1")))')
    text.append(")")
    with open(path, "w") as f:
        f.write("\n".join(text) + "\n")
    print("wrote", path)

