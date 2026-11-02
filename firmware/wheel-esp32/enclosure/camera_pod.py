"""Roof camera pod for the WiFiLink 2 camera on the MJX 14303 (1/14 Citroen C3
WRC), in the style of a WRC roof camera pod. It goes where the roof air scoop
was.

One part, camera_pod.stl, printed standing on its base:
  - a shell over the camera's body only (sides, top, back), with a flat top
    that tapers down to a low tail. Its front ends at the body's face, so
    the lens stands out in front of it.
  - the 19 mm camera hangs on two M2.5 side screws through the shell's walls,
    which are its tilt pivot: loosen them to set the angle (TILT range).
    The pivot is high enough that neither the body nor the lens reaches the
    roof over the whole range.
  - a flange round the base, bolted through the roof with three M2.5 screws
    and nuts (two at the front corners, one at the tail's tip).
  - a small hole in the roof under the camera's back for the MIPI cable to
    the WiFiLink 2.

Every size marked MEASURE is the worksheet's estimate, taken as right; check
them on the car before drilling the roof.

Hardware:
  2x M2.5 x 4              camera pivots, through the walls
  3x M2.5 x 8 + hex nut    pod -> roof (flange 2 + roof 1.5 + nut 2)

Coordinates: x = right, y = forward (towards the car's nose), z = up from the
roof's outer surface; the camera's pivot at x = y = 0.

Run:  python camera_pod.py  -> out/camera_pod.stl, out/camera_pod_preview.png,
      prints the roof holes to drill and cut
"""

import math
import os
import sys

from manifold3d import Manifold

from cad import OUT, box, cyl, preview, rrect, to_trimesh

FIT = 0.3

# ---- camera (WiFiLink 2, 19 mm Vista-style) -------------------------------------------
CAM_W = 19.0  # MEASURE: square body
CAM_L = 14.0  # MEASURE: body depth without the lens
CAM_PIVOT_BACK = 7.0  # MEASURE: side screw hole to the back of the body
LENS_D, LENS_L = 14.0, 10.0  # MEASURE
TILT = (-10, 5)  # degrees, nose down .. nose up

# ---- car -------------------------------------------------------------------------------
SHELL_T = 1.5  # MEASURE: body shell

# ---- pod ---------------------------------------------------------------------------------
WALL = 1.5
ROOF_CLEAR = 0.5  # camera and lens over the roof, at any tilt
HEAD_ROOM = 1.2  # over the camera's sweep, under the top (its rounded corners come down ~1)
PIVOT_R = 1.4  # M2.5 clearance
FLANGE, FLANGE_T = 4.0, 2.0  # base flange round the pod
BOLT_R = 1.45  # M2.5 clearance, through the flange and the roof
CABLE = (12.0, 6.0)  # roof hole for the MIPI cable, behind the camera's back
TAIL_Y, TAIL_W, TAIL_H = -28.0, 12.0, 6.0
R = 3.5  # edge rounding


def sweep():
    """Lowest, highest and rearmost points of the camera (body and lens) over TILT, from the pivot."""
    body = [(y, z) for y in (-CAM_PIVOT_BACK, CAM_L - CAM_PIVOT_BACK) for z in (-CAM_W / 2, CAM_W / 2)]
    lens_r = LENS_D / 2 + FIT
    lo = hi = back = 0.0
    for t in range(TILT[0], TILT[1] + 1):
        a = math.radians(t)
        rot = [(y * math.cos(a) - z * math.sin(a), y * math.sin(a) + z * math.cos(a)) for y, z in body]
        lens_lo = (CAM_L - CAM_PIVOT_BACK + LENS_L) * math.sin(a) - lens_r * math.cos(a)
        lo = min(lo, lens_lo, *(z for _, z in rot))
        hi = max(hi, *(z for _, z in rot))
        back = min(back, *(y for y, _ in rot))
    return lo, hi, back


cam_lo, cam_hi, cam_back = sweep()
PIVOT_Z = -cam_lo + ROOF_CLEAR
pod_in_w = CAM_W + 2 * FIT  # the camera fits between the walls, which hold it
pod_w = pod_in_w + 2 * WALL
top_in = PIVOT_Z + cam_hi + HEAD_ROOM
pod_h = top_in + WALL
FRONT_Y = CAM_L - CAM_PIVOT_BACK  # the body's face: the lens stands out ahead of the pod
FULL_BACK_Y = cam_back - 1.0  # full height back to here, then the taper


def section(y, w, h, r, z0=0.0):
    """Thin rounded-rectangle slab across the pod at y: w wide, from z0 up h."""
    s = Manifold.extrude(rrect(w, h, r), 0.01).translate([-w / 2, z0, 0])
    return s.rotate([90, 0, 0]).translate([0, y + 0.005, 0])


def hull(*parts):
    return Manifold.batch_hull(list(parts))


