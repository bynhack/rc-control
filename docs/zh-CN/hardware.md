# 硬件

[English](../en/hardware.md) | [繁體中文](../zh-TW/hardware.md) | **简体中文**

## 3D 打印件

所有模型都是 [`firmware/wheel-esp32/enclosure`](../../firmware/wheel-esp32/enclosure) 里的参数化 Python 脚本（manifold3d），STL 在 `enclosure/out/`。`*_viewer.html` 和 `*_assembly.html` 是装配预览，用浏览器打开。

| 模型 | 内容 |
|---|---|
| `p4_case.py` | P4 板的桌面外壳：屏幕托盘 `p4_tray.stl`；装在 MOZA 底座上的支架 `p4_stand.stl`，内有 100 × 45 双单元盒式喇叭的槽位和 ELRS Nano 的位置；以及把四合一挂在支架背板上的盖板 `p4_multi_cover.stl` |
| `minicar_cage.py` | 1:28 拉力车的测试框：车壳下可用空间的形状 |
| `minicar_mount.py` | 那台车车壳内的图传和接收机支架 |
| `vtx_mount.py` | Walksnail Avatar Ascent Lite+ 图传和摄像头的低矮风冷支架 |
| `camera_pod.py` | 美嘉欣 14303 车顶的 WRC 风格 WiFiLink 2 摄像头罩 |
| `wifilink_mount.py` | 夹在 8 mm 圆杆上的 RunCam WiFiLink 2 支架 |

每个脚本开头的注释说明打印方向和要用的螺丝。标了 `MEASURE` 的参数，打印前要用卡尺量你自己的零件再改。共用的几何和预览函数在 `cad.py`。

```bash
cd firmware/wheel-esp32
python3 -m venv .venv
.venv/bin/pip install manifold3d numpy trimesh matplotlib
.venv/bin/python enclosure/p4_case.py
```

## X2201 转接板

[`hardware/x2201-carrier`](../../hardware/x2201-carrier) 是改装极客者 X2201（1:22 四驱攀爬车）用的无源转接板。板上没有芯片，只有接头和焊盘，把电池、电源开关、ZERO-Z 电调、电机、ELRS 接收机（Lite RX 当 2 路 PWM 接收机）、舵机、车灯和图传供电接在同一块板上，减少飞线。固定在底盘中间的孔上。

| 位号 | 零件 |
|---|---|
| J1 | 电调，ZH1.5 4P（S2、S1、GND、5V） |
| J2 | Lite RX 焊盘 |
| C1、C2 | 5V 上的 220 µF（7343）和 100 nF |
| J3、J4 | 舵机输出和电调的舵机线（ZH 3P） |
| J5–J7、R1、R2 | 车灯，0 Ω 电阻先占位 |
| JP1、J9 | 图传供电选择和输出 |
| J8、J10 | 电池和电源开关（PH2.0 2P） |
| J11–J13 | 电调电源、电调电机线、电机（PH2.0 2P） |
| H1、H2 | M2 固定孔 |

- 原理图由 `gen_sch.py` 生成（KiCad 10）。要改连线就改脚本再运行一次；`x2201-carrier.pdf` 是导出的原理图。
- 目前只有原理图。PCB 布局要等零件实际量好尺寸再画。
- 电机的大电流走电调自己的线，1 oz 铜厚就够了。

```bash
python3 hardware/x2201-carrier/gen_sch.py
kicad-cli sch erc hardware/x2201-carrier/x2201-carrier.kicad_sch
kicad-cli sch export pdf -o hardware/x2201-carrier/x2201-carrier.pdf hardware/x2201-carrier/x2201-carrier.kicad_sch
```

`gen_sch.py` 里的 KiCad 符号库路径是 macOS 的默认安装位置，其他系统要改 `LIB`。
