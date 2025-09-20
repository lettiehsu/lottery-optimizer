# -*- coding: utf-8 -*-
from __future__ import annotations
import re, random, math, statistics
from collections import Counter, defaultdict
from typing import List, Tuple, Dict, Any, Optional, Iterable

# ---------------------------
# Game definitions
# ---------------------------

class GameSpec:
    def __init__(self, name: str, main_max: int, main_pick: int, has_bonus: bool, bonus_max: int = 0):
        self.name = name
        self.main_max = main_max
        self.main_pick = main_pick
        self.has_bonus = has_bonus
        self.bonus_max = bonus_max

G_MM = GameSpec("MM", main_max=70, main_pick=5, has_bonus=True, bonus_max=25)
G_PB = GameSpec("PB", main_max=69, main_pick=5, has_bonus=True, bonus_max=26)
G_IL = GameSpec("IL", main_max=50, main_pick=6, has_bonus=False, bonus_max=0)

# ---------------------------
# Parsing helpers
# ---------------------------

INT = r"(?:\d{1,2})"
LINE_MM_PB = re.compile(rf"\s*{INT}-{INT}-{INT}-{INT}-{INT}\s+(\d{{1,2}})\s*$")
LINE_IL = re.compile(rf"\s*{INT}-{INT}-{INT}-{INT}-{INT}-{INT}\s*$")

def _ints(s: str) -> List[int]:
    return [int(x) for x in re.findall(r"\d+", s)]

def parse_hist_blob(blob: str, game: GameSpec) -> List[Tuple[List[int], Optional[int]]]:
    rows = []
    for line in blob.strip().splitlines():
        line = line.strip()
        if not line: 
            continue
        if game is G_IL:
            if not LINE_IL.match(line):
                # allow loose parse
                nums = _ints(line)
                if len(nums) >= game.main_pick:
                    rows.append((sorted(nums[:game.main_pick]), None))
                continue
            nums = [int(x) for x in line.replace(" ", "").split("-")]
            rows.append((sorted(nums[:game.main_pick]), None))
        else:
            # MM/PB have bonus at the end
            nums = _ints(line)
            if len(nums) >= game.main_pick + 1:
                mains = sorted(nums[:game.main_pick])
                bonus = nums[game.main_pick]
                rows.append((mains, bonus))
    # keep order as given: top is newest in user convention
    return rows

def parse_feed_blob(feed: str, game: GameSpec) -> Dict[str, List[int]]:
    """
    Expects lines like:
      Top 8 hot numbers: 23, 61, ...
      Top 8 overdue numbers: ...
      Top 3 hot Power Ball numbers: ...
      Top 3 overdue Power Ball numbers: ...
    """
    out = {"hot": [], "overdue": [], "hot_bonus": [], "overdue_bonus": []}
    hot = re.search(r"Top\s+\d+\s+hot\s+numbers:\s*([0-9,\s]+)", feed, re.I)
    ovd = re.search(r"Top\s+\d+\s+overdue\s+numbers:\s*([0-9,\s]+)", feed, re.I)
    if hot:
        out["hot"] = [int(x) for x in re.findall(r"\d+", hot.group(1))]
    if ovd:
        out["overdue"] = [int(x) for x in re.findall(r"\d+", ovd.group(1))]

    if game.has_bonus:
        # bonus labels differ
        if game is G_PB:
            hotb = re.search(r"Top\s+\d+\s+hot\s+Power\s+Ball\s+numbers:\s*([0-9,\s]+)", feed, re.I)
            ovdb = re.search(r"Top\s+\d+\s+overdue\s+Power\s+Ball\s+numbers:\s*([0-9,\s]+)", feed, re.I)
        else:
            hotb = re.search(r"Top\s+\d+\s+hot\s+Mega\s+Ball\s+numbers:\s*([0-9,\s]+)", feed, re.I)
            ovdb = re.search(r"Top\s+\d+\s+overdue\s+Mega\s+Ball\s+numbers:\s*([0-9,\s]+)", feed, re.I)
        if hotb:
            out["hot_bonus"] = [int(x) for x in re.findall(r"\d+", hotb.group(1))]
        if ovdb:
            out["overdue_bonus"] = [int(x) for x in re.findall(r"\d+", ovdb.group(1))]
    return out

# ---------------------------
# “Latest” helpers
# ---------------------------

def parse_latest_line(s: str) -> Tuple[List[int], Optional[int]]:
    # e.g. "([10, 14, 34, 40, 43], 5)" or "([1, 4, 5, 10, 18, 49], None)"
    nums = re.findall(r"\[(.*?)\]", s)
    main = []
    if nums:
        main = [int(x) for x in re.findall(r"\d+", nums[0])]
    bonus = re.search(r",\s*([0-9Nn][\w]*)\s*\)?\s*$", s)
    bval = None
    if bonus:
        btxt = bonus.group(1)
        if re.match(r"^\d+$", btxt):
            bval = int(btxt)
    return (sorted(main), bval)

