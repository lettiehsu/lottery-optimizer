# ==== PHASE 1 (Evaluation) — complete replacement ====

import re, json, os, random
from statistics import median

def _parse_latest_pair(s: str):
    """
    Accepts strings like:
      '[[  10,  14,  34,  40,  43], 5]'
      '[[  1,   4,   5,  10,  18,  49], null]'
    Returns (mains:list[int], bonus:int|None)
    """
    if not s or "[" not in s:
        raise ValueError("LATEST_* must be a string like '[..], b' or '[..]'")
    s = s.strip()
    # Convert 'null' -> None for JSON parsing
    js = s.replace("null", "null")
    try:
        val = json.loads(js)
        if not (isinstance(val, list) and len(val) == 2):
            raise ValueError
        mains, bonus = val
        if not isinstance(mains, list):
            raise ValueError
        mains = [int(x) for x in mains]
        if bonus is None:
            b = None
        else:
            b = int(bonus)
        return mains, b
    except Exception:
        # Fallback: extract digits
        m = re.findall(r"\d+", s)
        if not m:
            raise
        # Heuristic: if length 5 or 6 first are mains; the last (if present & not 6th main) is bonus
        nums = list(map(int, m))
        if len(nums) == 6:  # IL-like
            return nums, None
        if len(nums) >= 6:
            return nums[:-1][:5], nums[-1]
        if len(nums) == 5:
            return nums, None
        raise

def _parse_hist_blob_mm_pb(blob: str):
    """
    Lines like: '09-12-25  17-18-21-42-64  07'
    Return list of tuples: (mains:list[int], bonus:int)
    """
    out = []
    for line in (blob or "").splitlines():
        line = line.strip()
        if not line: 
            continue
        parts = re.findall(r"(\d{2}-\d{2}-\d{2})\s+(\d{2}-\d{2}-\d{2}-\d{2}-\d{2})\s+(\d{2})", line)
        if parts:
            _, mains_str, b_str = parts[0]
            mains = [int(x) for x in mains_str.split("-")]
            out.append((mains, int(b_str)))
        else:
            # looser: find all ints; last 5 are mains, last is bonus
            nums = [int(x) for x in re.findall(r"\d+", line)]
            if len(nums) >= 6:
                mains = nums[-6:-1] if len(nums) >= 6 else nums[:5]
                bonus = nums[-1]
                if len(mains) == 5:
                    out.append((mains, int(bonus)))
    return out

def _parse_hist_blob_il(blob: str):
    """
    Lines like: '09-15-25  01-04-05-10-18-49'
    Return list of mains only.
    """
    out = []
    for line in (blob or "").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = re.findall(r"(\d{2}-\d{2}-\d{2})\s+(\d{2}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2})", line)
        if parts:
            _, mains_str = parts[0]
            mains = [int(x) for x in mains_str.split("-")]
            out.append(mains)
        else:
            nums = [int(x) for x in re.findall(r"\d+", line)]
            if len(nums) >= 6:
                out.append(nums[-6:])
    return out

def _extract_feed_sets(feed_text: str, bonus_label: str):
    """
    Parses FEED_MM/FEED_PB/FEED_IL blocks.
    For MM/PB: also returns hot_bonus / overdue_bonus (3 each).
    For IL: returns only hot/overdue mains.
    """
    hot = re.findall(r"Top\s+8\s+hot\s+numbers:\s*([0-9,\s]+)", feed_text or "", flags=re.I)
    over = re.findall(r"Top\s+8\s+overdue\s+numbers:\s*([0-9,\s]+)", feed_text or "", flags=re.I)
    hot_mains = [int(x) for x in re.findall(r"\d+", hot[0])] if hot else []
    overdue_mains = [int(x) for x in re.findall(r"\d+", over[0])] if over else []

    hot_bonus = []
    overdue_bonus = []
    if bonus_label:
        hb = re.findall(rf"Top\s+3\s+hot\s+{bonus_label}\s+numbers:\s*([0-9,\s]+)", feed_text or "", flags=re.I)
        ob = re.findall(rf"Top\s+3\s+overdue\s+{bonus_label}\s+numbers:\s*([0-9,\s]+)", feed_text or "", flags=re.I)
        hot_bonus = [int(x) for x in re.findall(r"\d+", hb[0])] if hb else []
        overdue_bonus = [int(x) for x in re.findall(r"\d+", ob[0])] if ob else []

    return {
        "hot": hot_mains,
        "overdue": overdue_mains,
        "hot_bonus": hot_bonus,
        "overdue_bonus": overdue_bonus
    }

