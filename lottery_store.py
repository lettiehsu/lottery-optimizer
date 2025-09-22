from __future__ import annotations

import csv
import io
import json
import os
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

# Where we persist the normalized rows
STORE_PATH = "/tmp/lotto_store.json"

# In-memory cache { (game, date, tier_or_empty): row_dict }
_DB: Dict[Tuple[str, str, str], Dict[str, Any]] = {}


# --------- date helpers ---------
def _norm_date(s: str) -> str:
    """
    Normalize various date shapes to MM/DD/YYYY (zero-padded).
    Accepts: 9/6/2025, 09/06/2025, 2025-09-06, 09-06-2025, 9-6-2025
    Rejects 2-digit years on purpose.
    """
    s = (s or "").strip()
    fmts = ["%m/%d/%Y", "%m-%d-%Y", "%Y-%m-%d"]  # allow 9/6/2025 and 09/06/2025 etc.
    # Try one more tolerant pass for unpadded M/D/YYYY like 9/6/2025
    try:
        if "/" in s:
            parts = s.split("/")
            if len(parts) == 3 and len(parts[2]) == 4:
                m = int(parts[0]); d = int(parts[1]); y = int(parts[2])
                return f"{m:02d}/{d:02d}/{y:04d}"
    except Exception:
        pass

    last = None
    for fmt in fmts:
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime("%m/%d/%Y")
        except Exception as e:
            last = e
    raise ValueError(f"Unrecognized date: {s!r} ({last})")


def _dt_key(date_str: str) -> datetime:
    return datetime.strptime(date_str, "%m/%d/%Y")


# --------- storage helpers ---------
def _load_db() -> None:
    global _DB
    if os.path.exists(STORE_PATH):
        try:
            with open(STORE_PATH, "r", encoding="utf-8") as f:
                raw = json.load(f)
            # rebuild tuple keys
            _DB = {tuple(k.split("|", 2)): v for k, v in raw.items()}
        except Exception:
            _DB = {}
    else:
        _DB = {}


def _save_db() -> None:
    raw = {"|".join(k): v for k, v in _DB.items()}
    with open(STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False)


def _key(game: str, date: str, tier: Optional[str]) -> Tuple[str, str, str]:
    return (game.upper(), date, (tier or "").upper())


# --------- import API (CSV) ---------
EXP_HEADERS = ["game", "draw_date", "tier", "n1", "n2", "n3", "n4", "n5", "n6", "bonus"]


def import_csv_io(file_obj, overwrite: bool = False) -> Dict[str, Any]:
    """Accepts a file-like object (BytesIO/StringIO)."""
    text = file_obj.read()
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="replace")
    return import_csv(text, overwrite=overwrite)


