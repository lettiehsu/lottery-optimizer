# lottery_fetch.py — fetch 3 most recent jackpots for MM, PB; IL JP/M1/M2 via DB (with web fallback)
from __future__ import annotations
import re
from typing import Any, Dict, List, Tuple, Optional

import requests
from bs4 import BeautifulSoup

# Try to use our local SQLite history if available (most reliable for IL)
try:
    import lottery_store as store
except Exception:
    store = None  # still works for MM/PB via NY SODA and IL fallback (newest only)

SODA_BASE = "https://data.ny.gov/resource"
HDRS = {"User-Agent": "lottery-optimizer/1.0 (+https://onrender.com)"}

# ---------------- MM / PB via Socrata ----------------

def _to_int_list(space_or_comma_numbers: str) -> List[int]:
    if not space_or_comma_numbers:
        return []
    parts = re.split(r"[,\s]+", space_or_comma_numbers.strip())
    out: List[int] = []
    for p in parts:
        if p.isdigit():
            out.append(int(p))
    return out

def fetch_mm_latest(n: int = 3) -> List[Tuple[List[int], int]]:
    # Mega Millions dataset: 5xaw-6ayf
    url = (
        f"{SODA_BASE}/5xaw-6ayf.json"
        f"?$select=winning_numbers,mega_ball,draw_date"
        f"&$order=draw_date DESC&$limit={n}"
    )
    r = requests.get(url, timeout=12, headers=HDRS)
    r.raise_for_status()
    data = r.json()
    out: List[Tuple[List[int], int]] = []
    for row in data:
        main = _to_int_list(row.get("winning_numbers", ""))
        mb = row.get("mega_ball")
        try:
            mb = int(mb) if mb is not None else 0
        except ValueError:
            mb = 0
        if len(main) == 5 and mb:
            out.append((main, mb))
    return out

def fetch_pb_latest(n: int = 3) -> List[Tuple[List[int], int]]:
    # Powerball dataset: d6yy-54nr
    url = (
        f"{SODA_BASE}/d6yy-54nr.json"
        f"?$select=winning_numbers,powerball,draw_date"
        f"&$order=draw_date DESC&$limit={n}"
    )
    r = requests.get(url, timeout=12, headers=HDRS)
    r.raise_for_status()
    data = r.json()
    out: List[Tuple[List[int], int]] = []
    for row in data:
        main = _to_int_list(row.get("winning_numbers", ""))
        pb = row.get("powerball")
        try:
            pb = int(pb) if pb is not None else 0
        except ValueError:
            pb = 0
        if len(main) == 5 and pb:
            out.append((main, pb))
    return out

# ---------------- IL via DB first, web fallback for newest ----------------

IL_URL = "https://www.illinoislottery.com/dbg/results/lotto"
NUM_RE = re.compile(r"\b\d{1,2}\b")

def fetch_il_newest_from_web() -> Tuple[List[int] | None, List[int] | None, List[int] | None]:
    """
    Scrape the IL page for the latest draw (JP/M1/M2).
    Returns (JP, M1, M2) where each is a list of 6 ints or None.
    """
    r = requests.get(IL_URL, timeout=15, headers=HDRS)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    text = soup.get_text(" ", strip=True)
    nums = [int(x) for x in NUM_RE.findall(text)]
    # Heuristic: first 18 numbers are JP(6), M1(6), M2(6)
    if len(nums) >= 18:
        return nums[0:6], nums[6:12], nums[12:18]
    return None, None, None