def _undrawn_from_last(hist_mains, last_n=10):
    """Numbers not appearing in the most recent `last_n` rows."""
    recent = hist_mains[:last_n]
    flat = set()
    for row in recent:
        flat.update(row)
    # Full domain guesses: MM/PB 1..70/69; IL 1..50
    # We'll infer domain from data (max seen).
    maxv = max((n for row in hist_mains for n in row), default=70)
    domain = set(range(1, maxv+1))
    return sorted(list(domain - flat))

def _lrr_from_20(hist_mains):
    """
    LRR = numbers that appear exactly twice in last 20, but not in most recent 5 rows.
    """
    from collections import Counter
    cnt = Counter()
    for row in hist_mains[:20]:
        cnt.update(row)
    twice = {n for n, c in cnt.items() if c == 2}
    recent5 = set(n for row in hist_mains[:5] for n in row)
    lrr = [n for n in twice if n not in recent5]
    return sorted(lrr)

def _vip(hot, overdue, lrr):
    inter = [n for n in hot if n in overdue]
    if inter:
        return inter
    return lrr

def _sum_band(hist_mains):
    """IQR band (25–75%) on sums of mains, using 20-history."""
    sums = sorted(sum(r) for r in hist_mains[:20] if r)
    if not sums:
        return (0, 10**9)
    # simple quartiles
    def q(p):
        k = (len(sums)-1)*p
        f = int(k)
        c = min(f+1, len(sums)-1)
        if f == c: return sums[f]
        return sums[f] + (sums[c]-sums[f])*(k-f)
    return (int(q(0.25)), int(q(0.75)))

def _pick_unique(src, k, avoid=None):
    avoid = set(avoid or [])
    choices = [x for x in src if x not in avoid]
    random.shuffle(choices)
    return sorted(choices[:k])

def _build_mains(pattern, hot, overdue, undrawn, vip_list, lrr_list, size):
    """
    pattern tokens: 'VIP','LRR','Hot','Overdue','Undrawn' with counts.
    Returns a sorted, unique mains of given size. If cannot satisfy, falls back to random from union.
    """
    pool_map = {
        "VIP": list(vip_list),
        "LRR": list(lrr_list),
        "Hot": list(hot),
        "Overdue": list(overdue),
        "Undrawn": list(undrawn),
    }
    need = []
    used = set()
    for token, count in pattern:
        src = pool_map.get(token, [])
        take = _pick_unique(src, count, avoid=used)
        used.update(take)
        need.extend(take)
    # If not enough, pad from union (hot+over+undrawn) without dup
    union = list(dict.fromkeys(hot + overdue + undrawn))
    for n in union:
        if len(need) >= size: break
        if n not in used:
            need.append(n); used.add(n)
    # If still short, pad from 1..max
    if len(need) < size:
        maxv = max(union+[70])
        cand = [n for n in range(1, maxv+1) if n not in used]
        random.shuffle(cand)
        for n in cand:
            if len(need) >= size: break
            need.append(n)
    need = sorted(need[:size])
    return need

def _within_band(mains, band):
    s = sum(mains)
    return band[0] <= s <= band[1]

