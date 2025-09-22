# lottery_store.py — single-source of truth for jackpots + history
from __future__ import annotations

import csv
import io
import json
import os
import re
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

# Persist the normalized rows here (works on Render)
STORE_PATH = "/tmp/lotto_store.json"

# In-memory DB: key = (game, date, tier_or_empty)
_DB: Dict[Tuple[str, str, str], Dict[str, Any]] = {}


# ---------------- Date helpers ----------------

_DATE_SPLIT = re.compile(r"^\s*(\d{1,4})[/-](\d{1,2})[/-](\d{1,4})\s*$")

def _norm_date(s: str) -> str:
    """
    Normalize many date shapes to MM/DD/YYYY.
    Accepts: 9/6/2025, 09/06/2025, 9/6/25, 2025-09-06, 09-06-2025.
    """
    s = (s or "").strip()
    if not s:
        raise ValueError("Empty date")

    # Try fast known strptime formats (no %-m directives for portability)
    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%m-%d-%Y", "%m-%d-%y"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime("%m/%d/%Y")
        except Exception:
            pass

    # Flexible parser: allow single-digit month/day and either 2 or 4-digit year
    m = _DATE_SPLIT.match(s.replace(".", "/"))
    if not m:
        raise ValueError(f"Unrecognized date: {s!r}")

    a, b, c = m.groups()
    # Try to decide shape:
    # If first is 4 digits => YYYY/MM/DD
    if len(a) == 4:
        yyyy, mm, dd = a, b, c
    # Else if last is 4 digits => MM/DD/YYYY
    elif len(c) == 4:
        mm, dd, yyyy = a, b, c
    else:
        # Two-digit year at the end -> assume 2000+
        mm, dd, yy = a, b, c
        yyyy = str(2000 + int(yy))

    mm_i = int(mm)
    dd_i = int(dd)
    yyyy_i = int(yyyy)
    dt = datetime(yyyy_i, mm_i, dd_i)
    return dt.strftime("%m/%d/%Y")


# ---------------- Persistence ----------------

def _load_db() -> None:
    global _DB
    if os.path.exists(STORE_PATH):
        try:
            with open(STORE_PATH, "r", encoding="utf-8") as f:
                raw = json.load(f)
            # Ensure keys back to tuples
            _DB = {
                tuple(k.split("|", 2)): v
                for k, v in raw.items()
            }
        except Exception:
            _DB = {}
    else:
        _DB = {}


