from __future__ import annotations

import json, os, random
from datetime import datetime
from typing import Dict, Any, List, Tuple

SAVE_DIR = "/tmp"

def _parse_latest(s: str, is_il: bool=False) -> Tuple[List[int], int|None]:
    """
    s like '[[10,22,34,40,66],24]'  or for IL '[[2,7,25,30,44,49],null]'
    """
    if isinstance(s, list):  # tolerate already-parsed
        mains = list(map(int, s[0]))
        bonus = None if is_il else (int(s[1]) if s[1] is not None else None)
        return mains, bonus
    if not isinstance(s, str) or "[[" not in s:
        raise ValueError("LATEST_* must be a string like '[[..],b]' or '[[..],null]'")
    obj = json.loads(s.replace("null","null"))
    mains = list(map(int, obj[0]))
    bonus = None if is_il else (int(obj[1]) if obj[1] is not None else None)
    return mains, bonus

def _parse_hist_blob(blob: str, is_il: bool=False) -> List[Tuple[List[int], int|None]]:
    """
    blob lines like:
    '09-12-25  17-18-21-42-64  07'  (MM/PB)
    '09-15-25  02-18-21-27-43-50'   (IL)
    """
    out = []
    for line in (blob or "").splitlines():
        line = line.strip()
        if not line or "-" not in line:
            continue
        parts = line.split()
        # mains part is last group of hyphen-numbers
        nums = parts[-1] if is_il else parts[-2]
        mains = [int(x) for x in nums.split("-")]
        bonus = None if is_il else int(parts[-1])
        out.append((mains, bonus))
    return out

def _score_row(mains: List[int], bonus: int|None, target_m: List[int], target_b: int|None, is_il: bool=False) -> Tuple[str,int]:
    hit = len(set(mains) & set(target_m))
    if is_il:
        # IL: 3/4/5/6 only
        if hit >= 6: return ("6", hit)
        if hit == 5: return ("5", hit)
        if hit == 4: return ("4", hit)
        if hit == 3: return ("3", hit)
        return ("", hit)
    # MM/PB with bonus classes
    with_bonus = (bonus is not None and target_b is not None and bonus == target_b)
    if hit == 5 and with_bonus: return ("5+B", hit)
    if hit == 5: return ("5", hit)
    if hit == 4 and with_bonus: return ("4+B", hit)
    if hit == 4: return ("4", hit)
    if hit == 3 and with_bonus: return ("3+B", hit)
    if hit == 3: return ("3", hit)
    return ("", hit)

def _make_batch(hist: List[Tuple[List[int],int|None]], latest: Tuple[List[int],int|None], size=50, seed=None) -> Tuple[List[str], Dict[str,Any]]:
    """
    Very simple sampler: take rolling windows from hist with a deterministic shuffle per run.
    """
    rnd = random.Random(seed or os.urandom(4))
    if not hist:
        return [], {"rows": {}, "counts": {}, "exact_rows": []}
    # expand by repeating history if needed
    picks = []
    # random window starts
    starts = list(range(0, max(1, len(hist)-5)))
    rnd.shuffle(starts)
    for st in starts:
        if len(picks) >= size: break
        window = hist[st:st+5]
        for row in window:
            if len(picks) < size:
                picks.append(row)
            else:
                break
    picks = picks[:size]
    # pretty strings & scoring
    batch_str = []
    counts = {"3":0,"4":0,"5":0,"3+B":0,"4+B":0,"5+B":0,"6":0}
    indices: Dict[str,List[int]] = {k:[] for k in counts.keys()}
    exact_rows: List[str] = []

    t_m, t_b = latest
    for i,(m,b) in enumerate(picks, start=1):
        if b is None:
            batch_str.append(f"{'-'.join(f'{x:02d}' for x in m)}")
        else:
            batch_str.append(f"{'-'.join(f'{x:02d}' for x in m)}  {b:02d}")
        cls,_ = _score_row(m,b,t_m,t_b, is_il=(b is None))
        if cls:
            counts[cls] = counts.get(cls,0)+1
            indices.setdefault(cls,[]).append(i)
        if m==t_m and ((b is None and t_b is None) or (b==t_b)):
            exact_rows.append(batch_str[-1])

    # trim zero classes for neat result
    counts = {k:v for k,v in counts.items() if v}
    indices = {k:v for k,v in indices.items() if v}
    return batch_str, {"counts": counts, "rows": indices, "exact_rows": exact_rows}

def handle_run(payload: Dict[str,Any]) -> Dict[str,Any]:
    # Read latests (strings)
    mm_latest = _parse_latest(payload.get("LATEST_MM",""), is_il=False)
    pb_latest = _parse_latest(payload.get("LATEST_PB",""), is_il=False)
    il_jp = _parse_latest(payload.get("LATEST_IL_JP",""), is_il=True)
    il_m1 = _parse_latest(payload.get("LATEST_IL_M1",""), is_il=True)
    il_m2 = _parse_latest(payload.get("LATEST_IL_M2",""), is_il=True)

    # History blobs
    mm_hist = _parse_hist_blob(payload.get("HIST_MM_BLOB",""), is_il=False)
    pb_hist = _parse_hist_blob(payload.get("HIST_PB_BLOB",""), is_il=False)
    il_hist = _parse_hist_blob(payload.get("HIST_IL_JP_BLOB",""), is_il=True) \
              + _parse_hist_blob(payload.get("HIST_IL_M1_BLOB",""), is_il=True) \
              + _parse_hist_blob(payload.get("HIST_IL_M2_BLOB",""), is_il=True)

    # Create 50-row batches and score
    seed = int(datetime.utcnow().timestamp()*1000) % 2_147_483_647
    mm_batch, mm_stats = _make_batch(mm_hist, mm_latest, 50, seed=seed+1)
    pb_batch, pb_stats = _make_batch(pb_hist, pb_latest, 50, seed=seed+2)
    il_batch, il_stats = _make_batch(il_hist, il_jp, 50, seed=seed+3)  # compare against IL JP by default

    out = {
        "ok": True,
        "phase": "phase1",
        "echo": {
            "BATCH_MM": mm_batch,
            "BATCH_PB": pb_batch,
            "BATCH_IL": il_batch,
            "HITS_MM": mm_stats,
            "HITS_PB": pb_stats,
            "HITS_IL_JP": il_stats,   # scored vs JP
        }
    }

    # Save to /tmp
    path = os.path.join(SAVE_DIR, f"lotto_1_{datetime.utcnow().strftime('%Y-%m-%d_%H-%M-%S')}.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    out["saved_path"] = path
    return out

def recent_files() -> List[str]:
    import glob
    return sorted(glob.glob(os.path.join(SAVE_DIR,"lotto_1_*.json")))[-20:]
