# 方向盘控制器

[English](../en/wheel-controller.md) | [繁體中文](../zh-TW/wheel-controller.md) | **简体中文**

这一篇讲独立控制器的硬件、接线，以及固件的编译和烧录。方向盘和踏板用 USB 接到 ESP32-P4，板子跑驾驶模型和那台车的操控设置，再用你给那台车选的发射方式发出去。7 寸触控屏显示仪表盘和设置，喇叭放引擎声浪，方向盘底座有力回馈。全程不用电脑。

固件在 [`firmware/wheel-esp32`](../../firmware/wheel-esp32)。

## 硬件

| 部件 | 型号 | 说明 |
|---|---|---|
| 主控和仪表盘 | 微雪 ESP32-P4-WIFI6-Touch-LCD-7B | USB-A（OTG）口接方向盘；USB-C“USB TO UART”口用来烧录和看日志；7 寸 1024×600 触控屏 |
| 方向盘底座 | MOZA R5（USB `346e:0004`） | 在 Pit House 里把方向盘角度设成 900° |
| ELRS 发射 | 刷成“RX as TX”的 CYCLONE Nano RX2400（双线），或 BETAFPV 高频头（单线） | 见[发射方式](radios.md#expresslrs) |
| 四合一（可选） | iRangeX IRX4+ 裸板 | 见[发射方式](radios.md#四合一-multi) |
| 遥控器主板（可选） | MCP4728 四路 I2C DAC 模块 | 见[改装玩具遥控器](toy-remote.md) |
| 喇叭（可选） | 8 Ω 3 W，PH2.0 插头 | 插板子的喇叭座（板载 NS4150B 功放） |

把板子固定在 MOZA 底座上的支架，里面留了 Nano、四合一和喇叭的位置，见[硬件](hardware.md)。

## 接线

| 用途 | P4 引脚 | 说明 |
|---|---|---|
| ELRS，Nano（双线） | GPIO28 → Nano RX，GPIO30 ← Nano TX | P3 端子；Nano 的 5V 接 CAN／RS485 端子第 1 脚 |
| ELRS，BETAFPV（单线） | GPIO28 → CRSF | 半双工，400000 baud |
| 四合一，PPM 或串口 | GPIO29 → 模块的 PPM 脚 | 模块 VIN 接 5V |
| MCP4728 | I2C 端子的 SCL／SDA／GND（GPIO8／GPIO7，跟触控共用） | **VCC 接 12 PIN 排针的 3V3**，不要接 I2C 端子。见[改装玩具遥控器](toy-remote.md#dac-接线) |

> [!WARNING]
> 板子 I2C PH2.0 端子的 VCC 是 **5 V**。3.3 V 的 I2C 模块从这里取电，会把总线拉到 5 V，整条总线卡死，触控也跟着失灵。

UART 端子（H8）跟烧录口共用 UART0，不能拿来接发射模块。

## 编译和烧录

需要 [ESP-IDF v5.5](https://docs.espressif.com/projects/esp-idf/zh_CN/v5.5/esp32p4/get-started/)，默认目标就是 ESP32-P4：

```bash
cd firmware/wheel-esp32
. ~/esp/esp-idf/export.sh
idf.py build
idf.py -p /dev/cu.usbmodemXXXX flash
```

第一次编译时，ESP-IDF 组件管理器会下载 LVGL 和微雪 BSP。看日志要接“USB TO UART”口，115200 baud（`idf.py -p … monitor`）。

> [!NOTE]
> 如果[调试页面](development.md#调试页面)连着，页面会占住串口，烧录会失败。先在页面上按“斷開”。

## 第一次使用

1. 把 MOZA 底座插到 USB-A 口。板子认到后，仪表盘上会显示方向盘。
2. 点屏幕右上角的 ⚙。在“车辆”选一台车，在“发射设置”选那台车的发射方式。
3. 照[发射方式](radios.md)里对应的说明，给接收机对频。
4. 挂 N 挡，两个踏板都放开，按 **Start** 点火，就可以[开车](driving.md)了。
