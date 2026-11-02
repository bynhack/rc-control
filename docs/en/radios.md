# Radios

**English** | [繁體中文](../zh-TW/radios.md) | [简体中文](../zh-CN/radios.md)

Each car picks its radio on the **Radio** (发射设置) tab, and only the selected radio transmits. All of them get the same signal from the [handling layer](driving.md#handling). Each radio only turns −1…+1 into its own output.

| Radio | Output | For |
|---|---|---|
| ELRS | CRSF on GPIO28 (and GPIO30) | Cars with an ExpressLRS receiver |
| 4-in-1, serial (四合一 串口) | MULTI serial protocol on GPIO29, protocol chosen on the screen | Cars with a receiver for one of the MULTI protocols |
| 4-in-1, PPM (四合一 PPM) | PPM on GPIO29, protocol chosen on the module's dial | The same, with the module in dial mode |
| Toy remote (遥控器主板) | Two DAC voltages over I2C | Toy cars without a standard receiver, through their own remote |

## ExpressLRS

### Nano RX2400 as the transmitter (two wires, recommended)

On the Radio tab, choose ELRS and set the button at the bottom left to **Wiring: two-wire Nano** (接法：双线 Nano). The Nano needs ELRS 3.5 or later receiver firmware built as "RX as TX" = internal. The ESP8285 only supports internal.

1. Power the Nano from 5V and GND only. After 60 s its LED blinks fast. Join the "ExpressLRS RX" Wi-Fi (password `expresslrs`) and open http://10.0.0.1.
2. Build the transmitter firmware with the flasher from the firmware package. Download the package from `https://artifactory.expresslrs.org/ExpressLRS/<commit>/firmware.zip`; the commit is listed in `index.json`. Then run:
   ```bash
   python3 flasher.pyz --dir firmware --target betafpv.rx_2400.nano --rx-as-tx internal --phrase <binding phrase>
   ```
3. Upload `firmware.bin.gz` under UPDATE on the web page. When it warns that the target doesn't match, choose to flash anyway.

The Nano's LED stays off while it runs. That's normal.

### BETAFPV module (one wire)

Connect the CRSF pin to GPIO28 and set DIP switches 3 and 4 to ON. Leave the wiring button on **one wire** (接法：单线).

### A plain ELRS receiver as a 2-channel PWM receiver

An ESP8285 receiver with only GND / VCC / TX / RX pads, such as the BETAFPV Lite RX, can drive a servo and an ESC directly, without reflashing:

1. Power the receiver from 5V and GND only. After 60 s, join its Wi-Fi and open `http://10.0.0.1/hardware.html`.
2. Set the PWM output pins to `1,3` (GPIO1 = TX pad, GPIO3 = RX pad), save and reboot.
3. Output 1 (TX pad) is CH1 steering and output 2 (RX pad) is CH2 throttle, at 50 Hz, with failsafe at 1500 µs.
4. Use the same binding phrase as the transmitter.

Put the ESC on the RX pad. The TX pad prints a boot message at power-up, which makes a servo twitch but can confuse an ESC.

ELRS only sends channels 1–4 at full resolution, so keep steering and throttle on them.

## MULTI 4-in-1

The iRangeX IRX4+ JR socket, from the top: 1 PPM → GPIO29, 2 unused, 3 VIN → 5V, 4 GND, 5 S.Port (not connected).

| Mode | Module dial | Binding |
|---|---|---|
| 4-in-1, serial | 0 | **Bind** (对频) on the Radio tab, or the wheel's N button. Lasts 30 s |
| 4-in-1, PPM | 1 to E (F selects the bank) | Hold the module's bind button while powering it, for 5 s |

- The module only reads the dial at power-up. After turning it, power-cycle the module.
- The serial signal is not inverted (a slowly blinking red LED means it is). A steady red LED means the module is receiving, and fast blinking means it is binding.
- Tested: a FlySky FS-GT2E car with an MXO-Racing RXC42-AG receiver (AFHDS 2A), in both modes. To bind the MXO receiver, put the transmitter into bind first, then hold the receiver's button for 2 s.
- MJX Hyper Go cars (14303 and others) use a protocol MULTI doesn't have. Replace their receiver instead.

## Toy remote

For toy cars without a standard receiver, the P4 drives the car's own remote: an MCP4728 DAC replaces the remote's steering and throttle pots, and the remote transmits to the car as usual. Tested with the JC-02T-2.4G remote of the X2201 (极客者).

Only a car set to this radio drives the remote. When you switch to another car, the remote holds its rest position, so the toy car doesn't move along.

How to convert the remote and calibrate it: [Converting a toy remote](toy-remote.md).
