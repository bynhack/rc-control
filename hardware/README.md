# hardware

Boards for the cars (KiCad). 車上用的電路板 · 车上用的电路板

- [PLAN.md](PLAN.md): the X2201's confirmed hardware plan, the parts and the wiring. The board's shape can change to suit the car; the parts and wiring follow this.
- [ROADMAP.md](ROADMAP.md): where the boards are going.
- [`x2201-mainboard`](x2201-mainboard): the X2201 main board, 40 × 40 mm, on one M2 screw and a locating post. ESP32-S3 SuperMini, DRV8874 brushed ESC, 5 V buck (about 2–2.5 A), side-entry ZH plugs, push-button power, the IR LED on board. Ordered from JLC on 2026-11-17 (commit `a1125d9`).
- [`transponder`](transponder): the lap-timing transponder on its own, for the other cars.

Earlier boards (v3 to v9) were removed on 2026-11-16; they're in git history up to commit `56bd000`.

Docs: [English](../docs/en/hardware.md#x2201-main-board) · [繁體中文](../docs/zh-TW/hardware.md#x2201-主板) · [简体中文](../docs/zh-CN/hardware.md#x2201-主板)

`pcbgen.py` and `schgen.py` are the helpers the boards' `gen_pcb.py` / `gen_sch.py` share. `lib/` holds symbols KiCad doesn't ship. See [lib/README.md](lib/README.md).
