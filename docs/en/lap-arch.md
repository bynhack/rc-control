# Lap-timing arch

**English** | [繁體中文](../zh-TW/lap-arch.md) | [简体中文](../zh-CN/lap-arch.md)

The arch over the finish line reads each car's IR transponder (see [Hardware](hardware.md#lap-timing-transponder)), works out every car's crossing time and lap time, and prints them on its USB serial. The first version uses off-the-shelf parts on perfboard, no PCB. Firmware: [`firmware/lap-arch`](../../firmware/lap-arch).

> Status: the firmware builds (ESP32-C3, or S3), and the decoder and lap logic pass simulated tests on the host. The arch hasn't been built or tried with a real car yet.

## How it works

- Each car sends its number from D6 on its main board (an IR204, 940 nm, pointing up): 38 kHz bursts at 1/3 duty, about 110 mA peak. 9–12 ms frames, a random 4–12 ms apart.
- Six TSOP38238 receivers on the arch's beam look down. A car passing under is read a few times.
- **Crossing = the middle of the first and last frame read.** As long as the arch's view is about symmetric front to back, it doesn't depend on how wide that view is.
- A pass ends when that car hasn't been read for 200 ms; then the event goes out. A crossing under 2 s after the last one isn't a lap (a car stopped under the arch, or backing through).

## Dimensions

A 1:28 car is about 70–90 mm wide and 50–60 mm tall with the FPV camera; the X2201's IR LED is inside the shell, 40–50 mm off the ground, pointing up.

| Item | Value |
|---|---|
| Inside width (between the legs) | 600 mm, for a 50–55 cm track |
| Clear height (track to the beam's underside) | 150 mm |
| Receivers | 160 mm above the track, 100 mm apart: ±50, ±150, ±250 mm |
| Number of receivers | 6 (8 bought); one more for every 100 mm of extra track width |
| Beam | 2020 aluminium extrusion, 700 mm |
| Legs | 2020 extrusion, 2 × 170 mm, each on 2 corner brackets; the feet taped down or weighted |

The LED is about 115 mm from the receivers. That's roughly 3–8 W/m² of irradiance: over ten thousand times the receivers' threshold (0.15 mW/m²), but under the datasheet's 30 W/m² maximum, so its pulse-width spec still holds. **The hard part isn't hearing the cars, it's not hearing them from too far**, so each receiver sits in a black shroud:

- A 20 mm deep rectangular tube with the receiver at its top, the opening 40 mm along the track (about ±45°) and 18 mm across (about ±25°). Printed in black PLA, clipped onto the 2020 and held with an M4 T-nut, so it slides sideways. The TSOP38238's own half-sensitivity angle is ±45°.
- The view along the track is then about 230 mm. At 5 m/s a car is in view for about 45 ms, at least one whole frame (the worst case needs 37 ms).
- No model for it yet (no script in `cad`): make it to the sizes above, or start with black heat-shrink over the receiver.

## Receiver vs. datasheet

The TSOP38238 is a TSOP382 (AGC2, for long-burst remotes). Against the Vishay datasheet (document 82491, rev 2.1):

| Datasheet | Transponder | Result |
|---|---|---|
| Supply 2.0–5.5 V | 3.3 V | runs straight off the C3's 3V3, no level shifting on OUT |
| Bursts at least 10 cycles | 1T = 400 µs = 15.2 cycles; the 4T header 61 cycles | OK |
| After a 10–70 cycle burst, a gap of at least 12 cycles | shortest gap 1T = 15.2 cycles; 2T = 30 cycles after the header | OK, only 3 cycles to spare on 1T |
| Bursts over 70 cycles need a gap over 5× | none over 70 cycles | n/a |
| At most 1700 short bursts a second | 10 bursts a frame, a frame every 13.2 ms at the fastest: at most ~760 a second | OK |
| Delay td 7–13 cycles, width ±5 cycles | the decoder reads burst start to start; the tests use a wider 7–15 and −5 to +6 | covered by the tests |
| Maximum irradiance 30 W/m² | about 3–8 W/m² | OK |

One thing not checked: the datasheet's Fig. 8, maximum envelope duty cycle vs. burst length, is a chart without numbers. The transponder's envelope duty is about 42–57% within a frame, 21–39% counting the gaps. If that's too much, the AGC turns the gain down; check with the fake car below at the real distance that every frame comes through.

## Parts

| Qty | Part | Notes |
|---|---|---|
| 1 | ESP32-C3 SuperMini | spare: an S3 SuperMini |
| 6 | Vishay TSOP38238 | straight off 3.3 V; pins (facing the lens, left to right) 1 OUT, 2 GND, 3 VS |
| 6 | 100 Ω resistor | each receiver's supply filter (the datasheet's R1) |
| 6 | 10 µF capacitor | each receiver's supply filter (the datasheet's C1), across VS–GND |
| 7 | small perfboard pieces | one per receiver (about 20 × 30 mm), one for the C3 |
| ~1.5 m | 3-core wire (servo lead or 26 AWG ribbon) | 3V3, GND and OUT along the beam through the 6 receivers |
| 1 | 2020 extrusion, 700 mm + 2 × 170 mm | beam and legs |
| 4 | 2020 corner brackets + M5 screws, T-nuts | |
| 6 | M4 T-nuts + screws | for the shrouds |
| 6 | printed shrouds | see above |
| 1 | USB-C cable | power and serial, to a computer or later the P4 |

