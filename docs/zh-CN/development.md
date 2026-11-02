# 开发

[English](../en/development.md) | [繁體中文](../zh-TW/development.md) | **简体中文**

## 固件结构

都在 [`firmware/wheel-esp32/main`](../../firmware/wheel-esp32/main)：

| 文件 | 作用 |
|---|---|
| `main.c` | 开机、USB 主机，把方向盘数据交给驾驶模型 |
| `wheel.c` | 按 VID:PID 解析方向盘底座的 HID 报告 |
| `control.c` | 驾驶模型和所有安全规则；发射端只读 `control_output()` |
| `radio.c` | 车辆、NVS 里的设置，以及所有发射方式都要经过的操控层 |
| `crsf.c` | ExpressLRS（CRSF）发送 |
| `multi.c` | 四合一 MULTI 发送，串口或 PPM |
| `remote.c` | 经 MCP4728 DAC 控制玩具遥控器，以及串口命令 |
| `ffb.c` | 力回馈（USB PID） |
| `sound.c` | 引擎声浪合成 |
| `display_p4.c`、`dash_p4.c`、`ui_p4.h` | 设置页、仪表盘、两种语言的界面文字 |

`components/usb_host_hid` 是 Espressif usb_host_hid 1.2.1 的拷贝，多了一个函数，原因见[力回馈](#力回馈)。

### 信号路径

```
wheel.c → control.c（驾驶模型、安全）→ radio.c（操控）→ crsf.c / multi.c / remote.c
```

要加一种新的发射方式，只要写一个发送端：读 `control_output()`，经过 `radio_steering()` 和 `radio_throttle()`，再把得到的 −1…+1 换成自己的信号。把它加进 `radio.h` 的 `radio_kind_t`，车辆、操控、反转和安全规则就都自动有了。

### 操控的实时响应优先

任何东西都不能拖慢发射。发送任务在 core 1，优先级最高：

| 任务 | Core | 优先级 |
|---|---|---|
| `crsf` | 1 | 10 |
| `multi` | 1 | 9 |
| `sound` | 0 | 6 |
| `ffb` | 0 | 4 |
| `remote` | 1 | 4 |
| `usb_lib` | 0 | 2 |
| `remote_con`（串口命令） | 1 | 2 |
| `ui` | 1 | 1 |

调试页面和串口命令的优先级都比发送任务低，不会拖慢车的响应。真方向盘在 0.5 秒内有数据时，模拟方向盘（`w`）一律不理。

### 力回馈

力回馈报告要从 HID 接口的中断 OUT 端点发（R5 是 0x03）。从控制通道用 SET_REPORT 发，R5 会回 OK，但什么都不做。ESP-IDF 的 usb_host_hid 不支持 OUT 端点，所以 `components/usb_host_hid` 多了 `hid_host_device_send_output_report()`。效果还要打开方向，并设成 90 度（X 轴），否则弹簧和阻尼都没有力。

## 串口命令

在看日志的那个口（“USB TO UART”，115200），一行一条：

| 命令 | 作用 |
|---|---|
| `w <方向> <油门> <刹车>` | 模拟一帧方向盘数据（−1…1、0…1、0…1），经过跟真方向盘一样的驾驶模型。要每 50 ms 发一次。真方向盘在 0.5 秒内有数据时不理 |
| `k start` / `k up` / `k down` / `k stop` | 点火／熄火、升挡、降挡、急停 |
| `d <A> <B>` | 直接设 DAC 两路的码（0–4095），1.5 秒没有新的就交回方向盘 |
| `x` | 马上交回方向盘 |
| `name <名字>` | 改当前那台车的名字 |
| `kind <0–3>` | 当前那台车的发射方式：0 ELRS、1 四合一串口、2 四合一 PPM、3 遥控器主板 |
| `dead <左> <右> <前进> <倒车>` | 当前那台车的方向和油门死区，千分比 |

## 调试页面

[`tools/remote_tune.html`](../../firmware/wheel-esp32/tools/remote_tune.html) 是通过串口命令操作的调试页面。要用支持 Web Serial 的 Chrome，从本地服务器打开：

```bash
python3 -m http.server 8765 --bind 127.0.0.1 --directory firmware/wheel-esp32/tools
```

打开 http://localhost:8765/remote_tune.html，按“連接 P4”。

- **模擬駕駛**：拖方向盘、踩踏板、点火换挡。也可以用键盘：A/D 方向，W/S 油门和刹车，Enter 点火，Q/E 换挡，空格键急停。走跟真方向盘一样的路径，会显示引擎、挡位、车速和输出。
- **精調 DAC**：每路 DAC 一条可以缩放的轴（⌘ 或 Ctrl ＋滚轮，或双指捏合）。滚轮一格 ±1，按住 Shift 是 ±10，在上面标记每一路的两端和死区边。见[改装玩具遥控器](toy-remote.md#校准)。

用完按“斷開”，不然页面占着串口，烧录会失败。页面文字是繁体中文。

## 字体和仪表盘图片

- **字体**：`main/fonts/gen_fonts.sh <字体目录>` 用 `lv_font_conv`（需要 Node）重新生成点阵字体。中文字体只收源码里出现的字，所以加了界面文字后要重跑。字体目录要放 Noto Sans SC Medium，以及仪表数字用的 Saira 和 Barlow Condensed，下载链接在脚本开头。
- **仪表盘图片**：静态图层画在 `design/render/dash_render.html`。`design/render/build_assets.py` 用 headless Chrome 渲染，输出到 `main/assets/*.bin`。需要 Google Chrome、Pillow 和 numpy。

## 电脑端结构

```
src/
  control.rs        跟发射方式无关的控制状态和全部安全规则
  config.rs         配置文件
  protocol/crsf.rs  CRSF 组帧、解析（链路质量、设备名、模块复位）
  backend/elrs.rs   定时发送线程
  gui/mod.rs        窗口布局和交互
  gui/widgets.rs    自绘组件：仪表、转向条、滑条、信号条、链路历史
  gui/theme.rs      配色、深色主题、字体
  gui/dev.rs        开发用：自动截图、演示输入
  video/rtp.rs      RTP 重组成 H.264/H.265 帧（丢包时丢弃残缺分片）
  video/decoder.rs  FFmpeg 低延迟解码，转成 RGBA
  video/mod.rs      收流线程、统计
  radio/mod.rs      内置图传：网卡选择、启动、断线重连、状态
  wheel.rs          T300RS HID 读取、报告解析、--probe-wheel
native/             C++ 层：编译 Aviateur 的收包代码，提供 C 接口（rcwfb.h）
third_party/aviateur  子模块，GPL-3.0
vendor/             ffmpeg-sys-next 9.0.1 加 Windows D3D 空 stub（[patch.crates-io]）
scripts/            Windows：编译、部署 DLL、把 8812AU 绑定到 WinUSB
```

`cargo test` 会跑协议、映射、安全规则和方向盘报告解析的单元测试，不需要接硬件。

### 调界面用的环境变量

- `RC_CONTROL_SNAPSHOT=out.bmp`：启动约 1.5 秒后，把窗口画面存成图片。程序自己画，不需要系统的屏幕录制权限。
- `RC_CONTROL_DEMO=方向,油门[,low|mid|high]`：用假输入看仪表效果，数值范围 −1 到 1。**只要有设备连着就自动失效**，要配合不存在的串口使用：

```bash
printf '[elrs]\nport = "/dev/none"\n' > /tmp/demo.toml
RC_CONTROL_DEMO="0.45,0.85,high" RC_CONTROL_SNAPSHOT=/tmp/ui.bmp ./target/release/rc-control --config /tmp/demo.toml
```

### 电脑端编译备注

- `vendor/ffmpeg-sys-next-9.0.1`：bindgen 解析 `<d3d11.h>` 时，会把 `amxintrin.h` 的 `__tile1024i_str` 带进来，它的 `packed` + `align` 组合 rustc 编译不过（E0587／E0080）。所以在 `hwcontext_stubs` 补了 d3d11／d3d12／d3d9／dxva2 空 stub，经 `[patch.crates-io]` 使用。
- Aviateur 的两处 MinGW 修正，编译时打在复制出来的文件上，子模块保持不动（见 `native/CMakeLists.txt` 的 `patch_staged`）：
  - MinGW 已经有 `clock_gettime`（winpthreads），所以 `net_compat.h` 里的内联版本只在其他平台用。
  - `compat/getopt.h` 里 getopt 全局变量的 weak 定义，在 PE 链接器下会重复，MinGW 下不提供。
- 一处对上游的修正，用同样的方式应用：Aviateur 停止链路后不会关闭 UDP 8001，同一个进程里再次启动会直接崩溃。复制出来的 `tx_frame.cpp` 会补上关闭。
- `native/CMakeLists.txt` 的 `/utf-8` 只对 MSVC 生效；`build.rs` 为 MinGW 链接静态 libstdc++／gcc_eh 和 ws2_32。

## 协议要点

- **CRSF**：地址 `0xEE`，CRC8 多项式 `0xD5`。通道值 172／992／1811 对应 988／1500／2012 µs。ELRS 只有通道 1–4 是全精度。
