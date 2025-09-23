from __future__ import annotations
import csv, io, json, os
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

# Persisted store
STORE_PATH = "/tmp/lotto_store.json"

# In-memory DB: key = (game, date, tier) -> dict row
_DB: Dict[Tuple[str, str, str], Dict[str, Any]] = {}

# ---------- Date helpers ----------
def _norm_date(s: str) -> str:
    """
    Normalize many date shapes to MM/DD/YYYY.
    """
    s = (s or "").strip()
    s = s.replace("-", "/")
    # Accept 2-digit year too
    fmts = ["%m/%d/%Y", "%m/%d/%y", "%-m/%-d/%Y", "%-m/%-d/%y"]
    last_err = None
    for fmt in fmts:
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime("%m/%d/%Y")
        except Exception as e:
            last_err = e
    raise ValueError(f"Unrecognized date: {s!r} ({last_err})")

def _load():
    _DB.clear()
    if os.path.exists(STORE_PATH):
        with open(STORE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        for k, row in data.items():
            g, d, t = k.split("|")
            _DB[(g, d, t)] = row

def _save():
    data = {}
    for (g, d, t), row in _DB.items():
        data[f"{g}|{d}|{t}"] = row
    with open(STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

# ---------- Public API ----------
def import_csv(csv_text: str, overwrite: bool=False) -> dict:
    """
    Columns: game,draw_date,tier,n1,n2,n3,n4,n5,n6,bonus
    game: MM|PB|IL
    tier: "" or "JP"/"M1"/"M2" (IL only)
    """
    _load()
    added = updated = 0
    rdr = csv.DictReader(io.StringIO(csv_text))
    for r in rdr:
        game = (r.get("game") or "").strip().upper()
        if game not in ("MM", "PB", "IL"):
            continue
        date = _norm_date(r.get("draw_date") or "")
        tier = (r.get("tier") or "").strip().upper()
        if game != "IL":
            tier = ""  # only IL uses tier

        def as_int(x: Optional[str]) -> Optional[int]:
            x = (x or "").strip()
            return int(x) if x.isdigit() else None

        n1 = as_int(r.get("n1")); n2 = as_int(r.get("n2")); n3 = as_int(r.get("n3"))
        n4 = as_int(r.get("n4")); n5 = as_int(r.get("n5")); n6 = as_int(r.get("n6"))
        bonus = as_int(r.get("bonus"))

        row = {
            "game": game,
            "date": date,
            "tier": tier,  # "", "JP", "M1", "M2"
            "mains": [n for n in [n1,n2,n3,n4,n5,n6] if n is not None],
            "bonus": bonus
        }
        key = (game, date, tier)
        if key in _DB:
            if overwrite:
                _DB[key] = row
                updated += 1
        else:
            _DB[key] = row
            added += 1

    _save()
    return {"added": added, "updated": updated, "total": len(_DB)}

def get_by_date(game: str, date: str) -> Optional[dict]:
    _load()
    g = (game or "").upper()
    d = _norm_date(date)
    if g in ("MM", "PB"):
        return _DB.get((g, d, ""))
    # IL: JP / M1 / M2
    # Caller should request each explicitly; here we just return JP by default.
    return _DB.get(("IL", d, "JP"))

def get_exact(game: str, date: str, tier: str) -> Optional[dict]:
    _load()
    g = (game or "").upper()
    d = _norm_date(date)
    t = (tier or "").upper()
    return _DB.get((g, d, t))

def get_history(game: str, start_date: str, limit: int=20, tier: str="") -> dict:
    """
    Return up to `limit` rows starting from `start_date` (inclusive) going backwards.
    Also provide a formatted blob for UI.
    """
    _load()
    g = (game or "").upper()
    t = (tier or "").upper()
    start = _norm_date(start_date)

    # collect all keys for this (game, tier)
    rows = [row for (gg, dd, tt), row in _DB.items() if gg == g and tt == (t if g=="IL" else "")]
    # sort by date desc
    def _key(r): return datetime.strptime(r["date"], "%m/%d/%Y")
    rows.sort(key=_key, reverse=True)

    # take from the start date (inclusive), then the next (limit-1)
    out: List[dict] = []
    seen_start = False
    for r in rows:
        if not seen_start:
            if r["date"] == start:
                seen_start = True
                out.append(r)
        else:
            out.append(r)
        if len(out) >= limit:
            break

    # blob formatting
    if g in ("MM","PB"):
        blob_lines = [f'{datetime.strptime(r["date"], "%m/%d/%Y").strftime("%m-%d-%y")}  '
                      f'{"-".join(f"{n:02d}" for n in r["mains"])}  {r["bonus"]:02d if r["bonus"] is not None else ""}'
                      for r in out]
    else:
        blob_lines = [f'{datetime.strptime(r["date"], "%m/%d/%Y").strftime("%m-%d-%y")}  '
                      f'{"-".join(f"{n:02d}" for n in r["mains"])}'
                      for r in out]

    return {"rows": out, "blob": "\n".join(blob_lines)}
