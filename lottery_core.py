# lottery_core.py
from __future__ import annotations

import json, random, time, re
from typing import Any, Dict, List, Optional, Tuple
from collections import Counter

# ------------------------------------------------------------
# Game specs
# ------------------------------------------------------------
GameSpec = Dict[str, Any]
SPECS: Dict[str, GameSpec] = {
    "MM": {"mains_max": 70, "bonus_max": 25, "mains_count": 5, "has_bonus": True},
    "PB": {"mains_max": 69, "bonus_max": 26, "mains_count": 5, "has_bonus": True},
    "IL": {"mains_max": 50, "mains_count": 6, "has_bonus": False},
}

# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def _norm_latest(val: Any, game: str) -> Tuple[List[int], Optional[int]]:
    """Accept [[m1..], bonus] OR its JSON string; returns (sorted mains, bonus/None)."""
    if isinstance(val, str):
        val = json.loads(val)
    if not isinstance(val, list) or len(val) != 2:
        raise ValueError("LATEST_* must be like [[..], b] or [[..], null]")
    mains, bonus = val
    mains = sorted(int(x) for x in mains)
    b = None if not SPECS[game].get("has_bonus") else (None if bonus is None else int(bonus))
    return mains, b

def _pretty_row(mains: List[int], bonus: Optional[int]) -> str:
    s = " ".join(f"{n:02d}" for n in mains)
    return f"{s}  {bonus:02d}" if bonus is not None else s

def _score_row(row_m: List[int], row_b: Optional[int], tgt_m: List[int], tgt_b: Optional[int]) -> Tuple[int,bool]:
    return len(set(row_m) & set(tgt_m)), (row_b is not None and tgt_b is not None and row_b == tgt_b)

def _safe_unique_sorted(nums: List[int], limit: int) -> List[int]:
    s = set(nums)
    while len(s) < len(nums):
        s.add(random.randint(1, limit))
    out = sorted(s)[: len(nums)]
    return out

def _extract_ints(text: str) -> List[int]:
    return [int(x) for x in re.findall(r"\d+", text or "")]

def _parse_feed_block(feed_text: str) -> Tuple[List[int], List[int], List[int], List[int]]:
    """
    Parse FEED_* pane text. Returns (hot_m, over_m, hot_b, over_b).
    Works for both MM/PB (with bonus lines) and IL (bonus lists come back empty).
    """
    t = (feed_text or "").replace(",", " ")
    def take_after(label: str, cap: int) -> List[int]:
        m = re.search(re.escape(label) + r"\s*([0-9\s]+)", t, re.I)
        if not m: return []
        return _extract_ints(m.group(1))[:cap]

    hot_m  = take_after("Top 8 hot numbers:", 16)
    over_m = take_after("Top 8 overdue numbers:", 16)
    hot_b  = take_after("Top 3 hot Mega Ball numbers:", 6) or take_after("Top 3 hot Power Ball numbers:", 6)
    over_b = take_after("Top 3 overdue Mega Ball numbers:", 6) or take_after("Top 3 overdue Power Ball numbers:", 6)
    return hot_m, over_m, hot_b, over_b

def _bias_pool(game: str, hot: List[int] | None, overdue: List[int] | None, include: List[int] | None) -> Tuple[List[int], List[int]]:
    spec = SPECS[game]
    mains_max = spec["mains_max"]
    mains_pool: List[int] = []
    if include: mains_pool.extend(include)
    if hot: mains_pool.extend(hot[:12])
    if overdue: mains_pool.extend(overdue[:12])
    mains_pool = [n for n in mains_pool if 1 <= int(n) <= mains_max]
    mains_pool = list(dict.fromkeys(mains_pool))
    full = list(range(1, mains_max + 1))
    extras = [x for x in full if x not in mains_pool]
    mixed = mains_pool + random.sample(extras, k=max(0, int(0.4 * mains_max)))
    mains_pool = list(dict.fromkeys(mixed))

    bonus_pool: List[int] = []
    if spec.get("has_bonus"):
        bmax = spec["bonus_max"]
        bonus_pool = list(range(1, bmax + 1))
    return mains_pool, bonus_pool

