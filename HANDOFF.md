# 交接文件（2026-11-16）

從這裡可以在另一台 Mac 上接著做。分支：`feat/esp32-wheel`。

## 目前狀態

- 階段 0 接線驗證（EP2 → CRSF → S3 → PWM）2026-11-13 全部通過。
- X2201 的硬體方案已確認，見 [hardware/PLAN.md](hardware/PLAN.md)：電調（DRV8874）、5V BEC、SuperMini 控制器都在主板上，電池只接主板，按鈕開關機。
- 照這份方案畫好的板子是 [`hardware/x2201-mainboard`](hardware/x2201-mainboard)，40×40 mm，用 M2 螺絲固定在前懸吊塊的凸台上、定位柱定位，已佈線，DRC、ERC 都沒有錯誤，Gerber、BOM、CPL 已產生，**還沒打板**。板子外形可以照車內空間再調整。
- 舊的板子（v3～v9）已刪除，需要時從 git 找回（commit `56bd000` 之前）。

## 接下來要做

1. 用卡尺量 SuperMini 兩排的針距（圖上用 15.24 mm）。
2. 在 JLC 下單，並在貼片預覽裡核對側插插座、Q1、U4、U5、L1 的方向。
3. 寫主板韌體，要點見 PLAN.md 的「韌體要做的事」：TX 保持電源、RX 讀按鈕、馬達用 H 橋兩腳控制。
4. 改線材：圖傳插頭改壓成 ZH1.5 4P，舵機換成 ZH1.5 3P。
5. 拿到板子後，先不接電池，用萬用表確認 BAT+ / BAT− 和 5V，再上電。

## 待決定或待做

- 用 S3 模擬 MSP DisplayPort 給 Ascent 圖傳畫 OSD，還沒實測（社群資料多半是 Avatar）。
- 圈速要從終點拱門 → P4 → ELRS AUX 通道 → S3，拱門還沒做。
- `firmware/elrs-bench` 是階段 0 開發板接線測試用的程式，腳位和主板不同。

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

重新佈線並輸出（在 `hardware/x2201-mainboard/`）：

```bash
FAB=1 /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 gen_pcb.py
/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 gen_sch.py
```

驗證：

```bash
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli pcb drc --refill-zones --severity-all -o /tmp/drc.rpt x2201-mainboard.kicad_pcb
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli sch erc --severity-all -o /tmp/erc.rpt x2201-mainboard.kicad_sch
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
- 自動佈線走不通的地方用 `HAND_T` / `HAND_V` 先手畫，Freerouting 會繞開它們。
- SuperMini 天線底下的禁銅區要留出走線通道，否則模組的訊號拉不出來。
- 只動絲印或 CPL 時用 `REUSE_SES=1`，不會重新佈線。
- 嘉立創預覽常有元件方向差異，每次都要看。

## 溝通偏好

- 回覆使用繁體中文。
- 有 brew install 要先問。
- 不改全域 git 設定。
- commit、push 要使用者明確要求才做。
- 重新燒錄前要先說明原因。
