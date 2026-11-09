# hardware

Boards for the cars (KiCad). 車上用的電路板 · 车上用的电路板

- [`x2201-carrier`](x2201-carrier): the X2201's FPV mount base and wiring board (极客者 1:22), with a lap-timing transponder.
- [`x2201-carrier-v4`](x2201-carrier-v4): the next carrier, with an ESP32-S3 between the receiver and the ESC (not built yet).
- [`x2201-carrier-v5`](x2201-carrier-v5): v4 with OpenIPC video (Thinker video board, BL-M8812EU2 WiFi, a 5V 3A buck) and the ELRS receiver on the board (ESP32-C3 + SX1280 + AT2401C). Circuit only; the layout waits for the parts to be measured.
- [`transponder`](transponder): the lap-timing transponder on its own, for the other cars.

Docs: [English](../docs/en/hardware.md#x2201-carrier-board) · [繁體中文](../docs/zh-TW/hardware.md#x2201-轉接板) · [简体中文](../docs/zh-CN/hardware.md#x2201-转接板)

`pcbgen.py` and `schgen.py` are the helpers the boards' `gen_pcb.py` / `gen_sch.py` share. `lib/` holds footprints and symbols KiCad doesn't ship: Espressif's ESP32-S3-MINI-1, and the SX1280, AT2401C and 2450FM07D0034 from AnyLeaf's elrs-hardware (MIT). See [lib/README.md](lib/README.md).
