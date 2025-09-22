from __future__ import annotations

import csv
import io
import json
import os
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

# Persist the normalized rows here (works on Render)
STORE_PATH = "/tmp/lotto_store.json"

# In-memory DB: key = (game, date, tier_or_empty)
_DB: Dict[Tuple[str, str, str], Dict[str, Any]] = {}

# ---------------- Date helpers ---------------- #

def _norm_date(s: str) -> str:
    """
    Normalize many date shapes to zero-padded MM/DD/YYYY.

    Accepts:
      9/6/2025, 09/06/2025, 9-6-2025,
      09/19/25, 9/19/25, 09-19-25  (2-digit year -> 2000+YY),
      2025-09-06, 2025/9/6

    Always returns: MM/DD/YYYY
    """
    s = (s or "").strip()
    if not s:
        raise ValueError("empty date")

    # uniform separators
    t = s.replace("-", "/")
    parts = [p.strip() for p in t.split("/") if p.strip()]
    if len(parts) != 3:
        raise ValueError(f"Unrecognized date: {s!r}")

    def to_int(x: str) -> int:
        if not x.isdigit():
            raise ValueError(f"Unrecognized date: {s!r}")
        return int(x, 10)

    if len(parts[0]) == 4:  # YYYY/M/D
        y = to_int(parts[0]); m = to_int(parts[1]); d = to_int(parts[2])
    else:
        if len(parts[2]) == 4:  # M/D/YYYY
            m = to_int(parts[0]); d = to_int(parts[1]); y = to_int(parts[2])
        else:  # M/D/YY -> 2000 + YY
            m = to_int(parts[0]); d = to_int(parts[1]); y = 2000 + to_int(parts[2])

    if not (1 <= m <= 12 and 1 <= d <= 31 and 1900 <= y <= 2100):
        raise ValueError(f"Unrecognized date: {s!r}")

    return f"{m:02d}/{d:02d}/{y:04d}"

def _dt_key(date_str: str) -> datetime:
    return datetime.strptime(date_str, "%m/%d/%Y")

# ---------------- Storage helpers ---------------- #

def _load_db() -> None:
    """Load persisted DB from STORE_PATH into _DB."""
    global _DB
    if os.path.exists(STORE_PATH):
        try:
            with open(STORE_PATH, "r", encoding="utf-8") as f:
                raw = json.load(f)
            _DB = {tuple(k.split("|", 2)): v for k, v in raw.items()}
        except Exception:
            _DB = {}
    else:
        _DB = {}

def _save_db() -> None:
    """Persist _DB into STORE_PATH."""
    raw = {"|".join(k): v for k, v in _DB.items()}
    with open(STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False)

def _key(game: str, date: str, tier: Optional[str]) -> Tuple[str, str, str]:
    return (game.upper(), date, (tier or "").upper())

# ---------------- Import API (CSV) ---------------- #

REQ_COLS = {"game","draw_date","tier","n1","n2","n3","n4","n5","n6","bonus"}

def import_csv_io(file_like, overwrite: bool = False) -> Dict[str, Any]:
    """
    Back-compat wrapper: accept a file-like object or bytes/str.
    """
    data = file_like.read() if hasattr(file_like, "read") else file_like
    if isinstance(data, bytes):
        text = data.decode("utf-8", errors="replace")
    else:
        text = str(data)
    return import_csv(text, overwrite=overwrite)

