from __future__ import annotations

import json
import os
import re
import random
from datetime import datetime
from typing import Any, Dict, List, Tuple, Optional

# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def _jsonish(x: Any) -> Any:
    """Parse strings that actually contain JSON; otherwise pass through."""
    if isinstance(x, str):
        s = x.strip()
        if (s.startswith("[") and s.endswith("]")) or (s.startswith("{") and s.endswith("}")):
            try:
                return json.loads(s)
            except Exception:
                return x
    return x

def _parse_hist_lines(blob: str, want_bonus: bool) -> List[Tuple[List[int], Optional[int]]]:
    """
    Accepts text like:
      09-12-25  17-18-21-42-64  07
      09-09-25  06-43-52-64-65  22
    For IL blobs (JP/M1/M2) there is no bonus.
    Returns [(mains, bonus_or_None), ...] newest first (top-down).
    """
    rows: List[Tuple[List[int], Optional[int]]] = []
    for raw in (blob or "").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        # take last group of 5 numbers, and optional trailing bonus
        nums = [int(n) for n in re.findall(r"\d{1,2}", raw)]
        if len(nums) >= 5:
            if want_bonus:
                if len(nums) >= 6:
                    mains = nums[-6:-1]
                    bonus = nums[-1]
                else:
                    # no bonus present, skip
                    continue
            else:
                mains = nums[-6:] if len(nums) >= 6 else nums[-5:]
                if len(mains) == 6:  # IL rows
                    bonus = None
                else:
                    # bad line shape
                    continue
            mains = sorted(mains)
            rows.append((mains, bonus))
    return rows

def _parse_latest(x: Any, want_bonus: bool) -> Tuple[List[int], Optional[int]]:
    """
    x may be already parsed or a string like [[..], b] or [[..], null]
    """
    x = _jsonish(x)
    if isinstance(x, list) and len(x) == 2 and isinstance(x[0], list):
        mains = [int(n) for n in x[0]]
        mains = sorted(mains)
        bonus = int(x[1]) if (x[1] is not None and want_bonus) else None
        return (mains, bonus)
    raise ValueError("LATEST_* must be a string like '[[..], b]' or '[.., null]'")

def _hit_counts_vs_mm_pb(ticket: Tuple[List[int], int], latest: Tuple[List[int], int]) -> Optional[str]:
    """
    For MM/PB produce one of: '5+B','5','4+B','4','3+B','3' or None if <3 hits.
    ticket & latest are (mains[5], bonus)
    """
    mains, b = set(ticket[0]), ticket[1]
    lmains, lb = set(latest[0]), latest[1]
    common = len(mains & lmains)
    bonus_hit = (b == lb)
    if common == 5 and bonus_hit: return "5+B"
    if common == 5:              return "5"
    if common == 4 and bonus_hit: return "4+B"
    if common == 4:              return "4"
    if common == 3 and bonus_hit: return "3+B"
    if common == 3:              return "3"
    return None

def _hit_counts_vs_il(ticket: List[int], latest: List[int]) -> Optional[str]:
    """For IL: return '6','5','4','3' or None if <3."""
    c = len(set(ticket) & set(latest))
    if c >= 3:
        return str(c)
    return None

# ------------------------------------------------------------
# Samplers (lightweight but structured; you can tune later)
# ------------------------------------------------------------

def _numbers_from_feed(feed_text: str, how_many: int, ceiling: int) -> List[int]:
    """
    Pull numbers out of FEED_* blobs. We don't rely on headings; we just grab digits.
    """
    pool = sorted({int(n) for n in re.findall(r"\b\d{1,2}\b", feed_text or "") if 1 <= int(n) <= ceiling})
    random.shuffle(pool)
    return pool[:how_many]

def _make_mm_ticket(feeds: str, hist20: List[Tuple[List[int], Optional[int]]]) -> Tuple[List[int], int]:
    # mains 1..70, MB 1..25
    # anchors: choose 1-2 numbers from the 2nd newest JP-like row (top of hist)
    mains_pool = set()
    if hist20:
        mains_pool.update(hist20[0][0][:2])
    mains_pool.update(_numbers_from_feed(feeds, 6, 70))
    while len(mains_pool) < 5:
        mains_pool.add(random.randint(1, 70))
    mains = sorted(random.sample(list(mains_pool), 5))
    bonus = random.randint(1, 25)
    return mains, bonus

def _make_pb_ticket(feeds: str, hist20: List[Tuple[List[int], Optional[int]]]) -> Tuple[List[int], int]:
    # mains 1..69, PB 1..26
    mains_pool = set()
    if hist20:
        mains_pool.update(hist20[0][0][:2])
    mains_pool.update(_numbers_from_feed(feeds, 6, 69))
    while len(mains_pool) < 5:
        mains_pool.add(random.randint(1, 69))
    mains = sorted(random.sample(list(mains_pool), 5))
    bonus = random.randint(1, 26)
    return mains, bonus

