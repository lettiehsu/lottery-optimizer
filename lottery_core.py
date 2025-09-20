# lottery_core.py — core engine with batch details

from __future__ import annotations
import json, os, re, random, datetime
from typing import List, Tuple, Dict, Optional

RNG = random.Random()

DEFAULT_SUM_BANDS = {"MM": (155, 201), "PB": (146, 207), "IL": (121, 158)}
GAME_SPECS = {
    "MM": {"main_n": 5, "main_max": 70, "bonus_max": 25},
    "PB": {"main_n": 5, "main_max": 69, "bonus_max": 26},
    "IL": {"main_n": 6, "main_max": 50, "bonus_max": None},
}

PATTERNS_MM_PB = [
    ("VIP", {"H":1, "O":0, "U":3}), ("VIP", {"H":1, "O":1, "U":2}),
    ("VIP", {"H":1, "O":2, "U":1}), ("VIP", {"H":2, "O":0, "U":2}),
    ("VIP", {"H":2, "O":1, "U":1}), ("VIP", {"H":3, "O":0, "U":1}),
    ("VIP", {"H":0, "O":1, "U":3}), ("VIP", {"H":0, "O":2, "U":2}),
    ("VIP", {"H":0, "O":3, "U":1}),
    ("LRR", {"H":1, "O":0, "U":3}), ("LRR", {"H":1, "O":1, "U":2}),
    ("LRR", {"H":1, "O":2, "U":1}), ("LRR", {"H":2, "O":0, "U":2}),
    ("LRR", {"H":2, "O":1, "U":1}), ("LRR", {"H":3, "O":0, "U":1}),
    ("LRR", {"H":0, "O":1, "U":3}), ("LRR", {"H":0, "O":2, "U":2}),
    ("LRR", {"H":0, "O":3, "U":1}),
]
PATTERNS_IL = [
    ("VIP", {"H":1, "O":0, "U":4}), ("VIP", {"H":1, "O":1, "U":3}),
    ("VIP", {"H":1, "O":2, "U":2}), ("VIP", {"H":1, "O":3, "U":1}),
    ("VIP", {"H":2, "O":0, "U":3}), ("VIP", {"H":2, "O":1, "U":2}),
    ("VIP", {"H":2, "O":2, "U":1}), ("VIP", {"H":2, "O":3, "U":0}),
    ("VIP", {"H":3, "O":0, "U":2}), ("VIP", {"H":3, "O":1, "U":1}),
    ("VIP", {"H":3, "O":2, "U":0}), ("VIP", {"H":4, "O":0, "U":1}),
    ("VIP", {"H":4, "O":1, "U":0}), ("VIP", {"H":5, "O":0, "U":0}),
    ("VIP", {"H":0, "O":1, "U":4}), ("VIP", {"H":0, "O":2, "U":3}),
    ("VIP", {"H":0, "O":3, "U":3}), ("VIP", {"H":0, "O":4, "U":1}),
    ("VIP", {"H":0, "O":5, "U":0}),
    ("LRR", {"H":1, "O":0, "U":4}), ("LRR", {"H":1, "O":1, "U":3}),
    ("LRR", {"H":1, "O":2, "U":2}), ("LRR", {"H":1, "O":3, "U":1}),
    ("LRR", {"H":2, "O":0, "U":3}), ("LRR", {"H":2, "O":1, "U":2}),
    ("LRR", {"H":2, "O":2, "U":1}), ("LRR", {"H":2, "O":3, "U":0}),
    ("LRR", {"H":3, "O":0, "U":2}), ("LRR", {"H":3, "O":1, "U":1}),
    ("LRR", {"H":3, "O":2, "U":0}), ("LRR", {"H":4, "O":0, "U":1}),
    ("LRR", {"H":4, "O":1, "U":0}), ("LRR", {"H":5, "O":0, "U":0}),
    ("LRR", {"H":0, "O":1, "U":4}), ("LRR", {"H":0, "O":2, "U":3}),
    ("LRR", {"H":0, "O":3, "U":3}), ("LRR", {"H":0, "O":4, "U":1}),
    ("LRR", {"H":0, "O":5, "U":0}),
]