def fetch_il_latest_k_from_db(k: int = 3) -> List[Dict[str, Any]]:
    """
    Return the last k draw-dates with tiers from our SQLite store as:
    [
      {"draw_date": "YYYY-MM-DD", "JP": [..6..] or None, "M1": [...], "M2": [...]},
      ...
    ]
    Ordered newest first.
    """
    result: List[Dict[str, Any]] = []
    if not store:
        return result
    # Collect distinct draw_dates from il_draws
    con = store._conn()
    try:
        dates = [r["draw_date"] for r in con.execute(
            "SELECT DISTINCT draw_date FROM il_draws ORDER BY draw_date DESC, id DESC LIMIT ?",
            (k,)
        ).fetchall()]
        for d in dates:
            row = {"draw_date": d, "JP": None, "M1": None, "M2": None}
            for tier in ("JP", "M1", "M2"):
                r = con.execute(
                    "SELECT n1,n2,n3,n4,n5,n6 FROM il_draws WHERE draw_date=? AND tier=? ORDER BY id DESC LIMIT 1",
                    (d, tier)
                ).fetchone()
                if r:
                    row[tier] = [r["n1"], r["n2"], r["n3"], r["n4"], r["n5"], r["n6"]]
            result.append(row)
    finally:
        con.close()
    return result

def build_autofill_payload() -> Dict[str, Any]:
    """
    Returns JSON for UI:
    {
      ok: true,
      phase1_latest: {...},  # 3rd newest (for Phase 1)
      phase2_latest: {...},  # 2nd newest (prefill Phase 1 → then P1/P2)
      phase3_latest: {...},  # newest NWJ (Phase 3 JSON)
      debug: {...}           # OPTIONAL hints if something missing
    }
    """
    debug: Dict[str, Any] = {}

    # MM / PB from Socrata
    mm, pb = [], []
    try:
        mm = fetch_mm_latest(3)
    except Exception as e:
        debug["mm_err"] = f"{type(e).__name__}: {e}"
    try:
        pb = fetch_pb_latest(3)
    except Exception as e:
        debug["pb_err"] = f"{type(e).__name__}: {e}"

    # IL from DB (preferred); if not present, fallback to web for newest only
    il_sets = []  # newest first, each: {"draw_date":..., "JP":[..], "M1":[..], "M2":[..]}
    try:
        il_sets = fetch_il_latest_k_from_db(3)
        if not il_sets:  # fallback: only newest from web
            jp, m1, m2 = fetch_il_newest_from_web()
            if jp or m1 or m2:
                il_sets = [{"draw_date": "latest", "JP": jp, "M1": m1, "M2": m2}]
            else:
                debug["il_note"] = "No IL data in DB and web scrape failed"
    except Exception as e:
        debug["il_err"] = f"{type(e).__name__}: {e}"

    def mm_json(i): return [mm[i][0], mm[i][1]] if len(mm) > i else None
    def pb_json(i): return [pb[i][0], pb[i][1]] if len(pb) > i else None

    def il_json(i, tier):
        if len(il_sets) > i and il_sets[i].get(tier):
            return [il_sets[i][tier], None]  # [mains6, null]
        return None

    L3: Dict[str, Any] = {}  # 3rd newest (Phase 1 autofill)
    L2: Dict[str, Any] = {}  # 2nd newest (Phase 2 prefill)
    L1: Dict[str, Any] = {}  # newest (Phase 3 NWJ)

    # 3rd newest → Phase 1
    if mm_json(2): L3["LATEST_MM"] = mm_json(2)
    if pb_json(2): L3["LATEST_PB"] = pb_json(2)
    # IL 3rd newest for Phase 1 (JP/M1/M2)
    for tier in ("JP", "M1", "M2"):
        v = il_json(2, tier)
        if v: L3[f"LATEST_IL_{tier}"] = v

    # 2nd newest → Phase 2 prefill (into Phase-1 boxes)
    if mm_json(1): L2["LATEST_MM"] = mm_json(1)
    if pb_json(1): L2["LATEST_PB"] = pb_json(1)
    for tier in ("JP", "M1", "M2"):
        v = il_json(1, tier)
        if v: L2[f"LATEST_IL_{tier}"] = v

    # newest → Phase 3 NWJ JSON
    if mm_json(0): L1["LATEST_MM"] = mm_json(0)
    if pb_json(0): L1["LATEST_PB"] = pb_json(0)
    for tier in ("JP", "M1", "M2"):
        v = il_json(0, tier)
        if v: L1[f"LATEST_IL_{tier}"] = v

    out = {"ok": True, "phase1_latest": L3, "phase2_latest": L2, "phase3_latest": L1}
    if debug:
        out["debug"] = debug
    return out

