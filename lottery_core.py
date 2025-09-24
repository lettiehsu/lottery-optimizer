from __future__ import annotations
import os, json, random
from datetime import datetime
from typing import List, Tuple, Dict, Any

# ----- helpers to parse inputs from UI -----
def _parse_latest(val: Any, expect_count: int) -> Tuple[List[int], int | None]:
    """
    Accepts JSON string like "[[1,2,3,4,5], 10]" (MM/PB) or "[[1,2,3,4,5,6], null]" (IL).
    """
    if isinstance(val, str):
        data = json.loads(val)
    else:
        data = val
    if not isinstance(data, list) or len(data) != 2:
        raise ValueError("LATEST_* must be a list like [[..nums..], bonus|null]")
    mains, bonus = data
    if not isinstance(mains, list) or len(mains) != expect_count:
        raise ValueError(f"Expected {expect_count} mains")
    mains = [int(x) for x in mains]
    if bonus is None:
        return mains, None
    return mains, int(bonus)

def _parse_hist_blob(text: str, is_bonus: bool) -> List[Tuple[List[int], int | None]]:
    """
    Lines like:
      09-12-25  17-18-21-42-64  07   (MM/PB)
      09-15-25  01-04-05-10-18-49     (IL)
    Only numbers are used to seed sampling.
    """
    out = []
    for raw in (text or "").splitlines():
        raw = raw.strip()
        if not raw: 
            continue
        parts = raw.split()
        nums = [int(x) for x in parts if x.replace("-","").isdigit()]
        # Extract mains and optional bonus by length
        if is_bonus:
            *mains, b = nums
            out.append((mains, b))
        else:
            out.append((nums, None))
    return out

# ----- sampling strategies -----
def _sample_from_hist(hist: List[Tuple[List[int], int | None]], k: int, size: int) -> List[List[int]]:
    """
    Build a 50-row batch by mixing history draws and small variations.
    k = how many mains per row (5 for MM/PB, 6 for IL)
    """
    out: List[List[int]] = []
    if not hist:
        # fallback random
        pool = list(range(1, 71)) if k == 5 else list(range(1, 47))
        while len(out) < size:
            row = sorted(random.sample(pool, k))
            out.append(row)
        return out

    pool = sorted({n for mains,_ in hist for n in mains})
    while len(out) < size:
        base_mains, _ = random.choice(hist)
        # keep 2–3 numbers from history row, fill the rest from pool biasing to history
        keep = random.sample(base_mains, k= min(len(base_mains), random.choice([2,3])))
        remain_pool = [n for n in pool if n not in keep]
        row = sorted(keep + random.sample(remain_pool, k - len(keep)))
        out.append(row)
    return out

def _score_lotto(row: List[int], target: List[int]) -> int:
    return len(set(row) & set(target))

def _score_plus_bonus(row: List[int], b: int | None, target: List[int], tb: int | None) -> Tuple[int, bool]:
    return _score_lotto(row, target), (b is not None and tb is not None and b == tb)

