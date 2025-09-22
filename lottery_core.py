# -*- coding: utf-8 -*-
"""
Core logic:
- parse inputs (feeds, history blobs, latest jackpots)
- build VIP/LRR/Undrawn pools
- generate 50-row batches by sampling patterns
- Phase 1 (Evaluation) / Phase 2 (Prediction 100×) / Phase 3 (Confirmation)
"""

import os
import re
import json
import random
import statistics
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional, Set

DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data"))
os.makedirs(DATA_DIR, exist_ok=True)

RNG = random.Random()

# Game bounds
MM_MAIN_MAX, MM_MAIN_PICK = 70, 5
MM_BONUS_MAX = 25

PB_MAIN_MAX, PB_MAIN_PICK = 69, 5
PB_BONUS_MAX = 26

IL_MAIN_MAX, IL_MAIN_PICK = 50, 6

# ---------- Defaults (UI shows these; you will override via CSV UI) ----------

DEFAULT_INPUTS = {
    "LATEST_MM": "([10, 14, 34, 40, 43], 5)",
    "LATEST_PB": "([14, 15, 32, 42, 49], 1)",
    "LATEST_IL_JP": "([1, 4, 5, 10, 18, 49], None)",
    "LATEST_IL_M1": "([6, 8, 10, 18, 26, 27], None)",
    "LATEST_IL_M2": "([2, 18, 21, 27, 43, 50], None)",
    "HIST_MM_BLOB": """
17-18-21-42-64 07
06-43-52-64-65 22
06-14-36-58-62 24
07-17-35-40-64 23
13-31-32-44-45 21
07-12-30-40-69 17
18-30-44-48-50 12
10-19-24-49-68 10
04-17-27-34-69 16
01-08-31-56-67 23
02-06-08-14-49 12
12-27-42-59-65 02
18-27-29-33-70 22
17-30-34-63-67 11
14-21-25-49-52 07
22-41-42-59-69 17
11-43-54-55-63 03
06-10-24-35-43 01
12-23-24-31-56 01
04-06-38-44-62 24
""",
    "HIST_PB_BLOB": """
28-37-42-50-53 19
02-24-45-53-64 05
26-28-41-53-64 09
11-23-44-61-62 17
03-16-29-61-69 22
08-23-25-40-53 05
03-18-22-27-33 17
09-12-22-41-61 25
16-19-34-37-64 22
11-14-34-47-51 18
31-59-62-65-68 05
15-46-61-63-64 01
23-40-49-65-69 23
04-11-40-44-50 04
06-16-33-40-62 02
07-14-23-24-60 14
15-27-43-45-53 09
08-09-19-31-38 21
06-18-34-35-36 02
04-15-35-50-64 08
""",
    "HIST_IL_BLOB": """
05-06-14-15-48-49
01-08-12-27-30-43
05-07-20-26-34-40
11-12-29-42-44-47
01-16-20-29-30-49
12-14-20-21-23-43
06-07-11-15-41-50
05-12-18-19-34-47
05-09-14-18-22-23
02-11-15-17-32-34
09-17-20-24-41-44
01-04-06-13-17-27
03-26-31-36-41-45
09-12-16-17-25-44
09-17-22-30-42-45
04-12-31-32-39-40
14-17-19-32-34-42
03-10-11-30-36-41
04-18-31-39-45-48
03-06-11-16-32-36
""",
    "FEED_PB": """
Top 8 hot numbers: 23, 61, 35, 28, 43, 62, 64, 52
Top 8 overdue numbers: 66, 39, 20, 10, 56, 30, 17, 32
Top 3 hot Power Ball numbers: 25, 5, 2
Top 3 overdue Power Ball numbers: 16, 26, 7
""",
    "FEED_MM": """
Top 8 hot numbers: 10, 40, 6, 17, 24, 18, 16, 49
Top 8 overdue numbers: 53, 3, 5, 15, 51, 9, 66, 37
Top 3 hot Mega Ball numbers: 1, 24, 2
Top 3 overdue Mega Ball numbers: 4, 6, 15
""",
    "FEED_IL": """
Top 8 hot numbers: 17, 20, 22, 14, 5, 1, 6, 3
Top 8 overdue numbers: 28, 35, 46, 38, 33, 37, 39, 25
"""
}

