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
| `x2201_carrier_frame.py` | The X2201 FPV mount's printed frame when the [carrier board](#x2201-carrier-board) is its base: VTX posts, fan pads and camera cheeks, screwed onto the board's M2 SMT nuts |
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

[`hardware/x2201-carrier`](../../hardware/x2201-carrier) is the base of the X2201's FPV mount and the car's low-current wiring in one. It takes the place of the printed mount's plate and reaches 10 mm further back: 54 × 52 mm, on 1 mm 3M VHB tape on the chassis' two strips either side of the middle channel. All parts are on the top, so the underside is flat. The printed frame (`x2201_carrier_frame.py`) screws onto its four M2 SMT nuts: set the VTX on the board, then lower the frame over it.

**Everything that leaves the board plugs in**, in one row along the back edge, under the rear window. Nothing is soldered to the board. Only the modules that come without a plug (the EP2, the IR LED, the fan) get a ZH pigtail soldered on once, at the module.

The ESC's switch turns everything on:

- **EP2 receiver, delayed 5V**: Q1 (AO3401) gives the EP2 its 5V 0.5–1 s after the ESC's BEC comes up. While the ZERO-Z starts, it holds the EP2's TX pad (GPIO1) low, and the EP2 hangs if it boots then. A series resistor doesn't help.
- **VTX switched by the BEC**: Q3 (AO3400) turns Q2 (AO3401) on while there is 5V, so the VTX gets the battery only while the ESC is on. R2 and R3 keep Q2's gate within its 12 V limit up to 3S.

