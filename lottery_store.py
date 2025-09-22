# lottery_store.py
# ----------------------------------------------------------------------
# In-memory store for lottery history with robust date normalization.
# Works with app.py endpoints: /store/import_csv, /store/get_by_date,
# /store/get_history, and any UI calling these routes.
#
# CSV schema (combined master):
#   game,draw_date,tier,n1,n2,n3,n4,n5,n6,bonus
# - game: MM | PB | IL
# - draw_date: M/D/YYYY or MM/DD/YYYY (both accepted)
# - tier: (blank) for MM/PB, JP|M1|M2 for IL
# - bonus: number for MM/PB, blank/null for IL
# ----------------------------------------------------------------------

from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional

# Internal store:
# MM_DATA[date] = {"mains":[n1..n5], "bonus": int}
# PB_DATA[date] = {"mains":[n1..n5], "bonus": int}
# IL_DATA[tier][date] = {"mains":[n1..n6], "bonus": None}
MM_DATA: Dict[str, Dict[str, Any]] = {}
PB_DATA: Dict[str, Dict[str, Any]] = {}
IL_DATA: Dict[str, Dict[str, Dict[str, Any]]] = {"JP": {}, "M1": {}, "M2": {}}

# ---------------------------- helpers ----------------------------

def _parse_int(x: Any) -> Optional[int]:
    try:
        if x is None:
            return None
        s = str(x).strip()
        if s == "" or s.lower() == "null":
            return None
        return int(s)
    except Exception:
        return None

def _norm_date(s: str) -> str:
    """
    Normalize any 'M/D/YYYY' or 'MM/DD/YYYY' string to unpadded 'M/D/YYYY'.
    This guarantees that 09/16/2025 == 9/16/2025 in lookups.
    """
    s = (s or "").strip()
    # Be tolerant of 0-padded and non-padded forms
    # Split manually to avoid %-m on Windows
    items = s.replace("-", "/").split("/")
    if len(items) != 3:
        # Try standard parsing as a fallback
        dt = datetime.strptime(s, "%m/%d/%Y")
        return f"{dt.month}/{dt.day}/{dt.year}"
    m = int(items[0])
    d = int(items[1])
    y = int(items[2])
    return f"{m}/{d}/{y}"

def _fmt_mm_blob(date_str: str, row: Dict[str, Any]) -> str:
    # "mm-dd-yy — n1-n2-n3-n4-n5 MB"
    dt = datetime.strptime(_norm_date(date_str), "%m/%d/%Y")
    mm = dt.strftime("%m-%d-%y")
    mains = row["mains"]
    bonus = row.get("bonus")
    return f"{mm} — {mains[0]:02d}-{mains[1]:02d}-{mains[2]:02d}-{mains[3]:02d}-{mains[4]:02d} {bonus:02d}"

def _fmt_pb_blob(date_str: str, row: Dict[str, Any]) -> str:
    # "mm-dd-yy — n1-n2-n3-n4-n5 PB"
    dt = datetime.strptime(_norm_date(date_str), "%m/%d/%Y")
    mm = dt.strftime("%m-%d-%y")
    mains = row["mains"]
    bonus = row.get("bonus")
    return f"{mm} — {mains[0]:02d}-{mains[1]:02d}-{mains[2]:02d}-{mains[3]:02d}-{mains[4]:02d} {bonus:02d}"

def _fmt_il_blob(date_str: str, row: Dict[str, Any]) -> str:
    # "mm-dd-yy — A-B-C-D-E-F"
    dt = datetime.strptime(_norm_date(date_str), "%m/%d/%Y")
    mm = dt.strftime("%m-%d-%y")
    mains = row["mains"]  # 6 numbers
    return f"{mm} — {mains[0]:02d}-{mains[1]:02d}-{mains[2]:02d}-{mains[3]:02d}-{mains[4]:02d}-{mains[5]:02d}"

def _sort_dates_desc(dates: List[str]) -> List[str]:
    return sorted(dates, key=lambda s: datetime.strptime(_norm_date(s), "%m/%d/%Y"), reverse=True)

# --------------------------- core API ----------------------------

