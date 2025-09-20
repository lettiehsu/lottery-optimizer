# lottery_core.py
# -----------------------------------------------------------------------------
# Core logic used by app.py. Pure-Python, no web/Flask code in here.
# Implements:
#   - run_phase_1_and_2(cfg)  -> dict
#   - confirm_phase_3(saved_file, nwj, data_dir) -> dict
# -----------------------------------------------------------------------------

from __future__ import annotations
import os, json, random, statistics, datetime as dt
from typing import List, Tuple, Optional, Dict, Iterable, Set
from collections import Counter, defaultdict

# ────────────────────────────────────────────────────────────────────────────────
# Parsing helpers (robust to either list/tuple inputs or strings from forms)
# ────────────────────────────────────────────────────────────────────────────────

def _coerce_mm_pb_tuple(x):
    """
    Accepts ([m1..m5], bonus) OR string like "[10,14,34,40,43],5"
    Returns (list[int], int) or None.
    """
    if x is None or x == "": return None
    if isinstance(x, (list, tuple)) and len(x) == 2:
        mains, bonus = x
        return [int(n) for n in mains], int(bonus)
    s = str(x).strip()
    if "]" in s and "," in s:
        mains_s, bonus_s = s.split("]", 1)
        mains_s = mains_s[mains_s.find("[")+1:]
        mains = [int(n.strip()) for n in mains_s.split(",") if n.strip()]
        bonus_s = bonus_s.lstrip(", ").strip()
        bonus = int(bonus_s)
        return mains, bonus
    return None

def _coerce_il_list(x):
    """
    Accepts [6 ints] OR string "[..6..]". Returns list[int] or None.
    """
    if x is None or x == "": return None
    if isinstance(x, (list, tuple)):
        return [int(n) for n in x]
    s = str(x).strip()
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1]
        return [int(n.strip()) for n in inner.split(",") if n.strip()]
    return None

def _coerce_feed(feed_in, game_tag):
    """
    Accept dict {'Hot':[], 'Overdue':[], 'BonusHot':[], 'BonusOverdue':[]}
    or multi-line text from Lottery Defeated pasted in the form.
    """
    if isinstance(feed_in, dict):
        out = {k: list(map(int, v)) for k, v in feed_in.items()}
        out.setdefault("Hot", []); out.setdefault("Overdue", [])
        out.setdefault("BonusHot", []); out.setdefault("BonusOverdue", [])
        return out
    text = (feed_in or "").strip()
    out = {"Hot": [], "Overdue": [], "BonusHot": [], "BonusOverdue": []}
    if not text:
        return out
    for line in text.splitlines():
        ln = line.strip().lower()
        if ln.startswith("top 8 hot numbers"):
            nums = line.split(":")[1]
            out["Hot"] = [int(x.strip()) for x in nums.split(",")]
        elif ln.startswith("top 8 overdue numbers"):
            nums = line.split(":")[1]
            out["Overdue"] = [int(x.strip()) for x in nums.split(",")]
        elif game_tag == "MM" and "hot mega ball" in ln:
            nums = line.split(":")[1]
            out["BonusHot"] = [int(x.strip()) for x in nums.split(",")]
        elif game_tag == "MM" and "overdue mega ball" in ln:
            nums = line.split(":")[1]
            out["BonusOverdue"] = [int(x.strip()) for x in nums.split(",")]
        elif game_tag == "PB" and "hot power ball" in ln:
            nums = line.split(":")[1]
            out["BonusHot"] = [int(x.strip()) for x in nums.split(",")]
        elif game_tag == "PB" and "overdue power ball" in ln:
            nums = line.split(":")[1]
            out["BonusOverdue"] = [int(x.strip()) for x in nums.split(",")]
    return out

# ────────────────────────────────────────────────────────────────────────────────
# Small utilities
# ────────────────────────────────────────────────────────────────────────────────

def clamp_last_n(items: List, n: int) -> List:
    return items[-n:] if len(items) > n else items[:]

def undrawn_from_last_k(main_hist: List[List[int]], k: int, max_num: int) -> Set[int]:
    recent = main_hist[-k:] if k else main_hist
    seen = set(n for row in recent for n in row)
    return set(range(1, max_num+1)) - seen

