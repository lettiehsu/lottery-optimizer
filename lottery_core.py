# lottery_core.py
from __future__ import annotations

import json, random, time
from typing import Any, Dict, List, Optional, Tuple

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
    """
    Accepts: [[m1..], bonus]  OR stringified version of the same (from UI preview).
    For IL, bonus may be None.
    Returns (mains_sorted, bonus_or_None)
    """
    if isinstance(val, str):
        val = json.loads(val)
    if not isinstance(val, list) or len(val) != 2:
        raise ValueError("LATEST_* must be like [[..], b] or [[..], null]")

    mains, bonus = val
    if not isinstance(mains, list) or len(mains) < 5:
        raise ValueError("LATEST mains are malformed")

    mains = sorted(int(x) for x in mains)
    if SPECS[game].get("has_bonus"):
        b = None if bonus is None else int(bonus)
    else:
        b = None
    return mains, b


def _pretty_row(mains: List[int], bonus: Optional[int]) -> str:
    s = " ".join(f"{n:02d}" for n in mains)
    return f"{s}  {bonus:02d}" if bonus is not None else s


def _score_row(
    row_mains: List[int],
    row_bonus: Optional[int],
    target_mains: List[int],
    target_bonus: Optional[int],
) -> Tuple[int, bool]:
    """Return (#mains matched, bonus_matched?)."""
    mains_hit = len(set(row_mains) & set(target_mains))
    b_hit = (row_bonus is not None and target_bonus is not None and row_bonus == target_bonus)
    return mains_hit, b_hit


def _safe_unique_sorted(nums: List[int], limit: int) -> List[int]:
    """De-dup and sort; if duplicates were generated, refill randomly within 1..limit."""
    s = set(nums)
    while len(s) < len(nums):
        s.add(random.randint(1, limit))
    out = sorted(s)[: len(nums)]
    return out


def _bias_pool(
    game: str,
    hot: List[int] | None,
    overdue: List[int] | None,
    include: List[int] | None,
) -> Tuple[List[int], List[int]]:
    """
    Build (mains_pool, bonus_pool) with bias.
    include = target mains (so we can anchor).
    """
    spec = SPECS[game]
    mains_max = spec["mains_max"]
    mains_pool = []

    # bias: include + hot + overdue, then fill to size
    if include:
        mains_pool.extend(include)
    if hot:
        mains_pool.extend(hot[:12])  # keep short
    if overdue:
        mains_pool.extend(overdue[:12])

    # normalize and lightly expand
    mains_pool = [n for n in mains_pool if 1 <= int(n) <= mains_max]
    mains_pool = list(dict.fromkeys(mains_pool))  # uniq, keep order

    # Ensure at least half of the space is available; fill with all numbers so we can sample fairly.
    full = list(range(1, mains_max + 1))
    extras = [x for x in full if x not in mains_pool]
    # Blend: 60% biased, 40% uniform
    mixed = mains_pool + random.sample(extras, k=max(0, int(0.4 * mains_max)))
    mains_pool = list(dict.fromkeys(mixed))

    # bonus pool (for MM/PB only)
    bonus_pool: List[int] = []
    if spec.get("has_bonus"):
        bmax = spec["bonus_max"]
        # small bias around 2nd newest bonus if caller wants to feed it later
        bonus_pool = list(range(1, bmax + 1))

    return mains_pool, bonus_pool


def _draw_row_mains(
    game: str, count: int, anchor: List[int], mains_pool: List[int]
) -> List[int]:
    """
    Pick `count` mains. If anchor present (2-3 numbers), include them, fill remainder from pool.
    """
    spec = SPECS[game]
    maxn = spec["mains_max"]

    chosen = list(anchor)
    need = count - len(chosen)
    # heavier bias from pool; fallback to full space
    pool = [n for n in mains_pool if n not in chosen]
    if len(pool) < need:
        pool = [n for n in range(1, maxn + 1) if n not in chosen]
    chosen.extend(random.sample(pool, k=need))
    return _safe_unique_sorted(chosen, maxn)


