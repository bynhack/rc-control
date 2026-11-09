# X2201 載板 v7（ESP32-S3-Zero + EP2）

47×30 mm，2 層，1.6 mm，單面零件，4 個 M2 不鍍銅孔（孔距 42×25）。

只做這些事：**電池電量偵測、計圈、讓 EP2 上電就能工作、接線**，並接上圖傳 UART，供之後做 OSD。

訊號鏈：`EP2 → CRSF → S3-Zero → PWM → 電調`。EP2 不再直接接電調，R11 再把它的 TX 腳拉高，這就是上電卡死的解法。

## 下單

| 項目 | 內容 |
|---|---|
| PCB | 上傳 `x2201-carrier-v7-gerber.zip`：2 層、1.6 mm、1 oz |
| 元件 | `bom.csv` 上的料號，全部可在立創商城買到 |
| 模組 | ESP32-S3-Zero、EP2 2400RX 各一 |
| 插頭線 | ZH1.5 4P ×1、ZH1.5 2P ×3（圖傳用它原裝的 SH1.0 線） |

## 手焊順序

位置看 `x2201-carrier-v7-assembly.png`，零件編號對照 `bom.csv`。

1. MOS（Q2 是 AO3401，Q3、Q4 是 AO3400）和二極體 D3。
2. 所有 0805 阻容。
3. 插座：先焊 J3（SH1.0，腳距最小），再焊 J1、J4、J5、J6。
4. 先量：5V、VBAT、3V3 對 GND 都不能短路。
5. 焊 S3-Zero：USB 朝板邊，對齊 18 個焊盤。
6. 焊 EP2：貼在絲印框內，四個焊盤用短線橋接到板上 TX / RX / 5V / G，**依名稱對應，不要只看位置**。

## 接法

| 位號 | 類型 | 腳位 |
|---|---|---|
| J1 電調 | ZH1.5 4P | 1 S2 黃、2 S1 藍、3 GND 綠、4 5V 棕 |
| J3 圖傳 | SH1.0 4P | 1 電源、2 GND、3 圖傳 RX、4 圖傳 TX |
| J4 風扇 | ZH1.5 2P | 1 5V、2 GND，電調一開就轉 |
| J5 IR | ZH1.5 2P | 1 LED+、2 LED− |
| J6 電池 | ZH1.5 2P | 1 VBAT、2 GND |

圖傳的電池電源由電調的 5V 控制（Q2、Q3）：電調開關關掉，圖傳也會斷電。

| GPIO | 功能 |
|---|---|
| 4 | IR |
| 5 / 6 | CRSF RX / TX |
| 7 / 8 | 電調 S2 / S1 |
| 9 | 電池電壓（×22/122） |
| 11 / 12 | 圖傳 UART TX / RX（MSP OSD） |

## 第一次上電

上電測試在 [firmware/elrs-bench](../../firmware/elrs-bench/README.md)，韌體的接腳和這塊板相同。

- D3 會擋住 USB 流進電調 BEC，焊好後可以同時插 USB 和電調。
- J1 的線序（第 1 腳是 S2）還要對照實車確認。

## 重新產生

```bash
/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 gen_pcb.py
```

佈線用 `../tools/freerouting-1.9.0.jar`；沒有這個檔案時加 `REUSE_SES=1`，沿用已存的 `.ses`。`FAB=1` 同時輸出 Gerber 和 BOM，之後再跑 `gen_sch.py` 更新原理圖。