| Ref | Part |
|---|---|
| J1 | ZERO-Z receiver cable, ZH1.5 4P (yellow S2, blue S1, green GND, brown 5V) |
| J2 | EP2, ZH1.5 4P: 1 RX pad (CH2 throttle), 2 TX pad (CH1 steering), 3 GND, 4 5V (delayed) |
| Q1, C1, R1, D1 | EP2 power delay |
| Q2, Q3, R2–R5 | VTX power switch |
| J6 | Battery tap, ZH1.5 2P: 1 battery +, 2 GND. A battery Y lead branches it off the battery-to-ESC lead |
| J3 | VTX, SH1.0 4P: 1 power, 2 GND (3 and 4 unused). A same-direction SH1.0 4P lead plugs straight into the VTX |
| J4 | 25 mm fan, ZH1.5 2P: 1 5V, 2 GND |
| C2, C3 | 22 µF on 5V and on the battery |
| U2, C4, JP1–JP3, TP11 | Lap-timing transponder: CH32V003, car-number jumpers, SWIO pad (for flashing only; the WCH-LinkE's GND goes on a nut) |
| Q4, R6–R8, J5 | The transponder's IR LED driver; J5 is ZH1.5 2P: 1 LED +, 2 LED − |
| H1–H4 | M2 SMT nuts (e.g. Würth 9774020151R) for the printed frame |

- The servo plugs into the ESC's servo port, since the ESC's gyro drives it.
- The transponder's LED points up through the shell's open rear window, at the finish-line arch.
- `gen_sch.py` writes the schematic and `gen_pcb.py` the layout, with the same net names. `x2201-carrier.pdf` is the exported schematic.
- With `FAB=1`, `gen_pcb.py` also writes the Gerbers, `bom.csv` and `cpl.csv` for JLCPCB's SMT assembly, so the small parts come soldered.
- Check the cable's colours against the labels by J1 before plugging it in.
- Check that the chassis is flat under the extra 10 mm at the back when you test-fit the cage.

**Ordering from JLCPCB**

1. Upload `x2201-carrier-gerber.zip`: 2 layers, 1.6 mm thick (the frame is drawn for 1.6 mm), any colour.
2. Turn on SMT assembly on the top side, then upload `bom.csv` and `cpl.csv`. The BOM has LCSC numbers. Pick R6 (33 Ω 1206) and the M2 SMT nuts yourself, or solder the nuts by hand if JLC doesn't stock them.
3. In JLC's placement preview, check that pin 1 of U2, Q1–Q4, D1 and J1–J6 sits on the right pad. KiCad and JLC disagree on some rotations; fix them there.
4. For J1, buy a ZH1.5 4P lead with both ends wired the same way (pin 1 to pin 1). Before the first power-up, check with a meter that the ESC's 5V lands on J1 pin 4.

```bash
cd hardware/x2201-carrier
python3 gen_sch.py
/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 gen_pcb.py   # FAB=1: gerber/, bom.csv, cpl.csv
kicad-cli pcb drc --refill-zones x2201-carrier.kicad_pcb
```

The scripts look for KiCad in the default macOS install location. On other systems, change `LIB` and `FP`.

## X2201 carrier board v4 (ESP32-S3)

[`hardware/x2201-carrier-v4`](../../hardware/x2201-carrier-v4) puts an ESP32-S3 on the carrier, so the car has its own brain. It's the next board, not yet built: the v3 above is the one being made.

- **Signal path**: EP2 → CRSF (UART) → ESP32-S3 → PWM → ESC. Set the EP2 to serial CRSF output instead of PWM; the ESP32 does the failsafe (throttle to neutral when CRSF stops).
- **What it adds**: battery voltage sent back to the wheel as telemetry, an OSD on the goggles (MSP over the VTX cable's pins 3 and 4), the lap-timing IR code (no CH32 needed), a status LED, and USB-C on the front edge for flashing and the console.
- **The EP2 boot hang is gone**: the ESC no longer touches the EP2's pins, so v3's delayed 5V (Q1, C1, R1, D1) is dropped.
- **WiFi is for setup only** (car number, trims), with the car still: it shares 2.4 GHz with ELRS.
- **Same plugs and cables as v3.** The board is 4 mm longer at the front for the module's antenna (58.2 × 52 mm). Check there's room under the shell in front.
- **The printed frame** fits both boards: [`x2201_carrier_frame.py`](../../firmware/wheel-esp32/enclosure/x2201_carrier_frame.py) now has a small notch under the camera cheeks, over v4's two decoupling caps.
- **Battery voltage** is read on IO17 (ADC2), which works with the WiFi off, i.e. whenever the car drives.
- DRC and the frame's fit check are clean. The ESP32 firmware isn't written yet.

```bash
cd hardware/x2201-carrier-v4
/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 gen_pcb.py   # FAB=1: gerber/, bom.csv, cpl.csv
/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 gen_sch.py   # the schematic, from the board's nets
```

## X2201 carrier board v5 (OpenIPC)

[`hardware/x2201-carrier-v5`](../../hardware/x2201-carrier-v5) is v4 with OpenIPC digital video in place of the Walksnail VTX, so the car only needs a camera plugged in. **Only the circuit is drawn.** The layout waits for the real parts to be measured.

- **Video**: a ready-made OpenIPC Thinker Base (SSC338Q, 25 × 25 mm, M2 holes on 20 × 20) sits on standoffs over the board. The IMX335 camera plugs into it. The desktop app already receives OpenIPC with an RTL8812AU card.
- **WiFi**: a BL-M8812EU2 (RTL8812EU) module. It draws up to 5 V 2.x A, far more than the ESC's 1 A BEC, so U4 (LMR51430, 5 V 3 A) makes its own rail from the battery. Its 98 % max duty keeps 5 V even from a flat 2S. It needs a heat sink and the fan. Keep its TX power low indoors.
- **ELRS receiver on the board**: ESP32-C3 + SX1280 + AT2401C, wired as ExpressLRS's "Generic C3 2400 PA" layout, so stock ELRS runs on it. The antenna is a U.FL (J10); route it out through a shell window, since the shell is metal. The ESP32-S3 controls the C3's EN and GPIO9, so ELRS can be flashed from the Mac over the USB-C. The EP2 plug (J2) stays as the fallback: hold the C3 in reset and plug in the EP2. The C3's own WiFi (ELRS's setup page) has its own U.FL (J11). Its periphery follows Espressif's reference schematic (40 MHz crystal) and AnyLeaf's open receiver design (MIT). The matching values are starting points and need tuning.
- **Plugs**:
  - J3, SH1.0 6P: Thinker Power/UART2 in its own order. Pins 1–2 are the switched battery, 3 is its RX, 4 is its TX, 5–6 are GND.
  - J7, SH1.0 4P: Thinker USB. Its Vd pin is left unused.
  - J8, ZH1.5 8P: the WiFi module in its pin order. The ESP32 can reset it (IO12).
  - J6, the battery plug, is now a PH2.0 (about 2 A).
  - The fan runs off the WiFi's 5 V.
- **The ESP32** sends MSP to the Thinker's UART2 (msposd draws the OSD), through 1k resistors so neither board powers the other.
- **Power**: the Thinker and the WiFi come on with the ESC, as v3's VTX did.
- **To measure when the parts arrive**: the module's height, holes and heat sink, the Thinker's height with its heat sink, and the plug types. Then lay out the board and redo the printed frame.
- ERC: 0 errors.

```bash
cd hardware/x2201-carrier-v5
/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 gen_pcb.py   # placed, not routed
/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 gen_sch.py   # the schematic, from the board's nets
```

## Lap-timing transponder

Each car carries a transponder that flashes its car number on a 940 nm IR LED, so the finish-line arch can tell the cars apart (up to 8). The X2201 has it on its carrier board. The other cars use the small board in [`hardware/transponder`](../../hardware/transponder) (15 × 22 mm).

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
