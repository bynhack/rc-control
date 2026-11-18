# rc-control

[English](README.md) | [繁體中文](README.zh-TW.md) | **简体中文**

用模拟赛车的方向盘和踏板开遥控车。方向盘插在一块 7 寸 ESP32-P4 触控屏上：它用 USB 读方向盘，跑一套有点火、挡位、滑行和真实刹车的驾驶模型，再用那台车的发射方式发出去。全程不用电脑。

## 功能

- **独立的方向盘控制器**：ESP32-P4 7 寸触控板加 MOZA R5 或 Thrustmaster T300RS 方向盘底座，在屏幕上选。
- **三种发射方式**，每台车各自选：
  - ExpressLRS（CRSF）
  - 四合一 MULTI 高频头，走串口协议或 PPM
  - 玩具车原装遥控器，用 DAC 取代它的电位器
- **每台车各自的操控设置**，所有发射方式都要经过它：转角、中心柔和、方向和油门死区、方向回正、舵量、反转，都直接用方向盘设置。
- **照真车驾驶**：点火、R N 1 2 3 挡、滑行、真实刹车；进倒挡时会自动替电调发“刹车 → 倒车”。
- **力回馈**：两种底座都有（MOZA 用 USB PID，T300 用 Thrustmaster 的协议），回正力随车速加强，打到转角极限时有软性顶点。
- **仪表盘**：两款仪表、简繁中文界面、6 台车的配置，板子的喇叭实时合成引擎声浪。
- **车上的部分**：X2201 的主板（KiCad：ESP32-S3、板载有刷电调和 5V BEC、按钮开关机）、红外计圈应答器和终点拱门，以及方向盘支架和车上用的 3D 打印件。

## 文档

| | |
|---|---|
| [方向盘控制器](docs/zh-CN/wheel-controller.md) | 硬件、接线、编译和烧录固件 |
| [驾驶和操控](docs/zh-CN/driving.md) | 按键、驾驶模型、车辆、操控设置、力回馈 |
| [发射方式](docs/zh-CN/radios.md) | ExpressLRS、四合一 MULTI、玩具遥控器 |
| [改装玩具遥控器](docs/zh-CN/toy-remote.md) | 用 MCP4728 DAC 控制玩具车的原装遥控器 |
| [硬件](docs/zh-CN/hardware.md) | 3D 打印件和 X2201 主板 |
| [计圈拱门](docs/zh-CN/lap-arch.md) | 终点拱门：接收头、接线、固件、圈速事件 |
| [开发](docs/zh-CN/development.md) | 代码结构、串口命令、调试页面、重新生成字体和图片 |

## 快速开始

```bash
git clone https://github.com/bynhack/rc-control.git
cd rc-control/firmware/wheel-controller
. ~/esp/esp-idf/export.sh          # ESP-IDF v5.5
idf.py build
idf.py -p /dev/cu.usbmodemXXXX flash
```

然后接好发射方式（见[发射方式](docs/zh-CN/radios.md)），把方向盘插到板子的 USB-A 口，按方向盘的 Start 点火。

## 仓库结构

```
firmware/
  wheel-controller/     ESP32-P4 方向盘控制器（ESP-IDF，C）
    main/               固件源码
    tools/              remote_tune.html，Web Serial 调试页面
    design/             仪表盘的美术稿
  lap-arch/             终点计圈拱门（ESP32-C3）
  transponder/          没有主板的车用的红外计圈应答器（CH32V003）
hardware/               电路板（KiCad，用 Python 生成）
  PLAN.md               X2201 已确认的硬件方案
  x2201-mainboard/      X2201 主板
  transponder/          应答器小板
cad/                    3D 打印件（Python，manifold3d）
docs/                   三种语言的文档
```

## 参与贡献

欢迎提 issue 和 pull request。提 pull request 前，先用 `idf.py build` 编译固件。新的文档要写进 `docs/` 下的三种语言；只会写一种的话，在 pull request 里说一声，会有人帮忙翻译。

## 许可证

本项目以 **GPL-3.0-only** 发布（[LICENSE](LICENSE)），范围包括固件、3D 模型和硬件设计。发布修改后的版本（包括烧进设备的固件）时，要以同样的许可证提供源码。

用到的第三方代码和资源各自保留原来的许可证：

| 部分 | 位置 | 许可证 |
|---|---|---|
| ESP-IDF usb_host_hid（加了中断 OUT 报告） | `firmware/wheel-controller/components/usb_host_hid` | Apache-2.0 |
| ESP-IDF、LVGL、微雪 BSP 等组件 | 由 ESP-IDF 组件管理器下载 | Apache-2.0 / MIT 等 |
| Noto Sans SC、Saira、Barlow Condensed（生成的点阵字形） | `firmware/wheel-controller/main/fonts` | SIL Open Font License 1.1 |

MOZA、Thrustmaster、ExpressLRS、微雪等名称只用来说明兼容的硬件，跟本项目没有关系。

**免责声明：** 遥控车有速度、有重量，改装涉及电池和无线电发射。照本项目操作造成的损坏或伤害，请自行负责；无线电发射请遵守当地法规。
