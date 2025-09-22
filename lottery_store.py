from __future__ import annotations

import csv
import io
import json
import os
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

# Where the normalized history lives on Render
STORE_PATH = "/tmp/lotto_store.json"

# In-memory db: key = (game, date, tier_or_empty)
_DB: Dict[Tuple[str, str, str], Dict[str, Any]] = {}


# ---------------- Date helpers ----------------

def _norm_date(s: str) -> str:
    """
    Normalize many shapes to MM/DD/YYYY.
    Accepts: 9/6/2025, 09/06/2025, 2025-09-06, 09-06-2025, 09/06/25
    Raises ValueError if not parseable.
    """
    s = (s or "").strip()
    fmts = ["%m/%d/%Y", "%-m/%-d/%Y", "%Y-%m-%d", "%m-%d-%Y", "%m/%d/%y", "%-m/%-d/%y"]
    last = None
    for fmt in fmts:
        try:
            dt = datetime.strptime(s, fmt)  # type: ignore[arg-type]
            return dt.strftime("%m/%d/%Y")
        except Exception as e:
            last = e
    raise ValueError(f"Unrecognized date: {s!r} ({last})")


def _disp_date_US(s: str) -> str:
    """Return MM-DD-YY for display blobs."""
    dt = datetime.strptime(s, "%m/%d/%Y")
    return dt.strftime("%m-%d-%y")


# ---------------- Game/tier helpers ----------------

_IL_ALIASES = {
    "IL_JP": ("IL", "JP"),
    "IL_M1": ("IL", "M1"),
    "IL_M2": ("IL", "M2"),
}

def _split_game_tier(game: str, tier: str = "") -> Tuple[str, str]:
    """
    Accept both:
      game=IL & tier=JP|M1|M2
    and aliases:
      game=IL_JP|IL_M1|IL_M2 (tier may be empty)
    """
    g = (game or "").strip().upper()
    t = (tier or "").strip().upper()
    if g in _IL_ALIASES:
        base, t_alias = _IL_ALIASES[g]
        return base, (t or t_alias)
    return g, t


def _load_store() -> None:
    if os.path.exists(STORE_PATH):
        try:
            with open(STORE_PATH, "r", encoding="utf-8") as f:
                payload = json.load(f)
            _DB.clear()
            for k, v in payload.items():
                g, d, t = k.split("|", 2)
                _DB[(g, d, t)] = v
        except Exception:
            # If corrupted, start fresh
            _DB.clear()


def _save_store() -> None:
    out: Dict[str, Any] = {}
    for (g, d, t), v in _DB.items():
        out[f"{g}|{d}|{t}"] = v
    with open(STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)


# ---------------- Import CSV ----------------

def import_csv(text: str, overwrite: bool = False) -> Dict[str, Any]:
    """
    Import a combined master CSV.
    Supported header (order can vary):
      game, draw_date, tier, n1, n2, n3, n4, n5, n6, bonus
    Examples:
      # MM/PB
      MM,9/16/2025,,10,14,34,40,43,,5
      PB,9/17/2025,,7,30,50,54,62,,20
      # IL
      IL,9/18/2025,JP,2,7,25,30,44,49,
      IL,9/18/2025,M1,10,20,22,23,24,39,
      IL,9/18/2025,M2,3,13,19,25,32,33,
    """
    buf = io.StringIO(text)
    reader = csv.DictReader(buf)

    added = 0
    total = 0
    for row in reader:
        total += 1

        game_raw = (row.get("game") or "").strip()
        date_raw = (row.get("draw_date") or "").strip()
        tier_raw = (row.get("tier") or "").strip()

        game, tier = _split_game_tier(game_raw, tier_raw)
        date = _norm_date(date_raw)

        # read numbers
        def gi(key: str) -> Optional[int]:
            v = (row.get(key) or "").strip()
            return int(v) if v else None

        n1, n2, n3, n4, n5, n6 = gi("n1"), gi("n2"), gi("n3"), gi("n4"), gi("n5"), gi("n6")
        bonus = gi("bonus")

        # Normalize record shape
        rec: Dict[str, Any] = {"game": game, "date": date, "tier": tier, "nums": []}  # type: ignore[typeddict-item]
        if game in ("MM", "PB"):
            if None in (n1, n2, n3, n4, n5) or bonus is None:
                continue
            rec["nums"] = [n1, n2, n3, n4, n5, bonus]
        elif game == "IL":
            if None in (n1, n2, n3, n4, n5, n6):
                continue
            rec["nums"] = [n1, n2, n3, n4, n5, n6]
            if tier not in ("JP", "M1", "M2"):
                # default to JP if missing/invalid
                tier = "JP"
                rec["tier"] = "JP"
        else:
            # Unknown game; skip row
            continue

        key = (game, date, tier if game == "IL" else "")
        if overwrite or key not in _DB:
            _DB[key] = rec
            added += 1

    _save_store()
    return {"ok": True, "added": added, "updated": total - added, "total": total}


# ---------------- Queries ----------------

def get_by_date(game: str, date: str, tier: str = "") -> Optional[Dict[str, Any]]:
    g, t = _split_game_tier(game, tier)
    d = _norm_date(date)
    key = (g, d, t if g == "IL" else "")
    return _DB.get(key)


def _blob_line(rec: Dict[str, Any]) -> str:
    """
    Produce one line of the history blob:
      MM/PB: mm-dd-yy  n1-n2-n3-n4-n5 MB
      IL:    mm-dd-yy  A-B-C-D-E-F
    """
    dd = _disp_date_US(rec["date"])
    nums = rec["nums"]
    if rec["game"] in ("MM", "PB"):
        n1, n2, n3, n4, n5, mb = nums
        return f"{dd}  {n1:02d}-{n2:02d}-{n3:02d}-{n4:02d}-{n5:02d} {mb:02d}"
    # IL
    A, B, C, D, E, F = nums
    return f"{dd}  {A:02d}-{B:02d}-{C:02d}-{D:02d}-{E:02d}-{F:02d}"


def get_history(game: str, start_date: str, limit: int = 20, tier: str = "") -> Dict[str, Any]:
    """
    Return up to `limit` rows BACKWARDS starting from `start_date` (inclusive)
    for the requested game (and tier for IL). Also returns the ‘blob’ text.
    """
    g, t = _split_game_tier(game, tier)
    start = _norm_date(start_date)

    # collect keys for that game/tier
    keys = [(gd, rec) for (gg, gd, gt), rec in _DB.items() if gg == g and (g != "IL" or gt == t)]
    # sort desc by date
    keys.sort(key=lambda kv: datetime.strptime(kv[0], "%m/%d/%Y"), reverse=True)

    out_rows: List[Dict[str, Any]] = []
    blob_lines: List[str] = []

    seen = 0
    for d, rec in keys:
        if datetime.strptime(d, "%m/%d/%Y") <= datetime.strptime(start, "%m/%d/%Y"):
            out_rows.append(rec)
            blob_lines.append(_blob_line(rec))
            seen += 1
            if seen >= limit:
                break

    return {"rows": out_rows, "blob": "\n".join(blob_lines)}
    

# Load on import
_load_store()