def _draw_row_mains(game: str, count: int, anchor: List[int], mains_pool: List[int]) -> List[int]:
    spec = SPECS[game]
    maxn = spec["mains_max"]
    chosen = list(anchor)
    need = count - len(chosen)
    pool = [n for n in mains_pool if n not in chosen]
    if len(pool) < need:
        pool = [n for n in range(1, maxn + 1) if n not in chosen]
    chosen.extend(random.sample(pool, k=need))
    return _safe_unique_sorted(chosen, maxn)

def _draw_bonus(game: str, latest_bonus: Optional[int], hot_b: List[int] | None, over_b: List[int] | None) -> Optional[int]:
    spec = SPECS[game]
    if not spec.get("has_bonus"): return None
    bmax = spec["bonus_max"]
    r = random.random()
    if latest_bonus is not None and r < 0.25:
        return latest_bonus
    if (hot_b or over_b) and r < 0.55:
        bag = []
        if hot_b: bag.extend(hot_b[:5])
        if over_b: bag.extend(over_b[:5])
        bag = [b for b in bag if 1 <= int(b) <= bmax]
        if bag: return int(random.choice(bag))
    return random.randint(1, bmax)

# --------- History mining for Phase 2 (pairs/triples) ----------
def _parse_history_block(block: str, game: str) -> List[List[int]]:
    """
    Accepts the 20-line history textarea (one line per draw like '09-12-25  17-18-21-42-64  07').
    Returns list of mains only (ints).
    """
    lines = [ln.strip() for ln in (block or "").splitlines() if ln.strip()]
    out: List[List[int]] = []
    k = SPECS[game]["mains_count"]
    for ln in lines:
        nums = _extract_ints(ln)
        if not nums: continue
        mains = nums[-(k + (1 if SPECS[game].get("has_bonus") else 0)) : -(1 if SPECS[game].get("has_bonus") else 0) or None]
        if len(mains) == k:
            out.append(sorted(mains))
    return out

def _mine_pairs_triples(rows: List[List[int]]) -> Tuple[List[Tuple[int,int]], List[Tuple[int,int,int]]]:
    pairs = Counter()
    trips = Counter()
    for ms in rows:
        mset = sorted(set(ms))
        # pairs
        for i in range(len(mset)):
            for j in range(i+1, len(mset)):
                pairs[(mset[i], mset[j])] += 1
        # triples
        for i in range(len(mset)):
            for j in range(i+1, len(mset)):
                for k in range(j+1, len(mset)):
                    trips[(mset[i], mset[j], mset[k])] += 1
    top_pairs = [p for p,_ in pairs.most_common(20)]
    top_trips = [t for t,_ in trips.most_common(12)]
    return top_pairs, top_trips

# ------------------------------------------------------------
# Phase 1 (evaluation) — JP-anchored batches and scoring
# ------------------------------------------------------------
def _make_batch_50_phase1(game: str, latest: Tuple[List[int], Optional[int]], feed_text: str) -> List[str]:
    target_m, target_b = latest
    hot_m, over_m, hot_b, over_b = _parse_feed_block(feed_text)
    pool_m, _ = _bias_pool(game, hot_m, over_m, include=target_m)
    spec = SPECS[game]; k = spec["mains_count"]

    def anchor_pick(n_anchor: int) -> str:
        anchor = random.sample(target_m, k=n_anchor)
        row_m = _draw_row_mains(game, k, anchor, pool_m)
        row_b = _draw_bonus(game, target_b, hot_b, over_b)
        return _pretty_row(row_m, row_b)

    def pool_pick() -> str:
        row_m = _draw_row_mains(game, k, [], pool_m)
        row_b = _draw_bonus(game, target_b, hot_b, over_b)
        return _pretty_row(row_m, row_b)

    def rnd_pick() -> str:
        row_m = sorted(random.sample(range(1, spec["mains_max"] + 1), k))
        row_b = _draw_bonus(game, target_b, hot_b, over_b)
        return _pretty_row(row_m, row_b)

    rows: List[str] = []
    for _ in range(20): rows.append(anchor_pick(2))
    for _ in range(15): rows.append(anchor_pick(3))
    for _ in range(10): rows.append(pool_pick())
    for _ in range(5):  rows.append(rnd_pick())
    return rows