def normalize_inputs(**raw) -> Dict[str, str]:
    out = deepcopy(DEFAULT_INPUTS)
    for k, v in raw.items():
        if k in out and isinstance(v, str) and v.strip():
            out[k] = v
    return out

# ---------- parsing helpers ----------

_num_re = re.compile(r"\d+")

def _grab_ints(line: str) -> List[int]:
    return list(map(int, _num_re.findall(line)))

def parse_latest(text: str) -> Tuple[List[int], Optional[int]]:
    try:
        arr = eval(text, {}, {})
        mains, bonus = arr
        return list(map(int, mains)), (None if bonus is None else int(bonus))
    except Exception:
        ints = _grab_ints(text)
        if len(ints) >= 5:
            mains, rest = ints[:5], ints[5:]
            bonus = rest[0] if rest else None
            return mains, bonus
        raise

def parse_hist_blob(blob: str) -> List[Tuple[List[int], Optional[int]]]:
    lines = [ln.strip() for ln in (blob or "").strip().splitlines() if ln.strip()]
    draws = []
    for ln in lines:
        parts = ln.split()
        mains = _grab_ints(parts[0])
        bonus = None
        if len(parts) > 1:
            rest = _grab_ints(parts[1])
            if rest:
                bonus = rest[0]
        draws.append((sorted(mains), bonus))
    return draws[-20:]  # keep last 20

def parse_feed(feed_blob: str) -> Dict[str, List[int]]:
    d = {"hot": [], "overdue": [], "bonus_hot": [], "bonus_overdue": []}
    for ln in (feed_blob or "").strip().splitlines():
        s = ln.strip().lower()
        if s.startswith("top 8 hot numbers"):
            d["hot"] = _grab_ints(ln)
        elif s.startswith("top 8 overdue numbers"):
            d["overdue"] = _grab_ints(ln)
        elif "hot power ball" in s or "hot mega ball" in s:
            d["bonus_hot"] = _grab_ints(ln)
        elif "overdue power ball" in s or "overdue mega ball" in s:
            d["bonus_overdue"] = _grab_ints(ln)
    return d

def middle_band_from_history(history: List[List[int]]) -> Tuple[int, int]:
    sums = [sum(row) for row in history]
    if not sums:
        return (0, 10**9)
    p25 = int(statistics.quantiles(sums, n=4)[0])
    p75 = int(statistics.quantiles(sums, n=4)[2])
    return (min(p25, p75), max(p25, p75))

def last_n(history: List[List[int]], n: int) -> List[List[int]]:
    return history[-n:] if len(history) >= n else history

# ---------- anchor pools ----------

def undrawn_pool(main_max: int, last10: List[List[int]]) -> Set[int]:
    seen = set(num for row in last10 for num in row)
    return set(range(1, main_max + 1)) - seen

def lrr_candidates(history20: List[List[int]], recent5: List[List[int]]) -> List[int]:
    cnt = Counter(num for row in history20 for num in row)
    recent_seen = set(num for row in recent5 for num in row)
    out = [n for n, c in cnt.items() if c == 2 and n not in recent_seen]
    return sorted(out)

def pick_bonus(bonus_max: int, feed_bonus_hot: List[int], feed_bonus_overdue: List[int], last10_bonus: List[int]) -> int:
    recent = set(last10_bonus)
    undrawn = [b for b in range(1, bonus_max + 1) if b not in recent]
    pool = list(set(feed_bonus_hot + feed_bonus_overdue + undrawn))
    RNG.shuffle(pool)
    return RNG.choice(pool) if pool else RNG.randint(1, bonus_max)

# ---------- patterns ----------

