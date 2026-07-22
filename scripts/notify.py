"""組合繁中操作訊息並推送至 Discord webhook。"""

import os

import requests

DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "")


def _fmt_lots_change(shares: float | None) -> str:
    """股數變化 → 張(/1000)，帶正負號與千分位，例如 +1,416張。"""
    lots = round((shares or 0) / 1000)
    return f"{lots:+,d}張"


def _fmt_lots_total(shares: float | None) -> str:
    """當日總股數 → 張，例如 5,441張。"""
    lots = round((shares or 0) / 1000)
    return f"{lots:,d}張"


def _fmt_rate(r) -> str:
    return f"{r:.2f}%" if isinstance(r, (int, float)) else "-"


def build_message(snap: dict, ops: dict) -> str:
    """回傳要送到 Discord 的文字。"""
    s = snap.get("summary", {})
    p_unit = s.get("p_unit")
    nav = s.get("nav")
    cash = s.get("cash")
    cash_pct = (cash / nav * 100) if (cash and nav) else None

    head = f"📊 {snap['fund']} 持股變動 | 資料日 {snap['trade_date']}"
    lines = [head]

    if ops.get("is_initial"):
        lines.append("📌 首次建立基準（初始建倉），共 "
                     f"{len(snap['holdings'])} 檔，明日起回報每日變動。")
    else:
        # 配色：🔴 紅=買進(新增/加碼)、🟢 綠=賣出(移除/減碼)
        any_change = False
        for rec in ops["added"]:
            any_change = True
            lines.append(
                f"🔴 新增：{rec['code']} {rec['name']} "
                f"{_fmt_lots_change(rec['share'])} → {_fmt_lots_total(rec['share'])} "
                f"(0.00%→{_fmt_rate(rec['nav_rate'])})"
            )
        for rec in ops["removed"]:
            any_change = True
            lines.append(
                f"🟢 移除：{rec['code']} {rec['name']} "
                f"{_fmt_lots_change(-(rec['share'] or 0))} → {_fmt_lots_total(0)} "
                f"({_fmt_rate(rec['nav_rate'])}→0.00%)"
            )
        for rec in ops["increased"]:
            any_change = True
            lines.append(
                f"🔴 加碼：{rec['code']} {rec['name']} "
                f"{_fmt_lots_change(rec['share_change'])} → {_fmt_lots_total(rec['share_to'])} "
                f"({_fmt_rate(rec['nav_rate_from'])}→{_fmt_rate(rec['nav_rate_to'])})"
            )
        for rec in ops["decreased"]:
            any_change = True
            lines.append(
                f"🟢 減碼：{rec['code']} {rec['name']} "
                f"{_fmt_lots_change(rec['share_change'])} → {_fmt_lots_total(rec['share_to'])} "
                f"({_fmt_rate(rec['nav_rate_from'])}→{_fmt_rate(rec['nav_rate_to'])})"
            )
        if not any_change:
            lines.append("➖ 今日無持股異動（張數與成分股不變）。")

    foot = []
    if p_unit is not None:
        foot.append(f"每單位淨值 {p_unit:.2f}")
    if cash_pct is not None:
        foot.append(f"現金 {cash_pct:.1f}%")
    if foot:
        lines.append("（" + " / ".join(foot) + "）")

    if DASHBOARD_URL:
        lines.append(f"📈 長期趨勢：{DASHBOARD_URL}")

    return "\n".join(lines)


def send_discord(content: str, webhook_url: str | None = None) -> bool:
    """送出訊息。未設定 webhook 時印出內容並回傳 False。"""
    webhook_url = webhook_url or os.environ.get("DISCORD_WEBHOOK_URL", "")
    if not webhook_url:
        print("[notify] 未設定 DISCORD_WEBHOOK_URL，僅預覽：\n" + content)
        return False

    # Discord 單則訊息上限 2000 字，超過則截斷
    if len(content) > 1900:
        content = content[:1900] + "\n…（內容過長已截斷）"

    resp = requests.post(webhook_url, json={"content": content}, timeout=30)
    resp.raise_for_status()
    return True