For bench tests (not part of the arch):

| Qty | Part | For |
|---|---|---|
| 1 | 38 kHz IR receiver module (23.5 × 20.8 mm, OUT/VCC/GND) | a single-receiver bench test |
| 1 | 38 kHz IR transmitter module (DAT/VCC/GND) | a "fake car": the arch's `sim` command sends transponder frames from GPIO10 |

## Wiring

The TSOP38238's output is NPN open-collector with a built-in 30 kΩ pull-up to VS. The 6 OUTs tied together make a wired-AND: any receiver that sees the signal pulls the line low. Six 30 kΩ pull-ups in parallel are about 5 kΩ, so no external pull-up is needed, and with VS at 3.3 V the GPIO never sees more than 3.3 V.

```
 3-core wire along the beam, through RX1–RX6

 C3 3V3   ────┬──────────┬──────── … ──┬──
 C3 GND   ────┼──┬───────┼──┬───── … ──┼──┬──
 C3 GPIO4 ────┼──┼──┬────┼──┼──┬── … ──┼──┼──┬──
              └──┴──┴─   └──┴──┴─      └──┴──┴─
                RX1        RX2           RX6

 Each receiver's perfboard piece:
   3V3   ──[100 Ω]──┬── VS   (pin 3)
                    ═  10 µF
   GND   ───────────┴── GND  (pin 2)
   GPIO4 ────────────── OUT  (pin 1)

 Optional fake car: C3 GPIO10 ── transmitter module DAT; its VCC ── C3 5V; GND ── GND
```

On each receiver's piece: 3V3 through 100 Ω to VS, 10 µF across VS–GND close to the receiver; OUT and GND straight onto the wire. The C3's piece only needs pin headers and the wire terminals.

### The receiver module (bench test)

The 23.5 × 20.8 mm receiver module is for trying things on the bench only; don't put it in parallel with the arch's six: its indicator LED and resistor hang off OUT, so in parallel they draw current and change the pull-up.

- On 3.3 V, OUT tops out at 3.3 V and can go straight to GPIO4 (check first that it receives at 3.3 V).
- On 5 V, OUT is pulled to 5 V: divide it first (e.g. 10 kΩ in series, 20 kΩ to ground, take the middle) before GPIO4.

### The fake car (transmitter module)

The transmitter module drives its LED straight from DAT and leaves the modulation to the program, so it needs the 38 kHz carrier, which is what `sim` sends. DAT to GPIO10, VCC to the SuperMini's 5V, GND to ground. Type `sim 3` and it sends car 3's frames in the transponder's format (T = 400 µs, 38 kHz, 1/3 duty, a random 4–12 ms between frames); `sim 0` stops. About 1.3 m range and 20°: point it at the arch's receivers.

### One input per receiver (if side-by-side crossings are missed)

The simulation shows that **when two cars cross side by side, the wired-AND arch misses both nearly every time**: their frames overlap and neither decodes. With each receiver's OUT on its own GPIO and its own decoder, the two cars are read by different receivers. The same parts, 5 more wires:

- C3 SuperMini: OUT1–OUT6 → GPIO 0, 1, 3, 4, 5, 6 (not 2, 8, 9: strapping pins; 10 stays for the fake car)
- S3 SuperMini: GPIO 4, 5, 6, 7, 8, 9
- Firmware: `idf.py menuconfig` → Lap arch → Receiver input GPIOs = `0,1,3,4,5,6`