# ----- main handler -----
def handle_run(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Phase 1: generate 50 rows for each game from its history,
    compare vs 2nd-newest jackpots (LATEST_*), return stats and row indices.
    """
    # Parse LATEST_* from the UI previews
    mm_latest = payload.get("LATEST_MM")
    pb_latest = payload.get("LATEST_PB")
    il_jp_latest = payload.get("LATEST_IL_JP")
    il_m1_latest = payload.get("LATEST_IL_M1")
    il_m2_latest = payload.get("LATEST_IL_M2")

    mm_target, mm_tb = _parse_latest(mm_latest, 5)
    pb_target, pb_tb = _parse_latest(pb_latest, 5)
    il_jp_target, _ = _parse_latest(il_jp_latest, 6)
    il_m1_target, _ = _parse_latest(il_m1_latest, 6)
    il_m2_target, _ = _parse_latest(il_m2_latest, 6)

    # Parse history blobs
    mm_hist = _parse_hist_blob(payload.get("HIST_MM_BLOB", ""), is_bonus=True)
    pb_hist = _parse_hist_blob(payload.get("HIST_PB_BLOB", ""), is_bonus=True)
    il_jp_hist = _parse_hist_blob(payload.get("HIST_IL_JP_BLOB", ""), is_bonus=False)
    il_m1_hist = _parse_hist_blob(payload.get("HIST_IL_M1_BLOB", ""), is_bonus=False)
    il_m2_hist = _parse_hist_blob(payload.get("HIST_IL_M2_BLOB", ""), is_bonus=False)

    random.seed()  # new batch every click

    # Build 50-row batches
    SIZE = 50
    batch_mm = _sample_from_hist(mm_hist, k=5, size=SIZE)
    batch_pb = _sample_from_hist(pb_hist, k=5, size=SIZE)
    # IL: mix JP/M1/M2 history together for a richer pool
    batch_il = _sample_from_hist(il_jp_hist + il_m1_hist + il_m2_hist, k=6, size=SIZE)

    # Score MM/PB (with bonus) vs their LATEST_*
    def score_with_bonus(batch: List[List[int]], target: List[int], tb: int | None):
        rows = {"3":[], "4":[], "5":[], "3+B":[], "4+B":[], "5+B":[]}
        counts = {k:0 for k in rows}
        exact_rows = []
        for i, r in enumerate(batch, start=1):
            m, hasb = _score_plus_bonus(r, None, target, tb)
            if m == 5: exact_rows.append(i)
            if m in (3,4,5):
                rows[str(m)].append(i); counts[str(m)] += 1
                if hasb and m in (3,4,5):
                    rows[f"{m}+B"].append(i); counts[f"{m}+B"] += 1
        return {"counts": counts, "rows": rows, "exact_rows": exact_rows}

    hits_mm = score_with_bonus(batch_mm, mm_target, mm_tb)
    hits_pb = score_with_bonus(batch_pb, pb_target, pb_tb)

    # Score IL (no bonus)
    def score_il(batch: List[List[int]], target: List[int]):
        rows = {"3":[], "4":[], "5":[], "6":[]}
        counts = {k:0 for k in rows}
        for i, r in enumerate(batch, start=1):
            m = _score_lotto(r, target)
            if m in (3,4,5,6):
                rows[str(m)].append(i)
                counts[str(m)] += 1
        return {"counts": counts, "rows": rows}

    hits_il_jp = score_il(batch_il, il_jp_target)
    hits_il_m1 = score_il(batch_il, il_m1_target)
    hits_il_m2 = score_il(batch_il, il_m2_target)

    # pretty strings for UI
    def fmt_row(nums: List[int], bonus: int | None = None) -> str:
        mains = "-".join(f"{n:02d}" for n in nums)
        return f"{mains}" if bonus is None else f"{mains}  {bonus:02d}"

    batch_mm_str = [fmt_row(r, None) for r in batch_mm]
    batch_pb_str = [fmt_row(r, None) for r in batch_pb]
    batch_il_str = [fmt_row(r, None) for r in batch_il]

    result = {
        "ok": True,
        "phase": "phase1",
        "echo": {
            "BATCH_MM": batch_mm_str,
            "BATCH_PB": batch_pb_str,
            "BATCH_IL": batch_il_str,
            "HITS_MM": hits_mm,
            "HITS_PB": hits_pb,
            "HITS_IL_JP": hits_il_jp,
            "HITS_IL_M1": hits_il_m1,
            "HITS_IL_M2": hits_il_m2,
        }
    }

    # save to /tmp
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path = f"/tmp/lotto_1_{ts}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    result["saved_path"] = path
    return result

def recent_files() -> list[str]:
    import glob
    return sorted(glob.glob("/tmp/lotto_1_*.json"))[-20:]
