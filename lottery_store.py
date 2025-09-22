from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple


# -----------------------------
# In-memory store
# -----------------------------

@dataclass
class Row:
    game: str                 # "MM" | "PB" | "IL"
    date_mmddyyyy: str        # always normalized “MM/DD/YYYY”
    tier: Optional[str]       # None for MM/PB, "JP" | "M1" | "M2" for IL
    mains: List[int]          # 5 for MM/PB, 6 for IL
    bonus: Optional[int]      # Mega/Power ball (MM/PB) or None for IL

_STORE: Dict[str, Any] = {
    "rows": [],           # List[Row]
    "by_game": {          # Dict[str, Dict[str, list[Row]]]   keyed by date (and tier for IL)
        "MM": {},
        "PB": {},
        "IL": {}          # IL: by date → {"JP": Row, "M1": Row, "M2": Row}
    }
}


# -----------------------------
# Utilities
# -----------------------------

def _norm_date(s: str) -> str:
    """
    Normalize many date shapes to zero-padded MM/DD/YYYY.

    Accepts (examples):
      9/6/2025, 09/06/2025, 9-6-2025
      09/19/25, 9/19/25, 09-19-25   (2-digit year -> 2000+YY)
      2025-09-06, 2025/9/6

    Always returns: MM/DD/YYYY (e.g., 09/06/2025)
    """
    s = (s or "").strip()
    if not s:
        raise ValueError("empty date")

    # Normalize separators to '/'
    t = s.replace("-", "/")
    parts = [p.strip() for p in t.split("/") if p.strip()]
    if len(parts) != 3:
        raise ValueError(f"Unrecognized date: {s!r}")

    def to_int(x: str) -> int:
        if not x.isdigit():
            raise ValueError(f"Unrecognized date: {s!r}")
        return int(x, 10)

    # Heuristics:
    # - If first part has 4 digits: YYYY/M/D
    # - Else if last part has 4 digits: M/D/YYYY
    # - Else last part has 2 digits: M/D/YY (assume 2000–2099)
    if len(parts[0]) == 4:
        y = to_int(parts[0]); m = to_int(parts[1]); d = to_int(parts[2])
    else:
        if len(parts[2]) == 4:
            m = to_int(parts[0]); d = to_int(parts[1]); y = to_int(parts[2])
        else:
            m = to_int(parts[0]); d = to_int(parts[1]); yy = to_int(parts[2])
            y = 2000 + yy

    # Basic range checks (lightweight)
    if not (1 <= m <= 12 and 1 <= d <= 31 and 1900 <= y <= 2100):
        raise ValueError(f"Unrecognized date: {s!r}")

    return f"{m:02d}/{d:02d}/{y:04d}"


def _to_int(x: str | int | None) -> Optional[int]:
    if x is None:
        return None
    if isinstance(x, int):
        return x
    s = str(x).strip()
    if s == "" or s.lower() == "null":
        return None
    return int(s)


def _clean_game(s: str) -> str:
    s = (s or "").strip().upper()
    # Accept “MEGAMILLIONS”, “MEGA MILLIONS”, etc.
    if s in ("MM", "MEGA", "MEGA MILLIONS", "MEGAMILLIONS"):
        return "MM"
    if s in ("PB", "POWERBALL"):
        return "PB"
    if s in ("IL", "ILLINOIS", "IL LOTTO", "ILLOTTO"):
        return "IL"
    return s


def _clean_tier(s: str | None) -> Optional[str]:
    if not s:
        return None
    val = s.strip().upper()
    if val in ("JP", "JACKPOT"):
        return "JP"
    if val in ("M1", "MILLION1", "MILLION 1", "MILLION_1"):
        return "M1"
    if val in ("M2", "MILLION2", "MILLION 2", "MILLION_2"):
        return "M2"
    return val


def _pack_row(r: Row) -> Dict[str, Any]:
    return {
        "game": r.game,
        "date": r.date_mmddyyyy,
        "tier": r.tier,
        "mains": r.mains,
        "bonus": r.bonus,
    }


# -----------------------------
# CSV import
# -----------------------------

def import_csv(text: str, overwrite: bool = False) -> Dict[str, int | bool]:
    """
    Import the combined master CSV from a raw string.
    Expected header (case-insensitive):
      game, draw_date, tier, n1, n2, n3, n4, n5, n6, bonus
    - MM/PB use n1..n5 + bonus (n6 ignored)
    - IL uses n1..n6, bonus ignored; tier must be JP/M1/M2
    """
    global _STORE

    if overwrite:
        _STORE = {"rows": [], "by_game": {"MM": {}, "PB": {}, "IL": {}}}

    reader = csv.DictReader(io.StringIO(text))
    added = 0

    for raw in reader:
        game = _clean_game(raw.get("game", ""))
        date = _norm_date(raw.get("draw_date", "") or raw.get("date", ""))
        tier = _clean_tier(raw.get("tier"))

        n1 = _to_int(raw.get("n1"))
        n2 = _to_int(raw.get("n2"))
        n3 = _to_int(raw.get("n3"))
        n4 = _to_int(raw.get("n4"))
        n5 = _to_int(raw.get("n5"))
        n6 = _to_int(raw.get("n6"))
        bonus = _to_int(raw.get("bonus"))

        if game not in ("MM", "PB", "IL"):
            continue

        if game in ("MM", "PB"):
            mains = [n1, n2, n3, n4, n5]
            if any(v is None for v in mains) or bonus is None:
                continue
            mains = [int(v) for v in mains]  # type: ignore[arg-type]
            row = Row(game=game, date_mmddyyyy=date, tier=None, mains=mains, bonus=int(bonus))
            _insert_row(row)
            added += 1

        else:  # IL
            # tier needed (JP/M1/M2). Keep flexible if a file omitted tier for JP newest/second/third.
            if tier not in ("JP", "M1", "M2"):
                # allow blank tier if the sheet actually put JP rows without tier:
                tier = "JP"
            mains_il = [n1, n2, n3, n4, n5, n6]
            if any(v is None for v in mains_il):
                continue
            mains_il = [int(v) for v in mains_il]  # type: ignore[arg-type]
            row = Row(game="IL", date_mmddyyyy=date, tier=tier, mains=mains_il, bonus=None)
            _insert_row(row)
            added += 1

    return {"ok": True, "added": added, "updated": 0, "total": len(_STORE["rows"])}


