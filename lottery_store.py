from __future__ import annotations

import csv
import io
import json
import os
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

# Where we persist the normalized rows (works on Render)
STORE_PATH = "/tmp/lotto_store.json"

# In-memory DB: key = (game, date, tier_or_empty)
_DB: Dict[Tuple[str, str, str], Dict[str, Any]] = {}


# ---------------- Date helpers ----------------

def _norm_date(s: str) -> str:
    """
    Accepts many shapes and returns MM/DD/YYYY.
    """
    s = (s or "").strip()
    # Accept: 9/6/2025, 09/06/2025, 2025-09-06, 09-06-2025, 09/06/25
    fmts = ["%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%m-%d-%Y", "%m-%d-%y"]
    last_err = None
    for fmt in fmts:
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime("%m/%d/%Y")
        except Exception as e:
            last_err = e
    raise ValueError(f"Unrecognized date: {s!r} ({last_err})")


def _load_from_disk() -> None:
    global _DB
    if os.path.exists(STORE_PATH):
        try:
            with open(STORE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            _DB = {tuple(k.split("|", 2)): v for k, v in data.items()}
        except Exception:
            _DB = {}
    else:
        _DB = {}


def _save_to_disk() -> None:
    os.makedirs(os.path.dirname(STORE_PATH), exist_ok=True)
    serial = {"|".join(k): v for k, v in _DB.items()}
    with open(STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(serial, f, ensure_ascii=False)


def _key(game: str, date_mmddyyyy: str, tier: str) -> Tuple[str, str, str]:
    return (game.upper(), date_mmddyyyy, tier.upper() if tier else "")


# ---------------- Public API used by app.py ----------------

def import_csv(text: str, overwrite: bool = False) -> Dict[str, Any]:
    """
    Accepts the entire CSV text as a string.
    Columns (header names are case-insensitive):
      game, draw_date, tier, n1, n2, n3, n4, n5, n6, bonus
    - game: MM | PB | IL
    - tier: blank for MM/PB; for IL use JP/M1/M2 (or blank for classic 6)
    - draw_date: any parseable date (see _norm_date)
    - n1..n6: integers (MM/PB use 5 mains; IL uses 6)
    - bonus: integer for MM/PB, blank for IL
    """
    _load_from_disk()

    if overwrite:
        _DB.clear()

    f = io.StringIO(text)
    reader = csv.DictReader(f)
    added = 0
    updated = 0

    for row in reader:
        game = (row.get("game") or row.get("Game") or "").strip().upper()
        if game not in ("MM", "PB", "IL"):
            # ignore empty or malformed lines
            continue

        raw_date = row.get("draw_date") or row.get("date") or row.get("DrawDate") or ""
        date = _norm_date(str(raw_date))

        tier = (row.get("tier") or row.get("Tier") or "").strip().upper()
        # Standardize IL tier names
        if game == "IL":
            if tier in ("JACKPOT", "JP", "IL_JP", "J"):
                tier = "JP"
            elif tier in ("M1", "IL_M1"):
                tier = "M1"
            elif tier in ("M2", "IL_M2"):
                tier = "M2"
            else:
                # if truly blank, treat as "JP" (classic jackpot) for compatibility
                if not tier:
                    tier = "JP"
        else:
            # MM/PB have no tier
            tier = ""

        # read mains (support 5 or 6)
        def iv(v): 
            v = (v or "").strip()
            return int(v) if v != "" else None

        n1 = iv(row.get("n1")); n2 = iv(row.get("n2")); n3 = iv(row.get("n3"))
        n4 = iv(row.get("n4")); n5 = iv(row.get("n5")); n6 = iv(row.get("n6"))
        mains = [x for x in (n1, n2, n3, n4, n5, n6) if x is not None]

        bonus_raw = row.get("bonus")
        bonus = iv(bonus_raw) if bonus_raw is not None and bonus_raw != "" else None
        if game in ("MM", "PB"):
            # must be 5 mains and a bonus
            mains = mains[:5]
        else:  # IL
            # must be 6 mains; bonus must be None
            bonus = None
            if len(mains) < 6:
                # skip malformed
                continue
            mains = mains[:6]

        rec = {
            "game": game,
            "date": date,
            "tier": tier,
            "mains": mains,
            "bonus": bonus
        }

        k = _key(game, date, tier)
        if k in _DB:
            _DB[k] = rec
            updated += 1
        else:
            _DB[k] = rec
            added += 1

    _save_to_disk()
    return {"ok": True, "added": added, "updated": updated, "total": len(_DB)}


def get_by_date(game: str, date: str) -> Optional[Dict[str, Any]]:
    """
    Returns one record for a game at a date.
    - MM/PB → tier is ""
    - IL    → You must specify a specific tier (JP/M1/M2) in the `game` name:
              use "IL_JP", "IL_M1", or "IL_M2"
    """
    _load_from_disk()
    game = (game or "").upper().strip()
    date = _norm_date(date)

    if game in ("MM", "PB"):
        tier = ""
        return _DB.get(_key(game, date, tier))

    # IL variants
    if game in ("IL_JP", "IL_M1", "IL_M2"):
        tier = game.split("_", 1)[1]
        return _DB.get(_key("IL", date, tier))

    # bare "IL" is ambiguous → None
    return None


def get_history(game: str, start_date: str, limit: int = 20) -> Dict[str, Any]:
    """
    Returns up to `limit` rows from `start_date` (inclusive), going older.
    - game ∈ {"MM","PB","IL_JP","IL_M1","IL_M2"}
    """
    _load_from_disk()
    game = (game or "").upper().strip()
    start_mmddyyyy = _norm_date(start_date)

    if game in ("MM", "PB"):
        tier = ""
        prefix = (game, )
        rows = [v for (g, d, t), v in _DB.items() if g == game and t == ""]
    elif game in ("IL_JP", "IL_M1", "IL_M2"):
        tier = game.split("_", 1)[1]
        rows = [v for (g, d, t), v in _DB.items() if g == "IL" and t == tier]
    else:
        return {"ok": False, "rows": [], "blob": ""}

    # sort newest → oldest by date
    def dkey(r): 
        return datetime.strptime(r["date"], "%m/%d/%Y")

    rows.sort(key=dkey, reverse=True)

    # find index of the start date
    start_idx = next((i for i, r in enumerate(rows) if r["date"] == start_mmddyyyy), None)
    if start_idx is None:
        return {"ok": False, "rows": [], "blob": ""}

    out = rows[start_idx:start_idx+limit]

    # pretty blob (matches your earlier UI)
    if game in ("MM", "PB"):
        blob = "\n".join(
            f'{datetime.strptime(r["date"], "%m/%d/%Y").strftime("%m-%d-%y")}  '
            f'{"-".join(f"{n:02d}" for n in r["mains"])}  {r["bonus"]:02d}'
            for r in out
        )
    else:
        blob = "\n".join(
            f'{datetime.strptime(r["date"], "%m/%d/%Y").strftime("%m-%d-%y")}  '
            f'{"-".join(f"{n:02d}" for n in r["mains"])}'
            for r in out
        )

    return {"ok": True, "rows": out, "blob": blob}
