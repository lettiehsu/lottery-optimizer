# lottery_core.py — complete, focused on Phase 1
from __future__ import annotations

import os, json, re, secrets
from typing import List, Dict, Any, Tuple

def _parse_latest(box: str, expect_len: int) -> Tuple[List[int], int|None]:
    """
    Accepts strings like: [[10,14,34,40,43], 5]  or  [[2,7,25,30,44,49], null]
    Returns (mains, bonus_or_None)
    """
    s = (box or "").strip()
    if not s:
        return [], None
    m = re.match(r'^\s*\[\s*\[(.*?)\]\s*,\s*(.*?)\]\s*$', s)
    if not m:
        raise ValueError("LATEST_* must be a string like '[[..], b]' or '[[..], null]'")
    mains_txt, bonus_txt = m.group(1), m.group(2)
    mains = [int(x.strip()) for x in mains_txt.split(',') if x.strip()]
    if len(mains) != expect_len:
        raise ValueError(f"Expected {expect_len} mains, got {len(mains)}")
    bonus = None
    if bonus_txt.lower() != 'null':
        bonus = int(bonus_txt)
    return mains, bonus

def _parse_hist_blob(blob: str, take: int = 50, il: bool=False) -> List[List[int]]:
    """
    Accepts preformatted lines like:
      09-12-25  17-18-21-42-64  07
      09-15-25  01-04-05-10-18-49
    Returns up to 'take' rows of mains (ignore bonus).
    """
    out : List[List[int]] = []
    for line in (blob or "").splitlines():
        line = line.strip()
        if not line: continue
        # try to find A-B-C-D-E (-F) in line
        parts = re.findall(r'\b(\d{2})-(\d{2})-(\d{2})-(\d{2})-(\d{2})(?:-(\d{2}))?', line)
        if not parts: continue
        nums = [int(x) for x in parts[0] if x]
        # keep only mains (5 for MM/PB, 6 for IL)
        mains = nums[:6] if il else nums[:5]
        out.append(mains)
        if len(out) >= take: break
    return out

def _hit_counts(batch: List[List[int]], target_mains: List[int], target_bonus: int|None) -> Dict[str, Any]:
    # MM/PB (5 mains + bonus)
    rows: Dict[str, List[int]] = {'3':[], '4':[], '5':[], '3+B':[], '4+B':[], '5+B':[]}
    counts = {k: 0 for k in rows.keys()}
    tset = set(target_mains)
    for idx, row in enumerate(batch, start=1):
        m = len(tset.intersection(row))
        if m in (3,4,5):
            counts[str(m)] += 1
            rows[str(m)].append(idx)
    # bonus: we don't know row bonus; treat as “+B not applicable” for batch; keep zeros
    return {'counts': counts, 'rows': rows, 'exact_rows': []}

def _hit_counts_il(batch: List[List[int]], target_mains: List[int]) -> Dict[str, Any]:
    rows: Dict[str, List[int]] = {'3':[], '4':[], '5':[], '6':[]}
    counts = {k: 0 for k in rows.keys()}
    tset = set(target_mains)
    for idx, row in enumerate(batch, start=1):
        m = len(tset.intersection(row))
        if m in (3,4,5,6):
            counts[str(m)] += 1
            rows[str(m)].append(idx)
    return {'counts': counts, 'rows': rows}

def _rand_sample(pop: List[int], k: int) -> List[int]:
    # cryptographically strong shuffle / sample
    if k > len(pop): k = len(pop)
    arr = pop[:]
    for i in range(len(arr)-1, 0, -1):
        j = secrets.randbelow(i+1)
        arr[i], arr[j] = arr[j], arr[i]
    return arr[:k]

def _gen_mm_batch(hist: List[List[int]]) -> List[str]:
    # hist: 50 rows of last draws; use positions to bias sampling a bit
    batch : List[str] = []
    pool = list(range(1,71))   # MM mains (1..70) – adjust if your rule differs
    # simple pattern: 50 rows, each is random 5 distinct numbers, sorted
    for _ in range(50):
        row = sorted(_rand_sample(pool, 5))
        # fake a displayed bonus for readability (not used for hits)
        bonus = secrets.randbelow(25) + 1
        batch.append(f"{str(row[0]).zfill(2)}-{str(row[1]).zfill(2)}-{str(row[2]).zfill(2)}-{str(row[3]).zfill(2)}-{str(row[4]).zfill(2)}  {str(bonus).zfill(2)}")
    return batch

