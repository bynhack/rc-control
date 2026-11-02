# wheel-esp32

The standalone wheel controller firmware for the ESP32-P4 7" touch board.
獨立方向盤控制器的韌體 · 独立方向盘控制器的固件

| | English | 繁體中文 | 简体中文 |
|---|---|---|---|
| Hardware, wiring, build | [Wheel controller](../../docs/en/wheel-controller.md) | [方向盤控制器](../../docs/zh-TW/wheel-controller.md) | [方向盘控制器](../../docs/zh-CN/wheel-controller.md) |
| Driving and handling | [Driving](../../docs/en/driving.md) | [駕駛和操控](../../docs/zh-TW/driving.md) | [驾驶和操控](../../docs/zh-CN/driving.md) |
| Radios | [Radios](../../docs/en/radios.md) | [發射方式](../../docs/zh-TW/radios.md) | [发射方式](../../docs/zh-CN/radios.md) |
| Toy remote | [Converting a toy remote](../../docs/en/toy-remote.md) | [改裝玩具遙控器](../../docs/zh-TW/toy-remote.md) | [改装玩具遥控器](../../docs/zh-CN/toy-remote.md) |
| 3D-printed parts | [Hardware](../../docs/en/hardware.md) | [硬體](../../docs/zh-TW/hardware.md) | [硬件](../../docs/zh-CN/hardware.md) |
| Code, console, tools | [Development](../../docs/en/development.md) | [開發](../../docs/zh-TW/development.md) | [开发](../../docs/zh-CN/development.md) |

```bash
. ~/esp/esp-idf/export.sh
idf.py build
idf.py -p /dev/cu.usbmodemXXXX flash
```