MM_PB_PATTERNS = [
    ("VIP", {"hot":1, "overdue":0, "undrawn":3}),
    ("VIP", {"hot":1, "overdue":1, "undrawn":2}),
    ("VIP", {"hot":1, "overdue":2, "undrawn":1}),
    ("VIP", {"hot":2, "overdue":0, "undrawn":2}),
    ("VIP", {"hot":2, "overdue":1, "undrawn":1}),
    ("VIP", {"hot":3, "overdue":0, "undrawn":1}),
    ("VIP", {"hot":0, "overdue":1, "undrawn":3}),
    ("VIP", {"hot":0, "overdue":2, "undrawn":2}),
    ("VIP", {"hot":0, "overdue":3, "undrawn":1}),
    ("LRR", {"hot":1, "overdue":0, "undrawn":3}),
    ("LRR", {"hot":1, "overdue":1, "undrawn":2}),
    ("LRR", {"hot":1, "overdue":2, "undrawn":1}),
    ("LRR", {"hot":2, "overdue":0, "undrawn":2}),
    ("LRR", {"hot":2, "overdue":1, "undrawn":1}),
    ("LRR", {"hot":3, "overdue":0, "undrawn":1}),
    ("LRR", {"hot":0, "overdue":1, "undrawn":3}),
    ("LRR", {"hot":0, "overdue":2, "undrawn":2}),
    ("LRR", {"hot":0, "overdue":3, "undrawn":1}),
]

IL_PATTERNS = [
    ("VIP", {"hot":1,"overdue":0,"undrawn":4}),
    ("VIP", {"hot":1,"overdue":1,"undrawn":3}),
    ("VIP", {"hot":1,"overdue":2,"undrawn":2}),
    ("VIP", {"hot":1,"overdue":3,"undrawn":1}),
    ("VIP", {"hot":2,"overdue":0,"undrawn":3}),
    ("VIP", {"hot":2,"overdue":1,"undrawn":2}),
    ("VIP", {"hot":2,"overdue":2,"undrawn":1}),
    ("VIP", {"hot":2,"overdue":3,"undrawn":0}),
    ("VIP", {"hot":3,"overdue":0,"undrawn":2}),
    ("VIP", {"hot":3,"overdue":1,"undrawn":1}),
    ("VIP", {"hot":3,"overdue":2,"undrawn":0}),
    ("VIP", {"hot":4,"overdue":0,"undrawn":1}),
    ("VIP", {"hot":4,"overdue":1,"undrawn":0}),
    ("VIP", {"hot":5,"overdue":0,"undrawn":0}),
    ("VIP", {"hot":0,"overdue":1,"undrawn":4}),
    ("VIP", {"hot":0,"overdue":2,"undrawn":3}),
    ("VIP", {"hot":0,"overdue":3,"undrawn":3}),
    ("VIP", {"hot":0,"overdue":4,"undrawn":1}),
    ("VIP", {"hot":0,"overdue":5,"undrawn":0}),
    ("LRR", {"hot":1,"overdue":0,"undrawn":4}),
    ("LRR", {"hot":1,"overdue":1,"undrawn":3}),
    ("LRR", {"hot":1,"overdue":2,"undrawn":2}),
    ("LRR", {"hot":1,"overdue":3,"undrawn":1}),
    ("LRR", {"hot":2,"overdue":0,"undrawn":3}),
    ("LRR", {"hot":2,"overdue":1,"undrawn":2}),
    ("LRR", {"hot":2,"overdue":2,"undrawn":1}),
    ("LRR", {"hot":2,"overdue":3,"undrawn":0}),
    ("LRR", {"hot":3,"overdue":0,"undrawn":2}),
    ("LRR", {"hot":3,"overdue":1,"undrawn":1}),
    ("LRR", {"hot":3,"overdue":2,"undrawn":0}),
    ("LRR", {"hot":4,"overdue":0,"undrawn":1}),
    ("LRR", {"hot":4,"overdue":1,"undrawn":0}),
    ("LRR", {"hot":5,"overdue":0,"undrawn":0}),
    ("LRR", {"hot":0,"overdue":1,"undrawn":4}),
    ("LRR", {"hot":0,"overdue":2,"undrawn":3}),
    ("LRR", {"hot":0,"overdue":3,"undrawn":3}),
    ("LRR", {"hot":0,"overdue":4,"undrawn":1}),
    ("LRR", {"hot":0,"overdue":5,"undrawn":0}),
]