def import_csv(text: str, overwrite: bool = False) -> Dict[str, Any]:
    """
    Import a combined master CSV. Header can be in any order, but must include:
      game, draw_date, tier, n1, n2, n3, n4, n5, n6, bonus

    MM/PB rows:
      - n1..n5 required, bonus required, n6 should be blank
      - tier must be blank (ignored)
    IL rows:
      - tier in {JP,M1,M2} (if blank, default to JP)
      - n1..n6 required, bonus must be blank
    """
    _load_db()
    if overwrite:
        _DB.clear()

    reader = csv.DictReader(io.StringIO(text))
    # Validate required columns (order-agnostic)
    cols = {c.strip().lower() for c in (reader.fieldnames or [])}
    if not REQ_COLS.issubset(cols):
        missing = sorted(list(REQ_COLS - cols))
        raise ValueError(f"Bad CSV header. Missing columns: {missing}")

    added = 0
    updated = 0

    for i, row in enumerate(reader, start=2):  # 1-based; include header
        try:
            game = (row.get("game") or "").strip().upper()
            if game not in ("MM","PB","IL"):
                raise ValueError(f"Row {i}: game must be MM/PB/IL")

            date = _norm_date(row.get("draw_date") or row.get("date") or "")

            # helper to parse int or None
            def gi(name: str) -> Optional[int]:
                v = (row.get(name) or "").strip()
                return int(v) if v != "" else None

            n1 = gi("n1"); n2 = gi("n2"); n3 = gi("n3"); n4 = gi("n4"); n5 = gi("n5")
            n6 = gi("n6")
            bonus = gi("bonus")

            if game in ("MM","PB"):
                if None in (n1,n2,n3,n4,n5) or bonus is None:
                    raise ValueError(f"Row {i}: MM/PB require n1..n5 and bonus")
                tier = ""  # ignored
                row_norm = {
                    "game": game,
                    "date": date,
                    "tier": tier,
                    "mains": [n1,n2,n3,n4,n5],
                    "bonus": bonus,
                }
            else:
                tier = (row.get("tier") or "").strip().upper() or "JP"
                if tier not in ("JP","M1","M2"):
                    raise ValueError(f"Row {i}: IL tier must be JP/M1/M2 (or blank for JP)")
                if None in (n1,n2,n3,n4,n5,n6):
                    raise ValueError(f"Row {i}: IL requires n1..n6")
                if bonus not in (None,):  # IL bonus must be blank
                    raise ValueError(f"Row {i}: IL must not have bonus")
                row_norm = {
                    "game": game,
                    "date": date,
                    "tier": tier,
                    "mains": [n1,n2,n3,n4,n5,n6],
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
            # Include row index context to debug quickly
            raise ValueError(f"Import error on CSV row {i}: {e}") from e

    _save_db()
    return {"ok": True, "added": added, "updated": updated, "total": len(_DB)}

# ---------------- Query API (used by UI) ---------------- #

def get_by_date(game: str, date: str, tier: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Return normalized row dict or None.
    - MM/PB: ignore tier
    - IL: require tier ∈ {JP,M1,M2}; if blank, default JP
    """
    _load_db()
    g = (game or "").strip().upper()
    d = _norm_date(date)
    t = (tier or "").strip().upper() if g == "IL" else ""

    if g == "IL" and t == "":
        t = "JP"

    row = _DB.get(_key(g, d, t))
    if not row and g.startswith("IL_"):  # back-compat: IL_JP, IL_M1, IL_M2
        t2 = g.split("_", 1)[1]
        row = _DB.get(_key("IL", d, t2))
    return row

def get_history(game: str, start_date: str, limit: int = 20) -> Dict[str, Any]:
    """
    Return last `limit` rows on/older than `start_date` (newest first),
    plus the “blob” text your UI displays.
    For MM/PB:  mm-dd-yy  a-b-c-d-e  BB
    For IL:     mm-dd-yy  A-B-C-D-E-F
    """
    _load_db()
    g_in = (game or "").strip().upper()
    d0 = _norm_date(start_date)
    start_dt = _dt_key(d0)

    # Gather rows per game/tier
    if g_in in ("MM","PB"):
        rows = [v for (kg, kd, kt), v in _DB.items() if kg == g_in]
    else:
        tier_filter = ""
        g = g_in
        if g_in.startswith("IL_"):
            g = "IL"
            tier_filter = g_in.split("_",1)[1]
        rows = [v for (kg, kd, kt), v in _DB.items() if kg == g and (not tier_filter or kt == tier_filter)]

    # Sort newest → oldest; then filter on/older than start_date
    rows.sort(key=lambda r: _dt_key(r["date"]), reverse=True)
    selected: List[Dict[str, Any]] = []
    for r in rows:
        if _dt_key(r["date"]) <= start_dt:
            selected.append(r)
        if len(selected) >= limit:
            break

    # Build blob text
    lines: List[str] = []
    for r in selected:
        ds = datetime.strptime(r["date"], "%m/%d/%Y").strftime("%m-%d-%y")
        if r["game"] in ("MM","PB"):
            a,b,c,d,e = r["mains"]; bb = r["bonus"]
            lines.append(f"{ds}  {a:02d}-{b:02d}-{c:02d}-{d:02d}-{e:02d}  {bb:02d}")
        else:
            a,b,c,d,e,f = r["mains"]
            lines.append(f"{ds}  {a:02d}-{b:02d}-{c:02d}-{d:02d}-{e:02d}-{f:02d}")

    return {"rows": selected, "blob": "\n".join(lines)}
