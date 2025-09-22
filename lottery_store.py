from __future__ import annotations
import csv, io, json, os
from datetime import datetime
from typing import Dict, Any, Tuple, List, Optional

# Persist here (works on Render)
STORE_PATH = "/tmp/lotto_store.json"

# in-memory db: key = (game, date, tier)
_DB: Dict[Tuple[str, str, str], Dict[str, Any]] = {}


# ---------- date helpers ----------

def _norm_date(s: str) -> str:
    """
    Normalize many date shapes to MM/DD/YYYY.
    Accepts: 9/6/2025, 09/06/2025, 2025-09-06, 09-06-2025, 09/06/25
    """
    s = (s or "").strip()
    fmts = ["%m/%d/%Y", "%-m/%-d/%Y", "%Y-%m-%d", "%m-%d-%Y", "%m/%d/%y"]
    last = None
    for fmt in fmts:
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime("%m/%d/%Y")
        except Exception as e:
            last = e
    raise ValueError(f"Unrecognized date: {s!r} ({last})")


def _to_display_date(iso_mmddyyyy: str) -> str:
    # UI wants mm-dd-yy on history lines
    dt = datetime.strptime(iso_mmddyyyy, "%m/%d/%Y")
    return dt.strftime("%m-%d-%y")


# ---------- disk I/O ----------

def _load():
    global _DB
    if os.path.exists(STORE_PATH):
        try:
            with open(STORE_PATH, "r", encoding="utf-8") as fp:
                raw = json.load(fp)
            _DB = {tuple(k.split("|", 2)): v for k, v in raw.items()}
        except Exception:
            _DB = {}
    else:
        _DB = {}


def _save():
    raw = {"|".join(k): v for k, v in _DB.items()}
    with open(STORE_PATH, "w", encoding="utf-8") as fp:
        json.dump(raw, fp, ensure_ascii=False)


# ---------- public API ----------

def import_csv(text: str, overwrite: bool = True) -> Dict[str, int | bool]:
    """
    CSV headers: game,draw_date,tier,n1,n2,n3,n4,n5,n6,bonus
    - game: MM, PB, or IL
    - tier: blank for MM/PB, or JP/M1/M2 for IL
    """
    _load()
    added = updated = 0

    rdr = csv.DictReader(io.StringIO(text))
    expected = {"game","draw_date","tier","n1","n2","n3","n4","n5","n6","bonus"}
    if set(h.lower() for h in rdr.fieldnames or []) != expected:
        # Try forgiving header names (case-insensitive, order-agnostic)
        fn = [h.lower() for h in (rdr.fieldnames or [])]
        missing = expected - set(fn)
        if missing:
            raise ValueError(f"CSV headers mismatch. Expected {sorted(expected)}, got {rdr.fieldnames}")

    for row in rdr:
        game = (row.get("game") or "").strip()
        raw_date = (row.get("draw_date") or "").strip()
        tier = (row.get("tier") or "").strip()
        date = _norm_date(raw_date)

        n1 = int(row["n1"]) if row.get("n1") else None
        n2 = int(row["n2"]) if row.get("n2") else None
        n3 = int(row["n3"]) if row.get("n3") else None
        n4 = int(row["n4"]) if row.get("n4") else None
        n5 = int(row["n5"]) if row.get("n5") else None
        n6 = int(row["n6"]) if row.get("n6") else None
        bonus = row.get("bonus")
        bonus = int(bonus) if (bonus and bonus.strip() != "") else None

        mains: List[int] = []
        for n in (n1, n2, n3, n4, n5, n6):
            if n is not None:
                mains.append(int(n))

        key_game: str
        key_tier = tier or ""

        if game == "MM":
            key_game = "MM"
            key_tier = ""
        elif game == "PB":
            key_game = "PB"
            key_tier = ""
        elif game == "IL":
            if tier not in ("JP", "M1", "M2"):
                # skip unknown IL tier row
                continue
            key_game = f"IL_{tier}"
            # IL has 6 mains and bonus = None
            bonus = None
        else:
            # unknown game row
            continue

        key = (key_game, date, key_tier)
        item = {"game": key_game, "date": date, "tier": key_tier, "mains": mains, "bonus": bonus}

        if key in _DB:
            if overwrite:
                _DB[key] = item
                updated += 1
        else:
            _DB[key] = item
            added += 1

    _save()
    return {"ok": True, "added": added, "updated": updated, "total": len(_DB)}


def get_by_date(game: str, date: str) -> Optional[Dict[str, Any]]:
    """
    game: "MM"|"PB"|"IL_JP"|"IL_M1"|"IL_M2"
    date: MM/DD/YYYY
    """
    _load()
    date = _norm_date(date)
    tier = ""  # stored key's 3rd part for IL rows is already "JP"/"M1"/"M2"
    if game.startswith("IL_"):
        tier = game.split("_", 1)[1]
        game = f"IL_{tier}"
        tier = tier
    key = (game, date, tier if game.startswith("IL_") else "")
    return _DB.get(key)


def get_history(game: str, start_date: str, limit: int = 20) -> Dict[str, Any]:
    """
    Returns last 'limit' rows including start_date and older (newest first in text blob).
    blob formats:
      - MM:  mm-dd-yy  a-b-c-d-e  BB
      - PB:  mm-dd-yy  a-b-c-d-e  PP
      - IL_*: mm-dd-yy  A-B-C-D-E-F
    """
    _load()
    sd = datetime.strptime(_norm_date(start_date), "%m/%d/%Y")

    # collect rows for this game
    rows = []
    for (g, d, t), v in _DB.items():
        if game == "MM" and g == "MM":
            rows.append(v)
        elif game == "PB" and g == "PB":
            rows.append(v)
        elif game == "IL_JP" and g == "IL_JP":
            rows.append(v)
        elif game == "IL_M1" and g == "IL_M1":
            rows.append(v)
        elif game == "IL_M2" and g == "IL_M2":
            rows.append(v)

    # sort by date desc
    rows.sort(key=lambda r: datetime.strptime(r["date"], "%m/%d/%Y"), reverse=True)

    # start from the first row whose date <= start_date
    filtered: List[Dict[str, Any]] = []
    for r in rows:
        if datetime.strptime(r["date"], "%m/%d/%Y") <= sd:
            filtered.append(r)
        if len(filtered) >= limit:
            break

    # build blob text
    lines: List[str] = []
    for r in filtered:
        disp = _to_display_date(r["date"])
        mains = r["mains"]
        if game in ("MM", "PB"):
            a, b, c, d, e = mains[:5]
            bonus = r.get("bonus", 0)
            suffix = f"{bonus:02d}"
            lines.append(f"{disp}  {a:02d}-{b:02d}-{c:02d}-{d:02d}-{e:02d}  {suffix}")
        else:
            A, B, C, D, E, F = mains[:6]
            lines.append(f"{disp}  {A:02d}-{B:02d}-{C:02d}-{D:02d}-{E:02d}-{F:02d}")

    return {"rows": filtered, "blob": "\n".join(lines)}