def import_csv(text: str, overwrite: bool = False) -> Dict[str, Any]:
    """
    Main importer used by the Flask endpoint.
    Expects header: game,draw_date,tier,n1,n2,n3,n4,n5,n6,bonus
    """
    _load_db()
    if overwrite:
        _DB.clear()

    added = 0
    updated = 0

    reader = csv.DictReader(io.StringIO(text))
    # Validate header names (order matters)
    found = [h.strip() for h in reader.fieldnames or []]
    if found != EXP_HEADERS:
        raise ValueError(f"Bad CSV header. Expected {EXP_HEADERS} but got {found}")

    for i, row in enumerate(reader, start=2):  # 1-based + header line
        try:
            game = (row["game"] or "").strip().upper()
            if game not in ("MM", "PB", "IL"):
                raise ValueError(f"Row {i}: game must be MM/PB/IL")

            date = _norm_date(row["draw_date"])
            tier = (row["tier"] or "").strip().upper() if game == "IL" else ""

            def _get_int(name: str) -> Optional[int]:
                v = (row.get(name) or "").strip()
                return int(v) if v != "" else None

            n1 = _get_int("n1"); n2 = _get_int("n2"); n3 = _get_int("n3")
            n4 = _get_int("n4"); n5 = _get_int("n5"); n6 = _get_int("n6")
            bonus = _get_int("bonus")

            if game in ("MM", "PB"):
                # MM/PB: n1..n5 + bonus required; n6 should be empty
                if None in (n1, n2, n3, n4, n5) or bonus is None:
                    raise ValueError(f"Row {i}: MM/PB require n1..n5 and bonus")
                row_norm = {
                    "game": game,
                    "date": date,
                    "tier": "",
                    "mains": [n1, n2, n3, n4, n5],
                    "bonus": bonus,
                }
            else:
                # IL: tier ∈ {JP,M1,M2}; n1..n6 required; bonus must be empty
                if tier not in ("JP", "M1", "M2"):
                    raise ValueError(f"Row {i}: IL tier must be JP/M1/M2")
                if None in (n1, n2, n3, n4, n5, n6):
                    raise ValueError(f"Row {i}: IL requires n1..n6")
                row_norm = {
                    "game": game,
                    "date": date,
                    "tier": tier,
                    "mains": [n1, n2, n3, n4, n5, n6],
                    "bonus": None,
                }

            k = _key(game, date, tier)
            if k in _DB:
                _DB[k] = row_norm
                updated += 1
            else:
                _DB[k] = row_norm
                added += 1

        except Exception as e:
            # bubble up with context
            raise ValueError(f"Import error on CSV row {i}: {e}") from e

    _save_db()
    return {"ok": True, "added": added, "updated": updated, "total": len(_DB)}


# --------- query API used by your UI ---------
def get_by_date(game: str, date: str, tier: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Return normalized row dict or None.
    For IL you should pass tier in {JP,M1,M2}; for MM/PB tier is ignored.
    """
    _load_db()
    g = (game or "").upper().strip()
    t = (tier or "").upper().strip() if g == "IL" else ""
    d = _norm_date(date)

    row = _DB.get(_key(g, d, t))
    if not row:
        # For safety, allow legacy calls that used game "IL_JP"/"IL_M1"/"IL_M2"
        if g.startswith("IL_"):
            t2 = g.split("_", 1)[1]
            row = _DB.get(_key("IL", d, t2))
    return row


def get_history(game: str, start_date: str, limit: int = 20) -> Dict[str, Any]:
    """
    Return up to `limit` rows on/older than `start_date`, newest first,
    plus a text blob convenient for your UI.
    """
    _load_db()
    g = (game or "").upper().strip()
    d0 = _norm_date(start_date)

    # Collect all rows for this game (and tier if IL_* passed)
    rows = []
    if g in ("MM", "PB"):
        want = [v for (kg, kd, kt), v in _DB.items() if kg == g]
    else:
        # g may be "IL" (all tiers) or "IL_JP"/"IL_M1"/"IL_M2"
        tier_filter = ""
        if g.startswith("IL_"):
            tier_filter = g.split("_", 1)[1]
            g = "IL"
        want = [v for (kg, kd, kt), v in _DB.items() if kg == g and (not tier_filter or kt == tier_filter)]

    # Sort newest → oldest
    want.sort(key=lambda r: _dt_key(r["date"]), reverse=True)

    # Start at the first row whose date <= start_date
    start_dt = _dt_key(d0)
    for r in want:
        if _dt_key(r["date"]) <= start_dt:
            rows.append(r)
        if len(rows) >= limit:
            break

    # Build a simple blob
    lines: List[str] = []
    for r in rows:
        ds = datetime.strptime(r["date"], "%m/%d/%Y").strftime("%m-%d-%y")
        if r["game"] in ("MM", "PB"):
            a, b, c, d, e = r["mains"]
            bb = r["bonus"]
            lines.append(f"{ds}  {a:02d}-{b:02d}-{c:02d}-{d:02d}-{e:02d}  {bb:02d}")
        else:
            a, b, c, d, e, f = r["mains"]
            lines.append(f"{ds}  {a:02d}-{b:02d}-{c:02d}-{d:02d}-{e:02d}-{f:02d}")

    return {"rows": rows, "blob": "\n".join(lines)}
