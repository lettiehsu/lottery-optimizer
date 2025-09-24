from __future__ import annotations

import csv
import io
import json
import os
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional

# Persisted JSON store
STORE_PATH = "/tmp/lotto_store.json"

# In-memory DB: key = (game, date, tier) ; tier "" for MM/PB, "JP"/"M1"/"M2" for IL
_DB: Dict[Tuple[str, str, str], Dict[str, Any]] = {}


# ---------- date helpers ----------
def _norm_date(s: str) -> str:
    """Normalize many date shapes to MM/DD/YYYY; raises ValueError if bad."""
    s = (s or "").strip()
    # Support 2-digit year too:
    fmts = [
        "%m/%d/%Y", "%m/%d/%y",
        "%-m/%-d/%Y", "%-m/%-d/%y",   # on Linux
        "%Y-%m-%d", "%m-%d-%Y", "%m-%d-%y",
    ]
    last = None
    for fmt in fmts:
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime("%m/%d/%Y")
        except Exception as e:
            last = e
    raise ValueError(f"Unrecognized date: {s!r} ({last})")


def _load():
    global _DB
    if os.path.exists(STORE_PATH):
        try:
            with open(STORE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            _DB = {tuple(k): v for k, v in data.items()}
        except Exception:
            _DB = {}
    else:
        _DB = {}


def _save():
    data = {",".join(k): v for k, v in _DB.items()}
    with open(STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


# ---------- CSV import ----------
def import_csv_io(buf: io.TextIOBase, overwrite: bool = False) -> Dict[str, int]:
    """
    CSV headers: game,draw_date,tier,n1,n2,n3,n4,n5,bonus
    - game: MM | PB | IL
    - tier: "" for MM/PB ; "JP"/"M1"/"M2" for IL (blank allowed)
    """
    _load()
    reader = csv.DictReader(buf)
    added = updated = 0
    for row in reader:
        game = (row.get("game") or "").strip()
        draw_date = _norm_date(row.get("draw_date") or "")
        tier = (row.get("tier") or "").strip()
        # ints
        ns = []
        for k in ("n1", "n2", "n3", "n4", "n5"):
            v = row.get(k)
            ns.append(int(v) if v not in (None, "", "null") else None)
        bonus_raw = row.get("bonus")
        bonus = None if (bonus_raw is None or bonus_raw == "" or bonus_raw == "null") else int(bonus_raw)

        key = (game, draw_date, tier)
        payload = {"game": game, "date": draw_date, "tier": tier, "mains": ns, "bonus": bonus}

        if key in _DB:
            if overwrite:
                _DB[key] = payload
                updated += 1
        else:
            _DB[key] = payload
            added += 1

    _save()
    return {"added": added, "updated": updated, "total": added + updated}


# Backward compatibility alias if your app called this:
def import_csv(text_or_io, overwrite: bool = False) -> Dict[str, int]:
    if isinstance(text_or_io, str):
        return import_csv_io(io.StringIO(text_or_io), overwrite=overwrite)
    return import_csv_io(text_or_io, overwrite=overwrite)


# ---------- public getters ----------
def get_by_date(game: str, date: str, tier: str = "") -> Optional[List[Any]]:
    _load()
    key = (game.strip(), _norm_date(date), (tier or "").strip())
    rec = _DB.get(key)
    if not rec:
        return None
    # Return [[mains], bonus] (bonus can be None for IL)
    return [rec["mains"], rec["bonus"]]


def get_history(game: str, since_date: str, tier: str = "", limit: int = 20) -> List[str]:
    """
    Returns formatted history strings newest→older starting from since_date.
    For IL, pass tier in {"JP","M1","M2"}.
    """
    _load()
    g = game.strip()
    t = (tier or "").strip()
    since = _norm_date(since_date)

    # Filter all keys for that (game,tier), then sort desc by date
    rows = []
    for (gg, dd, tt), rec in _DB.items():
        if gg == g and (tt or "") == t:
            rows.append(rec)
    rows.sort(key=lambda r: datetime.strptime(r["date"], "%m/%d/%Y"), reverse=True)

    # find index where date matches 'since'; then slice next 'limit'
    start = 0
    for i, r in enumerate(rows):
        if r["date"] == since:
            start = i
            break

    out = []
    for rec in rows[start:start + limit]:
        mains = "-".join(f"{n:02d}" for n in rec["mains"] if n is not None)
        if g in ("MM", "PB"):
            out.append(f"{rec['date'][6:]}-{rec['date'][:2]}-{rec['date'][3:5]}  {mains}  {rec['bonus']:02d}")
        else:
            # IL: no bonus in display
            out.append(f"{rec['date'][6:]}-{rec['date'][:2]}-{rec['date'][3:5]}  {mains}")
    return out