def pack_latest_dict(mm, pb, il_jp, il_m1, il_m2) -> Dict[str, Tuple[List[int], Optional[int]]]:
    out = {}
    if mm: out["MM"] = mm
    if pb: out["PB"] = pb
    # IL has three result sets
    ilx = []
    if il_jp: ilx.append(("Jackpot", il_jp))
    if il_m1: ilx.append(("Million1", il_m1))
    if il_m2: ilx.append(("Million2", il_m2))
    out["IL_X3"] = ilx
    return out

def normalize_latest_payload(payload: Dict[str, Any], prefix: str = "LATEST_") -> Dict[str, Any]:
    # Accept strings like "([10,14,34,40,43], 5)" or already parsed tuples
    def pick(key):
        v = payload.get(prefix + key)
        if v is None: return None
        if isinstance(v, (list, tuple)):
            return (sorted([int(x) for x in v[0]]), (int(v[1]) if v[1] is not None else None))
        if isinstance(v, str):
            return parse_latest_line(v)
        return v

    mm = pick("MM")
    pb = pick("PB")
    il_jp = pick("IL_JP")
    il_m1 = pick("IL_M1")
    il_m2 = pick("IL_M2")
    return pack_latest_dict(mm, pb, il_jp, il_m1, il_m2)

# ---------------------------
# Strategy core
# ---------------------------

def last_k_draws(draws: List[Tuple[List[int], Optional[int]]], k: int) -> List[Tuple[List[int], Optional[int]]]:
    return draws[:k]

def flatten_mains(draws: List[Tuple[List[int], Optional[int]]]) -> List[int]:
    out = []
    for m, _ in draws:
        out.extend(m)
    return out

def undrawn_set(draws_last10: List[Tuple[List[int], Optional[int]]], main_max: int) -> List[int]:
    used = set(flatten_mains(draws_last10))
    return [n for n in range(1, main_max+1) if n not in used]

def lrr_list(draws_last20: List[Tuple[List[int], Optional[int]]], recent_window: int = 5) -> List[int]:
    """
    LRR (Least Current Repeat): numbers that appear exactly twice in last 20 draws,
    BUT do not appear inside the most recent 'recent_window' draws.
    Return in descending recency-gap order (rotate later).
    """
    mains20 = flatten_mains(draws_last20)
    cnt = Counter(mains20)
    # mark recent set
    recent_nums = set(flatten_mains(draws_last20[:recent_window]))
    candidates = [n for n, c in cnt.items() if c == 2 and n not in recent_nums]
    # heuristic order: least recent appearance preferred => approximate by not-in-recent first (already),
    # then by number id (stable)
    return sorted(candidates)

def vip_from_feed(feed: Dict[str, List[int]]) -> List[int]:
    h = set(feed.get("hot", []))
    o = set(feed.get("overdue", []))
    vip = sorted(h.intersection(o))
    return vip

def sample_without_replacement(pool: Iterable[int], k: int, rng: random.Random) -> List[int]:
    arr = list(pool)
    if k <= 0: return []
    if len(arr) < k:
        # fallback: sample with replacement if pool is too small (rare edge)
        return sorted(rng.choices(arr, k=k))
    return sorted(rng.sample(arr, k=k))

def clamp_history_with_new_top(new_top: Tuple[List[int], Optional[int]],
                               old_hist: List[Tuple[List[int], Optional[int]]],
                               keep: int = 20) -> List[Tuple[List[int], Optional[int]]]:
    merged = [new_top] + [x for x in old_hist if x != new_top]
    return merged[:keep]

def est_middle_band(game: GameSpec, draws_for_estimate: int = 40000, seed: int = 20240913) -> Tuple[int, int]:
    """
    Estimate the middle-50% sum band (approx 25th–75th percentile) by Monte Carlo.
    This avoids hard-coding bands and adapts per game.
    """
    rng = random.Random(seed + game.main_max * 1000 + game.main_pick)
    sums = []
    for _ in range(draws_for_estimate):
        pick = sorted(rng.sample(range(1, game.main_max+1), k=game.main_pick))
        sums.append(sum(pick))
    sums.sort()
    q25 = sums[int(0.25 * len(sums))]
    q75 = sums[int(0.75 * len(sums))]
    return (q25, q75)

def within_band(mains: List[int], band: Tuple[int, int]) -> bool:
    s = sum(mains)
    return band[0] <= s <= band[1]

# ---------------------------
# Pattern engines
# ---------------------------

# Your provided patterns
PAT_MM_PB = [
    ("VIP", 1, "HOT", 1, "UND", 3, "OVD", 0),
    ("VIP", 1, "HOT", 1, "OVD", 1, "UND", 2),
    ("VIP", 1, "HOT", 1, "
