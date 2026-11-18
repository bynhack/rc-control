# 硬件

[English](../en/hardware.md) | [繁體中文](../zh-TW/hardware.md) | **简体中文**

## 3D 打印件

所有模型都是 [`cad`](../../cad) 里的参数化 Python 脚本（manifold3d），STL 在 `cad/out/`。`*_viewer.html` 和 `*_assembly.html` 是装配预览，用浏览器打开。

| 模型 | 内容 |
|---|---|
| `p4_case.py` | P4 板的桌面外壳：屏幕托盘 `p4_tray.stl`；装在 MOZA 底座上的支架 `p4_stand.stl`，内有 100 × 45 双单元盒式喇叭的槽位和 ELRS Nano 的位置；以及把四合一挂在支架背板上的盖板 `p4_multi_cover.stl` |
| `vtx_mount.py` | Walksnail Avatar Ascent Lite+ 图传和摄像头的低矮风冷支架 |
| `x2201_cage.py` | 极客者 X2201 驾驶舱的测试框：车壳内可用空间的形状，放驾驶视角的 Ascent Lite+ 摄像头用 |
| `x2201_fpv_mount.py` | X2201 驾驶舱内的驾驶视角图传支架：Ascent Lite+ 摄像头看出挡风玻璃，后面是图传和 25 mm 风扇，用 3M 胶粘在底盘中间走线槽两侧 |
| `x2201_liner.py` | 从 3D 扫描（点云）算出 X2201 黑色内衬的高度图 `x2201_liner.npz`，支架用它检查有没有碰到内衬；也输出可打印的复制件 `x2201_liner_replica.stl` |
| `x2201_liner_model.py` | 重新建模的 X2201 内衬（平滑曲线，不是扫描件），打印出来放进车壳试装 |
| `x2201_interior.py` | 从扫描算出 X2201 内衬里的整个可用空间：车上所有东西都要放得进去 |
| `x2201_datum.py` | X2201 的基准点和各坐标系（车身、底盘、KiCad 主板）之间的换算，其他 X2201 脚本都从这里取数字 |
| `mac_case.py`、`kids_dock.py` | 两款 P4 外壳的造型方案：装在 MOZA 底座上的 1984 麦金塔造型，和儿童桌面座 |

每个脚本开头的注释说明打印方向和要用的螺丝。标了 `MEASURE` 的参数，打印前要用卡尺量你自己的零件再改。共用的几何和预览函数在 `cad.py`。

```bash
cd cad
python3 -m venv .venv
.venv/bin/pip install manifold3d numpy trimesh matplotlib scipy
.venv/bin/python p4_case.py
```

## X2201 主板

X2201 已确认的硬件方案（元件和接线）在 [hardware/PLAN.md](../../hardware/PLAN.md)（繁体中文）。照这份方案画好的板子是 [`hardware/x2201-mainboard`](../../hardware/x2201-mainboard)，40 × 40 mm，用一颗 M2 螺丝固定在底盘凸台上、定位柱定位，在底盘 40 × 60 mm 的可用范围内。

- **只有一个电源入口**：2S 电池焊在主板上，经过防反接 Q1。
- **电调在主板上**：TI DRV8874 H 桥，经 ZH2.0 插座驱动 260 马达，限流约 4.9A。
- **5V BEC 在主板上**：LMR51430 降压，约 2–2.5A，供 ESP32、EP2、舵机、风扇、IR LED。
- **控制器**：ESP32-S3 SuperMini，用排针垫高后手焊，USB-C 伸出板外。
- **插座**：全部是侧插的 ZH1.5（EP2、图传、舵机、风扇、电源按钮），插口朝外，板子上方没有东西立起来。
- **电源按钮**：不自锁。按一下开机，S3 开机后用 TX 脚保持电源；再按一下关机。

板子外形可以按车内空间调整，元件和接线以 PLAN.md 为准。v3～v9 的旧板子已在 2026-11-16 删除，需要时可以从 git 找回（commit `56bd000` 之前）。

## 计圈应答器

每台车装一个应答器，用 940 nm 红外 LED 闪自己的车号，让终点线的拱门分辨是哪台车（最多 8 台）。X2201 的应答器做在主板上（IR LED 直接焊在主板车尾）；其他车用 [`hardware/transponder`](../../hardware/transponder) 的小板（15 × 22 mm）。

- **电路**：CH32V003J4M6 在 PC4（TIM1_CH4）产生 38 kHz 脉冲，AO3400 经 33 Ω 驱动 LED，脉冲时约 110 mA，平均约 10 mA。
- **车号**：烧录时设定，`make flash CAR=3`（1–15）。不带 `CAR` 烧录时，改读焊上的跳线：1 加上焊上的跳线（+1、+2、+4）。
- **J1**：5V、GND、SWIO（2.54 mm）。接到接收机任一个舵机口的正负极；烧录时 WCH-LinkE 也接这三脚。
- **LED**：3 mm 940 nm，可以直接焊在板上，也可以用两根线拉出去。要能从窗口或薄塑料车壳朝上照出去。
- **信号格式**：开头脉冲 4T、间隔 2T，接着 8 位、低位先发（脉冲 1T，间隔 1T = 0、2T = 1）：车号和它的反码，最后一个 1T 的结束脉冲。T = 400 µs。每帧之间随机隔 4～12 ms。
- **固件**：[`firmware/transponder`](../../firmware/transponder)，用 [ch32fun](https://github.com/cnlohr/ch32fun) 编译（`make`、`make flash CAR=n`）。

```bash
cd hardware/transponder
python3 gen_sch.py
FAB=1 /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 gen_pcb.py
```

两块板子的脚本共用 `hardware/pcbgen.py`（布局）和 `hardware/schgen.py`（原理图）。
