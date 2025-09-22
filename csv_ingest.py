# -*- coding: utf-8 -*-
"""
CSV import & lookup utilities.

Expected columns (case-insensitive, order flexible):
  game, draw_date, tier, n1, n2, n3, n4, n5, n6, bonus

- game: MM | PB | IL
- tier: JP | M1 | M2  (IL only; ignored for MM/PB)
- draw_date: MM/DD/YYYY (common variants auto-normalized)

We persist the latest upload to DATA_DIR/master_history.json.
"""

import os
import io
import csv
from datetime import datetime
from typing import Dict, List, Optional
import json

DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data"))
os.makedirs(DATA_DIR, exist_ok=True)
STORE_PATH = os.path.join(DATA_DIR, "master_history.json")

def _norm_date(s: str) -> str:
    s = (s or "").strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y", "%m/%d/%y"):
        try:
            d = datetime.strptime(s, fmt)
            return d.strftime("%m/%d/%Y")
        except Exception:
            pass
    try:
        from dateutil import parser
        return parser.parse(s).strftime("%m/%d/%Y")
    except Exception:
        raise ValueError(f"Unrecognized date: {s}")

def _to_int_or_none(v):
    try:
        return int(v)
    except Exception:
        return None

def csv_import_from_stream(stream, filename: str) -> Dict:
    content = stream.read()
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")
    f = io.StringIO(content)
    reader = csv.DictReader(f)
    cols = {c.lower(): c for c in (reader.fieldnames or [])}

    required = {"game", "draw_date", "tier", "n1", "n2", "n3", "n4", "n5"}
    if not required.issubset(set(cols.keys())):
        raise ValueError(f"CSV must include columns: {sorted(required)}")

    rows: List[Dict] = []
    for r in reader:
        game = (r.get(cols.get("game",""), "") or "").strip().upper()
        if game not in {"MM","PB","IL"}: continue

        date_s = _norm_date(r.get(cols.get("draw_date",""), ""))
        tier = (r.get(cols.get("tier",""), "") or "").strip().upper()
        if game in {"MM","PB"}: tier = "JP"
        elif game == "IL" and tier not in {"JP","M1","M2"}: continue

        mains = [
            _to_int_or_none(r.get(cols.get("n1",""), "")),
            _to_int_or_none(r.get(cols.get("n2",""), "")),
            _to_int_or_none(r.get(cols.get("n3",""), "")),
            _to_int_or_none(r.get(cols.get("n4",""), "")),
            _to_int_or_none(r.get(cols.get("n5",""), "")),
        ]
        n6 = _to_int_or_none(r.get(cols.get("n6",""), "")) if "n6" in cols else None
        if game == "IL" and n6 is not None:
            mains.append(n6)

        bonus = _to_int_or_none(r.get(cols.get("bonus",""), "")) if "bonus" in cols else None

        if game in {"MM","PB"} and len([x for x in mains if x is not None]) != 5: continue
        if game == "IL" and len([x for x in mains if x is not None]) != 6: continue

        rows.append({
            "game": game,
            "tier": tier,
            "date": date_s,
            "mains": [int(x) for x in mains if x is not None],
            "bonus": (int(bonus) if bonus is not None else None),
        })

    with open(STORE_PATH, "w", encoding="utf-8") as f2:
        json.dump({"filename": filename, "rows": rows}, f2, ensure_ascii=False)

    by_game = {"MM":0,"PB":0,"IL":0}
    for r in rows: by_game[r["game"]] += 1
    return {"filename": filename, "count": len(rows), "by_game": by_game, "path": STORE_PATH}

def _load_store() -> Dict:
    if not os.path.exists(STORE_PATH):
        raise FileNotFoundError("No CSV has been imported yet.")
    with open(STORE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def csv_list_meta() -> Dict:
    try:
        data = _load_store()
    except FileNotFoundError:
        return {"present": False}
    rows = data.get("rows", [])
    by_game = {"MM":0,"PB":0,"IL":0}
    for r in rows: by_game[r["game"]] += 1
    return {"present": True, "filename": data.get("filename"), "count": len(rows), "by_game": by_game}

def _filter_rows(game: str, tier: str) -> List[Dict]:
    data = _load_store()
    rows = [r for r in data.get("rows", []) if r["game"] == game]
    if game == "IL":
        rows = [r for r in rows if r["tier"] == tier]
    return rows

def csv_latest_for_game(game: str, asof_date: str, offset: int, tier: str = "JP") -> Dict:
    rows = _filter_rows(game, tier)
    if not rows:
        raise ValueError(f"No rows for game={game} tier={tier}")
    asof = datetime.strptime(asof_date, "%m/%d/%Y")
    rows = [r for r in rows if datetime.strptime(r["date"], "%m/%d/%Y") <= asof]
    if not rows:
        raise ValueError("No rows before/at given date")
    rows.sort(key=lambda r: datetime.strptime(r["date"], "%m/%d/%Y"), reverse=True)
    if offset <= 0 or offset > len(rows):
        raise ValueError(f"Offset {offset} out of range (1..{len(rows)})")
    pick = rows[offset-1]
    return {"mains": pick["mains"], "bonus": pick["bonus"], "date": pick["date"]}

def csv_history20_for_game(game: str, asof_date: str, tier: str = "JP") -> str:
    rows = _filter_rows(game, tier)
    if not rows:
        raise ValueError(f"No rows for game={game} tier={tier}")
    asof = datetime.strptime(asof_date, "%m/%d/%Y")
    rows = [r for r in rows if datetime.strptime(r["date"], "%m/%d/%Y") <= asof]
    rows.sort(key=lambda r: datetime.strptime(r["date"], "%m/%d/%Y"))
    rows = rows[-20:]
    lines = []
    if game in {"MM","PB"}:
        for r in rows:
            line = "-".join(f"{n:02d}" for n in r["mains"])
            if r["bonus"] is not None:
                line += f" {r['bonus']:02d}"
            lines.append(line)
    else:
        for r in rows:
            lines.append("-".join(f"{n:02d}" for n in r["mains"]))
    return "\n".join(lines) + "\n"
