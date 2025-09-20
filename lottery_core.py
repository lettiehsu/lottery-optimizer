#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import os, json, random, statistics, datetime as dt
from collections import Counter, defaultdict
from typing import List, Tuple, Optional, Dict, Iterable, Set
from contextlib import redirect_stdout
import io

"""
Lottery Optimizer — Mega Millions, Powerball, Illinois Lotto
============================================================
DISCLAIMER: Statistical toy. Lotteries are random and negative EV. Use responsibly.
This module is used both as a CLI script and as a library for the Flask app.
"""

# ────────────────────────────────────────────────────────────────────────────────
# ⛭ Configuration defaults (can be overridden by web adapters)
# ────────────────────────────────────────────────────────────────────────────────

# “NJ” — used in Phase 1/2
LATEST_MM: Tuple[List[int], int] = ([10, 14, 34, 40, 43], 5)
LATEST_PB: Tuple[List[int], int] = ([14, 15, 32, 42, 49], 1)
LATEST_IL_JP: Tuple[List[int], None] = ([1, 4, 5, 10, 18, 49], None)
LATEST_IL_M1: Tuple[List[int], None] = ([6, 8, 10, 18, 26, 27], None)
LATEST_IL_M2: Tuple[List[int], None] = ([2, 18, 21, 27, 43, 50], None)

# History blobs (20 most recent); replace later with CSV ingestion if you want
HIST_MM_BLOB = """
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
12-27-42-59-65 2
18-27-29-33-70 22
17-30-34-63-67 11
14-21-25-49-52 7
22-41-42-59-69 17
11-43-54-55-63 3
06-10-24-35-43 1
12-23-24-31-56 1
04-06-38-44-62 24
"""

HIST_PB_BLOB = """
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
"""

HIST_IL_BLOB = """
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
"""

# Feeds from “Lottery Defeated” style strings
FEED_PB = """
Top 8 hot numbers: 23, 61, 35, 28, 43, 62, 64, 52
Top 8 overdue numbers: 66, 39, 20, 10, 56, 30, 17, 32
Top 3 hot Power Ball numbers: 25, 5, 2
Top 3 overdue Power Ball numbers: 16, 26, 7
"""
FEED_MM = """
Top 8 hot numbers: 10, 40, 6, 17, 24, 18, 16, 49
Top 8 overdue numbers: 53, 3, 5, 15, 51, 9, 66, 37
Top 3 hot Mega Ball numbers: 1, 24, 2
Top 3 overdue Mega Ball numbers: 4, 6, 15
"""
FEED_IL = """
Top 8 hot numbers: 17, 20, 22, 14, 5, 1, 6, 3
Top 8 overdue numbers: 28, 35, 46, 38, 33, 37, 39, 25
"""

# AFTER the draw — set these (or leave None)
NWJ_MM: Optional[Tuple[List[int], int]] = None
NWJ_PB: Optional[Tuple[List[int], int]] = None
NWJ_IL_JP: Optional[Tuple[List[int], None]] = None
NWJ_IL_M1: Optional[Tuple[List[int], None]] = None
NWJ_IL_M2: Optional[Tuple[List[int], None]] = None

# Buy-list persistence and confirmation
SAVE_DIR = "buylists"; os.makedirs(SAVE_DIR, exist_ok=True)
CONFIRM_FROM_FILE: Optional[str] = None
CONFIRM_FALLBACK_TO_LATEST = False

# Repro/verbosity
RNG_SEED = 20250919
QUIET_SIM = True
PROGRESS_EVERY = 10  # show 10/100, 20/100, ...

# ────────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────────

def parse_mm_pb_blob(blob: str) -> List[Tuple[List[int], int]]:
    draws = []
    for line in blob.strip().splitlines():
        line = line.strip()
        if not line: continue
        mains_str, bonus_str = line.split()
        mains = list(map(int, mains_str.split("-")))
        bonus = int(bonus_str)
        draws.append((mains, bonus))
    return draws

def parse_il_blob(blob: str) -> List[List[int]]:
    draws = []
    for line in blob.strip().splitlines():
        line = line.strip()
        if not line: continue
        mains = list(map(int, line.split("-")))
        draws.append(mains)
    return draws

def clamp_last_n(items: List, n: int) -> List:
    return items[-n:] if len(items) > n else items[:]

