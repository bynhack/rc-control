# 發射方式

[English](../en/radios.md) | **繁體中文** | [简体中文](../zh-CN/radios.md)

每台車在「發射設定」分頁選自己的發射方式，只有選中的那一種會發射。所有發射方式拿到的都是[操控層](driving.md#操控)處理後的同一個訊號，各自只負責把 −1…+1 換成自己的輸出。

| 發射方式 | 輸出 | 適用 |
|---|---|---|
| ELRS | GPIO28（和 GPIO30）上的 CRSF | 裝了 ExpressLRS 接收機的車 |
| 四合一 串口 | GPIO29 上的 MULTI 串口協議，協議在螢幕上選 | 接收機是 MULTI 支援的協議之一的車 |
| 四合一 PPM | GPIO29 上的 PPM，協議用高頻頭的旋鈕選 | 同上，高頻頭用旋鈕模式 |
| 遙控器主板 | I2C 控制的兩路 DAC 電壓 | 沒有標準接收機的玩具車，經它自己的遙控器 |

## ExpressLRS

### Nano RX2400 當發射機（雙線，建議）

在「發射設定」選 ELRS，把左下角的按鈕切到「接法：雙線 Nano」。Nano 要刷 ELRS 3.5 以上的接收機韌體，並設成「RX as TX」= internal（ESP8285 只支援 internal）：

1. Nano 只接 5V 和 GND。60 秒後燈會快閃，連上「ExpressLRS RX」WiFi（密碼 `expresslrs`），打開 http://10.0.0.1。
2. 用韌體包裡的 flasher 產生發射機韌體。韌體包從 `https://artifactory.expresslrs.org/ExpressLRS/<commit>/firmware.zip` 下載，commit 查 `index.json`：
   ```bash
   python3 flasher.pyz --dir firmware --target betafpv.rx_2400.nano --rx-as-tx internal --phrase <綁定短語>
   ```
3. 在網頁的 UPDATE 上傳 `firmware.bin.gz`。出現型號不符的警告時，選強制刷入。

執行時 Nano 的燈不亮，這是正常的。

### BETAFPV 高頻頭（單線）

CRSF 腳接 GPIO28，撥碼開關 3、4 撥到 ON。接法按鈕保持「接法：單線」。

### 普通 ELRS 接收機當 2 路 PWM 接收機

只有 GND／VCC／TX／RX 四個焊盤的 ESP8285 接收機（例如 BETAFPV Lite RX），不用重刷就能直接接舵機和電調：

1. 接收機只接 5V 和 GND。60 秒後連上它的 WiFi，打開 `http://10.0.0.1/hardware.html`。
2. PWM 輸出腳位填 `1,3`（GPIO1 = TX 焊盤，GPIO3 = RX 焊盤），儲存並重啟。
3. 輸出 1（TX 焊盤）是 CH1 轉向，輸出 2（RX 焊盤）是 CH2 油門，50 Hz，失控保護 1500 µs。
4. 綁定短語跟發射機一致。

電調要接 RX 焊盤。TX 焊盤開機時會吐開機訊息，舵機抖一下沒關係，電調卻可能誤判。

ELRS 只有通道 1–4 是全精度，方向和油門要放在這幾個通道。

## 四合一 MULTI

iRangeX IRX4+ 的 JR 母座從上到下：1 PPM → GPIO29，2 空，3 VIN → 5V，4 GND，5 S.Port（不接）。

| 模式 | 高頻頭旋鈕 | 對頻 |
|---|---|---|
| 四合一 串口 | 0 | 「發射設定」的「對頻」，或方向盤的 N 鍵，持續 30 秒 |
| 四合一 PPM | 1～E（F 選組別） | 按住高頻頭的對頻鍵上電，5 秒 |

- 高頻頭**只在上電時讀旋鈕**。轉了旋鈕要斷電再上電。
- 串口訊號不反相（反相時紅燈慢閃）。紅燈常亮表示收到訊號，快閃表示正在對頻。
- 已驗證：富斯 FS-GT2E 的車（MXO-Racing RXC42-AG 接收機，AFHDS 2A），兩種模式都能開。MXO 接收機的對頻順序是：發射端先進入對頻，再長按接收機按鍵 2 秒。
- 美嘉欣 Hyper Go（14303 等）用的協議四合一沒有，要換接收機。

## 遙控器主板

沒有標準接收機的玩具車，可以讓 P4 控制它的原裝遙控器：MCP4728 DAC 取代遙控器的方向、油門電位器，遙控器照原本的方式發給車。已驗證：極客者 X2201 的 JC-02T-2.4G 遙控器。

只有選了這種發射方式的車會驅動遙控器。換到別台車時，遙控器停在停止位置，玩具車不會跟著動。

遙控器怎麼改、怎麼校準，見[改裝玩具遙控器](toy-remote.md)。
