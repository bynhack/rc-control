# hardware

Boards for the cars (KiCad). 車上用的電路板 · 车上用的电路板

Where the boards are going: [ROADMAP.md](ROADMAP.md).

- [`x2201-carrier-v8`](x2201-carrier-v8): ESP32-S3-MINI-1 control board, on hold. The base for the next board.
- [`transponder`](transponder): the lap-timing transponder on its own, for the other cars.
- [`archive`](archive): v3 to v7, kept for reference.

Docs: [English](../docs/en/hardware.md#x2201-carrier-board) · [繁體中文](../docs/zh-TW/hardware.md#x2201-轉接板) · [简体中文](../docs/zh-CN/hardware.md#x2201-转接板)

`pcbgen.py` and `schgen.py` are the helpers the boards' `gen_pcb.py` / `gen_sch.py` share. `lib/` holds footprints and symbols KiCad doesn't ship: Espressif's ESP32-S3-MINI-1, and the SX1280, AT2401C and 2450FM07D0034 from AnyLeaf's elrs-hardware (MIT). See [lib/README.md](lib/README.md).