# Sampling patterns (compact tuples: (label, [(Type, count)...]) )
_PAT_MM_PB = [
    ("1 VIP + 1 Hot + 3 Undrawn",        [("VIP",1),("Hot",1),("Undrawn",3)]),
    ("1 VIP + 1 Hot + 1 Overdue + 2 U",  [("VIP",1),("Hot",1),("Overdue",1),("Undrawn",2)]),
    ("1 VIP + 1 Hot + 2 Overdue + 1 U",  [("VIP",1),("Hot",1),("Overdue",2),("Undrawn",1)]),
    ("1 VIP + 2 Hot + 2 Undrawn",        [("VIP",1),("Hot",2),("Undrawn",2)]),
    ("1 VIP + 2 Hot + 1 Overdue + 1 U",  [("VIP",1),("Hot",2),("Overdue",1),("Undrawn",1)]),
    ("1 VIP + 3 Hot + 1 Undrawn",        [("VIP",1),("Hot",3),("Undrawn",1)]),
    ("1 VIP + 1 Overdue + 3 Undrawn",    [("VIP",1),("Overdue",1),("Undrawn",3)]),
    ("1 VIP + 2 Overdue + 2 Undrawn",    [("VIP",1),("Overdue",2),("Undrawn",2)]),
    ("1 VIP + 3 Overdue + 1 Undrawn",    [("VIP",1),("Overdue",3),("Undrawn",1)]),

    ("1 LRR + 1 Hot + 3 Undrawn",        [("LRR",1),("Hot",1),("Undrawn",3)]),
    ("1 LRR + 1 Hot + 1 Overdue + 2 U",  [("LRR",1),("Hot",1),("Overdue",1),("Undrawn",2)]),
    ("1 LRR + 1 Hot + 2 Overdue + 1 U",  [("LRR",1),("Hot",1),("Overdue",2),("Undrawn",1)]),
    ("1 LRR + 2 Hot + 2 Undrawn",        [("LRR",1),("Hot",2),("Undrawn",2)]),
    ("1 LRR + 2 Hot + 1 Overdue + 1 U",  [("LRR",1),("Hot",2),("Overdue",1),("Undrawn",1)]),
    ("1 LRR + 3 Hot + 1 Undrawn",        [("LRR",1),("Hot",3),("Undrawn",1)]),
    ("1 LRR + 1 Overdue + 3 Undrawn",    [("LRR",1),("Overdue",1),("Undrawn",3)]),
    ("1 LRR + 2 Overdue + 2 Undrawn",    [("LRR",1),("Overdue",2),("Undrawn",2)]),
    ("1 LRR + 3 Overdue + 1 Undrawn",    [("LRR",1),("Overdue",3),("Undrawn",1)]),
]