# ---------- generation ----------

def _choose_from(pool: Set[int], k: int, avoid: Set[int]) -> List[int]:
    choices = list(pool - avoid)
    RNG.shuffle(choices)
    return sorted(choices[:k])

def _next_anchor(anchor_kind: str, vip_list: List[int], lrr_list: List[int], anchor_index: Dict[str, int]) -> Optional[int]:
    if anchor_kind == "VIP" and vip_list:
        i = anchor_index.setdefault("VIP", 0) % len(vip_list)
        anchor_index["VIP"] += 1
        return vip_list[i]
    if anchor_kind == "LRR" and lrr_list:
        i = anchor_index.setdefault("LRR", 0) % len(lrr_list)
        anchor_index["LRR"] += 1
        return lrr_list[i]
    return None

def generate_batch(
    main_max: int,
    main_pick: int,
    bonus_max: Optional[int],
    history20: List[List[int]],
    bonus20: List[Optional[int]],
    feed_hot: List[int],
    feed_overdue: List[int],
    feed_bonus_hot: List[int],
    feed_bonus_overdue: List[int],
    patterns: List[Tuple[str, Dict[str, int]]],
    rows: int = 50,
) -> Tuple[List[Tuple[List[int], Optional[int], Dict]], Tuple[int,int]]:
    last10 = last_n(history20, 10)
    recent5 = last_n(history20, 5)
    undrawn = undrawn_pool(main_max, last10)
    hot = set(feed_hot)
    overdue = set(feed_overdue)
    vip = sorted(hot & overdue)
    lrr = lrr_candidates(history20, recent5)
    band = middle_band_from_history(history20)

    anchor_index = {}
    out = []
    pat_index = 0

    last10_bonus = [b for b in (bonus20[-10:] if len(bonus20) >= 10 else bonus20) if b]

    for _ in range(rows):
        anchor_kind, need = patterns[pat_index % len(patterns)]
        pat_index += 1

        anchor = _next_anchor(anchor_kind, vip, lrr, anchor_index)
        mains: Set[int] = set()
        if anchor is not None:
            mains.add(anchor)

        avoid = set(mains)
        if need.get("hot", 0):
            pool = hot - avoid
            mains.update(_choose_from(pool, need["hot"], avoid=set()))
            avoid = set(mains)
        if need.get("overdue", 0):
            pool = overdue - avoid
            mains.update(_choose_from(pool, need["overdue"], avoid=set()))
            avoid = set(mains)
        if need.get("undrawn", 0):
            pool = undrawn - avoid
            mains.update(_choose_from(pool, need["undrawn"], avoid=set()))
            avoid = set(mains)

        while len(mains) < main_pick:
            pool = (undrawn | hot | overdue) - mains
            if not pool:
                pool = set(range(1, main_max + 1)) - mains
            mains.add(RNG.choice(list(pool)))

        mains = sorted(mains)

        # enforce middle-50% band (resample one non-anchor up to 4 tries)
        s = sum(mains)
        tries = 0
        while not (band[0] <= s <= band[1]) and tries < 4:
            replaceable = [x for x in mains if x != anchor]
            if not replaceable:
                break
            throw = RNG.choice(replaceable)
            pool = (undrawn | hot | overdue | set(range(1, main_max + 1))) - set(mains)
            if not pool:
                break
            mains[mains.index(throw)] = RNG.choice(sorted(pool))
            mains = sorted(mains)
            s = sum(mains)
            tries += 1

        bonus = None
        if bonus_max:
            bonus = pick_bonus(bonus_max, feed_bonus_hot, feed_bonus_overdue, last10_bonus)

        meta = {"anchor_kind": anchor_kind, "anchor": anchor, "sum": sum(mains)}
        out.append((mains, bonus, meta))

    return out, band