def _draw_bonus(game: str, latest_bonus: Optional[int], hot_b: List[int] | None, overdue_b: List[int] | None) -> Optional[int]:
    spec = SPECS[game]
    if not spec.get("has_bonus"):
        return None
    bmax = spec["bonus_max"]

    # Mixture: sometimes re-use the 2nd newest, sometimes hot / overdue, sometimes random
    r = random.random()
    if latest_bonus is not None and r < 0.25:
        return latest_bonus
    if (hot_b or overdue_b) and r < 0.55:
        bag = []
        if hot_b:     bag.extend(hot_b[:5])
        if overdue_b: bag.extend(overdue_b[:5])
        bag = [b for b in bag if 1 <= int(b) <= bmax]
        if bag:
            return int(random.choice(bag))
    return random.randint(1, bmax)


# ------------------------------------------------------------
# Phase 1: batch builder + scorer
# ------------------------------------------------------------
def _parse_feed_block(feed_text: str) -> Tuple[List[int], List[int], List[int], List[int]]:
    """
    Accepts one of FEED_MM / FEED_PB blocks as raw text.
    Tries to extract hot / overdue mains and hot / overdue bonus (3 numbers).
    Returns (hot_m, over_m, hot_b, over_b).
    For IL, only mains will be used.
    """
    hot_m: List[int] = []
    over_m: List[int] = []
    hot_b: List[int] = []
    over_b: List[int] = []

    t = (feed_text or "").replace(",", " ").replace("\n", " ")
    # crude extraction; robust to varied spacing
    def take_after(label: str, limit: int = 16) -> List[int]:
        idx = t.find(label)
        if idx < 0:
            return []
        frag = t[idx + len(label) : idx + len(label) + 120]
        nums = []
        for tok in frag.split():
            if tok.isdigit():
                nums.append(int(tok))
            if len(nums) >= limit:
                break
        return nums

    hot_m = take_after("Top 8 hot numbers:")
    over_m = take_after("Top 8 overdue numbers:")
    hot_b = take_after("Top 3 hot Mega Ball numbers:")
    if not hot_b:
        hot_b = take_after("Top 3 hot Power Ball numbers:")
    over_b = take_after("Top 3 overdue Mega Ball numbers:")
    if not over_b:
        over_b = take_after("Top 3 overdue Power Ball numbers:")

    return hot_m, over_m, hot_b, over_b


def _make_batch_50(
    game: str,
    latest: Tuple[List[int], Optional[int]],
    feed_text: str,
    seed: Optional[int] = None,
) -> Tuple[List[str], Dict[str, Any]]:
    """
    Build 50 rows using a pattern mixture that keeps realistic hit rates:
      - 20 rows: anchor-2 (choose 2 from target, 3/4 from pool)
      - 15 rows: anchor-3 (choose 3 from target, 2/3 from pool)
      - 10 rows: pool-biased (no anchor)
      - 5  rows: pure random
    Returns (pretty_rows, meta) where meta has internals we may want later.
    """
    if seed is None:
        seed = int(time.time() * 1e6) ^ random.getrandbits(32)
    rnd = random.Random(seed)

    # use local RNG to keep batches independent of global random
    saved_state = random.getstate()
    random.setstate(rnd.getstate())

    try:
        target_m, target_b = latest
        hot_m, over_m, hot_b, over_b = _parse_feed_block(feed_text)
        pool_m, _ = _bias_pool(game, hot_m, over_m, include=target_m)

        spec = SPECS[game]
        k = spec["mains_count"]

        def anchor_pick(num_anchor: int) -> List[int]:
            anchor = random.sample(target_m, k=num_anchor)
            row_m = _draw_row_mains(game, k, anchor, pool_m)
            row_b = _draw_bonus(game, target_b, hot_b, over_b)
            return row_m + ([row_b] if row_b is not None else [])

        def pool_pick() -> List[int]:
            row_m = _draw_row_mains(game, k, [], pool_m)
            row_b = _draw_bonus(game, target_b, hot_b, over_b)
            return row_m + ([row_b] if row_b is not None else [])

        def random_pick() -> List[int]:
            row_m = sorted(random.sample(range(1, spec["mains_max"] + 1), k))
            row_b = _draw_bonus(game, target_b, hot_b, over_b)
            return row_m + ([row_b] if row_b is not None else [])

        rows: List[List[int]] = []
        # 20 anchor-2
        for _ in range(20):
            rows.append(anchor_pick(2))
        # 15 anchor-3
        for _ in range(15):
            rows.append(anchor_pick(3))
        # 10 pool-biased
        for _ in range(10):
            rows.append(pool_pick())
        # 5 pure random
        for _ in range(5):
            rows.append(random_pick())

        pretty = []
        for r in rows:
            mains = r[:k]
            bonus = r[k] if len(r) > k else None
            pretty.append(_pretty_row(mains, bonus))

        return pretty, {"seed": seed, "target": {"mains": target_m, "bonus": target_b}}
    finally:
        # restore global RNG
        random.setstate(saved_state)