_PAT_IL = [
    ("1 VIP + 1 Hot + 4 Undrawn",        [("VIP",1),("Hot",1),("Undrawn",4)]),
    ("1 VIP + 1 Hot + 1 Overdue + 3 U",  [("VIP",1),("Hot",1),("Overdue",1),("Undrawn",3)]),
    ("1 VIP + 1 Hot + 2 Overdue + 2 U",  [("VIP",1),("Hot",1),("Overdue",2),("Undrawn",2)]),
    ("1 VIP + 1 Hot + 3 Overdue + 1 U",  [("VIP",1),("Hot",1),("Overdue",3),("Undrawn",1)]),
    ("1 VIP + 2 Hot + 3 Undrawn",        [("VIP",1),("Hot",2),("Undrawn",3)]),
    ("1 VIP + 2 Hot + 1 Overdue + 2 U",  [("VIP",1),("Hot",2),("Overdue",1),("Undrawn",2)]),
    ("1 VIP + 2 Hot + 2 Overdue + 1 U",  [("VIP",1),("Hot",2),("Overdue",2),("Undrawn",1)]),
    ("1 VIP + 2 Hot + 3 Overdue",        [("VIP",1),("Hot",2),("Overdue",3)]),
    ("1 VIP + 3 Hot + 2 Undrawn",        [("VIP",1),("Hot",3),("Undrawn",2)]),
    ("1 VIP + 3 Hot + 1 Overdue + 1 U",  [("VIP",1),("Hot",3),("Overdue",1),("Undrawn",1)]),
    ("1 VIP + 3 Hot + 2 Overdue",        [("VIP",1),("Hot",3),("Overdue",2)]),
    ("1 VIP + 4 Hot + 1 Undrawn",        [("VIP",1),("Hot",4),("Undrawn",1)]),
    ("1 VIP + 4 Hot + 1 Overdue",        [("VIP",1),("Hot",4),("Overdue",1)]),
    ("1 VIP + 5 Hot",                    [("VIP",1),("Hot",5)]),
    ("1 VIP + 1 Overdue + 4 Undrawn",    [("VIP",1),("Overdue",1),("Undrawn",4)]),
    ("1 VIP + 2 Overdue + 3 Undrawn",    [("VIP",1),("Overdue",2),("Undrawn",3)]),
    ("1 VIP + 3 Overdue + 2 Undrawn",    [("VIP",1),("Overdue",3),("Undrawn",2)]),
    ("1 VIP + 4 Overdue + 1 Undrawn",    [("VIP",1),("Overdue",4),("Undrawn",1)]),
    ("1 VIP + 5 Overdue",                [("VIP",1),("Overdue",5)]),

    ("1 LRR + 1 Hot + 4 Undrawn",        [("LRR",1),("Hot",1),("Undrawn",4)]),
    ("1 LRR + 1 Hot + 1 Overdue + 3 U",  [("LRR",1),("Hot",1),("Overdue",1),("Undrawn",3)]),
    ("1 LRR + 1 Hot + 2 Overdue + 2 U",  [("LRR",1),("Hot",1),("Overdue",2),("Undrawn",2)]),
    ("1 LRR + 1 Hot + 3 Overdue + 1 U",  [("LRR",1),("Hot",1),("Overdue",3),("Undrawn",1)]),
    ("1 LRR + 2 Hot + 3 Undrawn",        [("LRR",1),("Hot",2),("Undrawn",3)]),
    ("1 LRR + 2 Hot + 1 Overdue + 2 U",  [("LRR",1),("Hot",2),("Overdue",1),("Undrawn",2)]),
    ("1 LRR + 2 Hot + 2 Overdue + 1 U",  [("LRR",1),("Hot",2),("Overdue",2),("Undrawn",1)]),
    ("1 LRR + 2 Hot + 3 Overdue",        [("LRR",1),("Hot",2),("Overdue",3)]),
    ("1 LRR + 3 Hot + 2 Undrawn",        [("LRR",1),("Hot",3),("Undrawn",2)]),
    ("1 LRR + 3 Hot + 1 Overdue + 1 U",  [("LRR",1),("Hot",3),("Overdue",1),("Undrawn",1)]),
    ("1 LRR + 3 Hot + 2 Overdue",        [("LRR",1),("Hot",3),("Overdue",2)]),
    ("1 LRR + 4 Hot + 1 Undrawn",        [("LRR",1),("Hot",4),("Undrawn",1)]),
    ("1 LRR + 4 Hot + 1 Overdue",        [("LRR",1),("Hot",4),("Overdue",1)]),
    ("1 LRR + 5 Hot",                    [("LRR",1),("Hot",5)]),
    ("1 LRR + 1 Overdue + 4 Undrawn",    [("LRR",1),("Overdue",1),("Undrawn",4)]),
    ("1 LRR + 2 Overdue + 3 Undrawn",    [("LRR",1),("Overdue",2),("Undrawn",3)]),
    ("1 LRR + 3 Overdue + 2 Undrawn",    [("LRR",1),("Overdue",3),("Undrawn",2)]),
    ("1 LRR + 4 Overdue + 1 Undrawn",    [("LRR",1),("Overdue",4),("Undrawn",1)]),
    ("1 LRR + 5 Overdue",                [("LRR",1),("Overdue",5)]),
]

def _gen_50_for_game(size, patterns, hist_mains, hot, overdue, undrawn, vip_list, lrr_list, band):
    rows = []
    pat_idx = 0
    safety = 0
    while len(rows) < 50 and safety < 5000:
        safety += 1
        label, spec = patterns[pat_idx % len(patterns)]
        pat_idx += 1
        mains = _build_mains(spec, hot, overdue, undrawn, vip_list, lrr_list, size)
        if not _within_band(mains, band):
            continue
        # avoid exact duplicates
        if mains in rows:
            continue
        rows.append(mains)
    return rows

def _count_hits_mm_pb(batch_rows, latest_mains, latest_bonus, batch_bonuses):
    hits = {"3":[], "4":[], "5":[], "3+B":[], "4+B":[], "5+B":[]}
    lm = set(latest_mains)
    for i, (mains, b) in enumerate(zip(batch_rows, batch_bonuses), start=1):
        m = len(set(mains) & lm)
        bonus_hit = (latest_bonus is not None and b == latest_bonus)
        if m == 3:
            hits["3"].append(i)
            if bonus_hit: hits["3+B"].append(i)
        elif m == 4:
            hits["4"].append(i)
            if bonus_hit: hits["4+B"].append(i)
        elif m == 5:
            hits["5"].append(i)
            if bonus_hit: hits["5+B"].append(i)
    return {
        "counts": {k: len(v) for k,v in hits.items()},
        "rows": hits,
        "exact_rows": [batch_rows[i-1] + [batch_bonuses[i-1]] for k in hits for i in hits[k]]
    }