# ---------- scoring ----------

def compare_row(mains: List[int], bonus: Optional[int], target_mains: List[int], target_bonus: Optional[int]) -> Tuple[int, bool]:
    hits = len(set(mains) & set(target_mains))
    bonus_hit = (bonus is not None and target_bonus is not None and bonus == target_bonus)
    return hits, bonus_hit

def summarize_hits(batch: List[Tuple[List[int], Optional[int], Dict]], target: Tuple[List[int], Optional[int]], is_il: bool) -> Dict:
    positions_by_key = defaultdict(list)
    total_by_key = Counter()
    t_mains, t_bonus = target

    for idx, (m, b, _) in enumerate(batch, start=1):
        hits, bonus_hit = compare_row(m, b, t_mains, t_bonus)
        if is_il:
            if hits >= 3:
                key = f"{hits}-ball" if hits < 6 else "6-ball"
                positions_by_key[key].append(idx)
                total_by_key[key] += 1
        else:
            if hits >= 3:
                if hits == 3:
                    key = "3-ball+bonus" if bonus_hit else "3-ball"
                elif hits == 4:
                    key = "4-ball+bonus" if bonus_hit else "4-ball"
                elif hits == 5:
                    key = "5-ball+bonus" if bonus_hit else "5-ball"
                else:
                    key = f"{hits}-ball"
                positions_by_key[key].append(idx)
                total_by_key[key] += 1

    return {"positions": {k: sorted(v) for k, v in positions_by_key.items()},
            "totals_in_batch": dict(total_by_key)}

def score_ticket(mains: List[int], hot: Set[int], overdue: Set[int], vip_set: Set[int], band: Tuple[int,int]) -> float:
    s = 0.0
    s += 1.3 * len(set(mains) & hot)
    s += 1.1 * len(set(mains) & overdue)
    s += 1.6 * len(set(mains) & vip_set)
    total = sum(mains)
    if band[0] and band[1] and band[1] > band[0]:
        mid = 0.5 * (band[0] + band[1])
        s += 0.8 * (1.0 - abs(total - mid) / max(1, band[1] - band[0]))
    s += 0.2 * (max(mains) - min(mains))
    return s

def unique_key(mains: List[int], bonus: Optional[int]) -> str:
    return f"{'-'.join(f'{x:02d}' for x in mains)}" + (f" {bonus:02d}" if bonus else "")

# ---------- phases ----------

@dataclass
class GameInputs:
    history: List[Tuple[List[int], Optional[int]]]
    feed: Dict[str, List[int]]
    latest_target: Tuple[List[int], Optional[int]]
    main_max: int
    main_pick: int
    bonus_max: Optional[int]
    patterns: List[Tuple[str, Dict[str, int]]]
    is_il: bool

def _build_game_inputs(payload: Dict[str, str]) -> Dict[str, GameInputs]:
    hist_mm = parse_hist_blob(payload["HIST_MM_BLOB"])
    hist_pb = parse_hist_blob(payload["HIST_PB_BLOB"])
    hist_il = parse_hist_blob(payload["HIST_IL_BLOB"])

    feeds = {"MM": parse_feed(payload["FEED_MM"]),
             "PB": parse_feed(payload["FEED_PB"]),
             "IL": parse_feed(payload["FEED_IL"])}

    latests_phase1 = {
        "MM": parse_latest(payload["LATEST_MM"]),
        "PB": parse_latest(payload["LATEST_PB"]),
        "IL_JP": parse_latest(payload["LATEST_IL_JP"]),
        "IL_M1": parse_latest(payload["LATEST_IL_M1"]),
        "IL_M2": parse_latest(payload["LATEST_IL_M2"]),
    }

    return {
        "MM": GameInputs(hist_mm, feeds["MM"], latests_phase1["MM"], MM_MAIN_MAX, MM_MAIN_PICK, MM_BONUS_MAX, MM_PB_PATTERNS, False),
        "PB": GameInputs(hist_pb, feeds["PB"], latests_phase1["PB"], PB_MAIN_MAX, PB_MAIN_PICK, PB_BONUS_MAX, MM_PB_PATTERNS, False),
        "IL": GameInputs(hist_il, feeds["IL"], latests_phase1["IL_JP"], IL_MAIN_MAX, IL_MAIN_PICK, None, IL_PATTERNS, True),
    }

