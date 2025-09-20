# lottery_core.py  — minimal, boot-safe version
from __future__ import annotations
import os, json, random, datetime as dt

SAVE_DIR = "buylists"
os.makedirs(SAVE_DIR, exist_ok=True)

# ───────────────── helpers ─────────────────

def _parse_list_or_none(s: str):
    s = (s or "").strip()
    if not s:
        return None
    # Accept "[1,2,3,4,5]" or "1,2,3,4,5"
    try:
        s2 = s
        if s2.startswith("[") and s2.endswith("]"):
            s2 = s2[1:-1]
        return [int(x.strip()) for x in s2.split(",") if x.strip()]
    except Exception:
        raise ValueError(f"Bad list input: {s!r}")

def _parse_mm_pb(s: str):
    s = (s or "").strip()
    if not s:
        return None
    # Accept "[1,2,3,4,5],6" or "1,2,3,4,5,6" (last is bonus)
    if "]" in s:
        left, _, right = s.partition("]")
        mains = _parse_list_or_none(left + "]")
        bonus = int(right.lstrip(",").strip())
    else:
        parts = [p.strip() for p in s.split(",") if p.strip()]
        if len(parts) < 6:
            raise ValueError(f"Need 5 mains + bonus, got: {s!r}")
        mains = [int(x) for x in parts[:-1]]
        bonus = int(parts[-1])
    if len(mains) != 5:
        raise ValueError(f"Need exactly 5 mains, got {len(mains)} in {s!r}")
    return (sorted(mains), bonus)

def _overlap(a, b): return len(set(a) & set(b))

def _mk_batch_5pick(n_rows, max_num, bonus_max, seed):
    random.seed(seed)
    seen = set(); out = []
    while len(out) < n_rows:
        mains = tuple(sorted(random.sample(range(1, max_num+1), 5)))
        bonus = random.randint(1, bonus_max)
        key = (mains, bonus)
        if key not in seen:
            seen.add(key); out.append((list(mains), bonus))
    return out

def _mk_batch_6pick(n_rows, max_num, seed):
    random.seed(seed)
    seen = set(); out = []
    while len(out) < n_rows:
        mains = tuple(sorted(random.sample(range(1, max_num+1), 6)))
        if mains not in seen:
            seen.add(mains); out.append(list(mains))
    return out