def import_csv_io(file_like, overwrite: bool = False) -> Dict[str, int | bool]:
    """
    Back-compat wrapper so code that calls `import_csv_io(...)` continues to work.
    Accepts a file-like object or raw bytes/text.
    """
    if hasattr(file_like, "read"):
        raw = file_like.read()
    else:
        raw = file_like
    if isinstance(raw, bytes):
        text = raw.decode("utf-8", errors="replace")
    else:
        text = str(raw)
    return import_csv(text, overwrite=overwrite)


def _insert_row(r: Row) -> None:
    _STORE["rows"].append(r)
    if r.game in ("MM", "PB"):
        _STORE["by_game"][r.game].setdefault(r.date_mmddyyyy, []).append(r)
    else:
        _STORE["by_game"]["IL"].setdefault(r.date_mmddyyyy, {})
        _STORE["by_game"]["IL"][r.date_mmddyyyy][r.tier] = r  # type: ignore[index]


# -----------------------------
# Query helpers used by UI
# -----------------------------

def get_by_date(game: str, date: str, tier: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Fetch one row by date (and tier for IL).
    - game: "MM"|"PB"|"IL"
    - date: MM/DD/YYYY
    - tier: required for IL ("JP"|"M1"|"M2")
    """
    game = _clean_game(game)
    date = _norm_date(date)
    t = _clean_tier(tier)

    if game in ("MM", "PB"):
        rows = _STORE["by_game"][game].get(date, [])
        # If multiple rows exist for same date (shouldn't), return the first
        if rows:
            return _pack_row(rows[0])
        return None

    # IL
    if t not in ("JP", "M1", "M2"):
        # try JP by default to be forgiving
        t = "JP"
    by_tier = _STORE["by_game"]["IL"].get(date, {})
    r = by_tier.get(t)
    return _pack_row(r) if r else None


def get_history(game: str, start_date: str, limit: int = 20, tier: Optional[str] = None) -> Dict[str, Any]:
    """
    Return last `limit` rows from `start_date` (inclusive → older), plus the “blob” text
    your UI displays.

    For MM/PB:  mm-dd-yy  n1-n2-n3-n4-n5  BB
    For IL:     mm-dd-yy  A-B-C-D-E-F
    """
    game = _clean_game(game)
    start = _norm_date(start_date)
    t = _clean_tier(tier)

    def dt_key(s: str) -> datetime:
        return datetime.strptime(s, "%m/%d/%Y")

    rows_out: List[Row] = []

    if game in ("MM", "PB"):
        by_date = _STORE["by_game"][game]
        # dates <= start, newest to oldest
        dates = sorted((d for d in by_date.keys() if dt_key(d) <= dt_key(start)), key=dt_key, reverse=True)
        for d in dates:
            rows_out.extend(by_date[d])
            if len(rows_out) >= limit:
                break
        rows_out = rows_out[:limit]

        blob_lines: List[str] = []
        for r in rows_out:
            mdyy = datetime.strptime(r.date_mmddyyyy, "%m/%d/%Y").strftime("%m-%d-%y")
            blob_lines.append(f"{mdyy}  {r.mains[0]:02d}-{r.mains[1]:02d}-{r.mains[2]:02d}-{r.mains[3]:02d}-{r.mains[4]:02d}  {r.bonus:02d}")
        blob = "\n".join(blob_lines)
        return {"rows": [_pack_row(r) for r in rows_out], "blob": blob}

    # IL
    if t not in ("JP", "M1", "M2"):
        t = "JP"
    by_date_tiers = _STORE["by_game"]["IL"]
    dates = sorted((d for d in by_date_tiers.keys() if dt_key(d) <= dt_key(start)), key=dt_key, reverse=True)

    for d in dates:
        r = by_date_tiers[d].get(t)
        if r:
            rows_out.append(r)
            if len(rows_out) >= limit:
                break

    blob_lines: List[str] = []
    for r in rows_out:
        mdyy = datetime.strptime(r.date_mmddyyyy, "%m/%d/%Y").strftime("%m-%d-%y")
        a, b, c, d, e, f = r.mains
        blob_lines.append(f"{mdyy}  {a:02d}-{b:02d}-{c:02d}-{d:02d}-{e:02d}-{f:02d}")
    blob = "\n".join(blob_lines)
    return {"rows": [_pack_row(r) for r in rows_out], "blob": blob}