def _count_hits_il(batch_rows, latest_mains):
    hits = {"3":[], "4":[], "5":[], "6":[]}
    lm = set(latest_mains)
    for i, mains in enumerate(batch_rows, start=1):
        m = len(set(mains) & lm)
        if m == 3: hits["3"].append(i)
        elif m == 4: hits["4"].append(i)
        elif m == 5: hits["5"].append(i)
        elif m == 6: hits["6"].append(i)
    return {"counts": {k: len(v) for k,v in hits.items()}, "rows": hits}

def handle_run(payload: dict) -> dict:
    """
    Phase 1 entry — expects:
      LATEST_MM, LATEST_PB (string [['..'], bonus])
      LATEST_IL_JP, LATEST_IL_M1, LATEST_IL_M2 (string [['..'], null])
      FEED_MM, FEED_PB, FEED_IL
      HIST_MM_BLOB, HIST_PB_BLOB (dated) ; HIST_IL_*_BLOB (dated)
    Returns 50-row batches and hit stats/positions per game.
    """
    # --- parse inputs ---
    latest_mm = _parse_latest_pair(payload.get("LATEST_MM",""))
    latest_pb = _parse_latest_pair(payload.get("LATEST_PB",""))
    latest_il_jp = _parse_latest_pair(payload.get("LATEST_IL_JP",""))
    latest_il_m1 = _parse_latest_pair(payload.get("LATEST_IL_M1",""))
    latest_il_m2 = _parse_latest_pair(payload.get("LATEST_IL_M2",""))

    hist_mm = _parse_hist_blob_mm_pb(payload.get("HIST_MM_BLOB",""))
    hist_pb = _parse_hist_blob_mm_pb(payload.get("HIST_PB_BLOB",""))
    hist_il_jp = _parse_hist_blob_il(payload.get("HIST_IL_JP_BLOB",""))
    hist_il_m1 = _parse_hist_blob_il(payload.get("HIST_IL_M1_BLOB",""))
    hist_il_m2 = _parse_hist_blob_il(payload.get("HIST_IL_M2_BLOB",""))

    feed_mm = _extract_feed_sets(payload.get("FEED_MM",""), "Mega Ball")
    feed_pb = _extract_feed_sets(payload.get("FEED_PB",""), "Power Ball")
    feed_il = _extract_feed_sets(payload.get("FEED_IL",""), "")  # no bonus label

    # --- derive helper sets per game ---
    mm_mains_hist = [m for m,_ in hist_mm]
    pb_mains_hist = [m for m,_ in hist_pb]
    il_hist_all = hist_il_jp  # for undrawn/LRR we can use JP track as baseline

    mm_undrawn = _undrawn_from_last(mm_mains_hist, 10)
    pb_undrawn = _undrawn_from_last(pb_mains_hist, 10)
    il_undrawn = _undrawn_from_last(il_hist_all, 10)

    mm_lrr = _lrr_from_20(mm_mains_hist)
    pb_lrr = _lrr_from_20(pb_mains_hist)
    il_lrr = _lrr_from_20(il_hist_all)

    mm_vip = _vip(feed_mm["hot"], feed_mm["overdue"], mm_lrr)
    pb_vip = _vip(feed_pb["hot"], feed_pb["overdue"], pb_lrr)
    il_vip = _vip(feed_il["hot"], feed_il["overdue"], il_lrr)

    mm_band = _sum_band(mm_mains_hist)
    pb_band = _sum_band(pb_mains_hist)
    il_band = _sum_band(il_hist_all)

    # --- generate 50 rows per game using patterns & band filter ---
    random.seed(42)  # deterministic for UI; you can swap to env-seeded if you prefer
    # MM/PB mains (5 each)
    batch_mm_mains = _gen_50_for_game(5, _PAT_MM_PB, mm_mains_hist, feed_mm["hot"], feed_mm["overdue"], mm_undrawn, mm_vip, mm_lrr, mm_band)
    batch_pb_mains = _gen_50_for_game(5, _PAT_MM_PB, pb_mains_hist, feed_pb["hot"], feed_pb["overdue"], pb_undrawn, pb_vip, pb_lrr, pb_band)
    # IL mains (6)
    batch_il_mains = _gen_50_for_game(6, _PAT_IL, il_hist_all, feed_il["hot"], feed_il["overdue"], il_undrawn, il_vip, il_lrr, il_band)

    # --- assign bonus numbers for MM/PB ---
    # Mega/Power ball selection: either from hot/overdue bonus or undrawn bonus from last 10 draws (we approximate with hot/overdue pools + spillover 1..max)
    def gen_bonuses(hot_b, over_b, count, maxb=25):
        pool = list(dict.fromkeys(hot_b + over_b))
        if not pool:
            pool = list(range(1, maxb+1))
        out = []
        for _ in range(count):
            out.append(random.choice(pool))
        return out

    mm_bonus_rows = gen_bonuses(feed_mm["hot_bonus"], feed_mm["overdue_bonus"], len(batch_mm_mains), maxb=25)
    pb_bonus_rows = gen_bonuses(feed_pb["hot_bonus"], feed_pb["overdue_bonus"], len(batch_pb_mains), maxb=26)

    # --- compute hits against the 2nd newest jackpots (provided LATEST_* inputs) ---
    mm_latest_m, mm_latest_b = latest_mm
    pb_latest_m, pb_latest_b = latest_pb
    il_latest_jp, _ = latest_il_jp
    il_latest_m1, _ = latest_il_m1
    il_latest_m2, _ = latest_il_m2

    mm_hits = _count_hits_mm_pb(batch_mm_mains, mm_latest_m, mm_latest_b, mm_bonus_rows)
    pb_hits = _count_hits_mm_pb(batch_pb_mains, pb_latest_m, pb_latest_b, pb_bonus_rows)
    il_jp_hits = _count_hits_il(batch_il_mains, il_latest_jp)
    il_m1_hits = _count_hits_il(batch_il_mains, il_latest_m1)
    il_m2_hits = _count_hits_il(batch_il_mains, il_latest_m2)

    # --- pretty batches for UI ---
    def fmt_row(nums, bonus=None):
        body = "-".join(str(n).zfill(2) for n in nums)
        return f"{body}  {str(bonus).zfill(2)}" if bonus is not None else body

    ui_mm = [fmt_row(r, b) for r,b in zip(batch_mm_mains, mm_bonus_rows)]
    ui_pb = [fmt_row(r, b) for r,b in zip(batch_pb_mains, pb_bonus_rows)]
    ui_il = [fmt_row(r) for r in batch_il_mains]

    # Optional save
    saved_path = f"/tmp/lotto_1_{os.environ.get('RENDER', 'local')}_{random.randint(1000,9999)}.json"
    try:
        with open(saved_path, "w", encoding="utf-8") as f:
            json.dump({
                "phase":"phase1",
                "BATCH_MM": batch_mm_mains, "BATCH_MM_BONUS": mm_bonus_rows,
                "BATCH_PB": batch_pb_mains, "BATCH_PB_BONUS": pb_bonus_rows,
                "BATCH_IL": batch_il_mains,
                "HITS_MM": mm_hits, "HITS_PB": pb_hits,
                "HITS_IL_JP": il_jp_hits, "HITS_IL_M1": il_m1_hits, "HITS_IL_M2": il_m2_hits
            }, f)
    except Exception:
        saved_path = None

    return {
        "ok": True,
        "phase": "phase1",
        "saved_path": saved_path,
        "echo": {
            "BATCH_MM": ui_mm,
            "BATCH_PB": ui_pb,
            "BATCH_IL": ui_il,
            "HITS_MM": mm_hits,
            "HITS_PB": pb_hits,
            "HITS_IL_JP": il_jp_hits,
            "HITS_IL_M1": il_m1_hits,
            "HITS_IL_M2": il_m2_hits,
        }
    }
