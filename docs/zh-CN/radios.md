# 发射方式

[English](../en/radios.md) | [繁體中文](../zh-TW/radios.md) | **简体中文**

每台车在“发射设置”标签页选自己的发射方式，只有选中的那一种会发射。所有发射方式拿到的都是[操控层](driving.md#操控)处理后的同一个信号，各自只负责把 −1…+1 换成自己的输出。

| 发射方式 | 输出 | 适用 |
|---|---|---|
| ELRS | GPIO28（和 GPIO30）上的 CRSF | 装了 ExpressLRS 接收机的车 |
| 四合一 串口 | GPIO29 上的 MULTI 串口协议，协议在屏幕上选 | 接收机是 MULTI 支持的协议之一的车 |
| 四合一 PPM | GPIO29 上的 PPM，协议用高频头的旋钮选 | 同上，高频头用旋钮模式 |
| 遥控器主板 | I2C 控制的两路 DAC 电压 | 没有标准接收机的玩具车，经它自己的遥控器 |

## ExpressLRS

### Nano RX2400 当发射机（双线，推荐）

在“发射设置”选 ELRS，把左下角的按钮切到“接法：双线 Nano”。Nano 要刷 ELRS 3.5 以上的接收机固件，并设成“RX as TX”= internal（ESP8285 只支持 internal）：

1. Nano 只接 5V 和 GND。60 秒后灯会快闪，连上“ExpressLRS RX”WiFi（密码 `expresslrs`），打开 http://10.0.0.1。
2. 用固件包里的 flasher 生成发射机固件。固件包从 `https://artifactory.expresslrs.org/ExpressLRS/<commit>/firmware.zip` 下载，commit 查 `index.json`：
   ```bash
   python3 flasher.pyz --dir firmware --target betafpv.rx_2400.nano --rx-as-tx internal --phrase <绑定短语>
   ```
3. 在网页的 UPDATE 上传 `firmware.bin.gz`。出现型号不符的警告时，选强制刷入。

运行时 Nano 的灯不亮，这是正常的。

### BETAFPV 高频头（单线）

CRSF 脚接 GPIO28，拨码开关 3、4 拨到 ON。接法按钮保持“接法：单线”。

### 普通 ELRS 接收机当 2 路 PWM 接收机

只有 GND／VCC／TX／RX 四个焊盘的 ESP8285 接收机（例如 BETAFPV Lite RX），不用重刷就能直接接舵机和电调：

1. 接收机只接 5V 和 GND。60 秒后连上它的 WiFi，打开 `http://10.0.0.1/hardware.html`。
2. PWM 输出引脚填 `1,3`（GPIO1 = TX 焊盘，GPIO3 = RX 焊盘），保存并重启。
3. 输出 1（TX 焊盘）是 CH1 转向，输出 2（RX 焊盘）是 CH2 油门，50 Hz，失控保护 1500 µs。
4. 绑定短语跟发射机一致。

电调要接 RX 焊盘。TX 焊盘开机时会吐开机信息，舵机抖一下没关系，电调却可能误判。

ELRS 只有通道 1–4 是全精度，方向和油门要放在这几个通道。

## 四合一 MULTI

iRangeX IRX4+ 的 JR 母座从上到下：1 PPM → GPIO29，2 空，3 VIN → 5V，4 GND，5 S.Port（不接）。

| 模式 | 高频头旋钮 | 对频 |
|---|---|---|
| 四合一 串口 | 0 | “发射设置”的“对频”，或方向盘的 N 键，持续 30 秒 |
| 四合一 PPM | 1～E（F 选组别） | 按住高频头的对频键上电，5 秒 |

- 高频头**只在上电时读旋钮**。转了旋钮要断电再上电。
- 串口信号不反相（反相时红灯慢闪）。红灯常亮表示收到信号，快闪表示正在对频。
- 已验证：富斯 FS-GT2E 的车（MXO-Racing RXC42-AG 接收机，AFHDS 2A），两种模式都能开。MXO 接收机的对频顺序是：发射端先进入对频，再长按接收机按键 2 秒。
- 美嘉欣 Hyper Go（14303 等）用的协议四合一没有，要换接收机。

## 遥控器主板

没有标准接收机的玩具车，可以让 P4 控制它的原装遥控器：MCP4728 DAC 取代遥控器的方向、油门电位器，遥控器照原来的方式发给车。已验证：极客者 X2201 的 JC-02T-2.4G 遥控器。

只有选了这种发射方式的车会驱动遥控器。换到别台车时，遥控器停在停止位置，玩具车不会跟着动。

遥控器怎么改、怎么校准，见[改装玩具遥控器](toy-remote.md)。
