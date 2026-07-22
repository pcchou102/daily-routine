"""00991A 每日主流程：fetch → 去重 store → diff → notify（邏輯與 main.py 相同）。

無新資料（同交易日已存在）時直接結束，不推送 Discord。
退出碼：
  0 正常（含「無新資料」）
  1 抓取或解析失敗
"""

import sys

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

from fetch_991a import fetch_snapshot
from store_991a import store_snapshot
from diff_991a import compute_operations
from notify_991a import build_message, send_discord


def main() -> int:
    try:
        snap = fetch_snapshot()
    except Exception as e:  # 網路或解析失敗
        print(f"[main_991a] 抓取失敗：{e}", file=sys.stderr)
        return 1

    print(f"[main_991a] 取得資料日 {snap['trade_date']}，持股 {len(snap['holdings'])} 檔")

    stored = store_snapshot(snap)
    if stored is None:
        print(f"[main_991a] {snap['trade_date']} 已存在（無新資料），靜默不推送。")
        return 0

    ops = compute_operations(snap)
    message = build_message(snap, ops)
    sent = send_discord(message)
    print(f"[main_991a] 已{'推送 Discord' if sent else '輸出預覽'}（資料日 {snap['trade_date']}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
