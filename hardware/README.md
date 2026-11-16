# hardware

Boards for the cars (KiCad). 車上用的電路板 · 车上用的电路板

Where the boards are going: [ROADMAP.md](ROADMAP.md).

- [`x2201-carrier-v10`](x2201-carrier-v10): the stage 1 main board, 76 x 20 mm. The battery comes in here; the board feeds an external brushed ESC that has no BEC, and makes the 5 V itself with a 3 A buck. Routed, not yet fabbed.
- [`x2201-carrier-v9`](x2201-carrier-v9): the earlier 49 x 38 drawing. Do not fab it: its reverse-guard MOSFET is wired the wrong way round.
- [`x2201-carrier-v8`](x2201-carrier-v8): the same board with the EP2 driving the ESC directly and a delayed 5 V, on hold. The base for stage 2.
- [`transponder`](transponder): the lap-timing transponder on its own, for the other cars.
- [`archive`](archive): v3 to v7, kept for reference.

Docs: [English](../docs/en/hardware.md#x2201-carrier-board) · [繁體中文](../docs/zh-TW/hardware.md#x2201-轉接板) · [简体中文](../docs/zh-CN/hardware.md#x2201-转接板)

`pcbgen.py` and `schgen.py` are the helpers the boards' `gen_pcb.py` / `gen_sch.py` share. `lib/` holds footprints and symbols KiCad doesn't ship: Espressif's ESP32-S3-MINI-1, and the SX1280, AT2401C and 2450FM07D0034 from AnyLeaf's elrs-hardware (MIT). See [lib/README.md](lib/README.md).