def shell_outer():
    # Bottom corners square (it sits on the roof), so each section reaches below the roof.
    return hull(section(FRONT_Y, pod_w, pod_h + R, R, -R), section(FULL_BACK_Y, pod_w, pod_h + R, R, -R),
                section(TAIL_Y, TAIL_W, TAIL_H + R, 2.0, -R)) ^ box(-50, -60, 0, 50, 60, 50)


def shell_inner():
    # Open at the front and the bottom.
    w, h = pod_in_w, top_in
    return hull(section(FRONT_Y + 1, w, h + 5, R - WALL, -5), section(FULL_BACK_Y, w, h + 5, R - WALL, -5),
                section(TAIL_Y + WALL * 2, TAIL_W - 2 * WALL, TAIL_H - WALL + 5, 1.0, -5))


def bolt_xy():
    x = pod_w / 2 + FLANGE / 2
    return [(-x, FRONT_Y - FLANGE / 2), (x, FRONT_Y - FLANGE / 2), (0, TAIL_Y - FLANGE / 2)]


def flange():
    foot = shell_outer().slice(0.01).offset(FLANGE)
    out = Manifold.extrude(foot, FLANGE_T) - box(-50, FRONT_Y, -1, 50, 60, 10)  # nothing ahead of the face
    return out - shell_inner()


def pod():
    out = shell_outer() - shell_inner()
    out += flange()
    # Pivot holes.
    out -= Manifold.cylinder(pod_w + 2, PIVOT_R).rotate([0, 90, 0]).translate([-pod_w / 2 - 1, 0, PIVOT_Z])
    for x, y in bolt_xy():
        out -= cyl(x, y, -1, FLANGE_T + 1, BOLT_R)
    return out


def cable_hole():
    w, d = CABLE
    return (-w / 2, cam_back - d + 1.0, w / 2, cam_back + 1.0)


# ---- stand-ins ----------------------------------------------------------------------------
def camera(tilt):
    body = box(-CAM_W / 2, -CAM_PIVOT_BACK, -CAM_W / 2, CAM_W / 2, CAM_L - CAM_PIVOT_BACK, CAM_W / 2)
    lens = Manifold.cylinder(LENS_L, LENS_D / 2).rotate([-90, 0, 0]).translate([0, CAM_L - CAM_PIVOT_BACK, 0])
    return (body + lens).rotate([tilt, 0, 0]).translate([0, 0, PIVOT_Z])


def roof():
    out = box(-40, -60, -SHELL_T, 40, 60, 0)
    x0, y0, x1, y1 = cable_hole()
    out -= box(x0, y0, -SHELL_T - 1, x1, y1, 1)
    for x, y in bolt_xy():
        out -= cyl(x, y, -SHELL_T - 1, 1, BOLT_R)
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    p = pod()
    if p.is_empty() or len(p.decompose()) != 1:
        sys.exit("pod: not a single solid")
    checks = {"pod x roof": (p ^ roof()).volume()}
    for t in range(TILT[0], TILT[1] + 1):
        c = camera(t)
        checks[f"camera at {t:+d} deg"] = max((c ^ p).volume(), (c ^ roof()).volume())
    for k, v in checks.items():
        if v > 0.001 or not k.startswith("camera"):
            print(f"{k}: {v:.3f} mm3")
    if max(checks.values()) > 0.01:
        sys.exit("parts overlap")
    print(f"camera clear over {TILT[0]}..{TILT[1]} deg")

    to_trimesh(p).export(os.path.join(OUT, "camera_pod.stl"))
    case, dark, car = (0.62, 0.68, 0.76), (0.15, 0.17, 0.2), (0.75, 0.15, 0.15)
    preview(
        [
            ("on the roof", [(p, case), (roof(), car), (camera(-5), dark)], 25, 35),
            ("from the side", [(p, case), (roof(), car), (camera(-5), dark)], 0, 0),
            ("from the front", [(p, case), (roof(), car), (camera(-5), dark)], 12, 70),
            ("from below", [(p, case)], -45, -40),
        ],
        os.path.join(OUT, "camera_pod_preview.png"),
    )
    lo, hi = p.bounding_box()[:3], p.bounding_box()[3:]
    print(f"pod: {hi[0]-lo[0]:.1f} wide (shell {pod_w:.1f}) x {hi[1]-lo[1]:.1f} long, {hi[2]:.1f} above the roof, "
          f"pivot {PIVOT_Z:.1f} up")
    (fx, fy), _, (tx, ty) = bolt_xy()
    x0, y0, x1, y1 = cable_hole()
    print(f"roof: 3x 2.9 holes, two {2*abs(fx):.1f} apart {FRONT_Y - fy:.1f} behind the pod's face, one on the centre line "
          f"{FRONT_Y - ty:.1f} behind it; cable slot {x1-x0:.0f} x {y1-y0:.0f}, {FRONT_Y - y1:.1f}..{FRONT_Y - y0:.1f} behind the face")


if __name__ == "__main__":
    main()
