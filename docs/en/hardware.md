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
| `x2201_cage.py` | Test cage for the Geeks X2201 cab: the room inside the shell, for a driver-view Ascent Lite+ camera |
| `x2201_fpv_mount.py` | Driver-view FPV mount inside the X2201 cab: the Ascent Lite+ camera looks out through the windscreen, the VTX and a 25 mm fan behind it, taped either side of the chassis channel |
| `x2201_liner.py` | Height map of the X2201 black inner liner from a 3D scan (point cloud), `x2201_liner.npz`; the mount checks against it; also a printable replica, `x2201_liner_replica.stl` |
| `camera_pod.py` | A WRC-style roof pod for a WiFiLink 2 camera on the MJX 14303 |
| `wifilink_mount.py` | A clamp mount for a RunCam WiFiLink 2 on an 8 mm round brace |

The comment at the top of each script says how to orient the print and which screws it takes. Parameters marked `MEASURE` should be measured on your own part with calipers before you print. The geometry and preview helpers they share are in `cad.py`.

```bash
cd firmware/wheel-esp32
python3 -m venv .venv
.venv/bin/pip install manifold3d numpy trimesh matplotlib
.venv/bin/python enclosure/p4_case.py
```

## X2201 main board

The X2201's confirmed hardware plan, its parts and wiring, is in [hardware/PLAN.md](../../hardware/PLAN.md) (Traditional Chinese). The board drawn from it is [`hardware/x2201-mainboard`](../../hardware/x2201-mainboard): 40 × 40 mm, held by one M2 screw on a chassis boss and located by a post, inside the 40 × 60 mm room on the chassis.

- **One power input**: the 2S battery solders to the board, through a reverse guard (Q1).
- **ESC on the board**: a TI DRV8874 H-bridge drives the 260 motor through a ZH2.0 plug, current-limited to about 4.9 A.
- **5 V BEC on the board**: an LMR51430 buck, about 2–2.5 A, for the ESP32, the EP2, the servo, the fan and the IR LED.
- **Controller**: an ESP32-S3 SuperMini, hand-soldered on header pins, its USB-C off the board's end.
- **Plugs**: all side-entry ZH1.5 (EP2, VTX, servo, fan, power button), mouths facing out, so nothing stands up.
- **Power button**: momentary. Press to turn on (the S3 then holds the power with its TX pin); press again to turn off.

The board's shape can change to fit the car; the parts and wiring follow PLAN.md. Earlier boards (v3 to v9) were removed on 2026-11-16 and are in git history up to commit `56bd000`.

## Lap-timing transponder

Each car carries a transponder that flashes its car number on a 940 nm IR LED, so the finish-line arch can tell the cars apart (up to 8). The X2201 has it on its main board (the IR LED soldered at the board's rear edge). The other cars use the small board in [`hardware/transponder`](../../hardware/transponder) (15 × 22 mm).

- **Circuit**: a CH32V003J4M6 makes 38 kHz bursts on PC4 (TIM1_CH4); an AO3400 drives the LED at about 110 mA through 33 Ω, about 10 mA on average.
- **Car number**: set when flashing, `make flash CAR=3` (1–15). Flashed without `CAR`, it falls back to the solder jumpers: 1 plus the closed ones (+1, +2, +4).
- **J1**: 5V, GND, SWIO (2.54 mm). Wire it to any servo plug's + and − on the car's receiver. The WCH-LinkE goes on the same pins for flashing.
- **LED**: a 3 mm 940 nm LED, in the board or on two wires. It must see up through a window or a thin plastic shell.
- **Frame**: header burst 4T, gap 2T, then 8 bits LSB first (burst 1T, gap 1T = 0 or 2T = 1): the car number and its complement, then a 1T stop burst. T = 400 µs. Frames repeat after a random 4–12 ms gap.
- **Firmware**: [`firmware/transponder`](../../firmware/transponder), built with [ch32fun](https://github.com/cnlohr/ch32fun) (`make`, `make flash CAR=n`).

```bash
cd hardware/transponder
python3 gen_sch.py
FAB=1 /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 gen_pcb.py
```

The board scripts share `hardware/pcbgen.py` (layout) and `hardware/schgen.py` (schematic).