def _score_batch(game: str, pretty_rows: List[str], latest: Tuple[List[int], Optional[int]]) -> Dict[str, Any]:
    tgt_m, tgt_b = latest
    spec = SPECS[game]; k = spec["mains_count"]
    counts: Dict[str,int] = {}; rows_idx: Dict[str,List[int]] = {}; exact_rows: List[int] = []
    def bump(lbl, i): counts[lbl]=counts.get(lbl,0)+1; rows_idx.setdefault(lbl,[]).append(i)
    for i, pr in enumerate(pretty_rows, start=1):
        parts = pr.split()
        mains = [int(x) for x in parts[:k]]
        b = int(parts[-1]) if spec.get("has_bonus") else None
        mh, bh = _score_row(mains, b, tgt_m, tgt_b)
        if spec.get("has_bonus"):
            if mh in (3,4,5): bump(str(mh), i); 
            if mh in (3,4,5) and bh: bump(f"{mh}+B", i)
            if mh==5 and bh: exact_rows.append(i)
        else:
            if mh in (3,4,5,6): bump(str(mh), i)
            if mh==6: exact_rows.append(i)
    if spec.get("has_bonus"):
        for lbl in ("3","4","5","3+B","4+B","5+B"): counts.setdefault(lbl,0); rows_idx.setdefault(lbl,[])
    else:
        for lbl in ("3","4","5","6"): counts.setdefault(lbl,0); rows_idx.setdefault(lbl,[])
    return {"counts": counts, "rows": rows_idx, "exact_rows": exact_rows}

# ------------------------------------------------------------
# Phase 2 (prediction) — NO JP anchoring
# ------------------------------------------------------------
def _make_batch_50_phase2(game: str, feed_text: str, hist_block: str) -> Tuple[List[str], Dict[str, Any]]:
    """
    Build 50 tickets using only feeds + mined history motifs (no JP).
    Pattern mix:
      - 18 rows: anchor=pair from top mined pairs (fill from pool)
      - 12 rows: anchor=triple from top mined triples (fill from pool)
      - 12 rows: anchor=2 from hot∩overdue (if exists) else hot
      - 6  rows: pool-biased
      - 2  rows: pure random
    """
    hot_m, over_m, hot_b, over_b = _parse_feed_block(feed_text)
    hist_rows = _parse_history_block(hist_block, game)
    top_pairs, top_trips = _mine_pairs_triples(hist_rows)

    # include = union of hot/overdue to bias pool (no JP mains)
    include = sorted(list({*hot_m, *over_m}))
    pool_m, _ = _bias_pool(game, hot_m, over_m, include=include)

    spec = SPECS[game]; k = spec["mains_count"]

    def mk(pair=None, triple=None, hv2=None, use_pool=False, rnd=False) -> str:
        anchor: List[int] = []
        if triple: anchor = list(triple)[: min(3, k)]
        elif pair: anchor = list(pair)[: min(2, k)]
        elif hv2:  anchor = list(hv2)[: min(2, k)]
        row_m = _draw_row_mains(game, k, anchor, pool_m if not rnd else [])
        row_b = _draw_bonus(game, None, hot_b, over_b)  # no JP bonus
        return _pretty_row(row_m, row_b)

    # precompute a 2-element anchor from hot∩overdue (or hot fallback)
    hv = [n for n in hot_m if n in set(over_m)]
    hv2 = hv[:2] if len(hv) >= 2 else hot_m[:2] if len(hot_m) >= 2 else None

    rows: List[str] = []
    for _ in range(18):
        if top_pairs:
            rows.append(mk(pair=random.choice(top_pairs)))
        else:
            rows.append(mk(hv2=hv2))
    for _ in range(12):
        if top_trips:
            rows.append(mk(triple=random.choice(top_trips)))
        else:
            rows.append(mk(hv2=hv2))
    for _ in range(12):
        rows.append(mk(hv2=hv2))
    for _ in range(6):
        rows.append(mk(use_pool=True))
    for _ in range(2):
        rows.append(mk(rnd=True))

    # Diversity report
    mains_counts = Counter()
    for r in rows:
        mains = _extract_ints(r)[:k]
        for n in mains: mains_counts[n] += 1
    diversity = {
        "unique_mains": len({n for r in rows for n in _extract_ints(r)[:k]}),
        "top_mains": mains_counts.most_common(10),
    }
    return rows, {"diversity": diversity, "used_pairs": len(top_pairs), "used_triples": len(top_trips)}

