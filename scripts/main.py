"""每日主流程：fetch → 去重 store → diff → notify。

無新資料（同 TranDate 已存在）時直接結束，不推送 Discord。
退出碼：
  0 正常（含「無新資料」）
  1 抓取或解析失敗
"""

import sys

# 確保在 Windows cp950 主控台也能印出中文與 emoji 預覽而不崩潰
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

from fetch import fetch_snapshot
from store import store_snapshot
from diff import compute_operations
from notify import build_message, send_discord


def main() -> int:
    try:
        snap = fetch_snapshot()
    except Exception as e:  # 網路或解析失敗
        print(f"[main] 抓取失敗：{e}", file=sys.stderr)
        return 1

    print(f"[main] 取得資料日 {snap['trade_date']}，持股 {len(snap['holdings'])} 檔")

    stored = store_snapshot(snap)
    if stored is None:
        print(f"[main] {snap['trade_date']} 已存在（無新資料），靜默不推送。")
        return 0

    ops = compute_operations(snap)
    message = build_message(snap, ops)
    sent = send_discord(message)
    print(f"[main] 已{'推送 Discord' if sent else '輸出預覽'}（資料日 {snap['trade_date']}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
