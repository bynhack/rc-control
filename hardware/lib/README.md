# Local KiCad libraries

- `rc_control.kicad_sym`:
  - `DRV8874`: TI's brushed DC H-bridge, the X2201 main board's ESC. Drawn from the datasheet (SLVSF66A), HTSSOP-16 pinout.
  - `SX1280`, `AT2401C`, `2450FM07D0034`: kept for stage 2 (ELRS on the board). From AnyLeaf's
    [elrs-hardware](https://github.com/AnyLeaf/elrs-hardware), MIT licence, Copyright 2023 AnyLeaf LLC. Changes: SX1281
    renamed SX1280 (same pinout), GND pins typed power input, the SX1280's regulator pins typed passive.
- `AnyLeaf.pretty` (2450FM07D0034): the same source and licence, for stage 2.
