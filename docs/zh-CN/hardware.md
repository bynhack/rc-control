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
| `x2201_cage.py` | 极客者 X2201 驾驶舱的测试框：车壳内可用空间的形状，放驾驶视角的 Ascent Lite+ 摄像头用 |
| `x2201_fpv_mount.py` | X2201 驾驶舱内的驾驶视角图传支架：Ascent Lite+ 摄像头看出挡风玻璃，后面是图传和 25 mm 风扇，用 3M 胶粘在底盘中间走线槽两侧 |
| `x2201_liner.py` | 从 3D 扫描（点云）算出 X2201 黑色内衬的高度图 `x2201_liner.npz`，支架用它检查有没有碰到内衬；也输出可打印的复制件 `x2201_liner_replica.stl` |
| `x2201_carrier_frame.py` | 以 [X2201 转接板](#x2201-转接板)当底座时的图传支架打印框架：图传柱子、风扇垫片和摄像头侧板，锁在板上的 M2 贴片螺母上 |
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

> 已归档，见 [hardware/ROADMAP.md](../../hardware/ROADMAP.md)。

[`hardware/archive/x2201-carrier`](../../hardware/archive/x2201-carrier) 同时是 X2201 图传支架的底座，也负责车上的小电流接线。它取代打印支架的底板，再往后多 10 mm：54 × 52 mm，用 1 mm 的 3M VHB 胶粘在底盘中间走线槽两侧的平面上。元件全部在正面，背面是平的。打印框架（`x2201_carrier_frame.py`）锁在板上的四个 M2 贴片螺母上：先把图传放在板上，再把框架从上面盖下来。

**往外的接线全部用插座**，集中在板子后端一排，正好在后窗下方。转接板上不用焊任何线；只有本身没有插头的模块（EP2、红外 LED、风扇）要在模块那端焊一次 ZH 单头线。

整台车只要电调一个开关：

- **EP2 接收机延时通电**：Q1（AO3401）在电调的 BEC 起来 0.5～1 秒后才给 EP2 供 5V。ZERO-Z 开机时会把 EP2 的 TX 焊盘（GPIO1）拉低，EP2 在这时开机就会卡住；串电阻没用。
- **图传由 BEC 控制**：有 5V 时 Q3（AO3400）打开 Q2（AO3401），图传只在电调开着时才接上电池。R2、R3 让 Q2 的栅极电压在 3S 以内都不超过 12 V。

| 位号 | 元件 |
|---|---|
| J1 | ZERO-Z 接收机线，ZH1.5 4P（黄 S2、蓝 S1、绿 GND、棕 5V） |
| J2 | EP2，ZH1.5 4P：1 RX 焊盘（CH2 油门）、2 TX 焊盘（CH1 转向）、3 GND、4 5V（延时） |
| Q1、C1、R1、D1 | EP2 延时通电 |
| Q2、Q3、R2–R5 | 图传电源开关 |
| J6 | 电池分接，ZH1.5 2P：1 电池正、2 GND。用电池 Y 线从电池到电调的主线分出来 |
| J3 | 图传，SH1.0 4P：1 电源、2 GND（3、4 不接）。用双头同向的 SH1.0 4P 线直接插图传 |
| J4 | 25 mm 风扇，ZH1.5 2P：1 5V、2 GND |
| C2、C3 | 5V 和电池上的 22 µF |
| U2、C4、JP1–JP3、TP11 | 计圈应答器：CH32V003、车号跳线、SWIO 焊盘（只在烧录时用，WCH-LinkE 的 GND 接在螺母上） |
| Q4、R6–R8、J5 | 应答器的红外 LED 驱动；J5 是 ZH1.5 2P：1 LED 正、2 LED 负 |
| H1–H4 | 给打印框架用的 M2 贴片螺母（例如 Würth 9774020151R） |

- 舵机插在电调的舵机口上，由电调的陀螺仪控制。
- 应答器的 LED 从车壳的后窗开口朝上照，对着终点线的拱门。
- 原理图由 `gen_sch.py` 生成，布局由 `gen_pcb.py` 生成，两边网络名称一致。`x2201-carrier.pdf` 是导出的原理图。
- 加上 `FAB=1`，`gen_pcb.py` 会一并输出 Gerber、`bom.csv` 和 `cpl.csv`，给嘉立创 SMT 贴片用，小元件由工厂焊好。
- 插线前先对照 J1 旁的标示确认线的颜色。
- 板子后端多出来的 10 mm 要确认底盘那里是平的，试装测试框时一起看。
- J1 要买两头同向（1 脚对 1 脚）的 ZH1.5 4P 线。第一次通电前用万用表量一下，电调的 5V 要落在 J1 第 4 脚。

```bash
cd hardware/archive/x2201-carrier
python3 gen_sch.py
/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 gen_pcb.py   # FAB=1: gerber/, bom.csv, cpl.csv
kicad-cli pcb drc --refill-zones x2201-carrier.kicad_pcb
```

脚本里的 KiCad 路径是 macOS 的默认安装位置，其他系统要改 `LIB` 和 `FP`。

## X2201 转接板 v4（ESP32-S3）

> 已归档，不在目前的迭代路径上，见 [hardware/ROADMAP.md](../../hardware/ROADMAP.md)。

[`hardware/archive/x2201-carrier-v4`](../../hardware/archive/x2201-carrier-v4) 在转接板上加了一颗 ESP32-S3，车子有了自己的大脑。这是下一版，还没做：目前在制作的是上面的 v3。

- **信号路线**：EP2 → CRSF（UART）→ ESP32-S3 → PWM → 电调。EP2 要改成串口 CRSF 输出，不再输出 PWM；失控保护由 ESP32 负责（CRSF 断掉就把油门归零）。
- **新增的功能**：电池电压回传到方向盘、眼镜里的 OSD（通过图传线第 3、4 脚的 MSP）、计圈红外码（不用 CH32）、状态灯，还有前缘的 USB-C，用来烧录和看串口。
- **EP2 开机卡住的问题消失**：电调不再碰 EP2 的脚，所以 v3 的延时供电（Q1、C1、R1、D1）拿掉了。
- **WiFi 只在设置时开**（车号、微调），车子要停着：它和 ELRS 同在 2.4 GHz。
- **插座和线材跟 v3 一样。** 板子前端加长 4 mm 给模块的天线（58.2 × 52 mm），要确认车壳前方放得下。
- **打印框架两版都能用**：[`x2201_carrier_frame.py`](../../firmware/wheel-esp32/enclosure/x2201_carrier_frame.py) 在摄像头侧板底下多了一个小缺口，让 v4 的两颗去耦电容通过。
- **电池电压**接在 IO17（ADC2），WiFi 关着时才能读，也就是车子在跑的时候都能读。
- DRC 和框架的干涉检查都通过。ESP32 的固件还没写。

```bash
cd hardware/archive/x2201-carrier-v4
/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 gen_pcb.py   # FAB=1: gerber/, bom.csv, cpl.csv
/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 gen_sch.py   # 原理图，从板子的网络生成
```

## X2201 转接板 v5（OpenIPC）

> 已归档，不在目前的迭代路径上，见 [hardware/ROADMAP.md](../../hardware/ROADMAP.md)。

[`hardware/archive/x2201-carrier-v5`](../../hardware/archive/x2201-carrier-v5) 是 v4 把 Walksnail 图传换成 OpenIPC 数字图传，车上只要接摄像头。**目前只画了电路。** 排板要等实物到了量过尺寸再做。

- **图像**：买现成的 OpenIPC Thinker Base（SSC338Q，25 × 25 mm，M2 孔距 20 × 20），用铜柱叠在板子上面。IMX335 摄像头插在它上面。电脑版本来就能用 RTL8812AU 网卡收 OpenIPC。
- **WiFi**：BL-M8812EU2（RTL8812EU）模块。它最大要 5 V 2 A 以上，电调的 1 A BEC 不够，所以由 U4（LMR51430，5 V 3 A）从电池另外降压供电。最大占空比 98%，2S 没电时也撑得住 5 V。要加散热片和风扇，室内发射功率调低。
- **主板内置 ELRS 接收机**：ESP32-C3 + SX1280 + AT2401C，按 ExpressLRS 官方「Generic C3 2400 PA」的脚位接，可以直接刷官方固件。天线用 U.FL（J10），车壳是金属的，要从车窗拉出去。ESP32-S3 控制 C3 的 EN 和 GPIO9，所以 Mac 插 USB-C 就能刷 ELRS。EP2 插座（J2）保留当备案：让 C3 停在复位状态，再插上 EP2。C3 自己的 WiFi（ELRS 设置页）另外接一个 U.FL（J11）。外围电路按 Espressif 的参考电路（40 MHz 晶振）和 AnyLeaf 的开源接收机设计（MIT 许可）。匹配电路的数值只是起始值，要再调。
- **插座**：
  - J3，SH1.0 6P：Thinker 的电源/UART2，按它的脚序。1–2 脚是开关后的电池，3 脚是它的 RX，4 脚是它的 TX，5–6 脚是 GND。
  - J7，SH1.0 4P：Thinker 的 USB，Vd 脚不接。
  - J8，ZH1.5 8P：WiFi 模块，按它的脚序。ESP32 可以复位它（IO12）。
  - J6 电池插座改成 PH2.0（约 2 A）。
  - 风扇改吃 WiFi 那路 5 V。
- **ESP32** 通过 MSP 接 Thinker 的 UART2（msposd 画 OSD），两边各串 1k，谁都不会反向供电给对方。
- **电源**：Thinker 和 WiFi 跟着电调开关，和 v3 的图传一样。
- **实物到了要量**：模块的厚度、固定孔、散热片，Thinker 加散热片的高度，以及插座型号。量完再排板、重画打印框架。
- ERC：0 个错误。

```bash
cd hardware/archive/x2201-carrier-v5
/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 gen_pcb.py   # 只放零件，没走线
/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 gen_sch.py   # 原理图，从板子的网络生成
```

## 计圈应答器

每台车装一个应答器，用 940 nm 红外 LED 闪自己的车号，让终点线的拱门分辨是哪台车（最多 8 台）。X2201 的应答器做在转接板上；其他车用 [`hardware/transponder`](../../hardware/transponder) 的小板（15 × 22 mm）。

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