def run_phase_1(payload: Dict[str, str]) -> Dict:
    games = _build_game_inputs(payload)
    out = {"ok": True, "phase": "eval", "batches": {}, "hit_summaries": {}}

    for code in ("MM", "PB"):
        g = games[code]
        batch, band = generate_batch(
            g.main_max, g.main_pick, g.bonus_max,
            [m for m, _ in g.history],
            [b for _, b in g.history],
            g.feed.get("hot", []),
            g.feed.get("overdue", []),
            g.feed.get("bonus_hot", []),
            g.feed.get("bonus_overdue", []),
            g.patterns,
            rows=50
        )
        out["batches"][code] = {"band": band}
        out["hit_summaries"][code] = summarize_hits(batch, g.latest_target, g.is_il)

    g = games["IL"]
    batch_il, band_il = generate_batch(
        g.main_max, g.main_pick, g.bonus_max,
        [m for m, _ in g.history],
        [b for _, b in g.history],
        g.feed.get("hot", []),
        g.feed.get("overdue", []),
        [], [],
        g.patterns,
        rows=50
    )
    il_targets = {
        "JP": parse_latest(payload["LATEST_IL_JP"]),
        "M1": parse_latest(payload["LATEST_IL_M1"]),
        "M2": parse_latest(payload["LATEST_IL_M2"]),
    }
    out["batches"]["IL"] = {"band": band_il}
    out["hit_summaries"]["IL"] = {label: summarize_hits(batch_il, target, True) for label, target in il_targets.items()}
    return out

def _promote_newest_to_top(history: List[Tuple[List[int], Optional[int]]], newest: Tuple[List[int], Optional[int]]) -> List[Tuple[List[int], Optional[int]]]:
    newhist = deepcopy(history) + [deepcopy(newest)]
    return newhist[-20:]

def _aggregate_over_runs(gen_fn, runs: int = 100):
    freq = Counter()
    details = defaultdict(list)
    bands_seen = []
    for _ in range(runs):
        batch, band = gen_fn()
        bands_seen.append(band)
        for (m, b, meta) in batch:
            key = unique_key(m, b)
            freq[key] += 1
            details[key].append({"m": m, "b": b, **meta})
    p25 = int(sum(b[0] for b in bands_seen) / len(bands_seen))
    p75 = int(sum(b[1] for b in bands_seen) / len(bands_seen))
    return freq, details, (p25, p75)

