# lottery_fetch.py — fetch 3 most recent jackpots for MM, PB; latest IL JP/M1/M2
from __future__ import annotations
import re
from typing import Any, Dict, List, Tuple

import requests
from bs4 import BeautifulSoup

# ---- Mega Millions & Powerball via NY Open Data SODA ----
SODA_BASE = "https://data.ny.gov/resource"

def _to_int_list(space_numbers: str) -> List[int]:
    return [int(s) for s in (space_numbers or "").split() if s.isdigit()]

def fetch_mm_latest(n: int = 3) -> List[Tuple[List[int], int]]:
    # Dataset: 5xaw-6ayf
    url = f"{SODA_BASE}/5xaw-6ayf.json?$order=draw_date DESC&$limit={n}"
    r = requests.get(url, timeout=12)
    r.raise_for_status()
    data = r.json()
    out = []
    for row in data:
        main = _to_int_list(row.get("winning_numbers", ""))
        mb = int(row.get("mega_ball") or 0)
        if len(main) == 5 and mb:
            out.append((main, mb))
    return out

def fetch_pb_latest(n: int = 3) -> List[Tuple[List[int], int]]:
    # Dataset: d6yy-54nr
    url = f"{SODA_BASE}/d6yy-54nr.json?$order=draw_date DESC&$limit={n}"
    r = requests.get(url, timeout=12)
    r.raise_for_status()
    data = r.json()
    out = []
    for row in data:
        main = _to_int_list(row.get("winning_numbers", ""))
        pb = int(row.get("powerball") or 0)
        if len(main) == 5 and pb:
            out.append((main, pb))
    return out

# ---- Illinois Lotto scrape (latest draw: JP / M1 / M2) ----
IL_URL = "https://www.illinoislottery.com/dbg/results/lotto"
NUM_RE = re.compile(r"\b\d{1,2}\b")

def fetch_il_latest() -> Tuple[List[int] | None, List[int] | None, List[int] | None]:
    """
    Returns (JP, M1, M2) mains for the latest draw; any may be None if not found.
    """
    r = requests.get(IL_URL, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    text = soup.get_text(" ", strip=True)

    nums = [int(x) for x in NUM_RE.findall(text)]
    # Heuristic: first 18 numbers we find are typically JP(6), M1(6), M2(6)
    if len(nums) >= 18:
        jp = nums[0:6]
        m1 = nums[6:12]
        m2 = nums[12:18]
        return jp, m1, m2
    return None, None, None

def build_autofill_payload() -> Dict[str, Any]:
    """
    Returns JSON for UI:
    {
      ok: true,
      phase1_latest: {...}  # 3rd newest (for Phase 1)
      phase2_latest: {...}  # 2nd newest (to prefill and then run Phase 1 → Phase 2)
      phase3_latest: {...}  # newest NWJ (Phase 3 JSON)
    }
    """
    mm = fetch_mm_latest(3)  # list of (mains5, bonus)
    pb = fetch_pb_latest(3)
    il_jp, il_m1, il_m2 = fetch_il_latest()

    def mm_json(i): return [mm[i][0], mm[i][1]] if len(mm) > i else None
    def pb_json(i): return [pb[i][0], pb[i][1]] if len(pb) > i else None

    L3, L2, L1 = {}, {}, {}

    # 3rd newest → Phase 1
    if mm_json(2): L3["LATEST_MM"] = mm_json(2)
    if pb_json(2): L3["LATEST_PB"] = pb_json(2)

    # 2nd newest → Phase 2 (prefill Phase-1 boxes then you run Phase 1)
    if mm_json(1): L2["LATEST_MM"] = mm_json(1)
    if pb_json(1): L2["LATEST_PB"] = pb_json(1)

    # newest → Phase 3 NWJ
    if mm_json(0): L1["LATEST_MM"] = mm_json(0)
    if pb_json(0): L1["LATEST_PB"] = pb_json(0)
    if il_jp: L1["LATEST_IL_JP"] = [il_jp, None]
    if il_m1: L1["LATEST_IL_M1"] = [il_m1, None]
    if il_m2: L1["LATEST_IL_M2"] = [il_m2, None]

    return {"ok": True, "phase1_latest": L3, "phase2_latest": L2, "phase3_latest": L1}