def _save_buylists(mm_list, pb_list, il_list):
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    payload = {
        "timestamp": stamp,
        "MM": [[t[0], t[1]] for t in mm_list],
        "PB": [[t[0], t[1]] for t in pb_list],
        "IL": [list(t) for t in il_list],
    }
    path = os.path.join(SAVE_DIR, f"buy_session_{stamp}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return path

def _load_buylists(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    mm = [(list(item[0]), int(item[1])) for item in data.get("MM", [])]
    pb = [(list(item[0]), int(item[1])) for item in data.get("PB", [])]
    il = [list(map(int, row)) for row in data.get("IL", [])]
    return mm, pb, il

# ─────────────── public API used by app.py ───────────────

def run_phase_1_and_2(cfg: dict) -> dict:
    """Build 50-row batches, do simple Phase-1 hit check, toy Phase-2 counts, save buy list."""
    # Parse “LATEST_*” inputs (blank is allowed)
    latest_mm = None
    latest_pb = None
    try:
        if cfg.get("LATEST_MM"): latest_mm = _parse_mm_pb(cfg["LATEST_MM"])
        if cfg.get("LATEST_PB"): latest_pb = _parse_mm_pb(cfg["LATEST_PB"])
    except Exception as e:
        # Surface a readable message back to the UI
        return {"error": f"Parse error (MM/PB): {e}"}

    latest_il_jp = _parse_list_or_none(cfg.get("LATEST_IL_JP", ""))
    latest_il_m1 = _parse_list_or_none(cfg.get("LATEST_IL_M1", ""))
    latest_il_m2 = _parse_list_or_none(cfg.get("LATEST_IL_M2", ""))

    runs = int(cfg.get("runs") or 100)

    # Generate simple placeholder batches (swap with your optimizer later)
    mm_batch = _mk_batch_5pick(50, 70, 25, seed=777)
    pb_batch = _mk_batch_5pick(50, 69, 26, seed=888)
    il_batch = _mk_batch_6pick(50, 50, seed=999)

    # Phase-1 hits (rows only)
    def _hits_mm_pb(batch, target):
        rows = []
        if not target: return rows
        tgt_m, tgt_b = target
        for i, (mains, b) in enumerate(batch, 1):
            m = _overlap(mains, tgt_m); bh = (b == tgt_b)
            if m >= 3 or (m >= 2 and bh):
                rows.append({"row": i, "mains": mains, "bonus": b, "m": m, "bonus_hit": bh})
        return rows

    def _hits_il(batch, target):
        rows = []
        if not target: return rows
        for i, mains in enumerate(batch, 1):
            m = _overlap(mains, target)
            if m >= 3:
                rows.append({"row": i, "mains": mains, "m": m})
        return rows

    phase1 = {
        "mm": {"batch": mm_batch, "hits": _hits_mm_pb(mm_batch, latest_mm)},
        "pb": {"batch": pb_batch, "hits": _hits_mm_pb(pb_batch, latest_pb)},
        "il": {
            "batch": il_batch,
            "hits_jp": _hits_il(il_batch, latest_il_jp),
            "hits_m1": _hits_il(il_batch, latest_il_m1),
            "hits_m2": _hits_il(il_batch, latest_il_m2),
        },
    }

    # Toy Phase-2 counts (not your full sim — just to keep UI happy)
    def _sim_mm_pb(target, max_num, bonus_max, base_seed):
        types = {"3":0,"3+":0,"4":0,"4+":0,"5":0,"5+":0}
        if not target: return types
        tgt_m, tgt_b = target
        for r in range(runs):
            batch = _mk_batch_5pick(50, max_num, bonus_max, seed=base_seed+r)
            for mains, b in batch:
                m = _overlap(mains, tgt_m); bh = (b == tgt_b)
                if   m==3 and not bh: types["3"]  += 1
                elif m==3 and bh:     types["3+"] += 1
                elif m==4 and not bh: types["4"]  += 1
                elif m==4 and bh:     types["4+"] += 1
                elif m==5 and not bh: types["5"]  += 1
                elif m==5 and bh:     types["5+"] += 1
        return types

    def _sim_il(targets, base_seed):
        types = {"3":0,"4":0,"5":0,"6":0}
        if not any(targets): return types
        for r in range(runs):
            batch = _mk_batch_6pick(50, 50, seed=base_seed+r)
            for mains in batch:
                best = 0
                for tgt in targets:
                    if tgt: best = max(best, _overlap(mains, tgt))
                if best>=3: types["3"] += 1
                if best>=4: types["4"] += 1
                if best>=5: types["5"] += 1
                if best==6: types["6"] += 1
        return types

    phase2_stats = {
        "mm": _sim_mm_pb(latest_mm, 70, 25, 17000),
        "pb": _sim_mm_pb(latest_pb, 69, 26, 18000),
        "il": _sim_il([latest_il_jp, latest_il_m1, latest_il_m2], 19000),
    }

    # Recommend first 10/10/15 (placeholder) and save
    mm_buy = mm_batch[:10]; pb_buy = pb_batch[:10]; il_buy = il_batch[:15]
    saved_path = _save_buylists(mm_buy, pb_buy, il_buy)

    return {
        "phase1": phase1,
        "phase2_stats": phase2_stats,
        "buylists": {"mm": mm_buy, "pb": pb_buy, "il": il_buy},
        "saved_path": saved_path,
    }

def confirm_phase_3(saved_file: str, nwj: dict, recall_headings: bool=False) -> dict:
    mm_buy, pb_buy, il_buy = _load_buylists(saved_file)
    out = {"saved_file": saved_file, "recall_headings": recall_headings}

    mm = pb = None
    try:
        if nwj.get("mm"): mm = _parse_mm_pb(nwj["mm"])
        if nwj.get("pb"): pb = _parse_mm_pb(nwj["pb"])
    except Exception as e:
        return {"error": f"Parse error (NWJ MM/PB): {e}"}

    il_jp  = _parse_list_or_none(nwj.get("il_jp"))
    il_m1  = _parse_list_or_none(nwj.get("il_m1"))
    il_m2  = _parse_list_or_none(nwj.get("il_m2"))

    if mm:
        tgt_m, tgt_b = mm
        tiers = {"2+":0,"3":0,"3+":0,"4":0,"4+":0,"5":0,"5+":0}
        rows = []
        for i,(mains,b) in enumerate(mm_buy,1):
            m=_overlap(mains,tgt_m); bh=(b==tgt_b)
            if m==2 and bh: tiers["2+"]+=1
            if m==3: tiers["3"]+=1
            if m==3 and bh: tiers["3+"]+=1
            if m==4: tiers["4"]+=1
            if m==4 and bh: tiers["4+"]+=1
            if m==5: tiers["5"]+=1
            if m==5 and bh: tiers["5+"]+=1
            if m>=3 or (m>=2 and bh): rows.append({"buy_index":i,"m":m,"bonus_hit":bh})
        out["mm"]={"totals":tiers,"rows":rows}

    if pb:
        tgt_m, tgt_b = pb
        tiers = {"2+":0,"3":0,"3+":0,"4":0,"4+":0,"5":0,"5+":0}
        rows = []
        for i,(mains,b) in enumerate(pb_buy,1):
            m=_overlap(mains,tgt_m); bh=(b==tgt_b)
            if m==2 and bh: tiers["2+"]+=1
            if m==3: tiers["3"]+=1
            if m==3 and bh: tiers["3+"]+=1
            if m==4: tiers["4"]+=1
            if m==4 and bh: tiers["4+"]+=1
            if m==5: tiers["5"]+=1
            if m==5 and bh: tiers["5+"]+=1
            if m>=3 or (m>=2 and bh): rows.append({"buy_index":i,"m":m,"bonus_hit":bh})
        out["pb"]={"totals":tiers,"rows":rows}

    if any([il_jp, il_m1, il_m2]):
        tiers={2:0,3:0,4:0,5:0,6:0}; rows=[]
        for i,mains in enumerate(il_buy,1):
            best=0; label=None
            for name,tgt in (("Jackpot",il_jp),("Million 1",il_m1),("Million 2",il_m2)):
                if tgt:
                    hits=_overlap(mains,tgt)
                    if hits>best: best,label=hits,name
            if best>=2: tiers[min(6,max(2,best))]+=1
            if best>=3: rows.append({"buy_index":i,"m":best,"vs":label})
        out["il"]={"totals":tiers,"rows":rows}

    return out
