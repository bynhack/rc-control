# Converting a toy remote

**English** | [繁體中文](../zh-TW/toy-remote.md) | [简体中文](../zh-CN/toy-remote.md)

Many toy RC cars have no standard receiver; the car only talks to its own remote. This conversion lets the P4 drive that remote instead of your hands. The remote then transmits to the car as usual, so the car itself stays stock.

Tested with the JC-02T-2.4G remote of the X2201 (极客者). Any remote with a potentiometer for steering and one for throttle works the same way.

## How it works

The remote's chip reads each pot's middle pin, the wiper, as a voltage between its supply and ground. An MCP4728 DAC puts that voltage on the chip's pin instead, set by the P4 over I2C. The remote runs from the same 3V3 as the DAC, so the voltages keep the same ratio the pots had.

```
wheel → P4 (driving model, handling) → I2C → MCP4728 → remote's chip → 2.4 GHz → car
```

## Parts

| Part | Notes |
|---|---|
| MCP4728 4-channel DAC board | Address 0x60. Two channels are used: A steering, B throttle |
| PH2.0 4-pin socket and plug | Goes on the remote. Carries 3V3, GND, VA, VB |
| 3PDT toggle switch (3 poles, 2 positions) | Switches the remote between the P4 and its own pots and battery |
| Thin wire | Signal currents are tiny |

## Recommended: a socket and a switch

With a socket and a switch, the remote stays fully usable on its own: switch to **Stock** and put batteries in, or switch to **P4** and plug in the cable. The switch keeps the DAC and the pots apart, and the battery and the P4's 3V3 apart.

| Switch pole | Common (the remote's board) | Stock position | P4 position |
|---|---|---|---|
| 1 | The chip's steering input (the steering pot's pad) | The steering pot's middle pin | Socket VA |
| 2 | The chip's throttle input (the throttle pot's pad) | The throttle pot's middle pin | Socket VB |
| 3 | The board's battery + input | The battery box + contact | Socket 3V3 |

Connect the socket's GND straight to the remote's ground. It doesn't go through the switch.

### Steps

1. **Separate each pot's middle pin from its pad.** Desolder the middle pin and bend it up, or cut the trace leaving the pad. The pad is now the chip's input, and the pin is the pot's output. Don't touch the two outer pins.
2. **Separate the battery +.** Unsolder the battery box's + wire from the board. That wire goes to the switch's stock position, and its pad on the board goes to the common.
3. Wire the switch as in the table.
4. Mount the socket and the switch in the remote's case.
5. Make the cable from the P4 side. See [Wiring the DAC](#wiring-the-dac): the DAC's top row VA / VB / VCC / GND go to the plug.

> [!CAUTION]
> Never have batteries in while the P4's 3V3 is connected to the remote. The battery and the 3V3 rail would push current into each other and can damage the P4. With the switch, this can't happen.

## Quick conversion: the DAC in parallel

If you don't want to cut anything, solder the DAC outputs straight onto the pots' middle pins, in parallel with the pots. The DAC is stronger than the pot and sets the voltage. The test remote is wired this way.

- **Before using the remote with batteries**, unplug all four wires to the DAC: VCC, GND, VA, VB. Unplug the power wires first: the battery box contacts are connected to the P4's 3V3. Unplug VA and VB as well, because a DAC without power can pull the pots' voltage down.
- **While the P4 drives it**, leave the remote's wheel and trigger in the middle. At the end of their travel the pot drives straight against the DAC output, and the output gets pulled off.

## Wiring the DAC

| MCP4728 pad | Connects to |
|---|---|
| Bottom row VCC | The **3V3** pin of the P4's 12-pin header |
| Bottom row GND, SCL, SDA | GND, SCL, SDA of the P4's I2C terminal |
| Bottom row LDAC | GND (the outputs don't update without it) |
| Top row VA | Steering: switch pole 1 P4 position, or the steering pot's middle pin |
| Top row VB | Throttle: switch pole 2 P4 position, or the throttle pot's middle pin |
| Top row VCC, GND | The remote's power: switch pole 3 P4 position and ground, or the battery box contacts |

> [!WARNING]
> The VCC pin of the P4's I2C terminal is 5 V; don't use it. The DAC board's 4.7k pull-ups go to its VCC. At 5 V they pull the I2C bus to 5 V and the whole bus hangs, touch panel included.

The DAC stores the rest position in its EEPROM, so the car doesn't move while the P4 is still booting.

## Calibration

A toy remote's wheel and trigger only turn a small part of each pot. **Outside that span the chip misreads the voltage.** On the test remote, 2.1 V on the throttle drives forward. So the firmware never goes past the two measured ends.

Each channel needs three points: full one way, rest, full the other way. The values are DAC codes, 0–4095 = 0–3.3 V:

1. Open the [tuning page](development.md#tuning-page) and connect to the P4.
2. On the **Fine-tune DAC** (精調 DAC) tab, move each channel slowly with the mouse wheel. Mark the codes where the car reaches full lock or full speed each way, and where it starts and stops moving. Rest is the middle of the span where the car doesn't move.
3. Write the six values into the top of [`main/remote.c`](../../firmware/wheel-esp32/main/remote.c), then build and flash:
   ```c
   #define STEER_LEFT 3320
   #define STEER_CENTER 2020
   #define STEER_RIGHT 660
   #define THR_REVERSE 1720
   #define THR_CENTER 1507
   #define THR_FORWARD 1320
   ```
4. Set the dead bands, the span around rest where the car doesn't move, as that car's [handling](driving.md#handling), like on any other car. You can also set them from the serial console with `dead <left> <right> <forward> <reverse>`, in thousandths.

The values above are the JC-02T's. For reference, the X2201 drives well with steering dead bands of 138 / 132 and throttle dead bands of 545 / 484 (thousandths).
