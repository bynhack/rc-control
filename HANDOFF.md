# 交接文件（2026-11-09）

從這裡可以在另一台 Mac 上接著做。分支：`feat/esp32-wheel`。

## 目前要做：用 ESP32 接線驗證，不打板

目的：驗證「EP2 → CRSF → ESP32-S3 → PWM → 電調」能不能避開 EP2 上電卡死。**v8 暫緩，等測完再決定。**

需要：S3 開發板或 S3-Zero、杜邦線、車上的 EP2 和電調。韌體在 `firmware/elrs-bench`，要有 ESP-IDF（舊 Mac 已裝好且編譯過）。

| 從 | 接到 S3 |
|---|---|
| EP2 TX | GPIO13 |
| EP2 RX | GPIO14 |
| EP2 5V | 5V |
| EP2 G | GND |
| 電調藍 S1 | GPIO8 |
| 電調黃 S2 | GPIO7 |
| 電調綠 GND | GND |
| 電調棕 5V | S3 的 5V（只在第 3 步接，先拔 USB） |

車輪先抬離地面。電池主線一直接電調。

1. **EP2 改 CRSF**：EP2 只接 5V、GND，等 60 秒，連上 `ExpressLRS RX` WiFi，在 `firmware/elrs-bench` 執行 `python3 ep2_serial.py`。電腦沒有 WiFi 時，用手機開 `http://10.0.0.1/hardware.html`，清空 PWM 輸出並儲存。
2. **燒錄並看訊號**：插 USB，棕線不接。不要接到 P4，燒錄會覆蓋板上韌體。
   `. ~/esp/esp-idf/export.sh`，然後 `idf.py -p /dev/cu.usbmodemXXXX flash monitor`。打開方向盤和發射端，應顯示「正常」，CH1、CH2 跟著動。
3. **上電卡死測試（重點）**：拔 USB，接棕線，由電調供電，重複開關電調 10 次，每次看 EP2 能否連上、電調能否解鎖、車能否控制。

結果：

- 10 次都正常：方案 B（S3 隔在中間）的解法成立，可以回頭比較 A、B。
- 仍會卡：繼續用方案 A 的延遲電路。

注意：

- USB 和電調棕線**絕對不能同時接**（開發板的 5V 可能和 USB 直通）。
- 測完要改回 PWM，車才能用原接法：連上 EP2 的 WiFi，執行 `python3 ep2_serial.py restore`。備份檔只存在跑第 1 步的那台電腦（`ep2_hardware_backup.json`）。

## X2201 控制板 v8（暫緩）

> 迭代路徑見 [hardware/ROADMAP.md](hardware/ROADMAP.md)。EP2 之後一律用插頭連接（J2），不焊在板上，下一版以 v8 為基礎修改。

路徑：`hardware/x2201-carrier-v8/`，說明見該目錄的 `README.md`。

**狀態**：設計完成，沒有實機驗證。DRC 0 錯誤（2 個絲印靠板邊的警告）、0 未連接、ERC 0 錯誤。

**規格**：46.3×34.5 mm，2 層，1.6 mm，單面零件，4 個 M2 不鍍銅孔（孔距 41.8×29.5）。

**訊號（方案 A，使用者已決定）**

- 電池 → 電調 → 馬達、舵機（主電源，和原本一樣）。
- EP2 維持 PWM 模式：TX 焊盤 = S1（CH1 轉向），RX 焊盤 = S2（CH2 油門），經板子直接到 J1，不經過 S3。
- 電調 BEC 5V → J1 → 板子。EP2 的 5V 由 Q1、C1（10µF）、R1（100k）、D1 延遲約 0.5～1 秒。
  原因：電調開機時把 EP2 的 TX 焊盤（ESP8285 GPIO1）拉低，EP2 此時開機會卡死。
- 電池 → Y 線 → J6：細線，給電量偵測和圖傳。
- 電調的開關關掉時，圖傳也斷電（Q2、Q3 由 BEC 5V 控制）。

**S3（ESP32-S3-MINI-1-N8）的 GPIO**：9 電池電壓（×22/122）、10/11 圖傳 UART RX/TX、15 IR、19/20 USB、0 接 B 焊盤（救磚：短接 B 和 G 再上電）。

**插座**

| 位號 | 用途 | 型號 | 腳位 |
|---|---|---|---|
| J1 | 電調 | ZH1.5 4P | 1 S2 黃、2 S1 藍、3 GND 綠、4 5V 棕（線序已確認） |
| J2 | EP2 外接 | ZH1.5 4P | 1 EP2 TX、2 EP2 RX、3 延遲 5V、4 GND |
| J3 | 圖傳 | JST1.0（SH）6P | 1 電源、2 GND、3 圖傳 RX、4 圖傳 TX，5、6 不接 |
| J4 | 風扇 | ZH1.5 2P | 1 5V、2 GND |
| J5 | IR 計圈燈 | ZH1.5 2P | 1 LED+、2 LED− |
| J6 | 電池 | ZH1.5 2P | 1 電池 +、2 GND |
| J9 | USB-C | | 燒錄 |