It relies on the shrouds narrowing each receiver's view across the track, so cars side by side land on different receivers. Compared:

| 4 cars, 31 crossings each, 14 of them side by side | wired-AND (1 GPIO) | one per receiver (6 GPIOs) |
|---|---|---|
| 40 ms in view | 16 missed (12 side by side) | 1 missed |
| 60 ms in view | 15 missed (13 side by side) | 0 missed |
| 100 ms in view | 8 missed (8 side by side) | 2 missed (0 side by side) |

The arch's plan is wired-AND; whether to switch is for when it exists. The firmware does both.

## Firmware

ESP-IDF 5.x, ESP32-C3 by default:

```bash
cd firmware/lap-arch
. ~/esp/esp-idf/export.sh
idf.py build
idf.py -p /dev/cu.usbmodemXXXX flash monitor
```

For an S3 SuperMini, `idf.py set-target esp32s3` first. Settings are in `idf.py menuconfig` → Lap arch: input GPIOs (default `4`), the fake car's GPIO (default 10), the pass gap (200 ms), the shortest lap (2000 ms).

The decoder and lap logic are plain C and test on the computer:

```bash
make -C firmware/lap-arch/test
```

The tests use a receiver model for 1–6 receivers wired-AND, noise, two cars in view at once, and 4 cars running 30 laps.

### Output

USB serial, one JSON object per line:

```
{"ev":"boot","inputs":[4],"pass_gap_ms":200,"min_lap_ms":2000}
{"ev":"start","car":3,"t_ms":12345,"frames":4,"span_ms":38}
{"ev":"lap","car":3,"lap":1,"t_ms":20579,"lap_ms":8234,"frames":3,"span_ms":30}
{"ev":"too_soon","car":3,"t_ms":21002,"after_ms":423,"frames":1}
```

- `start`: the car's first crossing since a reset, lap 0, no lap time.
- `lap`: `lap` is laps completed, `lap_ms` this lap's time.
- `too_soon`: under the shortest lap since the last crossing; not counted.
- `t_ms` is the arch's time since boot; `frames` how many frames were read in this pass, `span_ms` first to last.
- An event goes out 200 ms after the car leaves the view.

### Commands

Type a line on the serial port:

| Command | Does |
|---|---|
| `reset` | clear all laps (a new race) |
| `raw` | print every frame on/off (`{"ev":"frame",...}`), for setting up the shrouds |
| `stats` | frames decoded per input, and how many were rejected and why |
| `sim 3` | send car 3's frames from the fake car on GPIO10 (`sim 0` stops) |

## Decoding

- The receivers stretch or shrink a burst by up to ~130 µs and their delay varies; wired-AND, a near receiver answers before a far one and the bursts grow longer still. A 1T gap can shrink below 100 µs.
- So a bit isn't read from its gap but from **burst start to the next burst start**: 2T is a 0, 3T a 1. Burst length only picks out the 4T header.
- Spikes under 40 µs are dropped, and dropouts under 40 µs inside a burst are bridged.
- Two cars in view at once garble each other's frames, and the number-plus-complement check lets about 1 in 16 garbled frames through. So a frame must also end in **3.4 ms of quiet** after its stop burst (the transponder waits at least 4 ms), which the other car's bursts break. In the simulation no frame ever decoded as the wrong car.

## Before racing

1. Just the receiver module (or one TSOP38238), the fake car on `sim 3` pointed at it: about 50 `raw` frames a second.
2. All 6 receivers: `stats` shows the count. With the fake car about 115 mm away, check that every frame comes through (the Fig. 8 item).
3. Push a car slowly under the arch with `raw` on: the span it's read over should be symmetric and about 230 mm. Too wide, deepen the shrouds.
4. Race: `frames` should be at least 2, `span_ms` matching the speed.

## Later: lap times to the cars

The plan is arch → P4 → ELRS AUX channel → the car's S3 (see docs/project-notes.md); not in this version:

- Arch to P4: the arch's JSON already has what the P4 needs (car, lap, lap time). The P4's USB-A port has the wheel on it, so it's a UART, or ESP-NOW (the C3 has Wi-Fi).
- P4 to car: each car has its own ELRS link; the P4 puts that car's latest lap and lap time on an AUX channel. AUX channels have few bits, so the lap time goes in pieces, or only "lap count + new lap" and the car works out the rest.
- On the car: the S3 reads the AUX channel from CRSF and shows or announces it.
