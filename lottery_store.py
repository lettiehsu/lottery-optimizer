from __future__ import annotations
import csv, io, json, os
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

STORE_PATH = "/tmp/lotto_store.json"
_DB: Dict[Tuple[str, str, str], Dict[str, Any]] = {}  # (game, date, tier)

# ---------- Date helpers ----------
def _norm_date(s: str) -> str:
    """
    Normalize to MM/DD/YYYY. Accepts:
      - MM/DD/YYYY
      - MM/DD/YY
      - YYYY-MM-DD
      - M/D/YYYY / M/D/YY
    """
    s = (s or "").strip()
    # First handle YYYY-MM-DD from <input type="date">
    try:
        if len(s) == 10 and s[4] == "-" and s[7] == "-":
            dt = datetime.strptime(s, "%Y-%m-%d")
            return dt.strftime("%m/%d/%Y")
    except Exception:
        pass

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
    data = {f"{g}|{d}|{t}": row for (g, d, t), row in _DB.items()}
    with open(STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

# ---------- Public API ----------
def import_csv(csv_text: str, overwrite: bool=False) -> dict:
    """
    CSV columns: game,draw_date,tier,n1,n2,n3,n4,n5,n6,bonus
    game: MM|PB|IL
    tier: "" or "JP"/"M1"/"M2" (IL only)
    """
    _load()
    added = updated = 0
    rdr = csv.DictReader(io.StringIO(csv_text))
    for r in rdr:
        game = (r.get("game") or "").strip().upper()
        if game not in ("MM", "PB", "IL"):  # ignore unknown
            continue
        date = _norm_date(r.get("draw_date") or "")
        tier = (r.get("tier") or "").strip().upper()
        if game != "IL":
            tier = ""  # only IL uses JP/M1/M2

        def as_int(x: Optional[str]) -> Optional[int]:
            x = (x or "").strip()
            return int(x) if x.isdigit() else None

        mains = [as_int(r.get(f"n{i}")) for i in range(1, 7)]
        mains = [n for n in mains if n is not None]
        bonus = as_int(r.get("bonus"))

        row = {
            "game": game,
            "date": date,
            "tier": tier,  # "", JP, M1, M2
            "mains": mains,
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

def get_by_date(game: str, date: str, tier: str = "") -> Optional[dict]:
    _load()
    g = (game or "").upper()
    d = _norm_date(date)
    t = (tier or "").upper()
    if g in ("MM", "PB"):
        return _DB.get((g, d, ""))
    # IL:
    t = t or "JP"
    return _DB.get(("IL", d, t))

def get_history(game: str, start_date: str, limit: int=20, tier: str="") -> dict:
    _load()
    g = (game or "").upper()
    t = (tier or "").upper()
    start = _norm_date(start_date)

    rows = [row for (gg, dd, tt), row in _DB.items() if gg == g and (tt == (t or "") if g!="IL" else tt == (t or "JP"))]

    def _k(r): return datetime.strptime(r["date"], "%m/%d/%Y")
    rows.sort(key=_k, reverse=True)

    out: List[dict] = []
    seen = False
    for r in rows:
        if not seen:
            if r["date"] == start:
                out.append(r); seen = True
        else:
            out.append(r)
        if len(out) >= limit:
            break

    # blob
    if g in ("MM", "PB"):
        blob_lines = []
        for r in out:
            ds = datetime.strptime(r["date"], "%m/%d/%Y").strftime("%m-%d-%y")
            mains = "-".join(f"{n:02d}" for n in r["mains"])
            b = f"{r['bonus']:02d}" if r["bonus"] is not None else ""
            blob_lines.append(f"{ds}  {mains}  {b}")
    else:
        blob_lines = []
        for r in out:
            ds = datetime.strptime(r["date"], "%m/%d/%Y").strftime("%m-%d-%y")
            mains = "-".join(f"{n:02d}" for n in r["mains"])
            blob_lines.append(f"{ds}  {mains}")

    return {"rows": out, "blob": "\n".join(blob_lines)}

# Debug: list keys present
def list_keys() -> List[str]:
    _load()
    return [f"{g}|{d}|{t}" for (g,d,t) in sorted(_DB.keys())]
