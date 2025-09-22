from __future__ import annotations
import csv, io, json, os
from datetime import datetime
from typing import Dict, Any, Tuple, List, Optional

STORE_PATH = "/tmp/lotto_store.json"

# in-memory DB: key = (game, date_mmddyyyy, tier_or_empty)
_DB: Dict[Tuple[str, str, str], Dict[str, Any]] = {}

# ---------- date helpers ----------
def _norm_date(s: str) -> str:
    """
    Normalize many shapes to MM/DD/YYYY. Accepts: 09/16/2025, 9/16/2025, 2025-09-16, 09-16-2025, 09/16/25
    """
    s = (s or "").strip()
    fmts = ["%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%m-%d-%Y", "%m-%d-%y"]
    last_err = None
    for fmt in fmts:
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime("%m/%d/%Y")
        except Exception as e:
            last_err = e
    raise ValueError(f"Unrecognized date: '{s}' ({last_err})")

def _mmddyy(d_mmddyyyy: str) -> str:
    dt = datetime.strptime(d_mmddyyyy, "%m/%d/%Y")
    return dt.strftime("%m-%d-%y")

# ---------- storage ----------
def _load():
    global _DB
    if os.path.exists(STORE_PATH):
        with open(STORE_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
        _DB = {tuple(k.split("|", 2)): v for k, v in raw.items()}
    else:
        _DB = {}

def _save():
    raw = {"|".join(k): v for k, v in _DB.items()}
    with open(STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(raw, f)

def _norm_game(g: str) -> str:
    g = (g or "").strip().upper()
    if g in ("MM", "MEGAMILLIONS", "MEGA", "MEGA MILLIONS"): return "MM"
    if g in ("PB", "POWERBALL", "POWER BALL"): return "PB"
    if g in ("IL", "ILLOTTO", "ILLINOIS", "ILLINOIS LOTTO", "IL LOTTO"): return "IL"
    raise ValueError(f"Unknown game: {g!r}")

def _norm_tier(t: str) -> str:
    t = (t or "").strip().upper()
    if t in ("", "JP", "JACKPOT"): return "JP" if t else ""
    if t in ("M1", "MILLION1", "MILLION 1"): return "M1"
    if t in ("M2", "MILLION2", "MILLION 2"): return "M2"
    raise ValueError(f"Unknown tier: {t!r}")

# ---------- public: import ----------
def import_csv(text: str, overwrite: bool = False) -> Dict[str, int]:
    """
    CSV headers: game,draw_date,tier,n1,n2,n3,n4,n5,n6,bonus
    For MM/PB: n1..n5 + bonus
    For IL tiers (JP/M1/M2): n1..n6, bonus blank
    """
    _load()
    added = updated = 0

    f = io.StringIO(text)
    reader = csv.DictReader(f)
    needed = {"game", "draw_date", "n1", "n2", "n3", "n4", "n5"}
    lower = {h.lower() for h in (reader.fieldnames or [])}
    if not needed.issubset(lower):
        raise ValueError("CSV missing required headers")

    for row in reader:
        game = _norm_game(row.get("game", ""))
        date = _norm_date(row.get("draw_date", ""))
        tier = _norm_tier(row.get("tier", "")) if game == "IL" else ""

        # numbers
        nums: List[int] = []
        for i in range(1, 7):
            v = (row.get(f"n{i}") or "").strip()
            if v != "":
                try: nums.append(int(v))
                except: pass

        bonus_val = None
        b = (row.get("bonus") or "").strip()
        if b != "":
            try: bonus_val = int(b)
            except: bonus_val = None

        record: Dict[str, Any] = {
            "game": game,
            "draw_date": date,
            "draw_date_mmddyy": _mmddyy(date),
            "tier": tier,
            "n1": nums[0] if len(nums) > 0 else None,
            "n2": nums[1] if len(nums) > 1 else None,
            "n3": nums[2] if len(nums) > 2 else None,
            "n4": nums[3] if len(nums) > 3 else None,
            "n5": nums[4] if len(nums) > 4 else None,
            "n6": nums[5] if len(nums) > 5 else None,
        }
        if game in ("MM", "PB"):
            record["bonus"] = bonus_val

        key = (game, date, tier)
        if key in _DB:
            if overwrite:
                _DB[key] = record
                updated += 1
        else:
            _DB[key] = record
            added += 1

    _save()
    return {"added": added, "updated": updated, "total": added + updated}

# ---------- public: lookups ----------
def get_by_date(game: str, date: str, tier: str = "") -> Optional[Dict[str, Any]]:
    _load()
    g = _norm_game(game)
    d = _norm_date(date)
    t = _norm_tier(tier) if g == "IL" else ""
    return _DB.get((g, d, t))

def _gamekey_to_tuple(gamekey: str):
    gk = (gamekey or "").upper()
    if gk in ("MM", "PB"): return (gk, "")
    if gk in ("IL_JP", "IL_M1", "IL_M2"):
        _, tier = gk.split("_", 1)
        return ("IL", tier)
    raise ValueError(f"Unknown history game key: {gamekey!r}")

def get_history(game: str, start_date: str, limit: int = 20) -> Dict[str, Any]:
    _load()
    g, tier = _gamekey_to_tuple(game)
    sd = _norm_date(start_date)

    rows = []
    for (gg, dd, tt), rec in _DB.items():
        if gg != g: continue
        if g == "IL" and tier and tt != tier: continue
        if g != "IL" and tt != "": continue
        if datetime.strptime(dd, "%m/%d/%Y") <= datetime.strptime(sd, "%m/%d/%Y"):
            rows.append(rec)

    rows.sort(key=lambda r: datetime.strptime(r["draw_date"], "%m/%d/%Y"), reverse=True)
    rows = rows[: max(0, int(limit))]
    return {"rows": rows}
