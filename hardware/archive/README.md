# 封存的板子

這些方案都不在目前的路徑上，見 [ROADMAP.md](../ROADMAP.md)。

| 版本 | 內容 | 封存原因 | 還有什麼用 |
|---|---|---|---|
| `x2201-carrier` | v3，被動接線板，FPV 支架底座 | 被後續版本取代 | 延遲電路（Q1、C1、R1、D1）的來源，階段 2 參考 |
| `x2201-carrier-v4` | S3-MINI-1，EP2 → CRSF → S3 → PWM | 被 v8 取代 | 階段 1 的電路參考 |
| `x2201-carrier-v5` | 自製 ELRS、OpenIPC 圖傳 | 超出目前階段 | 階段 3 的電路參考 |
| `x2201-carrier-v6` | S3 裸晶片、板載天線、雙面貼片 | 一次整合太多，初版風險過高 | 階段 3 的教訓 |
| `x2201-carrier-v7` | S3-Zero + EP2 手焊 | 圖傳插座是錯的 4P，被 v8 取代 | 無，僅留存紀錄 |

`pcbgen.py`、`schgen.py`、`lib`、`tools` 是指向上一層的符號連結，讓各板的 `gen_pcb.py`、`gen_sch.py` 不用改就能執行。