def _gen_pb_batch(hist: List[List[int]]) -> List[str]:
    pool = list(range(1,70))   # PB mains up to 69
    out : List[str] = []
    for _ in range(50):
        row = sorted(_rand_sample(pool, 5))
        bonus = secrets.randbelow(26) + 1
        out.append(f"{str(row[0]).zfill(2)}-{str(row[1]).zfill(2)}-{str(row[2]).zfill(2)}-{str(row[3]).zfill(2)}-{str(row[4]).zfill(2)}  {str(bonus).zfill(2)}")
    return out

def _gen_il_batch(hist: List[List[int]]) -> List[str]:
    pool = list(range(1,53))   # IL Lotto mains up to 52
    out : List[str] = []
    for _ in range(50):
        row = sorted(_rand_sample(pool, 6))
        out.append("-".join(str(n).zfill(2) for n in row))
    return out

def _string_rows_to_mains(batch_lines: List[str], il: bool=False) -> List[List[int]]:
    mains : List[List[int]] = []
    for line in batch_lines:
        parts = re.findall(r'(\d{2})', line)
        if not parts: continue
        nums = [int(x) for x in parts]
        mains.append(nums[:6] if il else nums[:5])
    return mains

def handle_run(payload: Dict[str, Any]) -> Dict[str, Any]:
    if payload.get('phase') != 'phase1':
        return {'ok': False, 'error': 'Unsupported phase'}

    # Parse LATEST_* (the 2nd newest JP)
    mm_mains, mm_bonus = _parse_latest(payload.get('LATEST_MM',''), 5)
    pb_mains, pb_bonus = _parse_latest(payload.get('LATEST_PB',''), 5)
    # You can choose which IL tier to grade against; here I default to M2 if available, else M1, else JP
    il_choice = 'LATEST_IL_M2'
    if not payload.get(il_choice):
      il_choice = 'LATEST_IL_M1' if payload.get('LATEST_IL_M1') else 'LATEST_IL_JP'
    il_mains, _ = _parse_latest(payload.get(il_choice,''), 6)

    # Parse history blobs (top-down, newest first as pasted)
    hist_mm = _parse_hist_blob(payload.get('HIST_MM_BLOB',''), take=50, il=False)
    hist_pb = _parse_hist_blob(payload.get('HIST_PB_BLOB',''), take=50, il=False)
    # for IL we don’t need three blobs to build batch, one is fine; but keep them in echo for transparency
    hist_il = _parse_hist_blob(
        payload.get('HIST_IL_M2_BLOB') or payload.get('HIST_IL_M1_BLOB') or payload.get('HIST_IL_JP_BLOB') or '',
        take=50, il=True
    )

    # Generate 50 rows for each game (randomized every call)
    batch_mm = _gen_mm_batch(hist_mm)
    batch_pb = _gen_pb_batch(hist_pb)
    batch_il = _gen_il_batch(hist_il)

    # Compute hits vs your 2nd-newest jackpots
    mm_rows_mains = _string_rows_to_mains(batch_mm, il=False)
    pb_rows_mains = _string_rows_to_mains(batch_pb, il=False)
    il_rows_mains = _string_rows_to_mains(batch_il, il=True)

    hits_mm = _hit_counts(mm_rows_mains, mm_mains, mm_bonus)
    hits_pb = _hit_counts(pb_rows_mains, pb_mains, pb_bonus)
    hits_il = _hit_counts_il(il_rows_mains, il_mains)

    saved_path = f"/tmp/lotto_1_{payload.get('run_id','') or 'run'}.json"
    echo = {
        'BATCH_MM': batch_mm,
        'BATCH_PB': batch_pb,
        'BATCH_IL': batch_il,

        'HITS_MM': hits_mm,
        'HITS_PB': hits_pb,
        'HITS_IL_JP': hits_il,  # keep legacy keys for your UI; you can switch to a single HITS_IL
        'HITS_IL_M1': hits_il,
        'HITS_IL_M2': hits_il,

        # leave these for debugging/UI
        'LATEST_MM': payload.get('LATEST_MM',''),
        'LATEST_PB': payload.get('LATEST_PB',''),
        'LATEST_IL_JP': payload.get('LATEST_IL_JP',''),
        'LATEST_IL_M1': payload.get('LATEST_IL_M1',''),
        'LATEST_IL_M2': payload.get('LATEST_IL_M2',''),
    }
    try:
        with open(saved_path, 'w') as f:
            json.dump({'ok': True, 'phase': 'phase1', 'echo': echo}, f, indent=2)
    except Exception:
        pass

    return {'ok': True, 'phase': 'phase1', 'echo': echo, 'saved_path': saved_path}

# Optional: recent files list
def recent_files() -> List[str]:
    return sorted([p for p in os.listdir('/tmp') if p.startswith('lotto_1_')])