# ------------------------------------------------------------
# Public API
# ------------------------------------------------------------
def handle_run(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    If payload['phase'] == 'phase2', generate JP-free tickets (prediction).
    Otherwise default to phase1 evaluation (JP-anchored, scored vs latest).
    """
    phase = (payload.get("phase") or "phase1").lower()

    if phase == "phase2":
        # Inputs needed:
        #   FEED_MM, FEED_PB, FEED_IL  (text blocks)
        #   HIST_MM_BLOB, HIST_PB_BLOB, HIST_IL_JP_BLOB (or M1/M2; any IL history is fine)
        feed_mm = payload.get("FEED_MM", "") or ""
        feed_pb = payload.get("FEED_PB", "") or ""
        feed_il = payload.get("FEED_IL", "") or ""
        hist_mm = payload.get("HIST_MM_BLOB", "") or ""
        hist_pb = payload.get("HIST_PB_BLOB", "") or ""
        # pick any IL history block user loaded (JP/M1/M2). Prefer JP, else M1, else M2.
        hist_il = payload.get("HIST_IL_JP_BLOB") or payload.get("HIST_IL_M1_BLOB") or payload.get("HIST_IL_M2_BLOB") or ""

        mm_batch, mm_meta = _make_batch_50_phase2("MM", feed_mm, hist_mm)
        pb_batch, pb_meta = _make_batch_50_phase2("PB", feed_pb, hist_pb)
        il_batch, il_meta = _make_batch_50_phase2("IL", feed_il, hist_il)

        return {
            "ok": True,
            "phase": "phase2",
            "echo": {
                "BATCH_MM": mm_batch,
                "BATCH_PB": pb_batch,
                "BATCH_IL": il_batch,
                "META_MM": mm_meta,
                "META_PB": pb_meta,
                "META_IL": il_meta,
            },
        }

    # -------- Phase 1 (default) --------
    mm_latest = _norm_latest(payload.get("LATEST_MM"), "MM")
    pb_latest = _norm_latest(payload.get("LATEST_PB"), "PB")
    il_jp_latest = _norm_latest(payload.get("LATEST_IL_JP"), "IL")
    il_m1_latest = _norm_latest(payload.get("LATEST_IL_M1"), "IL")
    il_m2_latest = _norm_latest(payload.get("LATEST_IL_M2"), "IL")

    feed_mm = payload.get("FEED_MM", "") or ""
    feed_pb = payload.get("FEED_PB", "") or ""
    feed_il = payload.get("FEED_IL", "") or ""

    mm_batch = _make_batch_50_phase1("MM", mm_latest, feed_mm)
    pb_batch = _make_batch_50_phase1("PB", pb_latest, feed_pb)
    il_batch = _make_batch_50_phase1("IL", il_jp_latest, feed_il)

    mm_hits = _score_batch("MM", mm_batch, mm_latest)
    pb_hits = _score_batch("PB", pb_batch, pb_latest)
    il_jp_hits = _score_batch("IL", il_batch, il_jp_latest)
    il_m1_hits = _score_batch("IL", il_batch, il_m1_latest)
    il_m2_hits = _score_batch("IL", il_batch, il_m2_latest)

    return {
        "ok": True,
        "phase": "phase1",
        "echo": {
            "BATCH_MM": mm_batch,
            "BATCH_PB": pb_batch,
            "BATCH_IL": il_batch,
            "HITS_MM": mm_hits,
            "HITS_PB": pb_hits,
            "HITS_IL_JP": il_jp_hits,
            "HITS_IL_M1": il_m1_hits,
            "HITS_IL_M2": il_m2_hits,
        },
    }

def handle_confirm(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {"ok": True, "phase": "confirm", "echo": payload}

def recent_files() -> List[str]:
    return []
