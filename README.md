# rc-control

**English** | [繁體中文](README.zh-TW.md) | [简体中文](README.zh-CN.md)

Drive RC cars with a sim-racing wheel and pedals. Plug the wheel into a 7" ESP32-P4 touch screen: it reads the wheel over USB, runs a driving model with ignition, gears, coasting and a real brake, and sends the result to the car over the radio that car uses. You don't need a PC.

![Desktop app dashboard](docs/dashboard.png)

## Features

- **Standalone wheel controller.** Built on the ESP32-P4 7" touch board with a MOZA R5 wheel base.
- **Three ways to reach the car**, chosen per car:
  - ExpressLRS (CRSF)
  - a 4-in-1 MULTI module, over its serial protocol or as PPM
  - the toy car's own stock remote, with its pots driven by a DAC
- **Per-car handling** that every radio goes through. You set the steering range, expo, steering and throttle dead bands, trim, end points and reverse on the wheel itself.
- **Driving like a car.** Ignition, gears R N 1 2 3, coasting, a real brake, and an automatic brake-then-reverse sequence for the ESC.
- **USB PID force feedback** on the MOZA base. Centring gets stronger with speed, and a soft stop marks the steering lock.
- **Dashboard.** Two instrument clusters with Simplified and Traditional Chinese text, six car profiles, and engine sound synthesised live on the board's speaker.
- **Desktop app** (Rust, optional). Drives an ELRS module from a PC and shows OpenIPC FPV video from a USB Wi-Fi adapter.
- **3D-printable parts and a car carrier board.** A stand for the MOZA base, mounts for the car, and a KiCad schematic.

## Documentation

| | |
|---|---|
| [Wheel controller](docs/en/wheel-controller.md) | Hardware, wiring, building and flashing the firmware |
| [Driving and handling](docs/en/driving.md) | Buttons, the driving model, cars, the handling settings, force feedback |
| [Radios](docs/en/radios.md) | ExpressLRS, MULTI 4-in-1, the toy remote |
| [Converting a toy remote](docs/en/toy-remote.md) | Driving a toy car's stock remote with an MCP4728 DAC |
| [Hardware](docs/en/hardware.md) | 3D-printed parts and the X2201 carrier board |
| [Desktop app](docs/en/desktop-app.md) | PC version: ELRS control, FPV video, Windows build |
| [Development](docs/en/development.md) | Code layout, serial console, tuning page, regenerating fonts and assets |

## Quick start

```bash
git clone https://github.com/bynhack/rc-control.git
cd rc-control/firmware/wheel-esp32
. ~/esp/esp-idf/export.sh          # ESP-IDF v5.5
idf.py build
idf.py -p /dev/cu.usbmodemXXXX flash
```

Then wire up a radio ([Radios](docs/en/radios.md)), plug the wheel into the board's USB-A port, and press Start on the wheel to start the engine.

## Repository layout

```
firmware/wheel-esp32/   the standalone controller (ESP-IDF, C)
  main/                 firmware source
  tools/                remote_tune.html, a Web Serial bench page
  enclosure/            3D-printable parts (Python, manifold3d)
  design/               the dashboard artwork
hardware/               boards (KiCad)
src/, native/           the desktop app (Rust, with C++ for the video link)
docs/                   documentation in three languages
```

## Contributing

Issues and pull requests are welcome. Before you open a pull request, build the firmware with `idf.py build`. If you touched the desktop app, also run `cargo test`. New documentation goes into all three languages under `docs/`. If you can only write one, say so in the pull request and someone will translate it.

## License

This project is released under **GPL-3.0-only** ([LICENSE](LICENSE)). That covers the desktop app, the firmware, the 3D models and the hardware design. If you distribute a modified version, including firmware flashed onto a device, you must offer its source under the same license.

Third-party code and assets keep their own licenses:

| Part | Where | License |
|---|---|---|
| [Aviateur](https://github.com/OpenIPC/aviateur) (FPV receive: devourer + wfb-ng) | `third_party/aviateur` (submodule) | GPL-3.0 |
| ffmpeg-sys-next 9.0.1, with Windows stubs added | `vendor/ffmpeg-sys-next-9.0.1` | WTFPL (FFmpeg itself is LGPL/GPL) |
| ESP-IDF usb_host_hid, with interrupt OUT reports added | `firmware/wheel-esp32/components/usb_host_hid` | Apache-2.0 |
| ESP-IDF, LVGL, the Waveshare BSP and other components | downloaded by the ESP-IDF component manager | Apache-2.0 / MIT etc. |
| Noto Sans SC, Saira, Barlow Condensed (rendered glyphs) | `firmware/wheel-esp32/main/fonts` | SIL Open Font License 1.1 |

MOZA, Thrustmaster, ExpressLRS, OpenIPC, Waveshare and other names only say which hardware works with this project. The project has no affiliation with them.

**Disclaimer:** RC cars are fast and heavy, and these modifications involve batteries and radio transmitters. You are responsible for any damage or injury that comes from following this project. Follow your local radio regulations.
