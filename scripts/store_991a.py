"""00991A 快照儲存與時間序列彙整（結構與 store.py 相同，路徑獨立）。

- 每個交易日一份 snapshot：data/snapshots_991a/{trade_date}.json
- 若該日已存在則視為無新資料（回傳 None），上層據此靜默不推送。
- 彙整 docs/history_991a.json，供前端儀表板畫長期權重趨勢。
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SNAP_DIR = ROOT / "data" / "snapshots_991a"
HISTORY_FILE = ROOT / "docs" / "history_991a.json"


def _write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def snapshot_path(trade_date: str) -> Path:
    return SNAP_DIR / f"{trade_date}.json"


def load_snapshot(trade_date: str) -> dict | None:
    p = snapshot_path(trade_date)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def list_trade_dates() -> list[str]:
    """已存在的交易日（升冪）。"""
    if not SNAP_DIR.exists():
        return []
    return sorted(p.stem for p in SNAP_DIR.glob("*.json"))


def previous_trade_date(trade_date: str) -> str | None:
    """回傳早於 trade_date 的最近一個交易日。"""
    earlier = [d for d in list_trade_dates() if d < trade_date]
    return earlier[-1] if earlier else None


def _rebuild_history() -> None:
    """從所有 snapshot 重建 history_991a.json（含每日摘要與逐檔權重）。"""
    series = []
    for d in list_trade_dates():
        snap = load_snapshot(d)
        if not snap:
            continue
        series.append(
            {
                "date": snap["trade_date"],
                "summary": snap.get("summary", {}),
                "holdings": [
                    {
                        "code": h["code"],
                        "name": h["name"],
                        "nav_rate": h["nav_rate"],
                        "share": h["share"],
                        "amount": h["amount"],
                    }
                    for h in snap["holdings"]
                ],
            }
        )
    _write_json(HISTORY_FILE, {"fund": "00991A", "series": series})


def store_snapshot(snap: dict) -> dict | None:
    """寫入快照。若該交易日已存在則回傳 None（無新資料）。"""
    trade_date = snap["trade_date"]
    if snapshot_path(trade_date).exists():
        return None
    _write_json(snapshot_path(trade_date), snap)
    _rebuild_history()
    return snap
