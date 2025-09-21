# lottery_store.py
# Simple file-backed store for jackpots + CSV import + history slicing.

from __future__ import annotations
import os, csv, json
from datetime import datetime
from typing import List, Dict, Any, Optional

# Where to persist the master store on disk
DATA_DIR = os.environ.get("DATA_DIR", ".")
STORE_PATH = os.path.join(DATA_DIR, "lottery_store.json")

# In-memory rows: newest and older across all games/tiers
# Each row schema:
#   {
#     "game": "MM"|"PB"|"IL",
#     "draw_date": "M/D/YYYY",
#     "tier": ""|"JP"|"M1"|"M2",
#     "n1".. "n6": int or "",
#     "bonus": int or "",
#   }
ROWS: List[Dict[str, Any]] = []

DATE_FMTS = ["%m/%d/%Y", "%Y-%m-%d", "%-m/%-d/%Y"]  # be permissive on load

def _parse_date(s: str) -> Optional[datetime]:
    if not s:
        return None
    for f in DATE_FMTS:
        try:
            return datetime.strptime(str(s), f)
        except Exception:
            continue
    return None

def _norm_row(r: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a row's fields/types."""
    out = {
        "game": str(r.get("game", "")).strip().upper(),
        "draw_date": str(r.get("draw_date", "")).strip(),
        "tier": str(r.get("tier", "")).strip().upper(),
        "n1": _to_int_safe(r.get("n1")),
        "n2": _to_int_safe(r.get("n2")),
        "n3": _to_int_safe(r.get("n3")),
        "n4": _to_int_safe(r.get("n4")),
        "n5": _to_int_safe(r.get("n5")),
        "n6": _to_int_safe(r.get("n6")),
        "bonus": _to_int_safe(r.get("bonus")),
    }
    # IL always has 6 mains and no bonus
    if out["game"] == "IL":
        if out["bonus"] is None:  # keep None / "" as blank
            out["bonus"] = ""
    # MM/PB have 5 mains; n6 should be blank
    if out["game"] in ("MM", "PB"):
        out["n6"] = ""
    return out

def _to_int_safe(v) -> Any:
    if v in (None, "", "null", "None"):
        return ""
    try:
        return int(v)
    except Exception:
        try:
            # handle csv like "07"
            return int(str(v).strip())
        except Exception:
            return ""

def _key(row: Dict[str, Any]):
    return (row["game"], row["tier"], row["draw_date"])

def save():
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(ROWS, f, ensure_ascii=False, indent=2)

def load():
    global ROWS
    if os.path.exists(STORE_PATH):
        with open(STORE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            ROWS = [_norm_row(d) for d in data]
    else:
        ROWS = []

def clear():
    global ROWS
    ROWS = []
    save()

def import_csv(path: str, overwrite: bool = True) -> Dict[str, Any]:
    """
    Import a combined CSV with columns:
      game,draw_date,tier,n1,n2,n3,n4,n5,n6,bonus
    If overwrite=True, replaces the store completely. Otherwise, upserts rows.
    """
    global ROWS
    if overwrite:
        ROWS = []

    seen = { _key(r): i for i, r in enumerate(ROWS) }
    added, updated = 0, 0

    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            r = _norm_row(raw)
            if not r["game"] or not r["draw_date"]:
                continue
            k = _key(r)
            if k in seen:
                ROWS[seen[k]] = r
                updated += 1
            else:
                seen[k] = len(ROWS)
                ROWS.append(r)
                added += 1

    # keep rows sorted by date desc within (game,tier), but global order doesn't matter
    ROWS.sort(key=lambda x: (_parse_date(x["draw_date"]) or datetime.min), reverse=True)
    save()
    return {"ok": True, "added": added, "updated": updated, "total": len(ROWS)}

# ---- Add single entries (used by "Save current NJ → History") ----

def add_mm(mains: list[int], bonus: int, draw_date: Optional[str] = None):
    _add_single("MM", "", mains, bonus, draw_date)

def add_pb(mains: list[int], bonus: int, draw_date: Optional[str] = None):
    _add_single("PB", "", mains, bonus, draw_date)

def add_il(tier: str, mains: list[int], draw_date: Optional[str] = None):
    tier = (tier or "JP").upper()
    _add_single("IL", tier, mains, "", draw_date)

def _add_single(game: str, tier: str, mains: list[int], bonus: Any, draw_date: Optional[str]):
    global ROWS
    if not draw_date:
        # default to today M/D/YYYY
        draw_date = datetime.now().strftime("%-m/%-d/%Y")
        try:
            # Windows compatibility
            draw_date = datetime.now().strftime("%m/%d/%Y")
        except Exception:
            pass
    r = {
        "game": game,
        "draw_date": draw_date,
        "tier": tier,
        "n1": _to_int_safe(mains[0] if len(mains)>0 else ""),
        "n2": _to_int_safe(mains[1] if len(mains)>1 else ""),
        "n3": _to_int_safe(mains[2] if len(mains)>2 else ""),
        "n4": _to_int_safe(mains[3] if len(mains)>3 else ""),
        "n5": _to_int_safe(mains[4] if len(mains)>4 else ""),
        "n6": _to_int_safe(mains[5] if len(mains)>5 else ""),
        "bonus": _to_int_safe(bonus),
    }
    r = _norm_row(r)
    k = _key(r)
    # upsert
    idx = next((i for i,x in enumerate(ROWS) if _key(x) == k), None)
    if idx is None:
        ROWS.append(r)
    else:
        ROWS[idx] = r
    ROWS.sort(key=lambda x: (_parse_date(x["draw_date"]) or datetime.min), reverse=True)
    save()

# ---- Latest pickers for autofill ----

def get_latest(game: str, n: int) -> List[list]:
    """
    For MM/PB: returns newest-first list of [[mains], bonus]
    """
    items = [r for r in ROWS if r["game"] == game and (r.get("tier") or "") == ""]
    items.sort(key=lambda x: (_parse_date(x["draw_date"]) or datetime.min), reverse=True)
    out = []
    for r in items[:n]:
        mains = [r["n1"], r["n2"], r["n3"], r["n4"], r["n5"]]
        out.append([mains, r["bonus"]])
    return out

def get_latest_il(tier: str, n: int) -> List[list]:
    """
    For IL tiers: returns newest-first list of [[mains], null]
    """
    tier = (tier or "JP").upper()
    items = [r for r in ROWS if r["game"] == "IL" and (r.get("tier") or "") == tier]
    items.sort(key=lambda x: (_parse_date(x["draw_date"]) or datetime.min), reverse=True)
    out = []
    for r in items[:n]:
        mains = [r["n1"], r["n2"], r["n3"], r["n4"], r["n5"], r["n6"]]
        out.append([mains, None])
    return out

# ---- History slice (pivot date → 20 rows older) ----

def get_hist_slice(game: str, tier: str, pivot_date: str, limit: int = 20) -> List[Dict[str, Any]]:
    if game == "IL":
        tier = (tier or "JP").upper()
    else:
        tier = ""
    items = [r for r in ROWS if r["game"] == game and (r.get("tier") or "") == tier]
    for r in items:
        r["_dt"] = _parse_date(r.get("draw_date", ""))
    items = [r for r in items if r["_dt"] is not None]
    items.sort(key=lambda r: r["_dt"], reverse=True)

    pivot_dt = _parse_date(pivot_date) if pivot_date else (items[0]["_dt"] if items else None)
    if not pivot_dt:
        return []
    start_idx = next((i for i, r in enumerate(items) if r["_dt"] <= pivot_dt), None)
    if start_idx is None:
        return []
    return items[start_idx:start_idx + limit]

# ---- Date lists for "3rd newest" buttons ----

def top_dates_by_game():
    out = {"MM": [], "PB": [], "IL_JP": [], "IL_M1": [], "IL_M2": []}
    for r in ROWS:
        dt = _parse_date(r.get("draw_date",""))
        if not dt:
            continue
        if r["game"] == "MM":
            out["MM"].append(dt)
        elif r["game"] == "PB":
            out["PB"].append(dt)
        elif r["game"] == "IL":
            tier = (r.get("tier") or "")
            if tier == "JP": out["IL_JP"].append(dt)
            if tier == "M1": out["IL_M1"].append(dt)
            if tier == "M2": out["IL_M2"].append(dt)
    for k in out:
        # unique + sorted desc
        out[k] = sorted(list(set(out[k])), reverse=True)
    return out

# load at import
load()