def import_csv(text: str, overwrite: bool = False) -> Dict[str, Any]:
    """
    Import the entire master CSV content into memory.
      - overwrite=True replaces all existing data
      - overwrite=False appends/updates existing keys
    Returns stats: {"ok": True, "added": X, "updated": Y, "total": N}
    """
    if overwrite:
        MM_DATA.clear()
        PB_DATA.clear()
        for t in IL_DATA:
            IL_DATA[t].clear()

    added = 0
    updated = 0

    f = io.StringIO(text)
    reader = csv.DictReader(f)
    # Normalize header names (robust in case of casing)
    fieldmap = { (k or "").strip().lower(): k for k in reader.fieldnames or [] }

    def g(name: str) -> str:
        return fieldmap.get(name.lower(), name)

    for row in reader:
        game = (row.get(g("game")) or "").strip().upper()
        raw_date = row.get(g("draw_date")) or ""
        tier = (row.get(g("tier")) or "").strip().upper()
        n1 = _parse_int(row.get(g("n1")))
        n2 = _parse_int(row.get(g("n2")))
        n3 = _parse_int(row.get(g("n3")))
        n4 = _parse_int(row.get(g("n4")))
        n5 = _parse_int(row.get(g("n5")))
        n6 = _parse_int(row.get(g("n6")))
        bonus = _parse_int(row.get(g("bonus")))

        if not game or not raw_date:
            continue

        date = _norm_date(raw_date)

        if game == "MM":
            # Need 5 mains + bonus
            if None in (n1, n2, n3, n4, n5) or bonus is None:
                continue
            payload = {"mains": [n1, n2, n3, n4, n5], "bonus": bonus}
            if date in MM_DATA:
                MM_DATA[date] = payload
                updated += 1
            else:
                MM_DATA[date] = payload
                added += 1

        elif game == "PB":
            if None in (n1, n2, n3, n4, n5) or bonus is None:
                continue
            payload = {"mains": [n1, n2, n3, n4, n5], "bonus": bonus}
            if date in PB_DATA:
                PB_DATA[date] = payload
                updated += 1
            else:
                PB_DATA[date] = payload
                added += 1

        elif game == "IL":
            # IL Lotto: tier must be JP, M1, or M2; 6 mains, no bonus
            if tier not in ("JP", "M1", "M2"):
                # skip unknown tiers
                continue
            if None in (n1, n2, n3, n4, n5, n6):
                continue
            payload = {"mains": [n1, n2, n3, n4, n5, n6], "bonus": None}
            if date in IL_DATA[tier]:
                IL_DATA[tier][date] = payload
                updated += 1
            else:
                IL_DATA[tier][date] = payload
                added += 1

        else:
            # Unknown game
            continue

    total = len(MM_DATA) + len(PB_DATA) + sum(len(IL_DATA[t]) for t in IL_DATA)
    return {"ok": True, "added": added, "updated": updated, "total": total}

def get_by_date(game: str, date: str, tier: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Return a single row dict for a given game/date (and tier for IL).
    None if not found.
    """
    g = (game or "").strip().upper()
    d = _norm_date(date)

    if g == "MM":
        return MM_DATA.get(d)
    if g == "PB":
        return PB_DATA.get(d)
    if g == "IL":
        t = (tier or "").strip().upper()
        if t in IL_DATA:
            return IL_DATA[t].get(d)
        return None
    return None

def list_dates(game: str, limit: int = 40, tier: Optional[str] = None) -> List[str]:
    """ List newest->older dates for a game (and IL tier). """
    g = (game or "").strip().upper()

    if g == "MM":
        dates = _sort_dates_desc(list(MM_DATA.keys()))
    elif g == "PB":
        dates = _sort_dates_desc(list(PB_DATA.keys()))
    elif g == "IL":
        t = (tier or "").strip().upper()
        if t not in IL_DATA:
            return []
        dates = _sort_dates_desc(list(IL_DATA[t].keys()))
    else:
        return []

    return dates[:max(0, int(limit))]

def get_history(game: str, start_date: str, limit: int = 20, tier: Optional[str] = None) -> Dict[str, Any]:
    """
    From the given start_date (included), return up to 'limit' rows in
    newest->older order, and a 'blob' text formatted for the UI.
    """
    g = (game or "").strip().upper()
    d0 = _norm_date(start_date)
    lim = max(1, int(limit))

    if g == "MM":
        dates = _sort_dates_desc(list(MM_DATA.keys()))
        # start at the exact date
        try:
            idx = dates.index(d0)
        except ValueError:
            # if date not present, find the first date <= requested date
            dt0 = datetime.strptime(d0, "%m/%d/%Y")
            idx = next((i for i, ds in enumerate(dates)
                        if datetime.strptime(ds, "%m/%d/%Y") <= dt0), 0)

        picked = dates[idx: idx + lim]
        rows = [{"date": ds, **MM_DATA[ds]} for ds in picked]
        blob_lines = [_fmt_mm_blob(ds, MM_DATA[ds]) for ds in picked]
        return {"rows": rows, "blob": "\n".join(blob_lines)}

    if g == "PB":
        dates = _sort_dates_desc(list(PB_DATA.keys()))
        try:
            idx = dates.index(d0)
        except ValueError:
            dt0 = datetime.strptime(d0, "%m/%d/%Y")
            idx = next((i for i, ds in enumerate(dates)
                        if datetime.strptime(ds, "%m/%d/%Y") <= dt0), 0)

        picked = dates[idx: idx + lim]
        rows = [{"date": ds, **PB_DATA[ds]} for ds in picked]
        blob_lines = [_fmt_pb_blob(ds, PB_DATA[ds]) for ds in picked]
        return {"rows": rows, "blob": "\n".join(blob_lines)}

    if g == "IL":
        t = (tier or "").strip().upper()
        if t not in IL_DATA:
            return {"rows": [], "blob": ""}

        dates = _sort_dates_desc(list(IL_DATA[t].keys()))
        try:
            idx = dates.index(d0)
        except ValueError:
            dt0 = datetime.strptime(d0, "%m/%d/%Y")
            idx = next((i for i, ds in enumerate(dates)
                        if datetime.strptime(ds, "%m/%d/%Y") <= dt0), 0)

        picked = dates[idx: idx + lim]
        rows = [{"date": ds, **IL_DATA[t][ds]} for ds in picked]
        blob_lines = [_fmt_il_blob(ds, IL_DATA[t][ds]) for ds in picked]
        return {"rows": rows, "blob": "\n".join(blob_lines)}

    return {"rows": [], "blob": ""}

# Optional: a simple “ping” for debugging (importers/tests can call)
def _debug_counts() -> Dict[str, int]:
    return {
        "MM": len(MM_DATA),
        "PB": len(PB_DATA),
        "IL_JP": len(IL_DATA["JP"]),
        "IL_M1": len(IL_DATA["M1"]),
        "IL_M2": len(IL_DATA["M2"]),
    }