def _score_batch(
    game: str,
    pretty_rows: List[str],
    latest: Tuple[List[int], Optional[int]],
) -> Dict[str, Any]:
    """Return counts + row indices for hit categories."""
    target_m, target_b = latest
    spec = SPECS[game]
    k = spec["mains_count"]

    counts: Dict[str, int] = {}
    rows_idx: Dict[str, List[int]] = {}
    exact_rows: List[int] = []

    def bump(lbl: str, idx: int):
        counts[lbl] = counts.get(lbl, 0) + 1
        rows_idx.setdefault(lbl, []).append(idx)

    for i, pr in enumerate(pretty_rows, start=1):
        parts = pr.split()
        mains = [int(x) for x in parts[:k]]
        b = int(parts[-1]) if spec.get("has_bonus") else None

        mh, b_hit = _score_row(mains, b, target_m, target_b)

        if spec.get("has_bonus"):
            # MM / PB
            if mh in (3, 4, 5):
                bump(str(mh), i)
                if b_hit:
                    bump(f"{mh}+B", i)
            # exact 5+B (jackpot) — rare, but track rows
            if mh == 5 and b_hit:
                exact_rows.append(i)
        else:
            # IL: 3/4/5/6 mains only
            if mh in (3, 4, 5, 6):
                bump(str(mh), i)
            if mh == 6:
                exact_rows.append(i)

    # ensure all expected buckets exist
    if spec.get("has_bonus"):
        for lbl in ("3", "4", "5", "3+B", "4+B", "5+B"):
            counts.setdefault(lbl, 0)
            rows_idx.setdefault(lbl, [])
    else:
        for lbl in ("3", "4", "5", "6"):
            counts.setdefault(lbl, 0)
            rows_idx.setdefault(lbl, [])

    return {"counts": counts, "rows": rows_idx, "exact_rows": exact_rows}


# ------------------------------------------------------------
# Public API used by Flask route
# ------------------------------------------------------------
def handle_run(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Phase 1 handler.
    Expected keys (strings):
      LATEST_MM, LATEST_PB, LATEST_IL_JP, LATEST_IL_M1, LATEST_IL_M2
      FEED_MM, FEED_PB, FEED_IL
    Also optional: phase == "phase1"
    """
    # Parse latests
    mm_latest = _norm_latest(payload.get("LATEST_MM"), "MM")
    pb_latest = _norm_latest(payload.get("LATEST_PB"), "PB")
    il_jp_latest = _norm_latest(payload.get("LATEST_IL_JP"), "IL")
    il_m1_latest = _norm_latest(payload.get("LATEST_IL_M1"), "IL")
    il_m2_latest = _norm_latest(payload.get("LATEST_IL_M2"), "IL")

    # Feeds (raw text blocks)
    feed_mm = payload.get("FEED_MM", "") or ""
    feed_pb = payload.get("FEED_PB", "") or ""
    feed_il = payload.get("FEED_IL", "") or ""

    # Build 50-row batches
    mm_batch, _ = _make_batch_50("MM", mm_latest, feed_mm)
    pb_batch, _ = _make_batch_50("PB", pb_latest, feed_pb)

    # IL: build one 50 using JP/M1/M2 all sharing the same sampling bias
    # (that’s fine because scoring is per-target)
    il_batch, _ = _make_batch_50("IL", il_jp_latest, feed_il)

    # Score
    mm_hits = _score_batch("MM", mm_batch, mm_latest)
    pb_hits = _score_batch("PB", pb_batch, pb_latest)
    il_jp_hits = _score_batch("IL", il_batch, il_jp_latest)
    il_m1_hits = _score_batch("IL", il_batch, il_m1_latest)
    il_m2_hits = _score_batch("IL", il_batch, il_m2_latest)

    out = {
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
    return out


def handle_confirm(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {"ok": True, "phase": "confirm", "echo": payload}


def recent_files() -> List[str]:
    # Kept for your /recent endpoint
    return []
