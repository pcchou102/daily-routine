"""比較 00991A 相鄰兩個交易日的持股，產出經理人操作清單（邏輯與 diff.py 相同）。"""

from store_991a import load_snapshot, previous_trade_date


def _index(holdings: list[dict]) -> dict[str, dict]:
    return {h["code"]: h for h in holdings}


def compute_operations(snap: dict) -> dict:
    """回傳當日操作。snap 為今日快照。"""
    prev_date = previous_trade_date(snap["trade_date"])
    if prev_date is None:
        return {
            "trade_date": snap["trade_date"],
            "prev_date": None,
            "is_initial": True,
            "added": [],
            "removed": [],
            "increased": [],
            "decreased": [],
        }

    prev = load_snapshot(prev_date)
    today = _index(snap["holdings"])
    before = _index(prev["holdings"])

    added, removed, increased, decreased = [], [], [], []

    for code, h in today.items():
        if code not in before:
            added.append(
                {
                    "code": code,
                    "name": h["name"],
                    "nav_rate": h["nav_rate"],
                    "share": h["share"],
                }
            )
        else:
            b = before[code]
            d_share = (h["share"] or 0) - (b["share"] or 0)
            if d_share == 0:
                continue
            rec = {
                "code": code,
                "name": h["name"],
                "share_change": d_share,
                "share_to": h["share"],  # 當日總股數，供顯示「→ X張」
                "nav_rate_from": b["nav_rate"],
                "nav_rate_to": h["nav_rate"],
            }
            (increased if d_share > 0 else decreased).append(rec)

    for code, b in before.items():
        if code not in today:
            removed.append(
                {
                    "code": code,
                    "name": b["name"],
                    "nav_rate": b["nav_rate"],
                    "share": b["share"],
                }
            )

    added.sort(key=lambda x: (x["nav_rate"] or 0), reverse=True)
    removed.sort(key=lambda x: (x["nav_rate"] or 0), reverse=True)
    increased.sort(key=lambda x: x["share_change"], reverse=True)
    decreased.sort(key=lambda x: x["share_change"])

    return {
        "trade_date": snap["trade_date"],
        "prev_date": prev_date,
        "is_initial": False,
        "added": added,
        "removed": removed,
        "increased": increased,
        "decreased": decreased,
    }


def has_changes(ops: dict) -> bool:
    return bool(
        ops["added"] or ops["removed"] or ops["increased"] or ops["decreased"]
    )