def _make_il_ticket(feeds: str, jp_hist20: List[Tuple[List[int], Optional[int]]],
                    m1_hist20: List[Tuple[List[int], Optional[int]]],
                    m2_hist20: List[Tuple[List[int], Optional[int]]]) -> List[int]:
    # IL 6 from 1..50 (game range is 1..50 traditionally)
    pool = set()
    if jp_hist20:
        pool.update(jp_hist20[0][0][:2])
    pool.update(_numbers_from_feed(feeds, 8, 50))
    while len(pool) < 6:
        pool.add(random.randint(1, 50))
    return sorted(random.sample(list(pool), 6))

# ------------------------------------------------------------
# Phase 1 (unchanged behavior expected by your UI)
# ------------------------------------------------------------

def _phase1(payload: Dict[str, Any]) -> Dict[str, Any]:
    # We keep echo from your previous workflow so the page can render Phase-1 columns
    echo = {}
    for k in [
        "FEED_MM", "FEED_PB", "FEED_IL",
        "HIST_MM_BLOB", "HIST_PB_BLOB",
        "HIST_IL_JP_BLOB", "HIST_IL_M1_BLOB", "HIST_IL_M2_BLOB",
        "LATEST_MM", "LATEST_PB", "LATEST_IL_JP"
    ]:
        echo[k] = payload.get(k, "")

    # Produce one 50-row batch per game and evaluate vs the 2nd newest JP (which user put in LATEST_*)
    # If you prefer: you can swap LATEST_* to be "2nd newest" for phase1; we just echo now and let the UI show batch.
    random.seed(os.urandom(16))

    # Parse history blobs (top-down newest first)
    mm_hist = _parse_hist_lines(payload.get("HIST_MM_BLOB",""), want_bonus=True)
    pb_hist = _parse_hist_lines(payload.get("HIST_PB_BLOB",""), want_bonus=True)
    il_jp_hist = _parse_hist_lines(payload.get("HIST_IL_JP_BLOB",""), want_bonus=False)
    il_m1_hist = _parse_hist_lines(payload.get("HIST_IL_M1_BLOB",""), want_bonus=False)
    il_m2_hist = _parse_hist_lines(payload.get("HIST_IL_M2_BLOB",""), want_bonus=False)

    # Build batches
    batch_mm = [ _make_mm_ticket(payload.get("FEED_MM",""), mm_hist) for _ in range(50) ]
    batch_pb = [ _make_pb_ticket(payload.get("FEED_PB",""), pb_hist) for _ in range(50) ]
    batch_il = [ _make_il_ticket(payload.get("FEED_IL",""), il_jp_hist, il_m1_hist, il_m2_hist) for _ in range(50) ]

    def fmt_ticket_mm_pb(t): return f"{t[0][0]:02d}-{t[0][1]:02d}-{t[0][2]:02d}-{t[0][3]:02d}-{t[0][4]:02d}  {t[1]:02d}"
    def fmt_ticket_il(t):    return "-".join(f"{n:02d}" for n in t)

    echo["BATCH_MM"] = [fmt_ticket_mm_pb(t) for t in batch_mm]
    echo["BATCH_PB"] = [fmt_ticket_mm_pb(t) for t in batch_pb]
    echo["BATCH_IL"] = [fmt_ticket_il(t) for t in batch_il]

    return {"ok": True, "phase": "phase1", "echo": echo}

# ------------------------------------------------------------
# Phase 2
# ------------------------------------------------------------

def _score_bucket(bucket: str) -> int:
    # Weight hits for ranking buy-list candidates
    table = {
        "5+B": 1000, "5": 300,
        "4+B": 120,  "4": 40,
        "3+B": 15,   "3": 5,
        "6": 800,    "5": 120, "4": 25, "3": 5  # IL uses "6","5","4","3"
    }
    return table.get(bucket, 0)

def _pick_top(dist: Dict[str, int], k: int) -> List[str]:
    # Dist is ticket_string -> score; pick top-k, break ties randomly to keep diversity
    items = list(dist.items())
    random.shuffle(items)
    items.sort(key=lambda kv: kv[1], reverse=True)
    return [kv[0] for kv in items[:k]]

