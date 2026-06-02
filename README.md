# 00981A 持股追蹤

每日自動抓取 **00981A 統一台股增長主動式ETF基金** 的持股明細，計算經理人當日操作（新增/移除/加碼/減碼），透過 GitHub Actions 於週一到週五晚間 20:00（台灣時間）推送至 Discord，並提供網頁儀表板觀察長期權重趨勢。

資料來源：<https://www.ezmoney.com.tw/ETF/Fund/Info?fundCode=49YTW>（免登入，純 GET）。

## 運作方式

```
scripts/main.py
  fetch.py   抓頁面 → 解析內嵌 JSON → 當日快照
  store.py   寫 data/snapshots/<date>.json；以資料日去重；重建 docs/history.json
  diff.py    與前一交易日比較 → 經理人操作
  notify.py  組繁中訊息 → POST Discord webhook
```

- 資料有 **1 日遞延**（今天看到的是前一交易日收盤的持股）。
- 非交易日 / 資料未更新（同一資料日已存在）→ **靜默不推送**。
- 每日資料 commit 回 repo，`docs/history.json` 供儀表板讀取。

## 目錄結構

```
.github/workflows/daily.yml   每日排程（cron 0 12 * * 1-5 = 台灣 20:00）
scripts/                      抓取、儲存、比對、推送、主流程
data/snapshots/<date>.json    每交易日完整快照（原始存檔）
docs/index.html, app.js       GitHub Pages 儀表板
docs/history.json             時間序列（儀表板與長期趨勢用）
```

## 設定步驟

1. **建立 GitHub repo**（建議 public：持股資料本就公開，且 public Pages 免費），把本專案推上去。

2. **設定 Discord webhook**
   - Discord 頻道 → 編輯頻道 → 整合 → Webhook → 新增 Webhook → 複製網址。
   - GitHub repo → Settings → Secrets and variables → Actions → **New repository secret**
     - Name: `DISCORD_WEBHOOK_URL`
     - Value: 貼上 webhook 網址

3. **啟用 GitHub Pages**
   - repo → Settings → Pages → Source 選 **Deploy from a branch**，分支 `main`、資料夾 `/docs`。
   - 儀表板網址形如 `https://<帳號>.github.io/<repo>/`。
   - （選用）把該網址設為 Actions variable `DASHBOARD_URL`（Settings → Variables → Actions），Discord 訊息會附上儀表板連結。

4. **首次執行建立基準**
   - repo → Actions → 「00981A 每日持股追蹤」→ **Run workflow**（手動觸發 `workflow_dispatch`）。
   - 第一次會建立 baseline 快照並推送「初始建倉」訊息；隔日起回報每日變動。

## 本機執行

```bash
pip install -r requirements.txt

# 抓取並產生快照 / 更新 history.json（未設 webhook 時只會在終端機預覽訊息）
python scripts/main.py

# 預覽儀表板（從 docs 目錄起 http server，避免 file:// 的 CORS）
python -m http.server 8765 --directory docs
# 開 http://localhost:8765
```

設定 `DISCORD_WEBHOOK_URL` 環境變數即可實際推送：

```powershell
$env:DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/..."
python scripts/main.py
```

## 儀表板功能

- **個股權重趨勢**：點選股票 chip（預設權重前 5 大），看占淨值比隨時間變化（例如 2330 從 10% → 15%），可切換近 30/90 個交易日。
- **最新持股表**：依權重排序，顯示權重變化、排名變化與股數。
