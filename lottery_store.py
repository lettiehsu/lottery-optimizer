from __future__ import annotations

import csv
import io
import json
import os
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional

STORE_PATH = "/tmp/lotto_store.json"
_DB: Dict[Tuple[str, str, str], Dict[str, Any]] = {}

# ---------- dates ----------
def _norm_date(s: str) -> str:
    s = (s or "").strip()
    fmts = [
        "%m/%d/%Y", "%m/%d/%y",
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
                raw = json.load(f)
            _DB = {tuple(k.split(",")): v for k, v in raw.items()}
        except Exception:
            _DB = {}
    else:
        _DB = {}

def _save():
    data = {",".join(k): v for k, v in _DB.items()}
    with open(STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

# ---------- CSV import ----------
def import_csv(text: str, overwrite: bool = False) -> Dict[str, int]:
    _load()
    buf = io.StringIO(text)
    reader = csv.DictReader(buf)
    added = updated = 0
    for row in reader:
        game = (row.get("game") or "").strip()      # "MM","PB","IL"
        draw_date = _norm_date(row.get("draw_date") or "")
        tier = (row.get("tier") or "").strip()      # "", "JP","M1","M2"
        mains = []
        for k in ("n1","n2","n3","n4","n5","n6"):
            v = row.get(k)
            if v is None or v == "" or v == "null":
                continue
            mains.append(int(v))
        braw = row.get("bonus")
        bonus = None if (braw is None or braw == "" or braw == "null") else int(braw)

        key = (game, draw_date, tier)
        payload = {"game": game, "date": draw_date, "tier": tier, "mains": mains, "bonus": bonus}
        if key in _DB:
            if overwrite:
                _DB[key] = payload
                updated += 1
        else:
            _DB[key] = payload
            added += 1
    _save()
    return {"added": added, "updated": updated, "total": added + updated}

# ---------- lookups ----------
def list_keys() -> List[Tuple[str, str, str]]:
    _load()
    return sorted(_DB.keys(), key=lambda k: (k[0], k[2], datetime.strptime(k[1], "%m/%d/%Y")), reverse=True)

def dates_for(game: str, tier: str = "") -> List[str]:
    _load()
    ds = {dd for (g, dd, t) in _DB.keys() if g == game and (t or "") == (tier or "")}
    return sorted(ds, key=lambda s: datetime.strptime(s, "%m/%d/%Y"), reverse=True)

def nearest_dates(game: str, target: str, tier: str = "", n: int = 3) -> List[str]:
    ds = dates_for(game, tier)
    if not ds:
        return []
    target_dt = datetime.strptime(target, "%m/%d/%Y")
    return sorted(ds, key=lambda s: abs((datetime.strptime(s, "%m/%d/%Y") - target_dt).days))[:n]

def get_by_date(game: str, date: str, tier: str = "") -> Optional[List[Any]]:
    _load()
    key = (game.strip(), _norm_date(date), tier.strip())
    rec = _DB.get(key)
    if not rec:
        return None
    return [rec["mains"], rec["bonus"]]

def get_history(game: str, since_date: str, tier: str = "", limit: int = 20) -> List[str]:
    _load()
    g, t = game.strip(), tier.strip()
    since = _norm_date(since_date)
    rows = [r for (gg, dd, tt), r in _DB.items() if gg == g and (tt or "") == (t or "")]
    rows.sort(key=lambda r: datetime.strptime(r["date"], "%m/%d/%Y"), reverse=True)
    # start at matching since
    start = 0
    for i, r in enumerate(rows):
        if r["date"] == since:
            start = i
            break
    rows = rows[start:start+int(limit)]
    out = []
    for rec in rows:
        mains = "-".join(f"{n:02d}" for n in rec["mains"])
        if g in ("MM","PB"):
            out.append(f"{rec['date'][6:]}-{rec['date'][:2]}-{rec['date'][3:5]}  {mains}  {(rec['bonus'] or 0):02d}")
        else:
            out.append(f"{rec['date'][6:]}-{rec['date'][:2]}-{rec['date'][3:5]}  {mains}")
    return out
