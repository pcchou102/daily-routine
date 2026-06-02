"""抓取 ezmoney 頁面並解析 00981A 的每日持股快照。

資料來源：頁面 HTML 內嵌一個 <div id="DataAsset" data-content="...">，
其 data-content 是雙重 HTML 編碼的 JSON。免登入、純 GET。
"""

import html
import json
import re
from datetime import datetime, timezone

import requests

FUND_CODE = "49YTW"        # 00981A 統一台股增長主動式ETF基金
FUND_DISPLAY = "00981A"
PAGE_URL = f"https://www.ezmoney.com.tw/ETF/Fund/Info?fundCode={FUND_CODE}"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

# data-content 中各資產的代碼對應
_SUMMARY_CODES = {
    "NAV": "nav",            # 淨資產
    "OUT_UNIT": "out_unit",  # 流通在外單位數
    "P_UNIT": "p_unit",      # 每單位淨值
    "CASH": "cash",          # 現金
}


def _extract_data_asset(page_html: str) -> list:
    """從頁面 HTML 取出 #DataAsset 的 data-content 並解碼為 list。"""
    m = re.search(r'id="DataAsset"\s+data-content="(.*?)"', page_html, re.S)
    if not m:
        raise ValueError("頁面中找不到 #DataAsset，網站結構可能已改變")
    # data-content 是雙重 HTML 編碼
    raw = html.unescape(html.unescape(m.group(1)))
    return json.loads(raw)


def _to_trade_date(tran_date: str) -> str:
    """'2026-06-01T00:00:00' -> '2026-06-01'"""
    return tran_date[:10]


def fetch_snapshot(page_html: str | None = None) -> dict:
    """回傳當日持股快照。

    結構：
    {
        "fund": "00981A",
        "trade_date": "YYYY-MM-DD",
        "fetched_at": iso8601,
        "summary": {"nav":.., "out_unit":.., "p_unit":.., "cash":..},
        "holdings": [{"code","name","share","amount","nav_rate"}, ...]
    }
    """
    if page_html is None:
        resp = requests.get(PAGE_URL, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        page_html = resp.text

    assets = _extract_data_asset(page_html)

    summary = {}
    holdings = []
    trade_date = None

    for asset in assets:
        code = asset.get("AssetCode")
        if code in _SUMMARY_CODES:
            summary[_SUMMARY_CODES[code]] = asset.get("Value")
        if code == "ST" and asset.get("Details"):
            for d in asset["Details"]:
                if trade_date is None and d.get("TranDate"):
                    trade_date = _to_trade_date(d["TranDate"])
                holdings.append(
                    {
                        "code": str(d.get("DetailCode", "")).strip(),
                        "name": str(d.get("DetailName", "")).strip(),
                        "share": d.get("Share"),
                        "amount": d.get("Amount"),
                        "nav_rate": d.get("NavRate"),
                    }
                )

    if trade_date is None:
        raise ValueError("解析不到持股 TranDate，可能當日尚無資料")

    holdings.sort(key=lambda h: (h["nav_rate"] or 0), reverse=True)

    return {
        "fund": FUND_DISPLAY,
        "trade_date": trade_date,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "holdings": holdings,
    }


if __name__ == "__main__":
    snap = fetch_snapshot()
    print(f"資料日 {snap['trade_date']} | 持股 {len(snap['holdings'])} 檔")
    for h in snap["holdings"][:5]:
        print(f"  {h['code']} {h['name']}  {h['nav_rate']}%  {h['share']:,.0f} 股")
