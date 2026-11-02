# Hardware

**English** | [繁體中文](../zh-TW/hardware.md) | [简体中文](../zh-CN/hardware.md)

## 3D-printed parts

All models are parametric Python scripts (manifold3d) in [`firmware/wheel-esp32/enclosure`](../../firmware/wheel-esp32/enclosure). The STLs are in `enclosure/out/`. The `*_viewer.html` and `*_assembly.html` files are assembly previews you can open in a browser.

| Model | Parts |
|---|---|
| `p4_case.py` | A desk case for the P4 board: the screen tray `p4_tray.stl`; the stand on the MOZA base `p4_stand.stl`, with a slot for a 100 × 45 two-driver box speaker and room for the ELRS Nano; and `p4_multi_cover.stl`, which carries the 4-in-1 module on the stand's back wall |
| `minicar_cage.py` | A test cage for the 1:28 rally car: the shape of the free room under the shell |
| `minicar_mount.py` | A carrier for that car's FPV and radio parts, inside the shell |
| `vtx_mount.py` | A low, fan-cooled mount for a Walksnail Avatar Ascent Lite+ VTX and its camera |
| `camera_pod.py` | A WRC-style roof pod for a WiFiLink 2 camera on the MJX 14303 |
| `wifilink_mount.py` | A clamp mount for a RunCam WiFiLink 2 on an 8 mm round brace |

The comment at the top of each script says how to orient the print and which screws it takes. Parameters marked `MEASURE` should be measured on your own part with calipers before you print. The geometry and preview helpers they share are in `cad.py`.

```bash
cd firmware/wheel-esp32
python3 -m venv .venv
.venv/bin/pip install manifold3d numpy trimesh matplotlib
.venv/bin/python enclosure/p4_case.py
```

## X2201 carrier board

[`hardware/x2201-carrier`](../../hardware/x2201-carrier) is a passive carrier board for converting the X2201 (1:22 4WD crawler). It has no chips, only connectors and pads. It brings the battery, the power switch, the ZERO-Z ESC, the motor, the ELRS receiver (a Lite RX used as a 2-channel PWM receiver), the servo, the lights and the FPV power together on one board instead of a nest of wires. It mounts on the chassis' centre holes.

| Ref | Part |
|---|---|
| J1 | ESC, ZH1.5 4-pin (S2, S1, GND, 5V) |
| J2 | Lite RX pads |
| C1, C2 | 220 µF (7343) and 100 nF on the 5V rail |
| J3, J4 | Servo out and the ESC's servo lead (ZH 3-pin) |
| J5–J7, R1, R2 | Lights, with 0 Ω resistors as placeholders |
| JP1, J9 | FPV supply select and output |
| J8, J10 | Battery and power switch (PH2.0 2-pin) |
| J11–J13 | ESC power, ESC motor, and the motor (PH2.0 2-pin) |
| H1, H2 | M2 mounting holes |

- `gen_sch.py` generates the schematic (KiCad 10). To change a connection, edit the script and run it again. `x2201-carrier.pdf` is the exported schematic.
- Only the schematic exists so far. The PCB layout waits until the real parts are measured.
- The motor's high current runs on the ESC's own wires, so 1 oz copper is enough.

```bash
python3 hardware/x2201-carrier/gen_sch.py
kicad-cli sch erc hardware/x2201-carrier/x2201-carrier.kicad_sch
kicad-cli sch export pdf -o hardware/x2201-carrier/x2201-carrier.pdf hardware/x2201-carrier/x2201-carrier.kicad_sch
```

`gen_sch.py` looks for the KiCad symbol libraries in the default macOS install location. On other systems, change `LIB`.
