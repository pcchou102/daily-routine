"""抓取復華 fhtrust 網站並解析 00991A 的每日持股快照。

資料來源：Excel API `/api/assetsExcel/ETF23/YYYYMMDD`（免登入、純 GET，回傳 .xlsx）。
頁面 HTML 表格只顯示前 10 檔，Excel 才有完整 50 檔持股，故改用此 API。
若當日尚無資料，API 會回傳極小的 JSON（"查無資料"）而非 .xlsx，需往前逐日回退查找。
"""

import re
import zipfile
from datetime import datetime, timedelta, timezone
from io import BytesIO

import requests

FUND_DISPLAY = "00991A"
API_URL = "https://www.fhtrust.com.tw/api/assetsExcel/ETF23/{date}"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

_MAX_LOOKBACK_DAYS = 7  # 遇假日/國定假日時，最多往前回退幾天尋找最近一個交易日
_TW_TZ = timezone(timedelta(hours=8))


def _shared_strings(z: zipfile.ZipFile) -> list[str]:
    xml = z.read("xl/sharedStrings.xml").decode("utf-8")
    items = re.findall(r"<x:si>(.*?)</x:si>", xml, re.S)
    return ["".join(re.findall(r"<x:t[^>]*>(.*?)</x:t>", s, re.S)) for s in items]


def _sheet_rows(z: zipfile.ZipFile, sst: list[str]) -> dict[int, dict[str, str]]:
    """回傳 {row_number: {col_letter: resolved_text}}，數字型 cell 直接取原始字串。"""
    xml = z.read("xl/worksheets/sheet1.xml").decode("utf-8")
    rows: dict[int, dict[str, str]] = {}
    for row_m in re.finditer(r'<x:row r="(\d+)"[^>]*>(.*?)</x:row>', xml, re.S):
        rn = int(row_m.group(1))
        cells = re.findall(r'<x:c r="([A-Z]+)\d+"([^>]*)>.*?<x:v>(.*?)</x:v>', row_m.group(2), re.S)
        resolved = {}
        for col, attrs, v in cells:
            resolved[col] = sst[int(v)] if 't="s"' in attrs else v
        rows[rn] = resolved
    return rows


def _to_number(s: str) -> float:
    return float(s.replace(",", ""))


def _parse_xlsx(content: bytes) -> dict:
    z = zipfile.ZipFile(BytesIO(content))
    sst = _shared_strings(z)
    rows = _sheet_rows(z, sst)

    trade_date = None
    nav = out_unit = p_unit = None
    header_row = None

    for rn in sorted(rows):
        cell_a = rows[rn].get("A", "")
        if cell_a.startswith("日期:") or cell_a.startswith("日期："):
            m = re.search(r"(\d{4})/(\d{2})/(\d{2})", cell_a)
            if m:
                trade_date = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        elif cell_a == "基金資產淨值":
            nav = _to_number(rows[rn + 1]["A"]) if rn + 1 in rows else None
        elif cell_a == "基金在外流通單位數":
            out_unit = _to_number(rows[rn + 1]["A"]) if rn + 1 in rows else None
        elif cell_a == "基金每單位淨值":
            p_unit = _to_number(rows[rn + 1]["A"]) if rn + 1 in rows else None
        elif cell_a == "證券代號":
            header_row = rn

    if trade_date is None or header_row is None:
        raise ValueError("Excel 內容格式無法辨識，網站結構可能已改變")

    holdings = []
    rn = header_row + 1
    while rn in rows:
        r = rows[rn]
        code = r.get("A", "").strip()
        name = r.get("B", "").strip()
        if not code or not re.match(r"^\d{4,6}[A-Z]?$", code):
            break
        holdings.append(
            {
                "code": code,
                "name": name,
                "share": _to_number(r["C"]) if "C" in r else None,
                "amount": _to_number(r["D"]) if "D" in r else None,
                "nav_rate": _to_number(r["E"].rstrip("%")) if "E" in r else None,
            }
        )
        rn += 1

    if not holdings:
        raise ValueError("解析不到任何持股資料")

    holdings.sort(key=lambda h: (h["nav_rate"] or 0), reverse=True)

    return {
        "fund": FUND_DISPLAY,
        "trade_date": trade_date,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "summary": {"nav": nav, "out_unit": out_unit, "p_unit": p_unit, "cash": None},
        "holdings": holdings,
    }


def fetch_snapshot(xlsx_bytes: bytes | None = None) -> dict:
    """回傳當日持股快照（結構與 981A 的 fetch_snapshot 相同）。

    若未提供 xlsx_bytes，會從今天開始往前找最近一個有資料的交易日。
    """
    if xlsx_bytes is not None:
        return _parse_xlsx(xlsx_bytes)

    today = datetime.now(_TW_TZ).date()
    last_err = None
    for i in range(_MAX_LOOKBACK_DAYS):
        d = today - timedelta(days=i)
        url = API_URL.format(date=d.strftime("%Y%m%d"))
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
        except Exception as e:  # noqa: BLE001
            last_err = e
            continue
        if not resp.content.startswith(b"PK"):
            continue  # 該日無資料（回傳查無資料的 JSON），往前一天再試
        try:
            return _parse_xlsx(resp.content)
        except Exception as e:  # noqa: BLE001
            last_err = e
            continue

    raise ValueError(f"近 {_MAX_LOOKBACK_DAYS} 天皆抓不到 00991A 資料：{last_err}")


if __name__ == "__main__":
    snap = fetch_snapshot()
    print(f"資料日 {snap['trade_date']} | 持股 {len(snap['holdings'])} 檔")
    for h in snap["holdings"][:5]:
        print(f"  {h['code']} {h['name']}  {h['nav_rate']}%  {h['share']:,.0f} 股")