def _phase2(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    100 simulations; aggregate stats; choose final buy list; save to file.
    Inputs needed: FEED_*, HIST_* blobs, and the same LATEST_* you already provide,
    though here LATEST_* is used only for logging (Phase 3 will compare).
    """
    random.seed(os.urandom(16))

    # Parse history
    mm_hist = _parse_hist_lines(payload.get("HIST_MM_BLOB",""), want_bonus=True)
    pb_hist = _parse_hist_lines(payload.get("HIST_PB_BLOB",""), want_bonus=True)
    il_jp_hist = _parse_hist_lines(payload.get("HIST_IL_JP_BLOB",""), want_bonus=False)
    il_m1_hist = _parse_hist_lines(payload.get("HIST_IL_M1_BLOB",""), want_bonus=False)
    il_m2_hist = _parse_hist_lines(payload.get("HIST_IL_M2_BLOB",""), want_bonus=False)

    # We need the 1st newest JP numbers only when Phase 3 compares; for Phase 2
    # we still produce stats on per-run 50-row batches against the *same* "latest"
    # you passed (so you can see expected behavior). This keeps the UI consistent.
    latest_mm = _parse_latest(payload.get("LATEST_MM",""), want_bonus=True)
    latest_pb = _parse_latest(payload.get("LATEST_PB",""), want_bonus=True)
    latest_il = _parse_latest(payload.get("LATEST_IL_JP",""), want_bonus=False)[0]

    stats = {
        "MM": {"3":0,"3+B":0,"4":0,"4+B":0,"5":0,"5+B":0},
        "PB": {"3":0,"3+B":0,"4":0,"4+B":0,"5":0,"5+B":0},
        "IL": {"3":0,"4":0,"5":0,"6":0},
    }
    positions = {"MM":{}, "PB":{}, "IL":{}}
    # score distributions for picking final buy lists
    dist_mm: Dict[str,int] = {}
    dist_pb: Dict[str,int] = {}
    dist_il: Dict[str,int] = {}

    def mm_str(t): return f"{t[0][0]:02d}-{t[0][1]:02d}-{t[0][2]:02d}-{t[0][3]:02d}-{t[0][4]:02d} + {t[1]:02d}"
    def pb_str(t): return f"{t[0][0]:02d}-{t[0][1]:02d}-{t[0][2]:02d}-{t[0][3]:02d}-{t[0][4]:02d} + {t[1]:02d}"
    def il_str(t): return " ".join(f"{n:02d}" for n in t)

    for _ in range(100):
        batch_mm = [ _make_mm_ticket(payload.get("FEED_MM",""), mm_hist) for _ in range(50) ]
        batch_pb = [ _make_pb_ticket(payload.get("FEED_PB",""), pb_hist) for _ in range(50) ]
        batch_il = [ _make_il_ticket(payload.get("FEED_IL",""), il_jp_hist, il_m1_hist, il_m2_hist) for _ in range(50) ]

        # MM
        for idx, t in enumerate(batch_mm, start=1):
            bucket = _hit_counts_vs_mm_pb(t, latest_mm)
            if bucket:
                stats["MM"][bucket] += 1
                positions["MM"][str(idx)] = positions["MM"].get(str(idx), 0) + 1
                dist_mm[mm_str(t)] = dist_mm.get(mm_str(t), 0) + _score_bucket(bucket)
        # PB
        for idx, t in enumerate(batch_pb, start=1):
            bucket = _hit_counts_vs_mm_pb(t, latest_pb)
            if bucket:
                stats["PB"][bucket] += 1
                positions["PB"][str(idx)] = positions["PB"].get(str(idx), 0) + 1
                dist_pb[pb_str(t)] = dist_pb.get(pb_str(t), 0) + _score_bucket(bucket)
        # IL
        for idx, t in enumerate(batch_il, start=1):
            bucket = _hit_counts_vs_il(t, latest_il)
            if bucket:
                stats["IL"][bucket] += 1
                positions["IL"][str(idx)] = positions["IL"].get(str(idx), 0) + 1
                dist_il[il_str(t)] = dist_il.get(il_str(t), 0) + _score_bucket(bucket)

    # choose buy lists with diversity
    final_mm = _pick_top(dist_mm, 10)
    final_pb = _pick_top(dist_pb, 10)
    final_il = _pick_top(dist_il, 15)

    out = {
        "ok": True,
        "phase": "phase2",
        "stats": stats,
        "positions": positions,
        "buy_list": {"MM": final_mm, "PB": final_pb, "IL": final_il},
    }

    # save
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path = f"/tmp/buy_phase2_{ts}.json"
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    out["saved_path"] = path
    return out

# ------------------------------------------------------------
# Public entrypoints used by Flask
# ------------------------------------------------------------

def handle_run(payload: Dict[str, Any]) -> Dict[str, Any]:
    phase = (payload.get("phase") or "").strip().lower()
    if phase == "phase1":
        return _phase1(payload)
    if phase == "phase2":
        return _phase2(payload)
    return {"ok": False, "error": "Unsupported phase"}
    
def handle_confirm(payload: Dict[str, Any]) -> Dict[str, Any]:
    # Placeholder for Phase 3 confirm/compare (future)
    return {"ok": True, "phase": "confirm", "echo": payload}

def recent_files() -> List[str]:
    files = [os.path.join("/tmp", f) for f in os.listdir("/tmp") if f.startswith(("lotto_", "buy_phase2_")) and f.endswith(".json")]
    files.sort()
    return files[-20:]