def _save_db() -> None:
    os.makedirs(os.path.dirname(STORE_PATH), exist_ok=True)
    # Flatten tuple keys for JSON
    flat = {"|".join(k): v for k, v in _DB.items()}
    with open(STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(flat, f, ensure_ascii=False)


# ---------------- Normalization ----------------

def _norm_game(x: str) -> str:
    g = (x or "").strip().upper()
    if g in ("MEGAMILLIONS", "MEGA MILLIONS", "MM"):
        return "MM"
    if g in ("POWERBALL", "POWER BALL", "PB"):
        return "PB"
    if g in ("IL", "ILLINOIS", "ILLOTTO", "IL LOTTO"):
        return "IL"
    raise ValueError(f"Unknown game: {x!r}")

def _norm_tier(game: str, t: str) -> str:
    """
    For MM/PB the tier is empty string.
    For IL: allowed '', 'JP', 'M1', 'M2' (we coerce '' -> 'JP' when querying if needed).
    """
    if game in ("MM", "PB"):
        return ""
    tier = (t or "").strip().upper()
    if tier in ("", "JP", "M1", "M2"):
        return tier
    raise ValueError(f"Unknown IL tier: {t!r}")


def _row_key(game: str, date: str, tier: str) -> Tuple[str, str, str]:
    return (game, date, tier)


# ---------------- CSV Import ----------------

def import_csv(text: str, overwrite: bool = False) -> Dict[str, int | bool]:
    """
    Import a combined history CSV (one file for all games).
    Expected headers:
      game, draw_date, tier, n1, n2, n3, n4, n5, n6, bonus
    - MM/PB: use n1..n5 + bonus; n6 may be blank
    - IL:    use n1..n6; bonus blank; tier must be JP/M1/M2 (JP for 6-number jackpot)
    """
    _load_db()

    f = io.StringIO(text)
    reader = csv.DictReader(f)
    if not reader.fieldnames:
        raise ValueError("CSV has no header row")

    added = 0
    updated = 0

    for i, r in enumerate(reader, start=2):
        try:
            game = _norm_game(r.get("game", ""))
            date = _norm_date(r.get("draw_date", ""))
            tier = _norm_tier(game, r.get("tier", ""))

            # mains
            n1 = int(r.get("n1", "0"))
            n2 = int(r.get("n2", "0"))
            n3 = int(r.get("n3", "0"))
            n4 = int(r.get("n4", "0"))
            n5 = int(r.get("n5", "0"))
            mains: List[int]
            bonus: Optional[int]

            if game in ("MM", "PB"):
                mains = [n1, n2, n3, n4, n5]
                braw = r.get("bonus", "")
                bonus = None if (braw == "" or braw is None) else int(braw)
                if bonus is None:
                    raise ValueError("MM/PB row missing bonus")
                tier = ""  # ensure empty for MM/PB
            else:
                # IL — six numbers; bonus blank; tier required (JP/M1/M2)
                n6 = int(r.get("n6", "0"))
                mains = [n1, n2, n3, n4, n5, n6]
                bonus = None
                if tier == "":
                    # Default JP if omitted
                    tier = "JP"

            key = _row_key(game, date, tier)
            payload = {"game": game, "date": date, "tier": tier, "mains": mains, "bonus": bonus}

            if overwrite or key not in _DB:
                if key in _DB:
                    updated += 1
                else:
                    added += 1
                _DB[key] = payload
        except Exception as e:
            # Skip bad rows but keep going
            # You can log or collect errors if needed.
            continue

    _save_db()
    return {"ok": True, "added": added, "updated": updated, "total": added + updated}


# ---------------- Lookups ----------------

def _find_row(game: str, date: str, tier: str = "") -> Optional[Dict[str, Any]]:
    """Return the row dict or None."""
    game = _norm_game(game)
    date = _norm_date(date)
    if game == "IL":
        tier = _norm_tier(game, tier or "JP")
    else:
        tier = ""

    return _DB.get(_row_key(game, date, tier))


def get_by_date(game: str, date: str, tier: str = "") -> Optional[Dict[str, Any]]:
    """
    Public: return a normalized row or None.
      - MM/PB:   tier ignored
      - IL:      tier 'JP'/'M1'/'M2' (default 'JP')
    """
    _load_db()
    row = _find_row(game, date, tier)
    if not row:
        return None
    # Copy to avoid mutation
    return {
        "game": row["game"],
        "date": row["date"],
        "tier": row["tier"],
        "mains": list(row["mains"]),
        "bonus": row["bonus"],
    }


def _fmt_blob_mm(row: Dict[str, Any]) -> str:
    # mm-dd-yy — n1-n2-n3-n4-n5 MB(two-digit)
    dt = datetime.strptime(row["date"], "%m/%d/%Y")
    left = dt.strftime("%m-%d-%y")
    nums = "-".join(f"{n:02d}" for n in row["mains"])
    mb = f"{int(row['bonus']):02d}" if row.get("bonus") is not None else "00"
    return f"{left} — {nums} {mb}"

def _fmt_blob_il(row: Dict[str, Any]) -> str:
    dt = datetime.strptime(row["date"], "%m/%d/%Y")
    left = dt.strftime("%m-%d-%y")
    nums = "-".join(f"{n:02d}" for n in row["mains"])
    return f"{left} — {nums}"


def get_history(game: str, start_date: str, limit: int = 20, tier: str = "") -> Dict[str, Any]:
    """
    Return up to `limit` rows going back in time including `start_date`.
    Also returns a 'blob' string suitable for your UI history textareas.
    """
    _load_db()
    game = _norm_game(game)
    start_date = _norm_date(start_date)
    if game == "IL":
        tier = _norm_tier(game, tier or "JP")
    else:
        tier = ""

    # Gather all rows for this game/tier
    rows = [
        v for (g, d, t), v in _DB.items()
        if g == game and t == tier
    ]

    # Sort desc by date
    rows.sort(key=lambda r: datetime.strptime(r["date"], "%m/%d/%Y"), reverse=True)

    # Find start index (first row with date <= start_date, but we sort DESC,
    # so take the first row whose date == start_date, else the first earlier)
    start_dt = datetime.strptime(start_date, "%m/%d/%Y")

    start_idx = None
    for i, r in enumerate(rows):
        dt = datetime.strptime(r["date"], "%m/%d/%Y")
        if dt <= start_dt:
            start_idx = i
            break

    if start_idx is None:
        return {"rows": [], "blob": ""}

    pick = rows[start_idx:start_idx + max(1, int(limit))]

    # Blob
    if game in ("MM", "PB"):
        lines = [_fmt_blob_mm(r) for r in pick]
    else:
        lines = [_fmt_blob_il(r) for r in pick]

    return {"rows": pick, "blob": "\n".join(lines)}