def run_phase_2(payload: Dict[str, str]) -> Dict:
    games = _build_game_inputs(payload)
    results = {"ok": True, "phase": "predict", "stats": {}, "buy_lists": {}}

    for code in ("MM", "PB"):
        g = games[code]
        promoted = _promote_newest_to_top(g.history, g.latest_target)
        hot, overdue = set(g.feed.get("hot", [])), set(g.feed.get("overdue", []))
        vip_set = hot & overdue

        def gen():
            return generate_batch(
                g.main_max, g.main_pick, g.bonus_max,
                [m for m, _ in promoted],
                [b for _, b in promoted],
                g.feed.get("hot", []),
                g.feed.get("overdue", []),
                g.feed.get("bonus_hot", []),
                g.feed.get("bonus_overdue", []),
                g.patterns,
                rows=50
            )

        freq, details, band = _aggregate_over_runs(gen, runs=100)

        scored = []
        for key, c in freq.items():
            any_row = details[key][0]
            mains = any_row["m"]
            score = score_ticket(mains, hot, overdue, vip_set, band)
            scored.append((key, c, score))
        scored.sort(key=lambda x: (x[1], x[2]), reverse=True)

        top_n = 10
        picks, seen = [], set()
        for key, c, sc in scored:
            parts = key.split()
            mains = [int(x) for x in parts[0].split("-")]
            bonus = int(parts[1]) if len(parts) > 1 else None
            k2 = tuple(mains) + ((bonus,) if bonus is not None else ())
            if k2 in seen:
                continue
            seen.add(k2)
            picks.append({"mains": mains, "bonus": bonus, "freq": c, "score": round(sc, 3)})
            if len(picks) >= top_n:
                break

        results["buy_lists"][code] = {"band_avg": band, "tickets": picks}
        results["stats"][code] = {"unique_rows": len(freq), "most_common_freq": max(freq.values()) if freq else 0}

    g = games["IL"]
    promoted = _promote_newest_to_top(g.history, parse_latest(payload["LATEST_IL_JP"]))
    hot, overdue = set(g.feed.get("hot", [])), set(g.feed.get("overdue", []))
    vip_set = hot & overdue

    def gen_il():
        return generate_batch(
            g.main_max, g.main_pick, g.bonus_max,
            [m for m, _ in promoted],
            [b for _, b in promoted],
            g.feed.get("hot", []),
            g.feed.get("overdue", []),
            [], [],
            g.patterns,
            rows=50
        )

    freq, details, band = _aggregate_over_runs(gen_il, runs=100)
    scored = []
    for key, c in freq.items():
        mains = [int(x) for x in key.split("-")]
        score = score_ticket(mains, hot, overdue, vip_set, band)
        scored.append((key, c, score))
    scored.sort(key=lambda x: (x[1], x[2]), reverse=True)

    top_n = 15
    picks, seen = [], set()
    for key, c, sc in scored:
        mains = [int(x) for x in key.split("-")]
        k2 = tuple(mains)
        if k2 in seen:
            continue
        seen.add(k2)
        picks.append({"mains": mains, "freq": c, "score": round(sc, 3)})
        if len(picks) >= top_n:
            break

    results["buy_lists"]["IL"] = {"band_avg": band, "tickets": picks}
    results["stats"]["IL"] = {"unique_rows": len(freq), "most_common_freq": max(freq.values()) if freq else 0}
    return results

def run_phase_3(buy_lists: Dict, payload_with_nwj: Dict[str, str]) -> Dict:
    targets = {
        "MM": parse_latest(payload_with_nwj.get("LATEST_MM", "")),
        "PB": parse_latest(payload_with_nwj.get("LATEST_PB", "")),
        "IL_JP": parse_latest(payload_with_nwj.get("LATEST_IL_JP", "")),
        "IL_M1": parse_latest(payload_with_nwj.get("LATEST_IL_M1", "")),
        "IL_M2": parse_latest(payload_with_nwj.get("LATEST_IL_M2", "")),
    }

    out = {"ok": True, "phase": "confirm", "results": {}}

    for code in ("MM", "PB"):
        bl = buy_lists.get(code, {}).get("tickets", [])
        t = targets[code]
        hits = []
        for i, tkt in enumerate(bl, start=1):
            mains = tkt["mains"]
            bonus = tkt.get("bonus")
            match, bonus_hit = compare_row(mains, bonus, t[0], t[1])
            hits.append({"idx": i, "mains": mains, "bonus": bonus, "match_mains": match, "bonus_hit": bool(bonus_hit)})
        out["results"][code] = hits

    bl = buy_lists.get("IL", {}).get("tickets", [])
    for label in ("IL_JP", "IL_M1", "IL_M2"):
        t = targets[label]
        hits = []
        for i, tkt in enumerate(bl, start=1):
            mains = tkt["mains"]
            match, _ = compare_row(mains, None, t[0], None)
            hits.append({"idx": i, "mains": mains, "match_mains": match, "six_ball": (match == 6)})
        out["results"][label] = hits

    return out
