from __future__ import annotations

import csv, io, json, os
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

STORE_PATH = "/tmp/lotto_store.json"
_DB: Dict[Tuple[str,str,str], Dict[str,Any]] = {}  # key: (game, date_mmddyyyy, tier_or_empty)

# ---------- date helpers ----------
def _norm_date(s: str) -> str:
    """
    Normalize many date shapes to MM/DD/YYYY.
    Accepts: 9/6/2025, 09/06/2025, 2025-09-06, 09-06-2025, 09/06/25, 9/6/25
    """
    s = (s or "").strip()
    if not s:
        raise ValueError("empty date")
    # try flexible parsing
    for fmts in [
        ["%m/%d/%Y","%-m/%-d/%Y"],            # 09/06/2025 or 9/6/2025 (on linux)
        ["%m/%d/%y","%-m/%-d/%y"],            # 09/06/25      or 9/6/25
        ["%Y-%m-%d"],                          # 2025-09-06
        ["%m-%d-%Y","%-m-%-d-%Y"],             # 09-06-2025 or 9-6-2025
    ]:
        for fmt in fmts:
            try:
                dt = datetime.strptime(s, fmt)
                return dt.strftime("%m/%d/%Y")
            except Exception:
                pass
    # last-ditch: if already like mm/dd/yyyy but with leading zeros irregular
    parts = s.replace("-", "/").split("/")
    if len(parts) == 3 and all(p.isdigit() for p in parts):
        m, d, y = parts
        if len(y) == 2:
            y = ("20" if int(y) < 70 else "19") + y
        return f"{int(m):02d}/{int(d):02d}/{int(y):04d}"
    raise ValueError(f"Unrecognized date: {s!r}")

def _load():
    global _DB
    if os.path.exists(STORE_PATH):
        try:
            data = json.load(open(STORE_PATH, "r"))
            _DB = {tuple(k.split("|",2)): v for k, v in data.items()}
        except Exception:
            _DB = {}
    else:
        _DB = {}

def _save():
    data = {"|".join(k): v for k, v in _DB.items()}
    with open(STORE_PATH, "w") as f:
        json.dump(data, f)

_load()

# ---------- CRUD ----------
def import_csv(text: str, overwrite: bool = False) -> Dict[str,int]:
    """
    CSV headers: game,draw_date,tier,n1,n2,n3,n4,n5,n6,bonus
    """
    reader = csv.DictReader(io.StringIO(text))
    added = updated = 0
    for row in reader:
        game = (row.get("game") or "").strip().upper()
        tier = (row.get("tier") or "").strip().upper()
        if game not in ("MM","PB","IL"):
            continue
        date = _norm_date(row.get("draw_date") or row.get("date") or "")
        mains = []
        for k in ("n1","n2","n3","n4","n5","n6"):
            v = row.get(k)
            if v is None or v == "":
                continue
            mains.append(int(v))
        mains = [int(x) for x in mains]
        bonus_raw = row.get("bonus")
        bonus = None if game=="IL" else (int(bonus_raw) if (bonus_raw not in (None,"")) else None)

        key = (game, date, tier if game=="IL" else "")
        exists = key in _DB
        if not exists or overwrite:
            _DB[key] = {"game": game, "date": date, "tier": tier if game=="IL" else "",
                        "mains": mains, "bonus": bonus}
            added += (0 if exists else 1)
            updated += (1 if exists else 0)
    _save()
    return {"total": len(_DB), "added": added, "updated": updated}

def _row_to_latest_string(row: Dict[str,Any]) -> List[Any]:
    # API shape back to client: [[mains...], bonus] (bonus=null for IL)
    return [[int(x) for x in row["mains"]], (None if row["game"]=="IL" else int(row["bonus"]))]

def get_by_date(game: str, date: str, tier: Optional[str] = None) -> List[Any]:
    date = _norm_date(date)
    key = (game, date, (tier or "").upper() if game=="IL" else "")
    row = _DB.get(key)
    if not row:
        raise KeyError("not_found")
    return _row_to_latest_string(row)

def get_history(game: str, start_date: str, limit: int = 20, tier: Optional[str]=None) -> Dict[str,Any]:
    start = _norm_date(start_date)
    # gather all for game (+tier for IL), sort desc by date, find the index for start and take 'limit' from there
    rows = [v for (g,d,t),v in _DB.items() if g==game and (t==(tier or "") if g=="IL" else True)]
    rows.sort(key=lambda r: datetime.strptime(r["date"], "%m/%d/%Y"), reverse=True)
    # find index of start
    idx = 0
    for i, r in enumerate(rows):
        if r["date"] == start:
            idx = i
            break
    take = rows[idx: idx+limit]
    out_rows = []
    for r in take:
        out_rows.append({
            "date": r["date"],
            "mains": r["mains"],
            "bonus": (None if r["game"]=="IL" else r["bonus"])
        })
    # also return a printable blob (client fills)
    return {"rows": out_rows, "blob": ""}

