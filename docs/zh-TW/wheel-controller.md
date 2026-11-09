# 方向盤控制器

[English](../en/wheel-controller.md) | **繁體中文** | [简体中文](../zh-CN/wheel-controller.md)

這一篇講獨立控制器的硬體、接線，以及韌體的編譯和燒錄。方向盤和踏板用 USB 接到 ESP32-P4，板子跑駕駛模型和那台車的操控設定，再用你替那台車選的發射方式發出去。7 吋觸控螢幕顯示儀表盤和設定，喇叭放引擎聲浪，方向盤底座有力回饋。全程不用電腦。

韌體在 [`firmware/wheel-esp32`](../../firmware/wheel-esp32)。

## 硬體

| 部件 | 型號 | 說明 |
|---|---|---|
| 主控和儀表盤 | 微雪 ESP32-P4-WIFI6-Touch-LCD-7B | USB-A（OTG）口接方向盤；USB-C「USB TO UART」口用來燒錄和看 log；7 吋 1024×600 觸控螢幕 |
| 方向盤底座 | MOZA R5（USB `346e:0004`）或 Thrustmaster T300RS（`044f:b66e`） | MOZA：在 Pit House 裡把方向盤角度設成 900°。T300：底座開關撥到 PS3（PC）模式，900° 由韌體自己設 |
| ELRS 發射 | 刷成「RX as TX」的 CYCLONE Nano RX2400（雙線），或 BETAFPV 高頻頭（單線） | 見[發射方式](radios.md#expresslrs) |
| 四合一（可選） | iRangeX IRX4+ 裸板 | 見[發射方式](radios.md#四合一-multi) |
| 遙控器主板（可選） | MCP4728 四路 I2C DAC 模組 | 見[改裝玩具遙控器](toy-remote.md) |
| 喇叭（可選） | 8 Ω 3 W，PH2.0 插頭 | 插板子的喇叭座（板載 NS4150B 功放） |

把板子固定在 MOZA 底座上的支架，裡面留了 Nano、四合一和喇叭的位置，見[硬體](hardware.md)。

## 接線

| 用途 | P4 腳位 | 說明 |
|---|---|---|
| ELRS，Nano（雙線） | GPIO28 → Nano RX，GPIO30 ← Nano TX | P3 端子；Nano 的 5V 接 CAN／RS485 端子第 1 腳 |
| ELRS，BETAFPV（單線） | GPIO28 → CRSF | 半雙工，400000 baud |
| 四合一，PPM 或串口 | GPIO29 → 模組的 PPM 腳 | 模組 VIN 接 5V |
| MCP4728 | I2C 端子的 SCL／SDA／GND（GPIO8／GPIO7，跟觸控共用） | **VCC 接 12 PIN 排針的 3V3**，不要接 I2C 端子。見[改裝玩具遙控器](toy-remote.md#dac-接線) |

> [!WARNING]
> 板子 I2C PH2.0 端子的 VCC 是 **5 V**。3.3 V 的 I2C 模組從這裡取電，會把匯流排拉到 5 V，整條匯流排卡死，觸控也跟著失靈。

UART 端子（H8）跟燒錄口共用 UART0，不能拿來接發射模組。

## 編譯和燒錄

需要 [ESP-IDF v5.5](https://docs.espressif.com/projects/esp-idf/zh_CN/v5.5/esp32p4/get-started/)，預設目標就是 ESP32-P4：

```bash
cd firmware/wheel-esp32
. ~/esp/esp-idf/export.sh
idf.py build
idf.py -p /dev/cu.usbmodemXXXX flash
```

第一次編譯時，ESP-IDF 元件管理器會下載 LVGL 和微雪 BSP。看 log 要接「USB TO UART」口，115200 baud（`idf.py -p … monitor`）。

> [!NOTE]
> 如果[調試頁面](development.md#調試頁面)連著，頁面會佔住串口，燒錄會失敗。先在頁面上按「斷開」。

## 第一次使用

1. 把方向盤底座插到 USB-A 口。板子認到後，儀表盤上會顯示方向盤。T300 剛插上是基本模式，板子會把它切換過去，螢幕會短暫顯示「切換模式中」。
   - 「駕駛設定」分頁的「方向盤型號」選用哪個底座：「自動」插上哪個用哪個；選 MOZA R5 或 T300RS 就只用那一種。插著別的底座不會動，狀態分頁會顯示你選的是哪個。
2. 點螢幕右上角的 ⚙。在「車輛」選一台車，在「發射設定」選那台車的發射方式。
3. 照[發射方式](radios.md)裡對應的說明，替接收機對頻。
4. 掛 N 檔，兩個踏板都放開，按 **Start** 點火，就可以[開車](driving.md)了。