def bonus_undrawn_from_last_k(bonus_hist: List[int], k: int, max_num: int) -> Set[int]:
    recent = bonus_hist[-k:] if k else bonus_hist
    seen = set(recent)
    return set(range(1, max_num+1)) - seen

def iqr_band_from_history(main_hist: List[List[int]]) -> Tuple[int, int]:
    if not main_hist:
        return (0, 9999)
    sums = [sum(sorted(m)) for m in main_hist]
    try:
        q1 = int(statistics.quantiles(sums, n=4, method="inclusive")[0])
        q3 = int(statistics.quantiles(sums, n=4, method="inclusive")[2])
    except Exception:
        s2 = sorted(sums)
        q1 = s2[len(s2)//4]
        q3 = s2[3*len(s2)//4]
    return (q1, q3)

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

def draw_from_pool(pool: Iterable[int], need: int, used: Set[int]) -> List[int]:
    choices = [n for n in pool if n not in used]
    random.shuffle(choices)
    return choices[:max(0, need)]

# ────────────────────────────────────────────────────────────────────────────────
# Game specs & patterns (same as in your local script)
# ────────────────────────────────────────────────────────────────────────────────

GAME_MM = {"name": "Mega Millions", "main_max": 70, "main_pick": 5, "bonus_max": 25}
GAME_PB = {"name": "Powerball",     "main_max": 69, "main_pick": 5, "bonus_max": 26}
GAME_IL = {"name": "Illinois Lotto","main_max": 50, "main_pick": 6, "bonus_max": None}

PATTERNS_MM_PB = [
    ("VIP", 1, "Hot", 1, "Overdue", 0, "Undrawn", 3),
    ("VIP", 1, "Hot", 1, "Overdue", 1, "Undrawn", 2),
    ("VIP", 1, "Hot", 2, "Overdue", 0, "Undrawn", 2),
    ("LRR", 1, "Hot", 1, "Overdue", 0, "Undrawn", 3),
    ("LRR", 1, "Hot", 2, "Overdue", 0, "Undrawn", 2),
    ("LRR", 1, "Hot", 1, "Overdue", 2, "Undrawn", 1),
]

PATTERNS_IL = [
    ("VIP", 1, "Hot", 1, "Overdue", 0, "Undrawn", 4),
    ("VIP", 1, "Hot", 2, "Overdue", 0, "Undrawn", 3),
    ("VIP", 1, "Hot", 1, "Overdue", 2, "Undrawn", 2),
    ("LRR", 1, "Hot", 1, "Overdue", 0, "Undrawn", 4),
    ("LRR", 1, "Hot", 2, "Overdue", 0, "Undrawn", 3),
    ("LRR", 1, "Hot", 1, "Overdue", 2, "Undrawn", 2),
]

# ────────────────────────────────────────────────────────────────────────────────
# Feed → pools → ticket generators
# ────────────────────────────────────────────────────────────────────────────────

def build_pools(game_spec, main_hist, feeds) -> Dict[str, List[int]]:
    hot = [n for n in feeds.get("Hot", []) if 1 <= n <= game_spec["main_max"]]
    over = [n for n in feeds.get("Overdue", []) if 1 <= n <= game_spec["main_max"]]
    und = sorted(list(undrawn_from_last_k(main_hist, 10, game_spec["main_max"])))
    vip = sorted(list(set(hot) & set(over)))
    lrr = lrr_candidates(main_hist)
    return {"Hot": hot, "Overdue": over, "Undrawn": und, "VIP": vip, "LRR": lrr}

def iqr_ok(mains, band): 
    s = sum(mains)
    return band[0] <= s <= band[1]

def generate_ticket_from_pattern(game_spec, pattern, pools, iqr_band) -> Optional[List[int]]:
    anchor_type, a_ct, t1, t1_ct, t2, t2_ct, t3, t3_ct = pattern
    retries = 25
    while retries > 0:
        retries -= 1
        used = set(); mains = []

        anchor_pool = pools["VIP"] if anchor_type == "VIP" else pools["LRR"]
        if a_ct > 0:
            if not anchor_pool: continue
            a_pick = draw_from_pool(anchor_pool, 1, used)
            if not a_pick: continue
            mains.extend(a_pick); used.update(a_pick)

        for typ, ct in [(t1, t1_ct), (t2, t2_ct), (t3, t3_ct)]:
            if ct <= 0: continue
            add = draw_from_pool(pools[typ], ct, used)
            if len(add) < ct and typ != "Undrawn":
                add += draw_from_pool(pools["Undrawn"], ct - len(add), used)
            mains.extend(add); used.update(add)

        while len(mains) < game_spec["main_pick"]:
            need = game_spec["main_pick"] - len(mains)
            add = draw_from_pool(pools["Undrawn"], need, used)
            if not add:
                add = draw_from_pool(range(1, game_spec["main_max"]+1), need, used)
            mains.extend(add); used.update(add)

        mains = sorted(mains[:game_spec["main_pick"]])
        if len(set(mains)) == game_spec["main_pick"] and iqr_ok(mains, iqr_band):
            return mains
    return None

def pick_bonus(game_spec, feeds, bonus_hist: List[int]) -> Optional[int]:
    if game_spec["bonus_max"] is None: return None
    pool = list(dict.fromkeys(feeds.get("BonusHot", []) + feeds.get("BonusOverdue", [])))
    if len(pool) < 3:
        und = list(bonus_undrawn_from_last_k(bonus_hist, 10, game_spec["bonus_max"]))
        random.shuffle(und); pool += und
    if not pool:
        pool = list(range(1, game_spec["bonus_max"] + 1))
    return random.choice(pool)

def generate_batch_mm_pb(game_spec, main_hist, bonus_hist, feeds, patterns, batch_size=50):
    iqr = iqr_band_from_history(main_hist)
    pools = build_pools(game_spec, main_hist, feeds)
    batch = []; p_idx = 0; guard = 0
    while len(batch) < batch_size and guard < batch_size * 20:
        guard += 1
        pat = patterns[p_idx % len(patterns)]
        if pat[0] == "VIP" and not pools["VIP"]: p_idx += 1; continue
        if pat[0] == "LRR" and not pools["LRR"]: p_idx += 1; continue
        mains = generate_ticket_from_pattern(game_spec, pat, pools, iqr)
        if mains is None: p_idx += 1; continue
        b = pick_bonus(game_spec, feeds, bonus_hist)
        t = (mains, b)
        if t not in batch: batch.append(t)
        p_idx += 1
    return batch

def generate_batch_il(game_spec, main_hist, feeds, patterns, batch_size=50):
    iqr = iqr_band_from_history(main_hist)
    pools = build_pools(game_spec, main_hist, feeds)
    batch = []; p_idx = 0; guard = 0
    while len(batch) < batch_size and guard < batch_size * 20:
        guard += 1
        pat = patterns[p_idx % len(patterns)]
        if pat[0] == "VIP" and not pools["VIP"]: p_idx += 1; continue
        if pat[0] == "LRR" and not pools["LRR"]: p_idx += 1; continue
        mains = generate_ticket_from_pattern(game_spec, pat, pools, iqr)
        if mains is None: p_idx += 1; continue
        if mains not in batch: batch.append(mains)
        p_idx += 1
    return batch

# ────────────────────────────────────────────────────────────────────────────────
# Scoring & reporting
# ────────────────────────────────────────────────────────────────────────────────

def score_hits_mm_pb(ticket: Tuple[List[int], int], target: Tuple[List[int], int]) -> Tuple[int, bool]:
    mains, b = ticket; t_mains, t_b = target
    m = len(set(mains) & set(t_mains)); bonus_hit = (b == t_b)
    return m, bonus_hit

def score_hits_il(ticket: List[int], target: List[int]) -> int:
    return len(set(ticket) & set(target))

def _phase1_hits_lines_mm_pb(batch, latest_target, label):
    lines = []
    for idx, t in enumerate(batch, 1):
        m, bh = score_hits_mm_pb(t, latest_target)
        if m >= 3 or (m >= 2 and bh):
            tag = f"{m}-ball{' + Bonus' if bh else ''}"
            lines.append(f"{label} row #{idx:02d}: {tag}")
    if not lines:
        lines.append(f"No ≥3-ball (or 2+bonus) hits in this 50-row batch vs NJ.")
    return lines

def _phase1_hits_lines_il(batch, latest_targets):
    # latest_targets is list of (name, [6 nums])
    lines = []
    any_hit = False
    for name, tgt in latest_targets:
        got = []
        for idx, t in enumerate(batch, 1):
            hits = score_hits_il(t, tgt)
            if hits >= 3:
                any_hit = True
                got.append(f"  ≥3 mains vs {name} at row #{idx:02d}  [{hits} match]")
        if not got:
            lines.append(f"  No ≥3-ball hits vs {name}.")
        else:
            lines.extend(got)
    if not any_hit and not lines:
        lines.append("  No ≥3-ball hits.")
    return lines

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
    top = sorted(pos_hits.items(), key=lambda x: (-x[1], x[0]))[:10]
    return {"totals": dict(type_totals), "top_positions": top}, last_batch, pos_hits

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
    top = sorted(pos_hits.items(), key=lambda x: (-x[1], x[0]))[:10]
    return {"totals": dict(type_totals), "top_positions": top}, last_batch, pos_hits

def fmt_ticket_mm_pb(t): mains, b = t; return f"{' '.join(f'{n:02d}' for n in mains)}   {b:02d}"
def fmt_ticket_il(t): return " ".join(f"{n:02d}" for n in t)

def recommend_from_stats(last_batch, pos_hit_freq: Dict[int,int], k: int) -> List:
    scored = sorted(
        [(pos_hit_freq.get(i+1,0), i, t) for i, t in enumerate(last_batch)],
        key=lambda x: (-x[0], x[1])
    )
    picks = []; seen_sets = []
    for _, _, t in scored:
        mains = t[0] if isinstance(t, tuple) else t
        s = set(mains)
        too_close = any(len(s & prev) >= (5 if len(mains)==6 else 4) for prev in seen_sets)
        if too_close: continue
        picks.append(t); seen_sets.append(s)
        if len(picks) >= k: break
    i = 0
    while len(picks) < k and i < len(last_batch):
        t = last_batch[i]
        if t not in picks: picks.append(t)
        i += 1
    return picks

# ────────────────────────────────────────────────────────────────────────────────
# Public API used by app.py
# ────────────────────────────────────────────────────────────────────────────────

def run_phase_1_and_2(cfg: dict) -> dict:
    """
    Expects in cfg:
      - LATEST_MM, LATEST_PB -> ([mains], bonus)
      - LATEST_IL_JP, LATEST_IL_M1, LATEST_IL_M2 -> [6nums]
      - HIST_MM, HIST_PB -> list[(mains, bonus)]   (keep last 20 used)
      - HIST_IL -> list[[6nums]]
      - FEED_MM/FEED_PB/FEED_IL -> dict or text
      - runs (int), quiet (bool), data_dir (str)
    """
    random.seed(cfg.get("seed", 12345))

    latest_mm = _coerce_mm_pb_tuple(cfg.get("LATEST_MM"))
    latest_pb = _coerce_mm_pb_tuple(cfg.get("LATEST_PB"))
    latest_il_jp = _coerce_il_list(cfg.get("LATEST_IL_JP"))
    latest_il_m1 = _coerce_il_list(cfg.get("LATEST_IL_M1"))
    latest_il_m2 = _coerce_il_list(cfg.get("LATEST_IL_M2"))

    # histories already parsed by app.py; keep last 20
    hist_mm = clamp_last_n(cfg.get("HIST_MM", []), 20)
    hist_pb = clamp_last_n(cfg.get("HIST_PB", []), 20)
    hist_il = clamp_last_n(cfg.get("HIST_IL", []), 20)

    mm_mains = [row[0] for row in hist_mm]
    mm_bonus = [row[1] for row in hist_mm]
    pb_mains = [row[0] for row in hist_pb]
    pb_bonus = [row[1] for row in hist_pb]

    feeds_mm = _coerce_feed(cfg.get("FEED_MM"), "MM")
    feeds_pb = _coerce_feed(cfg.get("FEED_PB"), "PB")
    feeds_il = _coerce_feed(cfg.get("FEED_IL"), "IL")

    runs = int(cfg.get("runs", 100))
    data_dir = cfg.get("data_dir") or "/tmp"
    os.makedirs(os.path.join(data_dir, "buylists"), exist_ok=True)

    # Phase 1 — build one 50-row batch for each game
    mm_batch = generate_batch_mm_pb(GAME_MM, mm_mains, mm_bonus, feeds_mm, PATTERNS_MM_PB, 50)
    pb_batch = generate_batch_mm_pb(GAME_PB, pb_mains, pb_bonus, feeds_pb, PATTERNS_MM_PB, 50)
    il_batch = generate_batch_il(GAME_IL, hist_il, feeds_il, PATTERNS_IL, 50)

    phase1 = {
        "mm": {"batch": mm_batch, "hits_lines": _phase1_hits_lines_mm_pb(mm_batch, latest_mm, "MM")} if latest_mm else {"batch": mm_batch, "hits_lines": []},
        "pb": {"batch": pb_batch, "hits_lines": _phase1_hits_lines_mm_pb(pb_batch, latest_pb, "PB")} if latest_pb else {"batch": pb_batch, "hits_lines": []},
        "il": {"batch": il_batch, "hits_lines": _phase1_hits_lines_il(il_batch, [("Jackpot", latest_il_jp), ("Million 1", latest_il_m1), ("Million 2", latest_il_m2)]) if all([latest_il_jp, latest_il_m1, latest_il_m2]) else []}
    }

    # Phase 2 — simulate 100×
    # prepend latest to history window like your console script
    mm_hist2_mains = clamp_last_n([latest_mm[0]] + mm_mains if latest_mm else mm_mains, 20)
    mm_hist2_bonus = clamp_last_n([latest_mm[1]] + mm_bonus if latest_mm else mm_bonus, 20)
    pb_hist2_mains = clamp_last_n([latest_pb[0]] + pb_mains if latest_pb else pb_mains, 20)
    pb_hist2_bonus = clamp_last_n([latest_pb[1]] + pb_bonus if latest_pb else pb_bonus, 20)
    il_hist2 = clamp_last_n([latest_il_jp] + hist_il if latest_il_jp else hist_il, 20)

    mm_sim, mm_last_batch, mm_pos = ({"totals": {}, "top_positions": []}, mm_batch, defaultdict(int))
    pb_sim, pb_last_batch, pb_pos = ({"totals": {}, "top_positions": []}, pb_batch, defaultdict(int))
    il_sim, il_last_batch, il_pos = ({"totals": {}, "top_positions": []}, il_batch, defaultdict(int))

    if latest_mm:
        mm_sim, mm_last_batch, mm_pos = simulate_phase2_mm_pb(
            GAME_MM, mm_hist2_mains, mm_hist2_bonus, feeds_mm, PATTERNS_MM_PB, latest_mm, runs=runs, batch_size=50
        )
    if latest_pb:
        pb_sim, pb_last_batch, pb_pos = simulate_phase2_mm_pb(
            GAME_PB, pb_hist2_mains, pb_hist2_bonus, feeds_pb, PATTERNS_MM_PB, latest_pb, runs=runs, batch_size=50
        )
    if latest_il_jp and latest_il_m1 and latest_il_m2:
        il_sim, il_last_batch, il_pos = simulate_phase2_il(
            GAME_IL, il_hist2, feeds_il, PATTERNS_IL, [latest_il_jp, latest_il_m1, latest_il_m2], runs=runs, batch_size=50
        )

    # Recommend buy lists from the *last* simulated batch & position frequencies
    mm_buy = recommend_from_stats(mm_last_batch, mm_pos, 10)
    pb_buy = recommend_from_stats(pb_last_batch, pb_pos, 10)
    il_buy = recommend_from_stats(il_last_batch, il_pos, 15)

    # Save buylists
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    save_payload = {
        "timestamp": stamp,
        "LATEST_MM": latest_mm, "LATEST_PB": latest_pb,
        "LATEST_IL_JP": latest_il_jp, "LATEST_IL_M1": latest_il_m1, "LATEST_IL_M2": latest_il_m2,
        "MM": [[t[0], t[1]] for t in mm_buy],
        "PB": [[t[0], t[1]] for t in pb_buy],
        "IL": [list(t) for t in il_buy],
        "phase1_headings": {
            "mm": phase1["mm"]["hits_lines"],
            "pb": phase1["pb"]["hits_lines"],
            "il": phase1["il"]["hits_lines"],
        },
        "phase2_summaries": {"mm": mm_sim, "pb": pb_sim, "il": il_sim},
    }
    save_path = os.path.join(data_dir, "buylists", f"buy_session_{stamp}.json")
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(save_payload, f, indent=2)

    return {
        "phase1": phase1,
        "phase2": {"mm": mm_sim, "pb": pb_sim, "il": il_sim},
        "buy_lists": {"mm": mm_buy, "pb": pb_buy, "il": il_buy},
        "saved_path": save_path,
    }

def _tier_accumulate_mm_pb(res_lines, idx, m, bh):
    # helper to build per-ticket lines & totals
    if m>=3 or (m>=2 and bh):
        tag = f"{m}-ball{' + Bonus' if bh else ''}"
        res_lines.append(f"Buy #{idx:02d}: {tag}")

def confirm_phase_3(saved_file: str, nwj: dict, data_dir: str) -> dict:
    """
    saved_file: filename from dropdown (e.g., 'buy_session_YYYYMMDD_HHMMSS.json')
    nwj: dict possibly containing 'NWJ_MM', 'NWJ_PB', 'NWJ_IL_JP', 'NWJ_IL_M1', 'NWJ_IL_M2'
    """
    path = os.path.join(data_dir, "buylists", saved_file)
    with open(path, "r", encoding="utf-8") as f:
        saved = json.load(f)

    mm_buy = [(list(item[0]), int(item[1])) for item in saved.get("MM", [])]
    pb_buy = [(list(item[0]), int(item[1])) for item in saved.get("PB", [])]
    il_buy = [list(item) for item in saved.get("IL", [])]

    out = {"headings": saved.get("phase1_headings", {}), "phase2": saved.get("phase2_summaries", {}), "confirm": {}}

    # MM
    if nwj.get("NWJ_MM"):
        target = _coerce_mm_pb_tuple(nwj["NWJ_MM"])
        res_lines = []
        totals = {"2+":0, "3":0, "3+":0, "4":0, "4+":0, "5":0, "5+":0}
        for i, t in enumerate(mm_buy, 1):
            m, bh = score_hits_mm_pb(t, target)
            if m==2 and bh: totals["2+"] += 1
            if m==3: totals["3"] += 1
            if m==3 and bh: totals["3+"] += 1
            if m==4: totals["4"] += 1
            if m==4 and bh: totals["4+"] += 1
            if m==5: totals["5"] += 1
            if m==5 and bh: totals["5+"] += 1
            _tier_accumulate_mm_pb(res_lines, i, m, bh)
        out["confirm"]["mm"] = {"totals": totals, "lines": res_lines}

    # PB
    if nwj.get("NWJ_PB"):
        target = _coerce_mm_pb_tuple(nwj["NWJ_PB"])
        res_lines = []
        totals = {"2+":0, "3":0, "3+":0, "4":0, "4+":0, "5":0, "5+":0}
        for i, t in enumerate(pb_buy, 1):
            m, bh = score_hits_mm_pb(t, target)
            if m==2 and bh: totals["2+"] += 1
            if m==3: totals["3"] += 1
            if m==3 and bh: totals["3+"] += 1
            if m==4: totals["4"] += 1
            if m==4 and bh: totals["4+"] += 1
            if m==5: totals["5"] += 1
            if m==5 and bh: totals["5+"] += 1
            _tier_accumulate_mm_pb(res_lines, i, m, bh)
        out["confirm"]["pb"] = {"totals": totals, "lines": res_lines}

    # IL
    if any(nwj.get(k) for k in ("NWJ_IL_JP","NWJ_IL_M1","NWJ_IL_M2")):
        targets_named = []
        if nwj.get("NWJ_IL_JP"): targets_named.append(("Jackpot", _coerce_il_list(nwj["NWJ_IL_JP"])))
        if nwj.get("NWJ_IL_M1"): targets_named.append(("Million 1", _coerce_il_list(nwj["NWJ_IL_M1"])))
        if nwj.get("NWJ_IL_M2"): targets_named.append(("Million 2", _coerce_il_list(nwj["NWJ_IL_M2"])))
        totals = {2:0,3:0,4:0,5:0,6:0}
        lines = []
        for i, mains in enumerate(il_buy, 1):
            best = 0; best_name = None
            for name, tgt in targets_named:
                if tgt is None: continue
                hits = score_hits_il(mains, tgt)
                if hits > best: best = hits; best_name = name
            if best>=2: totals[max(2, min(6, best))] += 1
            if best>=3:
                lines.append(f"Buy #{i:02d}: {best}-ball vs {best_name}")
        out["confirm"]["il"] = {"totals": {f"{k}-ball": v for k,v in totals.items()}, "lines": lines}

    return out