def _nowstamp() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

def _save_json(obj, data_dir: str, prefix: str) -> str:
    os.makedirs(data_dir, exist_ok=True)
    path = os.path.join(data_dir, f"{prefix}_{_nowstamp()}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)
    return path

# ---------- parse helpers ----------

def parse_latest_pair(s: str) -> Tuple[List[int], Optional[int]]:
    s = (s or "").strip()
    if not s: raise ValueError("LATEST_* is empty")
    m = re.search(r"\[([0-9,\s]+)\]", s)
    if not m: raise ValueError(f"Bad LATEST format: {s}")
    mains = [int(x) for x in m.group(1).replace(" ", "").split(",") if x]
    rest = s[m.end():].strip().lstrip(",").strip()
    bonus = None
    if rest:
        rest = rest.split()[0]
        bonus = None if rest.lower().startswith("none") else int(re.sub(r"[^0-9]", "", rest) or "0")
    return mains, bonus

def parse_hist_blob_mm(s: str) -> List[Tuple[List[int], int]]:
    lines = [ln.strip() for ln in (s or "").splitlines() if ln.strip()]
    out = []
    for ln in lines:
        m = re.match(r"([0-9\-]+)\s+([0-9]+)", ln)
        if not m: continue
        mains = [int(x) for x in m.group(1).split("-")]
        b = int(m.group(2))
        out.append((sorted(mains), b))
    return out[:20]

def parse_hist_blob_il(s: str) -> List[List[int]]:
    lines = [ln.strip() for ln in (s or "").splitlines() if ln.strip()]
    out = []
    for ln in lines:
        parts = ln.split("-")
        if len(parts) >= 6:
            mains = [int(x) for x in parts[:6]]
            out.append(sorted(mains))
    return out[:20]

def parse_feed_mm_pb(s: str) -> Dict[str, List[int]]:
    s = s or ""
    def find_nums(label_regex: str) -> List[int]:
        m = re.search(label_regex + r"\s*:\s*([^\r\n]+)", s, flags=re.I)
        if not m: return []
        return [int(x) for x in re.findall(r"\d+", m.group(1))]
    hot = find_nums(r"Top\s+8\s+hot\s+numbers")
    overdue = find_nums(r"Top\s+8\s+overdue\s+numbers")
    b_hot = find_nums(r"Top\s+3\s+hot\s+(Mega|Power)\s*Ball\s+numbers")
    b_over = find_nums(r"Top\s+3\s+overdue\s+(Mega|Power)\s*Ball\s+numbers")
    return {"hot": hot, "overdue": overdue, "bonus_hot": b_hot, "bonus_overdue": b_over}

def parse_feed_il(s: str) -> Dict[str, List[int]]:
    s = s or ""
    def find_nums(label_regex: str) -> List[int]:
        m = re.search(label_regex + r"\s*:\s*([^\r\n]+)", s, flags=re.I)
        if not m: return []
        return [int(x) for x in re.findall(r"\d+", m.group(1))]
    hot = find_nums(r"Top\s+8\s+hot\s+numbers")
    overdue = find_nums(r"Top\s+8\s+overdue\s+numbers")
    return {"hot": hot, "overdue": overdue}

# ---------- feature sets ----------

def compute_vip(hot: List[int], overdue: List[int]) -> List[int]:
    return sorted(list(set(hot).intersection(overdue)))

def compute_lrr(main_lists: List[List[int]]) -> List[int]:
    from collections import Counter
    flat = [n for row in main_lists for n in row]
    c = Counter(flat)
    last5 = set(n for row in main_lists[:5] for n in row)
    return sorted([n for n, cnt in c.items() if cnt == 2 and n not in last5])

def compute_undrawn(main_lists: List[List[int]], universe_max: int, last_k: int = 10) -> List[int]:
    recent = set(n for row in main_lists[:last_k] for n in row)
    all_nums = set(range(1, universe_max + 1))
    return sorted(list(all_nums - recent))

def middle50_from_hist(main_lists: List[List[int]], fallback: Tuple[int,int]) -> Tuple[int,int]:
    sums = [sum(row) for row in main_lists]
    if len(sums) < 8: return fallback
    sums_sorted = sorted(sums)
    q1 = sums_sorted[len(sums_sorted)//4]
    q3 = sums_sorted[(3*len(sums_sorted))//4]
    return (q1, q3)

def _hist_mains_only_mm(hist_mm: List[Tuple[List[int], int]]) -> List[List[int]]:
    return [row for (row, _) in hist_mm]

def middle_band(game: str, hist_mains: List[List[int]]) -> Tuple[int,int]:
    base = DEFAULT_SUM_BANDS[game]
    try:
        q1, q3 = middle50_from_hist(hist_mains, base)
        return (q1, q3) if q1 < q3 else base
    except Exception:
        return base

# ---------- generation ----------

def _choose_from(pool: List[int], k: int, exclude: set) -> List[int]:
    cand = [x for x in pool if x not in exclude]
    RNG.shuffle(cand)
    return cand[:max(0, k)]

def _gen_ticket_with_pattern(game: str, pattern_anchor: str, pattern_counts: Dict[str,int],
                             pools: Dict[str,List[int]], lrr_rotation: List[int],
                             vip_rotation: List[int], sum_band: Tuple[int,int]) -> Tuple[List[int], Optional[int]]:
    spec = GAME_SPECS[game]
    need = spec["main_n"]; chosen = []; used = set()

    anchor_list = vip_rotation if (pattern_anchor == "VIP" and vip_rotation) else lrr_rotation
    if anchor_list:
        a = anchor_list.pop(0); anchor_list.append(a)
        chosen.append(a); used.add(a)

    for key, pool_key in [("H","hot"), ("O","overdue"), ("U","undrawn")]:
        cnt = pattern_counts.get(key, 0)
        if cnt <= 0: continue
        for n in _choose_from(pools.get(pool_key, []), cnt, used):
            if n not in used:
                chosen.append(n); used.add(n)

    union = list(dict.fromkeys(pools.get("hot", []) + pools.get("overdue", []) + pools.get("undrawn", [])))
    for n in union:
        if len(chosen) >= need: break
        if n not in used:
            chosen.append(n); used.add(n)

    if len(chosen) < need:
        for n in range(1, spec["main_max"]+1):
            if len(chosen) >= need: break
            if n not in used:
                chosen.append(n); used.add(n)

    mains = sorted(chosen[:need])

    lo, hi = sum_band
    if not (lo <= sum(mains) <= hi):
        RNG.shuffle(union)
        fill = []
        for n in union:
            if len(fill) >= need: break
            if n not in set(fill):
                fill.append(n)
        mains2 = sorted(fill[:need]) if len(fill) >= need else mains
        if lo <= sum(mains2) <= hi:
            mains = mains2

    bonus = None
    if spec["bonus_max"]:
        b_pool = (pools.get("bonus_hot", []) + pools.get("bonus_overdue", [])) or list(range(1, spec["bonus_max"]+1))
        bonus = RNG.choice(b_pool)

    return mains, bonus

def build_50_pool(game: str, pools: Dict[str,List[int]], sum_band: Tuple[int,int]) -> List[Tuple[List[int], Optional[int]]]:
    out = []
    vip_rotation = pools.get("vip", [])[:] or pools.get("hot", [])[:]
    lrr_rotation = pools.get("lrr", [])[:] or pools.get("hot", [])[:]
    patterns = PATTERNS_MM_PB if game in ("MM","PB") else PATTERNS_IL
    idx = 0; guard = 0
    while len(out) < 50 and guard < 1000:
        pa, pc = patterns[idx % len(patterns)]
        out.append(_gen_ticket_with_pattern(game, pa, pc, pools, lrr_rotation, vip_rotation, sum_band))
        idx += 1; guard += 1
    return out

# ---------- annotate (for detailed tables) ----------

def _annotate_mm_pb(pool, latest_pair):
    target_mains, target_bonus = latest_pair
    stats = {"3": [], "3B": [], "4": [], "4B": [], "5": [], "5B": []}
    rows = []
    tset = set(target_mains)
    for i, (mains, bonus) in enumerate(pool, start=1):
        hit = len(set(mains).intersection(tset))
        hasB = (bonus == target_bonus)
        label = None
        if hit == 3: label = "3B" if hasB else "3"
        elif hit == 4: label = "4B" if hasB else "4"
        elif hit == 5: label = "5B" if hasB else "5"
        if label: stats[label].append(i)
        rows.append({"row": i, "mains": mains, "bonus": bonus, "sum": sum(mains), "hit": label})
    return rows, stats

def _annotate_il(pool, latest_mains):
    tset = set(latest_mains)
    stats = {"3": [], "4": [], "5": [], "6": []}
    rows = []
    for i, (mains, _none) in enumerate(pool, start=1):
        hit = len(set(mains).intersection(tset))
        label = str(hit) if hit in (3,4,5,6) else None
        if label: stats[label].append(i)
        rows.append({"row": i, "mains": mains, "bonus": None, "sum": sum(mains), "hit": label})
    return rows, stats

# ---------- phases ----------

def _pools_for_game(game: str, feed_hot: List[int], feed_over: List[int], hist_mains: List[List[int]],
                    bonus_hot: List[int] = None, bonus_over: List[int] = None) -> Dict[str,List[int]]:
    spec = GAME_SPECS[game]
    vip = compute_vip(feed_hot, feed_over)
    lrr = compute_lrr(hist_mains)
    undrawn = compute_undrawn(hist_mains, spec["main_max"], last_k=10)
    pools = {
        "hot": [n for n in feed_hot if 1 <= n <= spec["main_max"]],
        "overdue": [n for n in feed_over if 1 <= n <= spec["main_max"]],
        "undrawn": [n for n in undrawn if 1 <= n <= spec["main_max"]],
        "vip": [n for n in vip if 1 <= n <= spec["main_max"]],
        "lrr": [n for n in lrr if 1 <= n <= spec["main_max"]],
    }
    if GAME_SPECS[game]["bonus_max"]:
        pools["bonus_hot"] = [n for n in (bonus_hot or []) if 1 <= n <= GAME_SPECS[game]["bonus_max"]]
        pools["bonus_overdue"] = [n for n in (bonus_over or []) if 1 <= n <= GAME_SPECS[game]["bonus_max"]]
    return pools

def handle_run(payload: Dict, data_dir: str) -> Dict:
    phase = (payload.get("phase") or "").lower()
    if phase == "phase2":
        saved_path = payload.get("saved_path") or ""
        if not saved_path: raise ValueError("phase2 requires saved_path")
        with open(saved_path, "r", encoding="utf-8") as f:
            state = json.load(f)
        return _run_phase2(state, data_dir)

    # Phase 1 inputs
    mm_latest = parse_latest_pair(payload.get("LATEST_MM",""))
    pb_latest = parse_latest_pair(payload.get("LATEST_PB",""))
    il_jp = parse_latest_pair(payload.get("LATEST_IL_JP",""))[0]
    il_m1 = parse_latest_pair(payload.get("LATEST_IL_M1",""))[0]
    il_m2 = parse_latest_pair(payload.get("LATEST_IL_M2",""))[0]
    f_mm = parse_feed_mm_pb(payload.get("FEED_MM",""))
    f_pb = parse_feed_mm_pb(payload.get("FEED_PB",""))
    f_il = parse_feed_il(payload.get("FEED_IL",""))
    hist_mm = parse_hist_blob_mm(payload.get("HIST_MM_BLOB",""))
    hist_pb = parse_hist_blob_mm(payload.get("HIST_PB_BLOB",""))
    hist_il = parse_hist_blob_il(payload.get("HIST_IL_BLOB",""))

    band_mm = middle_band("MM", _hist_mains_only_mm(hist_mm))
    band_pb = middle_band("PB", _hist_mains_only_mm(hist_pb))
    band_il = middle_band("IL", hist_il)

    pools_mm = _pools_for_game("MM", f_mm["hot"], f_mm["overdue"], _hist_mains_only_mm(hist_mm), f_mm["bonus_hot"], f_mm["bonus_overdue"])
    pools_pb = _pools_for_game("PB", f_pb["hot"], f_pb["overdue"], _hist_mains_only_mm(hist_pb), f_pb["bonus_hot"], f_pb["bonus_overdue"])
    pools_il = _pools_for_game("IL", f_il["hot"], f_il["overdue"], hist_il)

    # Generate + annotate
    pool_mm = build_50_pool("MM", pools_mm, band_mm)
    pool_pb = build_50_pool("PB", pools_pb, band_pb)
    pool_il = build_50_pool("IL", pools_il, band_il)
    rows_mm, stats_mm = _annotate_mm_pb(pool_mm, mm_latest)
    rows_pb, stats_pb = _annotate_mm_pb(pool_pb, pb_latest)
    rows_il_jp, stats_il_jp = _annotate_il(pool_il, il_jp)
    rows_il_m1, stats_il_m1 = _annotate_il(pool_il, il_m1)
    rows_il_m2, stats_il_m2 = _annotate_il(pool_il, il_m2)

    state = {
        "created_at": _nowstamp(), "phase": "phase1",
        "band": {"MM": band_mm, "PB": band_pb, "IL": band_il},
        "pools": {"MM": pools_mm, "PB": pools_pb, "IL": pools_il},
        "pool_rows": {"MM": pool_mm, "PB": pool_pb, "IL": pool_il},
        "latest": {"MM": mm_latest, "PB": pb_latest, "IL_JP": il_jp, "IL_M1": il_m1, "IL_M2": il_m2},
        "history": {"MM": hist_mm, "PB": hist_pb, "IL": hist_il}
    }
    saved_path = _save_json(state, data_dir, "lotto_phase1")

    return {
        "ok": True,
        "saved_path": saved_path,
        "bands": {"MM": band_mm, "PB": band_pb, "IL": band_il},
        "eval_vs_NJ": {
            "MM": stats_mm, "PB": stats_pb,
            "IL": {"JP": stats_il_jp, "M1": stats_il_m1, "M2": stats_il_m2}
        },
        "batches": {
            "MM": rows_mm,
            "PB": rows_pb,
            "IL": {"JP": rows_il_jp, "M1": rows_il_m1, "M2": rows_il_m2}
        },
        "note": "Use saved_path for Phase 2."
    }

def _promote_newest_into_history(state: Dict) -> Dict:
    latest = state["latest"]; hist = state["history"]
    hist["MM"] = [(sorted(latest["MM"][0]), int(latest["MM"][1]))] + hist["MM"]
    hist["PB"] = [(sorted(latest["PB"][0]), int(latest["PB"][1]))] + hist["PB"]
    hist["IL"] = [sorted(latest["IL_JP"])] + hist["IL"]
    hist["MM"] = hist["MM"][:20]; hist["PB"] = hist["PB"][:20]; hist["IL"] = hist["IL"][:20]
    return state

def _aggregate_hits(agg: Dict[str, Dict[str, List[int]]], stats: Dict[str, List[int]]):
    for k, v in stats.items():
        agg.setdefault(k, []); agg[k].extend(v)

def _run_phase2(state: Dict, data_dir: str) -> Dict:
    state = _promote_newest_into_history(state)
    hist_mm = state["history"]["MM"]; hist_pb = state["history"]["PB"]; hist_il = state["history"]["IL"]
    f_mm = state["pools"]["MM"]; f_pb = state["pools"]["PB"]; f_il = state["pools"]["IL"]
    band_mm = middle_band("MM", _hist_mains_only_mm(hist_mm))
    band_pb = middle_band("PB", _hist_mains_only_mm(hist_pb))
    band_il = middle_band("IL", hist_il)
    pools_mm = _pools_for_game("MM", f_mm["hot"], f_mm["overdue"], _hist_mains_only_mm(hist_mm), f_mm.get("bonus_hot",[]), f_mm.get("bonus_overdue",[]))
    pools_pb = _pools_for_game("PB", f_pb["hot"], f_pb["overdue"], _hist_mains_only_mm(hist_pb), f_pb.get("bonus_hot",[]), f_pb.get("bonus_overdue",[]))
    pools_il = _pools_for_game("IL", f_il["hot"], f_il["overdue"], hist_il)

    runs = 100
    latest = state["latest"]
    mm_latest = latest["MM"]; pb_latest = latest["PB"]
    il_jp, il_m1, il_m2 = latest["IL_JP"], latest["IL_M1"], latest["IL_M2"]

    agg_mm = {"3":[], "3B":[], "4":[], "4B":[], "5":[], "5B":[]}
    agg_pb = {"3":[], "3B":[], "4":[], "4B":[], "5":[], "5B":[]}
    agg_il = {"JP":{"3":[], "4":[], "5":[], "6":[]},
              "M1":{"3":[], "4":[], "5":[], "6":[]},
              "M2":{"3":[], "4":[], "5":[], "6":[]}}
    freq_mm = {}; freq_pb = {}; freq_il = {}

    for _ in range(runs):
        pool_mm = build_50_pool("MM", pools_mm, band_mm)
        pool_pb = build_50_pool("PB", pools_pb, band_pb)
        pool_il = build_50_pool("IL", pools_il, band_il)

        def bump(d, t): d[t] = d.get(t, 0) + 1
        for t in pool_mm: bump(freq_mm, (tuple(t[0]), t[1]))
        for t in pool_pb: bump(freq_pb, (tuple(t[0]), t[1]))
        for t in pool_il: bump(freq_il, (tuple(t[0]), None))

        from copy import deepcopy
        _, s_mm = _annotate_mm_pb(pool_mm, mm_latest); _aggregate_hits(agg_mm, s_mm)
        _, s_pb = _annotate_mm_pb(pool_pb, pb_latest); _aggregate_hits(agg_pb, s_pb)
        _, s_il_jp = _annotate_il(pool_il, il_jp)
        _, s_il_m1 = _annotate_il(pool_il, il_m1)
        _, s_il_m2 = _annotate_il(pool_il, il_m2)
        for k in ("3","4","5","6"):
            agg_il["JP"][k].extend(s_il_jp.get(k,[]))
            agg_il["M1"][k].extend(s_il_m1.get(k,[]))
            agg_il["M2"][k].extend(s_il_m2.get(k,[]))

    def top_list(freq_map, n):
        items = sorted(freq_map.items(), key=lambda kv: (-kv[1], kv[0]))
        out, used = [], set()
        for (mains, bonus), _score in items:
            if (mains, bonus) in used: continue
            out.append({"mains": list(mains), "bonus": bonus}); used.add((mains, bonus))
            if len(out) >= n: break
        return out

    buy_mm = top_list(freq_mm, 10)
    buy_pb = top_list(freq_pb, 10)
    buy_il = top_list(freq_il, 15)

    result = {
        "ok": True, "phase": "phase2",
        "bands": {"MM": band_mm, "PB": band_pb, "IL": band_il},
        "agg_hits": {"MM": agg_mm, "PB": agg_pb, "IL": agg_il},
        "buy_lists": {"MM": buy_mm, "PB": buy_pb, "IL": buy_il},
    }
    state2 = {
        "created_at": _nowstamp(), "phase": "phase2",
        "history": state["history"], "latest": state["latest"],
        "bands": {"MM": band_mm, "PB": band_pb, "IL": band_il},
        "buy_lists": result["buy_lists"],
    }
    result["saved_path"] = _save_json(state2, data_dir, "lotto_phase2")
    result["note"] = "Use saved_path for Phase 3 confirmation after the next official draw."
    return result

def list_recent(data_dir: str) -> Dict:
    files = []
    if os.path.isdir(data_dir):
        for name in os.listdir(data_dir):
            if name.endswith(".json") and (name.startswith("lotto_phase1") or name.startswith("lotto_phase2")):
                files.append(os.path.join(data_dir, name))
    files.sort(reverse=True)
    return {"files": files[:20]}

def _parse_nwj_blob(nwj: Dict) -> Dict:
    out = {}
    if not isinstance(nwj, dict): return out
    def conv_pair(v):
        if isinstance(v, list) and len(v) == 2:
            return (v[0], v[1])
        return None
    for k in ("LATEST_MM","LATEST_PB","LATEST_IL_JP","LATEST_IL_M1","LATEST_IL_M2"):
        if k in nwj: out[k] = conv_pair(nwj[k])
    return out

def handle_confirm(payload: Dict, data_dir: str) -> Dict:
    saved_path = payload.get("saved_path") or ""
    if not saved_path: raise ValueError("confirm requires saved_path")
    with open(saved_path, "r", encoding="utf-8") as f:
        state2 = json.load(f)

    nwj_raw = payload.get("NWJ")
    latest = state2.get("latest", {})
    if nwj_raw and isinstance(nwj_raw, dict):
        parsed = _parse_nwj_blob(nwj_raw)
        if parsed.get("LATEST_MM"): latest["MM"] = parsed["LATEST_MM"]
        if parsed.get("LATEST_PB"): latest["PB"] = parsed["LATEST_PB"]
        if parsed.get("LATEST_IL_JP"): latest["IL_JP"] = parsed["LATEST_IL_JP"][0]
        if parsed.get("LATEST_IL_M1"): latest["IL_M1"] = parsed["LATEST_IL_M1"][0]
        if parsed.get("LATEST_IL_M2"): latest["IL_M2"] = parsed["LATEST_IL_M2"][0]

    mm_stats = {"3":[], "3B":[], "4":[], "4B":[], "5":[], "5B":[]}
    pb_stats = {"3":[], "3B":[], "4":[], "4B":[], "5":[], "5B":[]}
    il_stats = {"JP":{"3":[], "4":[], "5":[], "6":[]},
                "M1":{"3":[], "4":[], "5":[], "6":[]},
                "M2":{"3":[], "4":[], "5":[], "6":[]}}

    buy = state2.get("buy_lists", {})
    buys_mm = [ (row["mains"], row.get("bonus")) for row in buy.get("MM", []) ]
    buys_pb = [ (row["mains"], row.get("bonus")) for row in buy.get("PB", []) ]
    buys_il = [ (row["mains"], None) for row in buy.get("IL", []) ]

    def eval_mm_pb(buys, latest_pair, stats):
        mains, bonus = latest_pair
        for i, (m, b) in enumerate(buys, start=1):
            hit = len(set(m).intersection(mains))
            hasB = (b == bonus)
            if hit == 3: (stats["3B"] if hasB else stats["3"]).append(i)
            elif hit == 4: (stats["4B"] if hasB else stats["4"]).append(i)
            elif hit == 5: (stats["5B"] if hasB else stats["5"]).append(i)

    eval_mm_pb(buys_mm, latest["MM"], mm_stats)
    eval_mm_pb(buys_pb, latest["PB"], pb_stats)

    def eval_il(buys, latest_mains):
        out = {"3":[], "4":[], "5":[], "6":[]}
        for i, (m, _) in enumerate(buys, start=1):
            hit = len(set(m).intersection(latest_mains))
            key = str(hit)
            if key in out: out[key].append(i)
        return out

    il_jp = eval_il(buys_il, latest["IL_JP"])
    il_m1 = eval_il(buys_il, latest["IL_M1"])
    il_m2 = eval_il(buys_il, latest["IL_M2"])

    return {"ok": True, "phase": "phase3",
            "confirm_hits": {"MM": mm_stats, "PB": pb_stats, "IL": {"JP": il_jp, "M1": il_m1, "M2": il_m2}}}
