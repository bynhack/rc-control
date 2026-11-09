# Wheel controller

**English** | [繁體中文](../zh-TW/wheel-controller.md) | [简体中文](../zh-CN/wheel-controller.md)

This page covers the standalone controller: hardware, wiring, and building and flashing the firmware. The wheel and pedals plug into an ESP32-P4 over USB. The board runs the driving model and the car's handling, then transmits over the radio you picked for that car. The 7" touch screen shows the dashboard and the settings, the speaker plays the engine sound, and the wheel base gets force feedback. You don't need a PC.

The firmware is in [`firmware/wheel-esp32`](../../firmware/wheel-esp32).

## Hardware

| Part | Model | Notes |
|---|---|---|
| Controller and dashboard | Waveshare ESP32-P4-WIFI6-Touch-LCD-7B | The USB-A (OTG) port takes the wheel. The USB-C "USB TO UART" port is for flashing and the log. 7" 1024×600 touch screen |
| Wheel base | MOZA R5 (USB `346e:0004`) or Thrustmaster T300RS (`044f:b66e`) | MOZA: set the wheel angle to 900° in Pit House. T300: put the switch on the base in PS3 (PC) mode; the firmware sets 900° itself |
| ELRS transmitter | A CYCLONE Nano RX2400 flashed as "RX as TX" (two wires), or a BETAFPV module (one wire) | See [Radios](radios.md#expresslrs) |
| 4-in-1 module (optional) | iRangeX IRX4+ bare board | See [Radios](radios.md#multi-4-in-1) |
| Toy remote driver (optional) | MCP4728 4-channel I2C DAC board | See [Converting a toy remote](toy-remote.md) |
| Speaker (optional) | 8 Ω 3 W, PH2.0 plug | Plugs into the board's speaker socket (on-board NS4150B amplifier) |

A stand that holds the board on the MOZA base, with room for the Nano, the 4-in-1 module and the speaker, is in [Hardware](hardware.md).

## Wiring

| Use | P4 pins | Notes |
|---|---|---|
| ELRS, Nano (two wires) | GPIO28 → Nano RX, GPIO30 ← Nano TX | P3 terminal. Power the Nano's 5V from pin 1 of the CAN / RS485 terminal |
| ELRS, BETAFPV (one wire) | GPIO28 → CRSF | Half duplex, 400000 baud |
| 4-in-1, PPM or serial | GPIO29 → the module's PPM pin | Module VIN to 5V |
| MCP4728 | I2C terminal SCL / SDA / GND (GPIO8 / GPIO7, shared with the touch panel) | **Take VCC from the 3V3 pin of the 12-pin header**, not from the I2C terminal. See [Converting a toy remote](toy-remote.md#wiring-the-dac) |

> [!WARNING]
> The VCC pin on the board's I2C PH2.0 terminal is **5 V**. A 3.3 V I2C module powered from it pulls the bus up to 5 V. The whole bus then hangs, and the touch panel stops with it.

The UART terminal (H8) shares UART0 with the flashing port, so don't use it for a radio.

## Build and flash

You need [ESP-IDF v5.5](https://docs.espressif.com/projects/esp-idf/en/v5.5/esp32p4/get-started/). The default target is the ESP32-P4.

```bash
cd firmware/wheel-esp32
. ~/esp/esp-idf/export.sh
idf.py build
idf.py -p /dev/cu.usbmodemXXXX flash
```

The ESP-IDF component manager downloads LVGL and the Waveshare BSP on the first build. To read the log, connect to the "USB TO UART" port at 115200 baud (`idf.py -p … monitor`).

> [!NOTE]
> If the [tuning page](development.md#tuning-page) is connected, flashing fails because the page holds the serial port. Press Disconnect (斷開) on the page first.

## First run

1. Plug the wheel base into the USB-A port. When the board recognises it, the dashboard shows the wheel. A T300 first shows up in a basic mode, and the board switches it over. The screen shows "switching mode" (切换模式中) for a moment while it does.
   - **Wheel model** (方向盘型号) on the **Drive** (驾驶设置) tab picks the base: **Auto** (自动) uses whichever is plugged in, and MOZA R5 or T300RS uses only that one. If a different base is plugged in, it is left alone and the status tab says which one you picked.
2. Tap ⚙ at the top right of the screen. Under **Cars** (车辆), choose a car. Under **Radio** (发射设置), choose how that car is reached. The screen is in Chinese; the docs give each label in English with the Simplified Chinese on screen in brackets.
3. Bind the receiver as described for that radio in [Radios](radios.md).
4. Put the gearbox in N, release both pedals, and press **Start** to start the engine. Then [drive](driving.md).