EP2 手焊，三選一：焊盤朝上緣、焊盤朝下（天線朝上緣），或插線到 J2。焊盤間距 2.4 mm（實測 TX 到 G 7.2 mm）。

### 下一版要確認

1. 貼片方向修正都在 `gen_pcb.py` 的 `CPL_TURN`、`CPL_MOVE_Y`，已對照預覽調過 Q2～Q4、U3、D2、D3、J1、J3、J9。
2. 確認 46×35 放得進車內，包含立式插座和線的高度。v8 沒做外殼干涉檢查。

### 拿到板子後

1. 電池先不接，插上電調線，從上往下看 J1 應是棕、綠、藍、黃。
2. 用萬用表確認 J6 正負極。板上沒有防反接，接反會燒板。
3. USB-C 朝下看：J6、J5 右邊是第 1 腳，J4 也是右邊第 1 腳（下緣，同 J5）。
4. 上電看 EP2 是否在約 1 秒內啟動並連上發射端。**RC 延遲本身還沒實測**，延遲不夠就把 C1 換 22µF（C45783）。

### 待決定或待做

- 車端韌體還沒寫：讀電量、IR 計圈發射、圖傳 OSD。電量在 EP2 為 PWM 模式時無法用 ELRS 回傳，只能走 OSD。
- 用 S3 模擬 MSP DisplayPort 給 Ascent 圖傳，沒有實測（社群資料多半是 Avatar）。
- 圈速要從終點拱門 → P4 → ELRS AUX 通道 → S3，拱門還沒做。
- 接線測試見本文件開頭。`firmware/elrs-bench` 是方案 B 的韌體，v8 目前的方案 A 不使用它。
- 文件 `docs/*/hardware.md`、`hardware/README.md` 還沒更新到 v8。

### 其他板子

v3～v7 已移到 `hardware/archive/`，用途見該目錄的 `README.md`。

## 新電腦要裝的東西

| 用途 | 需要 | 這台的版本 |
|---|---|---|
| macOS | | 27.0.1 |
| 電路板 | KiCad，裝在 `/Applications/KiCad/` | 10.0.7 |
| 自動佈線 | Java 17（`openjdk@17`）；Freerouting 1.9.0 已在 `hardware/tools/` | 17.0.15 |
| 韌體 | ESP-IDF，裝在 `~/esp/esp-idf` | v5.5.6 |
| 桌面端 | Rust/Cargo，FFmpeg 等，見 `docs/en/development.md` | rustc 1.99.1 |
| 外殼 CAD | Python 虛擬環境：`pip install manifold3d numpy trimesh matplotlib scipy` | |
| IR 發射器 | ch32fun（clone 到 `~/ch32fun`）、minichlink、WCH-LinkE；編譯用 ESP-IDF 的 riscv32 GCC | |
| 其他 | `git`、`gh`（已登入）；瀏覽器工具 ego-browser（選用） | |

**不在 git 裡，要手動處理：**

- 完整的歷史和決策已整理在 [docs/project-notes.md](docs/project-notes.md)。Claude 的原始筆記在 `~/.claude/projects/` 下，新電腦不需要；綁定短語沒有寫進文件，請從接收機設定取得。
- `third_party/aviateur` 是 submodule，只需要它和底下的 `3rd/devourer`，指令見下一節。**不要用 `--recursive`**：`devourer/reference/rtl8852cu` 記錄的提交在遠端已不存在，會卡住，而且 `reference/*` 不參與編譯。

## 取得程式碼與重新產生

```bash
git clone https://github.com/bynhack/rc-control.git
cd rc-control
git checkout feat/esp32-wheel
git submodule update --init third_party/aviateur
git -C third_party/aviateur submodule update --init 3rd/devourer
```

重新佈線並輸出（在 `hardware/x2201-carrier-v8/`）：

```bash
FAB=1 /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 gen_pcb.py
/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 gen_sch.py
```

驗證：

```bash
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli pcb drc --refill-zones --severity-all -o /tmp/drc.rpt x2201-carrier-v8.kicad_pcb
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli sch erc --severity-all -o /tmp/erc.rpt x2201-carrier-v8.kicad_sch
```

韌體：

```bash
. ~/esp/esp-idf/export.sh
cd firmware/wheel-esp32
idf.py build
```

## 佈線的注意事項（踩過的坑）

- DRC 通過不代表電路對：要逐條檢查網路（曾把 IR 打成兩個網路）和線寬。
- `gen_pcb.py` 的 `rules()` 要在匯出 DSN 之前執行，否則全部走線只有 0.2 mm。
- KiCad 匯入 SES 時遇到螺絲孔的 placement 區塊會中斷，`import_ses()` 會先去掉它。
- USB 交叉是手畫的（`draw_usb()`）。板高改變時 `_P` 會跟著 `H`，不用手改。
- 只動絲印或 CPL 時用 `REUSE_SES=1`，不會重新佈線。
- 嘉立創預覽常有元件方向差異，每次都要看。

## 溝通偏好

- 回覆使用繁體中文。
- 有 brew install 要先問。
- 不改全域 git 設定。
- commit、push 要使用者明確要求才做。
- 重新燒錄前要先說明原因。