def iqr_band_from_history(main_hist: List[List[int]]) -> Tuple[int, int]:
    sums = [sum(sorted(m)) for m in main_hist]
    try:
        q1 = int(statistics.quantiles(sums, n=4, method="inclusive")[0])
        q3 = int(statistics.quantiles(sums, n=4, method="inclusive")[2])
    except Exception:
        sums_sorted = sorted(sums)
        q1 = sums_sorted[len(sums)//4]
        q3 = sums_sorted[3*len(sums)//4]
    return (q1, q3)

def undrawn_from_last_k(main_hist: List[List[int]], k: int, max_num: int) -> Set[int]:
    recent = main_hist[-k:]
    seen = set(n for row in recent for n in row)
    return set(range(1, max_num+1)) - seen

def bonus_undrawn_from_last_k(bonus_hist: List[int], k: int, max_num: int) -> Set[int]:
    recent = bonus_hist[-k:]
    seen = set(recent)
    return set(range(1, max_num+1)) - seen

def lrr_candidates(main_hist: List[List[int]]) -> List[int]:
    last20 = main_hist[-20:]
    last5 = set(n for row in last20[-5:] for n in row)
    counts = Counter(n for row in last20 for n in row)
    cands = [n for n, c in counts.items() if c == 2 and n not in last5]
    last_seen_idx = {}
    for idx, row in enumerate(last20):
        for n in row:
            last_seen_idx[n] = idx
    cands.sort(key=lambda x: last_seen_idx.get(x, 1e9))
    return cands[:2]

def parse_feed_sets(feed: str, game: str) -> Dict[str, List[int]]:
    out = {}
    for line in feed.strip().splitlines():
        line = line.strip()
        if not line: continue
        if line.lower().startswith("top 8 hot numbers"):
            nums = line.split(":")[1]
            out["Hot"] = [int(x.strip()) for x in nums.split(",")]
        elif line.lower().startswith("top 8 overdue numbers"):
            nums = line.split(":")[1]
            out["Overdue"] = [int(x.strip()) for x in nums.split(",")]
        elif game == "MM" and "mega ball" in line.lower():
            nums = line.split(":")[1]
            if "hot" in line.lower(): out["BonusHot"] = [int(x.strip()) for x in nums.split(",")]
            else: out["BonusOverdue"] = [int(x.strip()) for x in nums.split(",")]
        elif game == "PB" and "power ball" in line.lower():
            nums = line.split(":")[1]
            if "hot" in line.lower(): out["BonusHot"] = [int(x.strip()) for x in nums.split(",")]
            else: out["BonusOverdue"] = [int(x.strip()) for x in nums.split(",")]
    out.setdefault("Hot", []); out.setdefault("Overdue", [])
    out.setdefault("BonusHot", []); out.setdefault("BonusOverdue", [])
    return out

def pick_bonus(game_spec, feeds, bonus_hist: List[int]) -> int:
    if game_spec["bonus_max"] is None: return None
    pool = list(dict.fromkeys(feeds["BonusHot"] + feeds["BonusOverdue"]))
    if len(pool) < 3:
        und = list(bonus_undrawn_from_last_k(bonus_hist, 10, game_spec["bonus_max"]))
        random.shuffle(und); pool += und
    if not pool: pool = list(range(1, game_spec["bonus_max"]+1))
    return random.choice(pool)

def draw_from_pool(pool: Iterable[int], need: int, used: Set[int]) -> List[int]:
    choices = [n for n in pool if n not in used]
    random.shuffle(choices)
    return choices[:max(0, need)]

def generate_ticket_from_pattern(game_spec, pattern, pools, iqr_band) -> Optional[Tuple[List[int], Optional[int]]]:
    anchor_type, a_ct, t1, t1_ct, t2, t2_ct, t3, t3_ct = pattern
    retries = 20
    while retries > 0:
        retries -= 1
        used = set(); mains = []

        anchor_pool = pools["VIP"] if anchor_type == "VIP" else pools["LRR"]
        if a_ct > 0:
            if not anchor_pool: return None
            a_pick = draw_from_pool(anchor_pool, 1, used)
            if not a_pick: return None
            mains.extend(a_pick); used.update(a_pick)

        for typ, ct in [(t1, t1_ct), (t2, t2_ct), (t3, t3_ct)]:
            if ct <= 0: continue
            add = draw_from_pool(pools[typ], ct, used)
            if len(add) < ct and typ != "Undrawn":
                add += draw_from_pool(pools["Undrawn"], ct - len(add), used)
            mains.extend(add); used.update(add)

        while len(mains) < game_spec["main_pick"]:
            for fallback in ("Undrawn", "Hot", "Overdue"):
                need = game_spec["main_pick"] - len(mains)
                add = draw_from_pool(pools[fallback], need, used)
                mains.extend(add); used.update(add)
                if len(mains) >= game_spec["main_pick"]:
                    break

        if len(set(mains)) != game_spec["main_pick"]:
            continue

        mains = sorted(mains)
        s = sum(mains)
        if iqr_band[0] <= s <= iqr_band[1]:
            return (mains, None)
    return None

def ensure_bonus(game_spec, ticket_mb, feeds, bonus_hist):
    mains, b = ticket_mb
    if game_spec["bonus_max"] is None: return (mains, None)
    if b is None: b = pick_bonus(game_spec, feeds, bonus_hist)
    return (mains, b)

def score_hits_mm_pb(ticket: Tuple[List[int], int], target: Tuple[List[int], int]) -> Tuple[int, bool]:
    mains, b = ticket; t_mains, t_b = target
    m = len(set(mains) & set(t_mains)); bonus_hit = (b == t_b)
    return m, bonus_hit

def score_hits_il(ticket: List[int], target: List[int]) -> int:
    return len(set(ticket) & set(target))

def print_phase1_batch(game_name: str, batch: List, latest_target, is_il=False):
    print(f"\n======================== {game_name} ========================")
    # print the 50 rows
    for idx, t in enumerate(batch, 1):
        if is_il:
            print(f"{idx:02d}. " + " ".join(f"{n:02d}" for n in t))
        else:
            mains, b = t
            print(f"{idx:02d}. " + " ".join(f"{n:02d}" for n in mains) + f"   {b:02d}")
    # and show hits ≥3 (or 2+bonus)
    if is_il:
        rows = [(i, score_hits_il(t, latest_target)) for i, t in enumerate(batch, 1)]
        hits = [(i, m) for i, m in rows if m >= 3]
        if hits:
            print("\nHits (≥3-ball):")
            for i, m in hits:
                print(f"  row #{i}: {m}-ball")
        else:
            print("\nNo ≥3-ball hits in this 50-row batch vs NJ.")
    else:
        rows = [(i,)+score_hits_mm_pb(t, latest_target) for i, t in enumerate(batch, 1)]
        hits = [(i, m, bh) for i, m, bh in rows if m >= 3 or (m >= 2 and bh)]
        if hits:
            print("\nHits (≥3-ball or 2+bonus):")
            for i, m, bh in hits:
                label = f\"{m}-ball{' + Bonus' if bh else ''}\"
                print(f"  row #{i}: {label}")
        else:
            print("\nNo ≥3-ball (or 2+bonus) hits in this 50-row batch vs NJ.")

def recommend_from_stats(last_batch, pos_hit_freq: Dict[int,int], k: int) -> List:
    scored = sorted(
        [(pos_hit_freq.get(i+1,0), i, t) for i, t in enumerate(last_batch)],
        key=lambda x: (-x[0], x[1])
    )
    picks = []; seen_sets = []
    for _, _, t in scored:
        mains = t[0] if isinstance(t, tuple) else t
        mains_set = set(mains)
        too_close = any(len(mains_set & s) >= (5 if len(mains)==6 else 4) for s in seen_sets)
        if too_close: continue
        picks.append(t); seen_sets.append(mains_set)
        if len(picks) >= k: break
    i = 0
    while len(picks) < k and i < len(last_batch):
        t = last_batch[i]
        if t not in picks: picks.append(t)
        i += 1
    return picks

# ────────────────────────────────────────────────────────────────────────────────
# Generators
# ────────────────────────────────────────────────────────────────────────────────

GAME_MM = {"name": "Mega Millions", "main_max": 70, "main_pick": 5, "bonus_max": 25}
GAME_PB = {"name": "Powerball",     "main_max": 69, "main_pick": 5, "bonus_max": 26}
GAME_IL = {"name": "Illinois Lotto","main_max": 50, "main_pick": 6, "bonus_max": None}

PATTERNS_MM_PB = [
    ("VIP", 1, "Hot", 1, "Overdue", 0, "Undrawn", 3),
    ("VIP", 1, "Hot", 1, "Overdue", 1, "Undrawn", 2),
    ("VIP", 1, "Hot", 1, "Overdue", 2, "Undrawn", 1),
    ("VIP", 1, "Hot", 2, "Overdue", 0, "Undrawn", 2),
    ("VIP", 1, "Hot", 2, "Overdue", 1, "Undrawn", 1),
    ("VIP", 1, "Hot", 3, "Overdue", 0, "Undrawn", 1),
    ("VIP", 1, "Hot", 0, "Overdue", 1, "Undrawn", 3),
    ("VIP", 1, "Hot", 0, "Overdue", 2, "Undrawn", 2),
    ("VIP", 1, "Hot", 0, "Overdue", 3, "Undrawn", 1),
    ("LRR", 1, "Hot", 1, "Overdue", 0, "Undrawn", 3),
    ("LRR", 1, "Hot", 1, "Overdue", 1, "Undrawn", 2),
    ("LRR", 1, "Hot", 1, "Overdue", 2, "Undrawn", 1),
    ("LRR", 1, "Hot", 2, "Overdue", 0, "Undrawn", 2),
    ("LRR", 1, "Hot", 2, "Overdue", 1, "Undrawn", 1),
    ("LRR", 1, "Hot", 3, "Overdue", 0, "Undrawn", 1),
    ("LRR", 1, "Hot", 0, "Overdue", 1, "Undrawn", 3),
    ("LRR", 1, "Hot", 0, "Overdue", 2, "Undrawn", 2),
    ("LRR", 1, "Hot", 0, "Overdue", 3, "Undrawn", 1),
]
PATTERNS_IL = [
    ("VIP", 1, "Hot", 1, "Overdue", 0, "Undrawn", 4),
    ("VIP", 1, "Hot", 1, "Overdue", 1, "Undrawn", 3),
    ("VIP", 1, "Hot", 1, "Overdue", 2, "Undrawn", 2),
    ("VIP", 1, "Hot", 1, "Overdue", 3, "Undrawn", 1),
    ("VIP", 1, "Hot", 2, "Overdue", 0, "Undrawn", 3),
    ("VIP", 1, "Hot", 2, "Overdue", 1, "Undrawn", 2),
    ("VIP", 1, "Hot", 2, "Overdue", 2, "Undrawn", 1),
    ("VIP", 1, "Hot", 2, "Overdue", 3, "Undrawn", 0),
    ("VIP", 1, "Hot", 3, "Overdue", 0, "Undrawn", 2),
    ("VIP", 1, "Hot", 3, "Overdue", 1, "Undrawn", 1),
    ("VIP", 1, "Hot", 3, "Overdue", 2, "Undrawn", 0),
    ("VIP", 1, "Hot", 4, "Overdue", 0, "Undrawn", 1),
    ("VIP", 1, "Hot", 4, "Overdue", 1, "Undrawn", 0),
    ("VIP", 1, "Hot", 5, "Overdue", 0, "Undrawn", 0),
    ("LRR", 1, "Hot", 1, "Overdue", 0, "Undrawn", 4),
    ("LRR", 1, "Hot", 1, "Overdue", 1, "Undrawn", 3),
    ("LRR", 1, "Hot", 1, "Overdue", 2, "Undrawn", 2),
    ("LRR", 1, "Hot", 1, "Overdue", 3, "Undrawn", 1),
    ("LRR", 1, "Hot", 2, "Overdue", 0, "Undrawn", 3),
    ("LRR", 1, "Hot", 2, "Overdue", 1, "Undrawn", 2),
    ("LRR", 1, "Hot", 2, "Overdue", 2, "Undrawn", 1),
    ("LRR", 1, "Hot", 2, "Overdue", 3, "Undrawn", 0),
    ("LRR", 1, "Hot", 3, "Overdue", 0, "Undrawn", 2),
    ("LRR", 1, "Hot", 3, "Overdue", 1, "Undrawn", 1),
    ("LRR", 1, "Hot", 3, "Overdue", 2, "Undrawn", 0),
    ("LRR", 1, "Hot", 4, "Overdue", 0, "Undrawn", 1),
    ("LRR", 1, "Hot", 4, "Overdue", 1, "Undrawn", 0),
    ("LRR", 1, "Hot", 5, "Overdue", 0, "Undrawn", 0),
]

def build_pools(game_spec, main_hist, feeds) -> Dict[str, List[int]]:
    hot = [n for n in feeds["Hot"] if 1 <= n <= game_spec["main_max"]]
    over = [n for n in feeds["Overdue"] if 1 <= n <= game_spec["main_max"]]
    und = sorted(list(undrawn_from_last_k(main_hist, 10, game_spec["main_max"])))
    vip = sorted(list(set(hot) & set(over)))
    lrr = lrr_candidates(main_hist)
    return {"Hot": hot, "Overdue": over, "Undrawn": und, "VIP": vip, "LRR": lrr}

def generate_batch_mm_pb(game_spec, main_hist, bonus_hist, feeds, patterns, batch_size=50):
    iqr = iqr_band_from_history(main_hist)
    pools = build_pools(game_spec, main_hist, feeds)
    batch = []; p_idx = 0; guard = 0
    while len(batch) < batch_size and guard < batch_size * 10:
        guard += 1
        pat = patterns[p_idx % len(patterns)]
        if pat[0] == "VIP" and not pools["VIP"]: p_idx += 1; continue
        if pat[0] == "LRR" and not pools["LRR"]: p_idx += 1; continue
        ticket = generate_ticket_from_pattern(game_spec, pat, pools, iqr)
        if ticket is None: p_idx += 1; continue
        ticket = ensure_bonus(game_spec, ticket, feeds, bonus_hist)
        if ticket not in batch: batch.append(ticket)
        p_idx += 1
    return batch

def generate_batch_il(game_spec, main_hist, feeds, patterns, batch_size=50):
    iqr = iqr_band_from_history(main_hist)
    pools = build_pools(game_spec, main_hist, feeds)
    batch = []; p_idx = 0; guard = 0
    while len(batch) < batch_size and guard < batch_size * 10:
        guard += 1
        pat = patterns[p_idx % len(patterns)]
        if pat[0] == "VIP" and not pools["VIP"]: p_idx += 1; continue
        if pat[0] == "LRR" and not pools["LRR"]: p_idx += 1; continue
        t = generate_ticket_from_pattern(game_spec, pat, pools, iqr)
        if t is None: p_idx += 1; continue
        mains, _ = t
        if mains not in batch: batch.append(mains)
        p_idx += 1
    return batch

def simulate_phase2_mm_pb(game_spec, main_hist, bonus_hist, feeds, patterns, target, runs=100, batch_size=50):
    pos_hits = defaultdict(int); type_totals = Counter(); last_batch = None
    for r in range(1, runs+1):
        batch = generate_batch_mm_pb(game_spec, main_hist, bonus_hist, feeds, patterns, batch_size=batch_size)
        if r == runs: last_batch = batch
        for idx, t in enumerate(batch, 1):
            m, bh = score_hits_mm_pb(t, target)
            if m >= 3 or (m >= 2 and bh): pos_hits[idx] += 1
            key = None
            if   m == 3 and not bh: key = "3"
            elif m == 3 and bh:     key = "3+"
            elif m == 4 and not bh: key = "4"
            elif m == 4 and bh:     key = "4+"
            elif m == 5 and not bh: key = "5"
            elif m == 5 and bh:     key = "5+"
            if key: type_totals[key] += 1
        if not QUIET_SIM and (r % PROGRESS_EVERY == 0 or r == runs):
            print(f"  {r}/{runs} complete.")
    return pos_hits, type_totals, last_batch

def simulate_phase2_il(game_spec, main_hist, feeds, patterns, targets: List[List[int]], runs=100, batch_size=50):
    pos_hits = defaultdict(int); type_totals = Counter(); last_batch = None
    for r in range(1, runs+1):
        batch = generate_batch_il(game_spec, main_hist, feeds, patterns, batch_size=batch_size)
        if r == runs: last_batch = batch
        for idx, t in enumerate(batch, 1):
            best = max(score_hits_il(t, tgt) for tgt in targets)
            if best >= 3: pos_hits[idx] += 1
            if best >= 3: type_totals["3"] += 1
            if best >= 4: type_totals["4"] += 1
            if best >= 5: type_totals["5"] += 1
            if best == 6: type_totals["6"] += 1
        if not QUIET_SIM and (r % PROGRESS_EVERY == 0 or r == runs):
            print(f"  {r}/{runs} complete.")
    return pos_hits, type_totals, last_batch

def fmt_ticket_mm_pb(t):
    mains, b = t
    return f"{' '.join(f'{n:02d}' for n in mains)}   {b:02d}"

def fmt_ticket_il(t):
    return " ".join(f"{n:02d}" for n in t)

def print_buy_list(title: str, tickets: List):
    print(f"\n{title}"); print("-"*len(title))
    for i, t in enumerate(tickets, 1):
        if isinstance(t, tuple): print(f"{i:>2}. {fmt_ticket_mm_pb(t)}")
        else:                    print(f"{i:>2}. {fmt_ticket_il(t)}")

def evaluate_vs_target_mm_pb(batch: List[Tuple[List[int], int]], target):
    return [(idx,)+score_hits_mm_pb(t, target) for idx, t in enumerate(batch, 1)]

def evaluate_vs_target_il(batch: List[List[int]], target: List[int]):
    return [(idx, score_hits_il(t, target)) for idx, t in enumerate(batch, 1)]

def save_buylists(mm_list, pb_list, il_list, out_dir=None):
    out_dir = out_dir or SAVE_DIR
    os.makedirs(out_dir, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    mm_norm = [[t[0], t[1]] for t in mm_list]
    pb_norm = [[t[0], t[1]] for t in pb_list]
    il_norm = [list(t) for t in il_list]
    payload = {
        "timestamp": stamp,
        "LATEST_MM": LATEST_MM, "LATEST_PB": LATEST_PB,
        "LATEST_IL_JP": LATEST_IL_JP, "LATEST_IL_M1": LATEST_IL_M1, "LATEST_IL_M2": LATEST_IL_M2,
        "MM": mm_norm, "PB": pb_norm, "IL": il_norm
    }
    path = os.path.join(out_dir, f"buy_session_{stamp}.json")
    with open(path, "w", encoding="utf-8") as f: json.dump(payload, f, indent=2)
    print(f"\nSaved buy lists to: {path}"); return path

def load_buylists(path: str):
    with open(path, "r", encoding="utf-8") as f: data = json.load(f)
    mm = [(list(item[0]), item[1]) for item in data.get("MM", [])]
    pb = [(list(item[0]), item[1]) for item in data.get("PB", [])]
    il = [list(item) for item in data.get("IL", [])]
    return data, mm, pb, il

# ────────────────────────────────────────────────────────────────────────────────
# Phase Orchestration (prints console-style report)
# ────────────────────────────────────────────────────────────────────────────────

def run_all_phases():
    random.seed(RNG_SEED)
    mm_hist_full = clamp_last_n(parse_mm_pb_blob(HIST_MM_BLOB), 20)
    pb_hist_full = clamp_last_n(parse_mm_pb_blob(HIST_PB_BLOB), 20)
    il_hist_full = clamp_last_n(parse_il_blob(HIST_IL_BLOB), 20)
    mm_mains = [row[0] for row in mm_hist_full]; mm_bonus = [row[1] for row in mm_hist_full]
    pb_mains = [row[0] for row in pb_hist_full]; pb_bonus = [row[1] for row in pb_hist_full]

    feeds_mm = parse_feed_sets(FEED_MM, "MM")
    feeds_pb = parse_feed_sets(FEED_PB, "PB")
    feeds_il = parse_feed_sets(FEED_IL, "IL")

    # Phase 1 — generate batches and print with hits
    mm_batch = generate_batch_mm_pb(GAME_MM, mm_mains, mm_bonus, feeds_mm, PATTERNS_MM_PB, batch_size=50)
    pb_batch = generate_batch_mm_pb(GAME_PB, pb_mains, pb_bonus, feeds_pb, PATTERNS_MM_PB, batch_size=50)
    il_batch = generate_batch_il(GAME_IL, il_hist_full, feeds_il, PATTERNS_IL, batch_size=50)

    print_phase1_batch("Mega Millions", mm_batch, LATEST_MM, is_il=False)
    print_phase1_batch("Powerball",     pb_batch, LATEST_PB, is_il=False)
    print_phase1_batch("Illinois Lotto", il_batch, LATEST_IL_JP[0], is_il=True)

    # Phase 2 — simulate (with NJ prepended to history)
    mm_hist2 = clamp_last_n([(LATEST_MM[0], LATEST_MM[1])] + mm_hist_full, 20)
    pb_hist2 = clamp_last_n([(LATEST_PB[0], LATEST_PB[1])] + pb_hist_full, 20)
    il_hist2 = clamp_last_n([LATEST_IL_JP[0]] + il_hist_full, 20)
    mm_mains2 = [row[0] for row in mm_hist2]; mm_bonus2 = [row[1] for row in mm_hist2]
    pb_mains2 = [row[0] for row in pb_hist2]; pb_bonus2 = [row[1] for row in pb_hist2]

    print("\nPhase 2 — Simulating 100×...")
    print("\nMega Millions:")
    pos_mm, types_mm, last_mm = simulate_phase2_mm_pb(GAME_MM, mm_mains2, mm_bonus2, feeds_mm, PATTERNS_MM_PB, LATEST_MM, runs=100, batch_size=50)
    print("\nPowerball:")
    pos_pb, types_pb, last_pb = simulate_phase2_mm_pb(GAME_PB, pb_mains2, pb_bonus2, feeds_pb, PATTERNS_MM_PB, LATEST_PB, runs=100, batch_size=50)
    print("\nIllinois Lotto:")
    pos_il, types_il, last_il = simulate_phase2_il(GAME_IL, il_hist2, feeds_il, PATTERNS_IL, [LATEST_IL_JP[0], LATEST_IL_M1[0], LATEST_IL_M2[0]], runs=100, batch_size=50)

    def print_stats(title, types_counter, pos_hits):
        print(f"\n{title} — Hit Totals over 100×50:")
        if any(k in types_counter for k in ("3+","4+","5+")):
            for k in ["3","3+","4","4+","5","5+"]:
                if k in types_counter: print(f"  {k:>2}: {types_counter[k]}")
        else:
            for k in ["3","4","5","6"]:
                if k in types_counter: print(f"  {k:>2}: {types_counter[k]}")
        if pos_hits:
            top = sorted(pos_hits.items(), key=lambda x: (-x[1], x[0]))[:10]
            if top:
                print("  Top hit positions (row#:count):", ", ".join(f"{i}:{c}" for i,c in top))

    print_stats("Mega Millions", types_mm, pos_mm)
    print_stats("Powerball",     types_pb, pos_pb)
    print_stats("Illinois Lotto",types_il, pos_il)

    # Recommendations & save
    mm_buy = recommend_from_stats(last_mm, pos_mm, 10)
    pb_buy = recommend_from_stats(last_pb, pos_pb, 10)
    il_buy = recommend_from_stats(last_il, pos_il, 15)

    print_buy_list("[MM — Buy 10 tickets]", mm_buy)
    print_buy_list("[PB — Buy 10 tickets]", pb_buy)
    print_buy_list("[Lotto — Buy 15 tickets]", il_buy)

    saved_path = save_buylists(mm_buy, pb_buy, il_buy)

    # Phase 3 confirmation if requested
    if any([NWJ_MM, NWJ_PB, NWJ_IL_JP, NWJ_IL_M1, NWJ_IL_M2]) and not CONFIRM_FROM_FILE:
        _run_confirmation_only(mm_buy, pb_buy, il_buy)
    elif CONFIRM_FROM_FILE:
        try:
            print(f"\nLoaded buy list from: {CONFIRM_FROM_FILE}")
            _, mm2, pb2, il2 = load_buylists(CONFIRM_FROM_FILE)
            confirm_targets_set = any([NWJ_MM, NWJ_PB, NWJ_IL_JP, NWJ_IL_M1, NWJ_IL_M2])
            if confirm_targets_set or CONFIRM_FALLBACK_TO_LATEST:
                _run_confirmation_only(mm2, pb2, il2)
            else:
                print("(No NWJ_* provided; nothing to confirm.)")
        except Exception as e:
            print(f"\nWARNING: Could not load CONFIRM_FROM_FILE ({CONFIRM_FROM_FILE}): {e}")

    return saved_path

def _run_confirmation_only(mm_buy, pb_buy, il_buy):
    SHOW_2BALL_LINES = False
    eff_NWJ_MM = NWJ_MM if NWJ_MM else (LATEST_MM if CONFIRM_FALLBACK_TO_LATEST else None)
    eff_NWJ_PB = NWJ_PB if NWJ_PB else (LATEST_PB if CONFIRM_FALLBACK_TO_LATEST else None)
    eff_NWJ_IL_JP = NWJ_IL_JP if NWJ_IL_JP else (LATEST_IL_JP if CONFIRM_FALLBACK_TO_LATEST else None)
    eff_NWJ_IL_M1 = NWJ_IL_M1 if NWJ_IL_M1 else (LATEST_IL_M1 if CONFIRM_FALLBACK_TO_LATEST else None)
    eff_NWJ_IL_M2 = NWJ_IL_M2 if NWJ_IL_M2 else (LATEST_IL_M2 if CONFIRM_FALLBACK_TO_LATEST else None)

    print("\n[Confirmation Setup]")
    print("  Using buy list from:", CONFIRM_FROM_FILE if CONFIRM_FROM_FILE else "<this run>")
    print("  NWJ_MM:", eff_NWJ_MM)
    print("  NWJ_PB:", eff_NWJ_PB)
    print("  NWJ_IL_JP:", eff_NWJ_IL_JP)
    print("  NWJ_IL_M1:", eff_NWJ_IL_M1)
    print("  NWJ_IL_M2:", eff_NWJ_IL_M2)
    if CONFIRM_FALLBACK_TO_LATEST and (not any([NWJ_MM, NWJ_PB, NWJ_IL_JP, NWJ_IL_M1, NWJ_IL_M2])):
        print("  Note: Falling back to LATEST_* values because NWJ_* are None.")

    if eff_NWJ_MM:
        print("\n[Mega Millions — Confirmation vs NWJ]")
        res = [(i,)+score_hits_mm_pb(t, eff_NWJ_MM) for i,t in enumerate(mm_buy,1)]
        tiers = {"2+":0, "3":0, "3+":0, "4":0, "4+":0, "5":0, "5+":0}
        for _, m, bh in res:
            if m==2 and bh: tiers["2+"] += 1
            if m==3: tiers["3"] += 1
            if m==3 and bh: tiers["3+"] += 1
            if m==4: tiers["4"] += 1
            if m==4 and bh: tiers["4+"] += 1
            if m==5: tiers["5"] += 1
            if m==5 and bh: tiers["5+"] += 1
        print("  Totals:", ", ".join(f"{k}:{v}" for k,v in tiers.items()))
        rows = [(i,m,bh) for i,(_,m,bh) in enumerate(res,1) if m>=3 or (m>=2 and bh)]
        if rows:
            print("  Detailed rows (≥3 or 2+bonus):")
            for i,m,bh in rows:
                label = f\"{m}-ball{' + Bonus' if bh else ''}\"
                print(f"    row #{i:02d}: {label}")
        else:
            print("  (none)")

    if eff_NWJ_PB:
        print("\n[Powerball — Confirmation vs NWJ]")
        res = [(i,)+score_hits_mm_pb(t, eff_NWJ_PB) for i,t in enumerate(pb_buy,1)]
        tiers = {"2+":0, "3":0, "3+":0, "4":0, "4+":0, "5":0, "5+":0}
        for _, m, bh in res:
            if m==2 and bh: tiers["2+"] += 1
            if m==3: tiers["3"] += 1
            if m==3 and bh: tiers["3+"] += 1
            if m==4: tiers["4"] += 1
            if m==4 and bh: tiers["4+"] += 1
            if m==5: tiers["5"] += 1
            if m==5 and bh: tiers["5+"] += 1
        print("  Totals:", ", ".join(f"{k}:{v}" for k,v in tiers.items()))
        rows = [(i,m,bh) for i,(_,m,bh) in enumerate(res,1) if m>=3 or (m>=2 and bh)]
        if rows:
            print("  Detailed rows (≥3 or 2+bonus):")
            for i,m,bh in rows:
                label = f\"{m}-ball{' + Bonus' if bh else ''}\"
                print(f"    row #{i:02d}: {label}")
        else:
            print("  (none)")

    if eff_NWJ_IL_JP or eff_NWJ_IL_M1 or eff_NWJ_IL_M2:
        print("\n[Lotto — Confirmation vs NWJ]")
        targets_named = [(name, t) for name, t in [("Jackpot", eff_NWJ_IL_JP), ("Million 1", eff_NWJ_IL_M1), ("Million 2", eff_NWJ_IL_M2)] if t]
        tiers = {2:0, 3:0, 4:0, 5:0, 6:0}; rows=[]
        for i, mains in enumerate(il_buy, 1):
            best = 0; best_name=None
            for name, t in targets_named:
                hits = score_hits_il(mains, t[0])
                if hits > best: best = hits; best_name = name
            if best>=2: tiers[max(2, min(6, best))] += 1
            if best>=3: rows.append((i, best, best_name))
        print("  Totals:", ", ".join(f"{k}-ball:{tiers[k]}" for k in [2,3,4,5,6]))
        if rows:
            print("  Detailed rows (≥3-ball):")
            for i, best, best_name in rows:
                print(f"    row #{i:02d}: {best}-ball vs {best_name}")
        else:
            print("  (none)")

# ────────────────────────────────────────────────────────────────────────────────
# CLI entry
# ────────────────────────────────────────────────────────────────────────────────

def main():
    run_all_phases()

if __name__ == "__main__":
    main()

# ===== Web Adapters ============================================================
# These two helpers are called by app.py. They capture stdout and return text.

def _set_if_str(name, raw, is_il=False):
    """Quick parse for form fields:
       MM/PB:  "[10,14,34,40,43],5"
       IL:     "[1,4,5,10,18,49]"
    """
    if not raw:
        return
    raw = raw.strip()
    if is_il:
        try:
            mains = json.loads(raw.replace("'", '"'))
            globals()[name] = (mains, None)
        except Exception:
            pass
    else:
        try:
            if "]" in raw:
                mains_txt, bonus_txt = raw.split("]", 1)
                mains = json.loads(mains_txt + "]".replace("'", '"'))
                bonus = int(bonus_txt.strip(" ,"))
                globals()[name] = (mains, bonus)
        except Exception:
            pass

def web_phase12(data_dir: str, buy_dir: str, form: dict):
    """Runs Phase 1 & 2 and returns (report_text, saved_json_path)."""
    global SAVE_DIR, QUIET_SIM
    SAVE_DIR = buy_dir
    QUIET_SIM = form.get("quiet", True)

    _set_if_str("LATEST_MM", form.get("LATEST_MM"))
    _set_if_str("LATEST_PB", form.get("LATEST_PB"))
    _set_if_str("LATEST_IL_JP", form.get("LATEST_IL_JP"), is_il=True)
    _set_if_str("LATEST_IL_M1", form.get("LATEST_IL_M1"), is_il=True)
    _set_if_str("LATEST_IL_M2", form.get("LATEST_IL_M2"), is_il=True)

    f = io.StringIO()
    with redirect_stdout(f):
        main()
    text = f.getvalue()

    saved = None
    try:
        files = [x for x in os.listdir(SAVE_DIR) if x.startswith("buy_session_") and x.endswith(".json")]
        if files:
            saved = os.path.join(SAVE_DIR, sorted(files)[-1])
    except Exception:
        pass
    return text, saved

def web_phase3(data_dir: str, buy_dir: str, confirm_file: str, nwj: dict):
    """Loads a buy list JSON and confirms vs NWJ. Returns report_text."""
    global SAVE_DIR, CONFIRM_FROM_FILE, NWJ_MM, NWJ_PB, NWJ_IL_JP, NWJ_IL_M1, NWJ_IL_M2, CONFIRM_FALLBACK_TO_LATEST

    SAVE_DIR = buy_dir
    CONFIRM_FROM_FILE = os.path.join(SAVE_DIR, confirm_file)

    def _set(name, raw, is_il=False):
        if raw and raw.strip():
            _set_if_str(name, raw, is_il=is_il)
    _set("NWJ_MM", nwj.get("NWJ_MM"))
    _set("NWJ_PB", nwj.get("NWJ_PB"))
    _set("NWJ_IL_JP", nwj.get("NWJ_IL_JP"), is_il=True)
    _set("NWJ_IL_M1", nwj.get("NWJ_IL_M1"), is_il=True)
    _set("NWJ_IL_M2", nwj.get("NWJ_IL_M2"), is_il=True)

    CONFIRM_FALLBACK_TO_LATEST = False

    f = io.StringIO()
    with redirect_stdout(f):
        main()
    return f.getvalue()
# ===========================================================================
