# lottery_core.py — complete core for Phase 1/2/3
# Works with app.py endpoints: /run_json, /confirm_json, /recent, /health

from __future__ import annotations
import os, json, random, math
from datetime import datetime
from typing import List, Tuple, Optional, Dict, Any

# ---- Config ----
N_PHASE2_RUNS = int(os.environ.get("PHASE2_RUNS", "100"))  # e.g., 300/500/1000 for steadier stats
SAFE_MODE = int(os.environ.get("SAFE_MODE", "0"))           # not used directly here; harmless if present
DATA_DIR = os.environ.get("DATA_DIR", "/tmp")
os.makedirs(DATA_DIR, exist_ok=True)

# Official pools
MM_MAIN_MAX, MM_MAIN_COUNT, MM_BONUS_MAX = 70, 5, 25   # Mega Millions
PB_MAIN_MAX, PB_MAIN_COUNT, PB_BONUS_MAX = 69, 5, 26   # Powerball
IL_MAIN_MAX, IL_MAIN_COUNT = 50, 6                     # IL Lotto

# -----------------------------------------------------------------------------
# Small utils
# -----------------------------------------------------------------------------
def _now_stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

def _save_json(obj: dict, prefix: str) -> str:
    path = os.path.join(DATA_DIR, f"{prefix}_{_now_stamp()}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    return path

def _quantile(x: List[int], q: float) -> int:
    if not x: return 0
    s = sorted(x)
    pos = q * (len(s) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi: return s[lo]
    return int(round(s[lo] + (s[hi] - s[lo]) * (pos - lo)))

def _sum_band_from_history(hist: List[List[int]], default_lo: int, default_hi: int) -> Tuple[int, int]:
    if not hist: return (default_lo, default_hi)
    sums = [sum(row) for row in hist]
    lo = _quantile(sums, 0.25)
    hi = _quantile(sums, 0.75)
    if lo >= hi: return (default_lo, default_hi)
    return (lo, hi)

def _flatten(lst): return [y for x in lst for y in x]

# -----------------------------------------------------------------------------
# Parsing helpers
# -----------------------------------------------------------------------------
def _parse_latest_pair(s: str, has_bonus: bool) -> Tuple[List[int], Optional[int]]:
    """
    Accepts strings like "[10,14,34,40,43], 5" or "([..], 5)" or "[1,4,5,10,18,49]".
    """
    if not isinstance(s, str):
        raise ValueError("LATEST_* must be a string like '[..], b' or '[..]'")
    txt = s.strip().replace("(", "[").replace(")", "]")
    if "]," in txt:
        left, right = txt.split("],", 1)
        mains_txt = left.strip().lstrip("[").strip()
        mains = [int(x.strip()) for x in mains_txt.split(",") if x.strip()]
        bonus = int(right.strip().strip(","))
        return mains, bonus
    else:
        mains_txt = txt.lstrip("[").rstrip("]")
        mains = [int(x.strip()) for x in mains_txt.split(",") if x.strip()]
        return mains, None

def _parse_hist_blob(blob: str, has_bonus: bool) -> List[Tuple[List[int], Optional[int]]]:
    """
    HIST blobs:
      MM/PB: "17-18-21-42-64 07"
      IL   : "05-06-14-15-48-49"
    Only the **first 20** lines are used (last 20 draws).
    """
    out = []
    for line in (blob or "").strip().splitlines():
        L = line.strip()
        if not L: continue
        if has_bonus:
            parts = L.split()
            mains = [int(x) for x in parts[0].split("-")]
            bonus = int(parts[1])
            out.append((mains, bonus))
        else:
            mains = [int(x) for x in L.split("-")]
            out.append((mains, None))
    return out[:20]

def _parse_feed_lines(feed: str) -> Dict[str, List[int]]:
    """
    FEED_MM / FEED_PB:
      Top 8 hot numbers: ...
      Top 8 overdue numbers: ...
      Top 3 hot Mega/Power Ball numbers: ...
      Top 3 overdue Mega/Power Ball numbers: ...
    FEED_IL:
      Top 8 hot numbers: ...
      Top 8 overdue numbers: ...
    """
    d: Dict[str, List[int]] = {}
    for line in (feed or "").strip().splitlines():
        L = line.strip()
        if not L: continue
        low = L.lower()
        key = None
        if low.startswith("top 8 hot numbers"):
            key = "hot_mains"
        elif low.startswith("top 8 overdue numbers"):
            key = "overdue_mains"
        elif ("mega ball" in low or "power ball" in low):
            if "hot" in low: key = "hot_bonus"
            elif "overdue" in low: key = "overdue_bonus"
        if key:
            nums_part = L.split(":", 1)[1] if ":" in L else ""
            vals = [int(x.strip()) for x in nums_part.replace(",", " ").split() if x.strip().isdigit()]
            d[key] = vals
    for k in ("hot_mains", "overdue_mains", "hot_bonus", "overdue_bonus"):
        d.setdefault(k, [])
    return d

# -----------------------------------------------------------------------------
# Pools & anchors (VIP, LRR, Undrawn, Hot, Overdue)
# -----------------------------------------------------------------------------
def _counts_in_history(history: List[List[int]]) -> Dict[int, int]:
    c: Dict[int, int] = {}
    for row in history:
        for n in row:
            c[n] = c.get(n, 0) + 1
    return c

def _lrr_set(history20: List[List[int]], recent5: List[List[int]]) -> List[int]:
    cnt = _counts_in_history(history20)
    recent = set(_flatten(recent5))
    return [n for n, c in cnt.items() if c == 2 and n not in recent]

def _undrawn_set(all_numbers: List[int], recent10: List[List[int]]) -> List[int]:
    recent = set(_flatten(recent10))
    return [n for n in all_numbers if n not in recent]

def _vip_set(hot: List[int], overdue: List[int]) -> List[int]:
    return sorted(list(set(hot) & set(overdue)))

def _cap_pool(pool: List[int], limit: int) -> List[int]:
    # cap pool without reseeding RNG (keeps runs varied)
    if len(pool) <= limit: return pool[:]
    return random.sample(pool, limit)

# -----------------------------------------------------------------------------
# Hit labeling
# -----------------------------------------------------------------------------
def _label_hit(game: str,
               mains: List[int],
               bonus: Optional[int],
               target_mains: List[int],
               target_bonus: Optional[int]) -> Optional[str]:
    """
    MM/PB: '3','3B','4','4B','5','5B' ; IL: '3','4','5','6'
    """
    m = len(set(mains) & set(target_mains))
    if game in ("MM", "PB"):
        b = (bonus is not None and target_bonus is not None and bonus == target_bonus)
        if m == 5: return "5B" if b else "5"
        if m == 4: return "4B" if b else "4"
        if m == 3: return "3B" if b else "3"
        return None
    if game == "IL":
        if m == 6: return "6"
        if m == 5: return "5"
        if m == 4: return "4"
        if m == 3: return "3"
        return None
    return None

# -----------------------------------------------------------------------------
# Bands (middle 50%)
# -----------------------------------------------------------------------------
def _bands_from_histories(mm_hist: List[List[int]],
                          pb_hist: List[List[int]],
                          il_hist: List[List[int]]) -> Dict[str, List[int]]:
    mm_default = (158, 205)
    pb_default = (149, 210)
    il_default = (123, 158)
    mm = _sum_band_from_history(mm_hist, *mm_default)
    pb = _sum_band_from_history(pb_hist, *pb_default)
    il = _sum_band_from_history(il_hist, *il_default)
    return {"MM": [mm[0], mm[1]], "PB": [pb[0], pb[1]], "IL": [il[0], il[1]]}

# -----------------------------------------------------------------------------
# Row generation & per-batch creation
# -----------------------------------------------------------------------------
def _choose_bonus(feed_bonus_hot: List[int], feed_bonus_overdue: List[int],
                  bonus_max: int, recent10_bonus: List[int]) -> int:
    candidates = []
    candidates += feed_bonus_hot[:]
    candidates += feed_bonus_overdue[:]
    undrawn = [n for n in range(1, bonus_max + 1) if n not in recent10_bonus]
    candidates += _cap_pool(undrawn, 10)
    candidates = [n for n in candidates if 1 <= n <= bonus_max]
    return random.choice(candidates) if candidates else random.randint(1, bonus_max)

def _make_row_with_pattern(game: str,
                           pattern: Tuple[int, int, int, int],  # (vip_or_lrr, hot, overdue, undrawn)
                           pools: Dict[str, List[int]],
                           count_required: int,
                           sum_band: Tuple[int, int],
                           universe_max: int,
                           max_tries: int = 50) -> Optional[List[int]]:
    lo, hi = sum_band
    vip = pools.get("VIP", [])
    lrr = pools.get("LRR", [])
    hot = pools.get("HOT", [])
    overdue = pools.get("OVERDUE", [])
    undrawn = pools.get("UNDRAWN", [])
    other = pools.get("OTHER", [])

    def try_once() -> List[int]:
        k_anchor, k_hot, k_over, k_und = pattern
        chosen: List[int] = []
        # Anchor (VIP else LRR)
        anchors = vip[:] if vip else lrr[:]
        random.shuffle(anchors); chosen += anchors[:k_anchor]
        # Hot
        h = _cap_pool(hot, max(0, k_hot * 8)); random.shuffle(h); chosen += h[:k_hot]
        # Overdue
        o = _cap_pool(overdue, max(0, k_over * 8)); random.shuffle(o); chosen += o[:k_over]
        # Undrawn
        u = _cap_pool(undrawn, max(0, k_und * 10)); random.shuffle(u); chosen += u[:k_und]
        base = [n for n in chosen if 1 <= n <= universe_max]
        # Fill remaining from other
        need = count_required - len(set(base))
        if need > 0:
            rest = [n for n in other if n not in base]
            random.shuffle(rest)
            base += rest[:need]
        uniq = sorted(list(set(base)))
        while len(uniq) > count_required:
            uniq.pop(random.randrange(len(uniq)))
        return uniq

    for _ in range(max_tries):
        row = try_once()
        if len(row) != count_required:
            continue
        s = sum(row)
        if lo <= s <= hi:
            return sorted(row)
    return None

def _build_pools_for_game(hist20: List[List[int]],
                          feeds: Dict[str, List[int]],
                          all_numbers: List[int]) -> Dict[str, List[int]]:
    recent10 = hist20[:10] if len(hist20) >= 10 else hist20
    recent5 = hist20[:5] if len(hist20) >= 5 else hist20
    undrawn = _undrawn_set(all_numbers, recent10)
    lrr = _lrr_set(hist20, recent5)
    hot = feeds.get("hot_mains", [])
    overdue = feeds.get("overdue_mains", [])
    vip = _vip_set(hot, overdue)
    used = set(vip) | set(lrr) | set(hot) | set(overdue) | set(undrawn)
    other = [n for n in all_numbers if n not in used]
    return {"VIP": vip, "LRR": lrr, "HOT": hot, "OVERDUE": overdue, "UNDRAWN": undrawn, "OTHER": other}

# Patterns (approximation combining VIP/LRR variants)
MM_PB_PATTERNS = [
    (1,1,0,3),(1,1,1,2),(1,1,2,1),(1,2,0,2),(1,2,1,1),(1,3,0,1),
    (1,0,1,3),(1,0,2,2),(1,0,3,1),
] * 2  # 18 patterns
IL_PATTERNS = [
    (1,1,0,4),(1,1,1,3),(1,1,2,2),(1,1,3,1),
    (1,2,0,3),(1,2,1,2),(1,2,2,1),(1,2,3,0),
    (1,3,0,2),(1,3,1,1),(1,3,2,0),
    (1,4,0,1),(1,4,1,0),(1,5,0,0),
    (1,0,1,4),(1,0,2,3),(1,0,3,3),(1,0,4,1),(1,0,5,0),
] * 2

def _generate_batches(state: dict) -> Dict[str, Any]:
    bands = state["BANDS"]

    # MM
    mm_rows = []
    mm_patterns = MM_PB_PATTERNS[:]; random.shuffle(mm_patterns)
    mm_pool = state["POOLS_MM"]
    for i in range(50):
        pat = mm_patterns[i % len(mm_patterns)]
        mains = _make_row_with_pattern("MM", pat, mm_pool, MM_MAIN_COUNT, tuple(bands["MM"]), MM_MAIN_MAX)
        if mains is None:
            mains = sorted(random.sample(range(1, MM_MAIN_MAX + 1), MM_MAIN_COUNT))
        bonus = _choose_bonus(
            state["FEED_MM"].get("hot_bonus", []),
            state["FEED_MM"].get("overdue_bonus", []),
            MM_BONUS_MAX,
            state["RECENT_MM_BONUS"],
        )
        mm_rows.append({"row": i + 1, "mains": mains, "bonus": bonus, "sum": sum(mains)})

    # PB
    pb_rows = []
    pb_patterns = MM_PB_PATTERNS[:]; random.shuffle(pb_patterns)
    pb_pool = state["POOLS_PB"]
    for i in range(50):
        pat = pb_patterns[i % len(pb_patterns)]
        mains = _make_row_with_pattern("PB", pat, pb_pool, PB_MAIN_COUNT, tuple(bands["PB"]), PB_MAIN_MAX)
        if mains is None:
            mains = sorted(random.sample(range(1, PB_MAIN_MAX + 1), PB_MAIN_COUNT))
        bonus = _choose_bonus(
            state["FEED_PB"].get("hot_bonus", []),
            state["FEED_PB"].get("overdue_bonus", []),
            PB_BONUS_MAX,
            state["RECENT_PB_BONUS"],
        )
        pb_rows.append({"row": i + 1, "mains": mains, "bonus": bonus, "sum": sum(mains)})

    # IL (JP/M1/M2)
    il_rows = {"JP": [], "M1": [], "M2": []}
    il_patterns = IL_PATTERNS[:]; random.shuffle(il_patterns)
    il_pool = state["POOLS_IL"]
    for bucket in ("JP", "M1", "M2"):
        rows = []
        for i in range(50):
            pat = il_patterns[i % len(il_patterns)]
            mains = _make_row_with_pattern("IL", pat, il_pool, IL_MAIN_COUNT, tuple(bands["IL"]), IL_MAIN_MAX)
            if mains is None:
                mains = sorted(random.sample(range(1, IL_MAIN_MAX + 1), IL_MAIN_COUNT))
            rows.append({"row": i + 1, "mains": mains, "bonus": None, "sum": sum(mains)})
        il_rows[bucket] = rows

    return {"MM": mm_rows, "PB": pb_rows, "IL": il_rows}

def _eval_vs_target(state: dict, batches: dict) -> Dict[str, Any]:
    mm_t = state["LATEST_MM"]
    pb_t = state["LATEST_PB"]
    il_jp = state["LATEST_IL_JP"][0]
    il_m1 = state["LATEST_IL_M1"][0]
    il_m2 = state["LATEST_IL_M2"][0]

    eval_dict = {
        "MM": {"3": [], "3B": [], "4": [], "4B": [], "5": [], "5B": []},
        "PB": {"3": [], "3B": [], "4": [], "4B": [], "5": [], "5B": []},
        "IL": {
            "JP": {"3": [], "4": [], "5": [], "6": []},
            "M1": {"3": [], "4": [], "5": [], "6": []},
            "M2": {"3": [], "4": [], "5": [], "6": []},
        },
    }
    for r in batches["MM"]:
        hit = _label_hit("MM", r["mains"], r["bonus"], mm_t[0], mm_t[1])
        r["hit"] = hit
        if hit: eval_dict["MM"][hit].append(r["row"])
    for r in batches["PB"]:
        hit = _label_hit("PB", r["mains"], r["bonus"], pb_t[0], pb_t[1])
        r["hit"] = hit
        if hit: eval_dict["PB"][hit].append(r["row"])
    for bucket, target in (("JP", il_jp), ("M1", il_m1), ("M2", il_m2)):
        for r in batches["IL"][bucket]:
            hit = _label_hit("IL", r["mains"], None, target, None)
            r["hit"] = hit
            if hit: eval_dict["IL"][bucket][hit].append(r["row"])
    return eval_dict

# -----------------------------------------------------------------------------
# Build state from Phase-1 inputs / saved file
# -----------------------------------------------------------------------------
def _build_state_from_phase1_inputs(data: dict) -> dict:
    mm_latest = _parse_latest_pair(data.get("LATEST_MM", ""), True)
    pb_latest = _parse_latest_pair(data.get("LATEST_PB", ""), True)
    il_jp_latest = _parse_latest_pair(data.get("LATEST_IL_JP", ""), False)
    il_m1_latest = _parse_latest_pair(data.get("LATEST_IL_M1", ""), False)
    il_m2_latest = _parse_latest_pair(data.get("LATEST_IL_M2", ""), False)

    feed_mm = _parse_feed_lines(data.get("FEED_MM", ""))
    feed_pb = _parse_feed_lines(data.get("FEED_PB", ""))
    feed_il = _parse_feed_lines(data.get("FEED_IL", ""))

    mm_hist_pairs = _parse_hist_blob(data.get("HIST_MM_BLOB", ""), True)
    pb_hist_pairs = _parse_hist_blob(data.get("HIST_PB_BLOB", ""), True)
    il_hist_pairs = _parse_hist_blob(data.get("HIST_IL_BLOB", ""), False)

    mm_hist = [m for (m, _) in mm_hist_pairs]
    pb_hist = [m for (m, _) in pb_hist_pairs]
    il_hist = [m for (m, _) in il_hist_pairs]

    bands = _bands_from_histories(mm_hist, pb_hist, il_hist)

    state = {
        "LATEST_MM": mm_latest,
        "LATEST_PB": pb_latest,
        "LATEST_IL_JP": il_jp_latest,
        "LATEST_IL_M1": il_m1_latest,
        "LATEST_IL_M2": il_m2_latest,
        "FEED_MM": feed_mm,
        "FEED_PB": feed_pb,
        "FEED_IL": feed_il,
        "HIST_MM": mm_hist,
        "HIST_PB": pb_hist,
        "HIST_IL": il_hist,
        "BANDS": bands,
        "POOLS_MM": _build_pools_for_game(mm_hist, feed_mm, list(range(1, MM_MAIN_MAX + 1))),
        "POOLS_PB": _build_pools_for_game(pb_hist, feed_pb, list(range(1, PB_MAIN_MAX + 1))),
        "POOLS_IL": _build_pools_for_game(il_hist, feed_il, list(range(1, IL_MAIN_MAX + 1))),
        "RECENT_MM_BONUS": [b for (_, b) in mm_hist_pairs[:10] if b is not None],
        "RECENT_PB_BONUS": [b for (_, b) in pb_hist_pairs[:10] if b is not None],
    }
    return state

def rebuild_state_from_phase1(p1: dict) -> dict:
    inputs = p1.get("inputs", {})
    return _build_state_from_phase1_inputs(inputs)

# -----------------------------------------------------------------------------
# Buy list (single-batch quick recommender, Phase-2 uses cross-run freq)
# -----------------------------------------------------------------------------
def _recommend_from_freq(freq_main: Dict[int, int], k: int, exclude: List[int] = []) -> List[int]:
    cand = [(n, c) for n, c in freq_main.items() if n not in exclude]
    cand.sort(key=lambda t: (-t[1], t[0]))
    return [n for (n, _) in cand[:k]]

def recommend_buy_lists(state: dict, runs: dict) -> Dict[str, Any]:
    def freq_of(rows: List[dict]) -> Dict[int, int]:
        f: Dict[int, int] = {}
        for r in rows:
            for n in r["mains"]:
                f[n] = f.get(n, 0) + 1
        return f

    mm_f = freq_of(runs.get("MM", []))
    pb_f = freq_of(runs.get("PB", []))
    il_jp_f = freq_of(runs.get("IL", {}).get("JP", []))
    il_m1_f = freq_of(runs.get("IL", {}).get("M1", []))
    il_m2_f = freq_of(runs.get("IL", {}).get("M2", []))
    il_all = {k: il_jp_f.get(k, 0) + il_m1_f.get(k, 0) + il_m2_f.get(k, 0) for k in range(1, IL_MAIN_MAX + 1)}

    mm_top = _recommend_from_freq(mm_f, 20)
    pb_top = _recommend_from_freq(pb_f, 20)
    il_top = _recommend_from_freq(il_all, 30)

    mm_bonus_pool = state["FEED_MM"].get("hot_bonus", []) + state["FEED_MM"].get("overdue_bonus", [])
    pb_bonus_pool = state["FEED_PB"].get("hot_bonus", []) + state["FEED_PB"].get("overdue_bonus", [])

    def top_bonus(pool: List[int], mx: int, take: int) -> List[int]:
        ok = [n for n in pool if 1 <= n <= mx]
        if not ok: return [random.randint(1, mx) for _ in range(take)]
        while len(ok) < take: ok.append(random.choice(ok))
        return ok[:take]

    mm_tickets, pb_tickets, il_tickets = [], [], []
    mm_bonus_list = top_bonus(mm_bonus_pool, MM_BONUS_MAX, 10)
    pb_bonus_list = top_bonus(pb_bonus_pool, PB_BONUS_MAX, 10)

    for i in range(10):
        chunk = mm_top[i:i + 5] if len(mm_top) >= i + 5 else sorted(random.sample(range(1, MM_MAIN_MAX + 1), 5))
        mm_tickets.append({"mains": sorted(chunk), "bonus": mm_bonus_list[i]})
    for i in range(10):
        chunk = pb_top[i:i + 5] if len(pb_top) >= i + 5 else sorted(random.sample(range(1, PB_MAIN_MAX + 1), 5))
        pb_tickets.append({"mains": sorted(chunk), "bonus": pb_bonus_list[i]})
    for i in range(15):
        chunk = il_top[i:i + 6] if len(il_top) >= i + 6 else sorted(random.sample(range(1, IL_MAIN_MAX + 1), 6))
        il_tickets.append({"mains": sorted(chunk), "bonus": None})

    return {"MM": mm_tickets, "PB": pb_tickets, "IL": il_tickets}

# -----------------------------------------------------------------------------
# PHASE 1 / 2 / 3
# -----------------------------------------------------------------------------
def run_phase1(data: dict) -> dict:
    try:
        state = _build_state_from_phase1_inputs(data)
    except Exception as e:
        return {"ok": False, "error": type(e).__name__, "detail": str(e)}

    batches = _generate_batches(state)
    eval_vs = _eval_vs_target(state, batches)

    p1_save = {"inputs": data, "bands": state["BANDS"], "ok": True, "phase": "phase1"}
    saved = _save_json(p1_save, "lotto_phase1")

    return {
        "ok": True,
        "phase": "phase1",
        "bands": state["BANDS"],
        "batches": batches,
        "eval_vs_NJ": eval_vs,
        "saved_path": saved,
        "note": "Use saved_path for Phase 2.",
    }

def run_phase2(saved_phase1_path: str) -> dict:
    try:
        with open(saved_phase1_path, "r", encoding="utf-8") as f:
            p1 = json.load(f)
    except Exception as e:
        return {"ok": False, "error": type(e).__name__, "detail": str(e)}

    # Optional reproducibility
    seed = os.environ.get("PHASE2_SEED")
    if seed:
        random.seed(int(seed))

    state = rebuild_state_from_phase1(p1)

    agg = {
        "MM": {"3": [], "3B": [], "4": [], "4B": [], "5": [], "5B": []},
        "PB": {"3": [], "3B": [], "4": [], "4B": [], "5": [], "5B": []},
        "IL": {
            "JP": {"3": [], "4": [], "5": [], "6": []},
            "M1": {"3": [], "4": [], "5": [], "6": []},
            "M2": {"3": [], "4": [], "5": [], "6": []},
        },
    }

    freq_mm: Dict[int, int] = {}
    freq_pb: Dict[int, int] = {}
    freq_il: Dict[int, int] = {}

    for _ in range(N_PHASE2_RUNS):
        runs = _generate_batches(state)
        tmp_eval = _eval_vs_target(state, runs)

        for k in ("3", "3B", "4", "4B", "5", "5B"):
            agg["MM"][k] += tmp_eval["MM"][k]
            agg["PB"][k] += tmp_eval["PB"][k]
        for bucket in ("JP", "M1", "M2"):
            for k in ("3", "4", "5", "6"):
                agg["IL"][bucket][k] += tmp_eval["IL"][bucket][k]

        for r in runs.get("MM", []):
            for n in r["mains"]:
                freq_mm[n] = freq_mm.get(n, 0) + 1
        for r in runs.get("PB", []):
            for n in r["mains"]:
                freq_pb[n] = freq_pb.get(n, 0) + 1
        for bucket in ("JP", "M1", "M2"):
            for r in runs.get("IL", {}).get(bucket, []):
                for n in r["mains"]:
                    freq_il[n] = freq_il.get(n, 0) + 1

    mm_bonus_pool = state["FEED_MM"].get("hot_bonus", []) + state["FEED_MM"].get("overdue_bonus", [])
    pb_bonus_pool = state["FEED_PB"].get("hot_bonus", []) + state["FEED_PB"].get("overdue_bonus", [])

    def pick_bonus(pool: List[int], mx: int, take: int) -> List[int]:
        ok = [x for x in pool if 1 <= x <= mx]
        if not ok:
            return [random.randint(1, mx) for _ in range(take)]
        res: List[int] = []
        while len(res) < take: res += ok
        return res[:take]

    mm_sorted = sorted(freq_mm.items(), key=lambda t: (-t[1], t[0]))
    pb_sorted = sorted(freq_pb.items(), key=lambda t: (-t[1], t[0]))
    il_sorted = sorted(freq_il.items(), key=lambda t: (-t[1], t[0]))
    mm_nums = [n for (n, _) in mm_sorted]
    pb_nums = [n for (n, _) in pb_sorted]
    il_nums = [n for (n, _) in il_sorted]

    buy_mm: List[Dict[str, Any]] = []
    buy_pb: List[Dict[str, Any]] = []
    buy_il: List[Dict[str, Any]] = []

    mm_bonus_list = pick_bonus(mm_bonus_pool, MM_BONUS_MAX, 10)
    pb_bonus_list = pick_bonus(pb_bonus_pool, PB_BONUS_MAX, 10)

    for i in range(10):
        chunk = mm_nums[i * 5:(i + 1) * 5]
        if len(chunk) < 5:
            rem = [x for x in range(1, MM_MAIN_MAX + 1) if x not in chunk]
            random.shuffle(rem); chunk += rem[:5 - len(chunk)]
        buy_mm.append({"mains": sorted(chunk), "bonus": mm_bonus_list[i]})

    for i in range(10):
        chunk = pb_nums[i * 5:(i + 1) * 5]
        if len(chunk) < 5:
            rem = [x for x in range(1, PB_MAIN_MAX + 1) if x not in chunk]
            random.shuffle(rem); chunk += rem[:5 - len(chunk)]
        buy_pb.append({"mains": sorted(chunk), "bonus": pb_bonus_list[i]})

    for i in range(15):
        chunk = il_nums[i * 6:(i + 1) * 6]
        if len(chunk) < 6:
            rem = [x for x in range(1, IL_MAIN_MAX + 1) if x not in chunk]
            random.shuffle(rem); chunk += rem[:6 - len(chunk)]
        buy_il.append({"mains": sorted(chunk), "bonus": None})

    result = {
        "ok": True,
        "phase": "phase2",
        "bands": state["BANDS"],
        "buy_lists": {"MM": buy_mm, "PB": buy_pb, "IL": buy_il},
        "agg_hits": agg,
        "note": "Use saved_path for Phase 3 confirmation after the next official draw.",
    }
    result["saved_path"] = _save_json(result, "lotto_phase2")
    return result

def run_phase3(saved_phase2_path: str, nwj: Optional[dict] = None) -> dict:
    try:
        with open(saved_phase2_path, "r", encoding="utf-8") as f:
            p2 = json.load(f)
    except Exception as e:
        return {"ok": False, "error": type(e).__name__, "detail": str(e)}

    if nwj:
        mm_t = (nwj.get("LATEST_MM", [[], None])[0], nwj.get("LATEST_MM", [[], None])[1])
        pb_t = (nwj.get("LATEST_PB", [[], None])[0], nwj.get("LATEST_PB", [[], None])[1])
        il_jp = nwj.get("LATEST_IL_JP", [[], None])[0]
        il_m1 = nwj.get("LATEST_IL_M1", [[], None])[0]
        il_m2 = nwj.get("LATEST_IL_M2", [[], None])[0]
    else:
        mm_t = ([], None); pb_t = ([], None)
        il_jp = []; il_m1 = []; il_m2 = []

    bl = p2.get("buy_lists", {})
    out = {
        "MM": {"3": [], "3B": [], "4": [], "4B": [], "5": [], "5B": []},
        "PB": {"3": [], "3B": [], "4": [], "4B": [], "5": [], "5B": []},
        "IL": {
            "JP": {"3": [], "4": [], "5": [], "6": []},
            "M1": {"3": [], "4": [], "5": [], "6": []},
            "M2": {"3": [], "4": [], "5": [], "6": []},
        },
    }
    for i, t in enumerate(bl.get("MM", []), start=1):
        hit = _label_hit("MM", t.get("mains", []), t.get("bonus"), mm_t[0], mm_t[1])
        if hit: out["MM"][hit].append(i)
    for i, t in enumerate(bl.get("PB", []), start=1):
        hit = _label_hit("PB", t.get("mains", []), t.get("bonus"), pb_t[0], pb_t[1])
        if hit: out["PB"][hit].append(i)
    for i, t in enumerate(bl.get("IL", []), start=1):
        for bucket, target in (("JP", il_jp), ("M1", il_m1), ("M2", il_m2)):
            hit = _label_hit("IL", t.get("mains", []), None, target, None)
            if hit: out["IL"][bucket][hit].append(i)

    return {"ok": True, "confirm_hits": out}

# -----------------------------------------------------------------------------
# Recent & health
# -----------------------------------------------------------------------------
def list_recent_files(limit: int = 50) -> List[str]:
    try:
        files = sorted(
            [os.path.join(DATA_DIR, f) for f in os.listdir(DATA_DIR)
             if f.startswith("lotto_phase") and f.endswith(".json")],
            key=lambda p: os.path.getmtime(p),
            reverse=True,
        )
        return files[:limit]
    except Exception:
        return []

def health() -> dict:
    try:
        return {"ok": True, "core_loaded": True, "err": None}
    except Exception as e:
        return {"ok": True, "core_loaded": False, "err": f"{type(e).__name__}: {e}"}

# =========================
# COMPATIBILITY APPENDIX
# Ensure the functions that app.py expects are present, forwarding to alternates if needed.
# Append this block at the very bottom of lottery_core.py.
# =========================
import os, glob, json, traceback
from typing import Any, Dict

# Where we save JSON state files
_DATA_DIR = os.environ.get("DATA_DIR", "/tmp")

def _err(msg: str) -> Dict[str, Any]:
    return {"ok": False, "error": "MissingFunction", "detail": msg}

def _exists(name: str) -> bool:
    return name in globals() and callable(globals()[name])

# ---- Phase 1 wrapper ----
if "handle_run" not in globals():
    def handle_run(payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Expected by app.py for Phase 1.
        Tries to forward to your existing Phase-1 function if named differently.
        """
        for alt in ("run_phase1", "phase1_run", "evaluate_phase1", "run_json_core"):
            if _exists(alt):
                try:
                    return globals()[alt](payload)
                except Exception as e:
                    tb = traceback.format_exc()
                    return {"ok": False, "error": type(e).__name__, "detail": str(e), "trace": tb}
        return _err("lottery_core.handle_run not defined and no known Phase-1 function found "
                    "(looked for run_phase1 / evaluate_phase1 / run_json_core).")

# ---- Phase 2 wrapper ----
if "run_phase2" not in globals():
    def run_phase2(saved_phase1_path: str) -> Dict[str, Any]:
        """
        Expected by app.py for Phase 2.
        Tries to forward to your existing Phase-2 function if named differently.
        """
        for alt in ("phase2_run", "predict_phase2", "run_phase2_core"):
            if _exists(alt):
                try:
                    return globals()[alt](saved_phase1_path)
                except Exception as e:
                    tb = traceback.format_exc()
                    return {"ok": False, "error": type(e).__name__, "detail": str(e), "trace": tb}
        return _err("lottery_core.run_phase2 not defined and no known Phase-2 function found "
                    "(looked for phase2_run / predict_phase2 / run_phase2_core).")

# ---- Phase 3 wrapper ----
if "handle_confirm" not in globals():
    def handle_confirm(saved_phase2_path: str, nwj: Dict[str, Any] | None) -> Dict[str, Any]:
        """
        Expected by app.py for Phase 3.
        Tries to forward to your existing Phase-3 function if named differently.
        """
        for alt in ("confirm_phase3", "phase3_confirm", "run_confirmation"):
            if _exists(alt):
                try:
                    return globals()[alt](saved_phase2_path, nwj)
                except Exception as e:
                    tb = traceback.format_exc()
                    return {"ok": False, "error": type(e).__name__, "detail": str(e), "trace": tb}
        return _err("lottery_core.handle_confirm not defined and no known Phase-3 function found "
                    "(looked for confirm_phase3 / phase3_confirm / run_confirmation).")

# ---- Recent files helper ----
if "list_recent" not in globals():
    def list_recent() -> list[str]:
        """
        Returns a list of recent Phase-1/2 JSON files in DATA_DIR (default /tmp).
        """
        patterns = [
            os.path.join(_DATA_DIR, "lotto_phase1_*.json"),
            os.path.join(_DATA_DIR, "lotto_phase2_*.json"),
        ]
        files = []
        for pat in patterns:
            for f in glob.glob(pat):
                try:
                    mtime = os.path.getmtime(f)
                except OSError:
                    mtime = 0
                files.append((mtime, f))
        files.sort(reverse=True)
        return [f for _, f in files][:100]
