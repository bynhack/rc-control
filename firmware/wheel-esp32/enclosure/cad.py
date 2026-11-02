"""Shared helpers for the printed parts: manifold3d primitives, STL export
and a matplotlib preview renderer.

Needs: pip install manifold3d numpy trimesh matplotlib
"""

import os

import numpy as np
from manifold3d import CrossSection, JoinType, Manifold, set_circular_segments

set_circular_segments(64)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")


def box(x0, y0, z0, x1, y1, z1):
    return Manifold.cube([x1 - x0, y1 - y0, z1 - z0]).translate([x0, y0, z0])


def cyl(x, y, z0, z1, r, r_top=None):
    return Manifold.cylinder(z1 - z0, r, r if r_top is None else r_top).translate([x, y, z0])


def rrect(w, d, r):
    """Rounded rectangle cross-section, origin at its lower-left corner."""
    return CrossSection.square([w - 2 * r, d - 2 * r]).offset(r, JoinType.Round).translate([r, r])


def rbox(x0, y0, z0, w, d, h, r):
    return Manifold.extrude(rrect(w, d, r), h).translate([x0, y0, z0])


def extrude_xz(points, y0, y1):
    """Prism from a polygon in the x-z plane, spanning y0..y1."""
    cs = CrossSection([[(x, z) for x, z in points]])
    # Rotating +90 about x maps the profile's y onto z and the extrusion onto -y.
    return Manifold.extrude(cs, y1 - y0).rotate([90, 0, 0]).translate([0, y1, 0])


def to_trimesh(m):
    import trimesh

    mesh = m.to_mesh()
    return trimesh.Trimesh(vertices=np.asarray(mesh.vert_properties)[:, :3], faces=np.asarray(mesh.tri_verts), process=True)


def render(parts, elev, azim, size=(760, 560)):
    """Orthographic z-buffer render with flat shading; returns an RGB array."""
    e, a = np.radians(elev), np.radians(azim)
    view = np.array([np.cos(e) * np.cos(a), np.cos(e) * np.sin(a), np.sin(e)])  # towards the eye
    right = np.cross([0, 0, 1], view)
    right /= np.linalg.norm(right)
    up = np.cross(view, right)
    light = view + 0.6 * up - 0.3 * right
    light /= np.linalg.norm(light)

    meshes = [(to_trimesh(m), np.array(rgb)) for m, rgb in parts]
    pts = np.vstack([tm.vertices for tm, _ in meshes])
    u, v = pts @ right, pts @ up
    scale = 0.9 * min(size[0] / np.ptp(u), size[1] / np.ptp(v))
    cu, cv = (u.max() + u.min()) / 2, (v.max() + v.min()) / 2

    w, h = size
    zbuf = np.full((h, w), -np.inf)
    img = np.ones((h, w, 3))
    for tm, rgb in meshes:
        tri = tm.vertices[tm.faces]
        sx = (tri @ right - cu) * scale + w / 2
        sy = h / 2 - (tri @ up - cv) * scale
        sz = tri @ view
        shade = 0.35 + 0.65 * np.abs(tm.face_normals @ light)
        for i in range(len(tri)):
            x, y, z = sx[i], sy[i], sz[i]
            x0, x1 = int(max(np.floor(x.min()), 0)), int(min(np.ceil(x.max()), w - 1))
            y0, y1 = int(max(np.floor(y.min()), 0)), int(min(np.ceil(y.max()), h - 1))
            if x0 > x1 or y0 > y1:
                continue
            gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
            d = (y[1] - y[2]) * (x[0] - x[2]) + (x[2] - x[1]) * (y[0] - y[2])
            if abs(d) < 1e-9:
                continue
            l0 = ((y[1] - y[2]) * (gx - x[2]) + (x[2] - x[1]) * (gy - y[2])) / d
            l1 = ((y[2] - y[0]) * (gx - x[2]) + (x[0] - x[2]) * (gy - y[2])) / d
            l2 = 1 - l0 - l1
            inside = (l0 >= -1e-6) & (l1 >= -1e-6) & (l2 >= -1e-6)
            depth = l0 * z[0] + l1 * z[1] + l2 * z[2]
            sub = zbuf[y0 : y1 + 1, x0 : x1 + 1]
            hit = inside & (depth > sub)
            sub[hit] = depth[hit]
            img[y0 : y1 + 1, x0 : x1 + 1][hit] = np.clip(rgb * shade[i], 0, 1)
    return img


def preview(scenes, path):
    """scenes: [(title, [(manifold, rgb)], elev, azim)] -> one PNG grid."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    cols = 2
    rows = (len(scenes) + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(15, 5.6 * rows), dpi=100)
    for ax, (title, parts, elev, azim) in zip(axes.flat, scenes):
        ax.imshow(render(parts, elev, azim))
        ax.set_title(title, fontsize=14)
        ax.set_axis_off()
    for ax in list(axes.flat)[len(scenes) :]:
        ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(path)
