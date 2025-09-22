from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import re
import hashlib

# --------------------------
# Helpers to parse blobs/feeds
# --------------------------

def _lines(s: str) -> List[str]:
    return [ln.rstrip("\n\r") for ln in (s or "").splitlines() if ln.strip()]

def _to_ints(s: str) -> List[int]:
    return [int(x) for x in re.findall(r"\d+", s)]

def _pad2(n: int) -> str:
    return f"{n:02d}"

def _fmt5(date_mdyy: str, mains: List[int], bonus: int) -> str:
    # date is mm-dd-yy already
    return f"{date_mdyy}  {'-'.join(_pad2(n) for n in mains)}  {_pad2(bonus)}"

def _fmt6(date_mdyy: str, mains: List[int]) -> str:
    return f"{date_mdyy}  {'-'.join(_pad2(n) for n in mains)}"

def _parse_mm_pb_line(line: str) -> Optional[Tuple[str, List[int], int]]:
    # "mm-dd-yy  n1-n2-n3-n4-n5  BB"
    m = re.match(r"^\s*(\d{2}-\d{2}-\d{2})\s+(\d{2}(?:-\d{2}){4})\s+(\d{2})\s*$", line)
    if not m:
        return None
    date = m.group(1)
    mains = [int(x) for x in m.group(2).split("-")]
    bonus = int(m.group(3))
    if len(mains) != 5:
        return None
    return (date, mains, bonus)

def _parse_il_line(line: str) -> Optional[Tuple[str, List[int]]]:
    # "mm-dd-yy  A-B-C-D-E-F"
    m = re.match(r"^\s*(\d{2}-\d{2}-\d{2})\s+(\d{2}(?:-\d{2}){5})\s*$", line)
    if not m:
        return None
    date = m.group(1)
    mains = [int(x) for x in m.group(2).split("-")]
    if len(mains) != 6:
        return None
    return (date, mains)

def _match_count(a: List[int], b: List[int]) -> int:
    sb = set(b)
    return sum(1 for x in a if x in sb)

def _pick_cycle(values: List[int], i: int) -> int:
    return values[i % len(values)] if values else 0

def _md5_int(seed: str) -> int:
    return int(hashlib.md5(seed.encode("utf-8")).hexdigest(), 16)

# --------------------------
# FEED parsers (very forgiving)
# --------------------------

def _parse_feed_hot_overdue(feed: str) -> Tuple[List[int], List[int], List[int]]:
    """
    Returns: (hot8, overdue8, top3_bonus)
    For IL, top3_bonus will be [].
    """
    hot8: List[int] = []
    overdue8: List[int] = []
    top3_bonus: List[int] = []

    for ln in _lines(feed):
        l = ln.lower()
        if "top 8 hot numbers" in l:
            hot8 = _to_ints(ln)[:8]
        elif "top 8 overdue numbers" in l:
            overdue8 = _to_ints(ln)[:8]
        elif "top 3 hot mega ball numbers" in l or "top 3 hot power ball numbers" in l:
            top3_bonus = _to_ints(ln)[:3]
        elif "top 3 overdue mega ball numbers" in l or "top 3 overdue power ball numbers" in l:
            # If we didn't get top3 hot, try to use overdue as backup
            if not top3_bonus:
                top3_bonus = _to_ints(ln)[:3]

    return (hot8, overdue8, top3_bonus)

# --------------------------
# Batch builders (deterministic)
# --------------------------

def _build_batch_mm_pb(
    nj_mains: List[int],
    nj_bonus: Optional[int],
    hist_blob: str,
    feed_text: str,
    game_tag: str
) -> List[str]:
    """
    Produce a deterministic 50-row batch:
      1-20: historical (as supplied, top-down)
     21-35: historical (first 15) but bonus swapped by cycling top-3 bonus from feed
     36-50: historical (first 15) with one main replaced by cycling overdue numbers
    """
    rows: List[str] = []
    hist = [_parse_mm_pb_line(ln) for ln in _lines(hist_blob)]
    hist = [t for t in hist if t]

    # keep exact formatting from blob
    for t in hist[:20]:
        if not t: continue
        rows.append(_fmt5(t[0], t[1], t[2]))

    hot8, overdue8, top3_bonus = _parse_feed_hot_overdue(feed_text)
    if not top3_bonus:
        top3_bonus = [1, 2, 3]  # safe fallback

    # 21-35: bonus swap
    for i, t in enumerate(hist[:15], start=0):
        if not t: 
            # pad with something if history shorter
            date = "01-01-70"
            mains = [1, 2, 3, 4, 5]
            bb = _pick_cycle(top3_bonus, i)
        else:
            date, mains, _oldb = t
            bb = _pick_cycle(top3_bonus, i)
        rows.append(_fmt5(date, mains, bb))

    # 36-50: overdue-injected
    for i, t in enumerate(hist[:15], start=0):
        if not t:
            date = "01-01-70"
            mains = [1, 2, 3, 4, 5]
            bb = _pick_cycle(top3_bonus, i)
        else:
            date, mains, bb = t
            mains = mains[:]
            if overdue8:
                pos = _md5_int(f"{game_tag}-{i}-{sum(mains)}") % 5
                mains[pos] = _pick_cycle(overdue8, i)
                mains = sorted(mains)
        rows.append(_fmt5(date, mains, bb))

    return rows[:50]

def _build_batch_il(
    hist_jp_blob: str,
    hist_m1_blob: str,
    hist_m2_blob: str,
    feed_text: str
) -> List[str]:
    """
    Single 50-row IL batch shared for JP/M1/M2 comparison:
      1-30: interleave 10 from JP, 10 from M1, 10 from M2
     31-50: make 20 synthetic rows by taking source rows cyclically and
            replacing one main with a cycling hot/overdue number from feed.
    """
    jp = [_parse_il_line(ln) for ln in _lines(hist_jp_blob)]
    m1 = [_parse_il_line(ln) for ln in _lines(hist_m1_blob)]
    m2 = [_parse_il_line(ln) for ln in _lines(hist_m2_blob)]
    jp = [t for t in jp if t]
    m1 = [t for t in m1 if t]
    m2 = [t for t in m2 if t]

    hot8, overdue8, _ = _parse_feed_hot_overdue(feed_text)

    rows: List[str] = []
    # 1-30 interleave
    for i in range(10):
        if i < len(jp): rows.append(_fmt6(jp[i][0], jp[i][1]))
        if i < len(m1): rows.append(_fmt6(m1[i][0], m1[i][1]))
        if i < len(m2): rows.append(_fmt6(m2[i][0], m2[i][1]))

    # 31-50 synthetic (from whichever has content)
    pool = (jp + m1 + m2) or []
    for i in range(20):
        if pool:
            src = pool[i % len(pool)]
            date, mains = src[0], src[1][:]
        else:
            date, mains = "01-01-70", [1, 2, 3, 4, 5, 6]
        # pick a slot and replace with a cycling hot/overdue
        pos = _md5_int(f"IL-{i}-{sum(mains)}") % 6
        replacement = (_pick_cycle(hot8, i) if i % 2 == 0 else _pick_cycle(overdue8, i))
        if replacement:
            mains[pos] = replacement
            mains = sorted(mains)
        rows.append(_fmt6(date, mains))

    return rows[:50]

# --------------------------
# Hit tables
# --------------------------

def _hits_mm_pb(batch: List[str], nj_mains: List[int], nj_bonus: int) -> Dict[str, Any]:
    cats = {"3":[], "3+B":[], "4":[], "4+B":[], "5":[], "5+B":[]}
    exact_rows: List[int] = []
    for idx, line in enumerate(batch, start=1):
        parsed = _parse_mm_pb_line(line)
        if not parsed: continue
        _, mains, bonus = parsed
        m = _match_count(nj_mains, mains)
        bonus_hit = (bonus == nj_bonus)
        if m == 5 and bonus_hit: cats["5+B"].append(idx)
        elif m == 5: cats["5"].append(idx)
        elif m == 4 and bonus_hit: cats["4+B"].append(idx)
        elif m == 4: cats["4"].append(idx)
        elif m == 3 and bonus_hit: cats["3+B"].append(idx)
        elif m == 3: cats["3"].append(idx)
        if m == 5 and bonus_hit:
            exact_rows.append(idx)
    return {
        "counts": {k: len(v) for k,v in cats.items()},
        "rows": cats,
        "exact_rows": exact_rows
    }

def _hits_il(batch: List[str], nj_mains: List[int]) -> Dict[str, Any]:
    cats = {3:[], 4:[], 5:[], 6:[]}
    for idx, line in enumerate(batch, start=1):
        parsed = _parse_il_line(line)
        if not parsed: continue
        _, mains = parsed
        m = _match_count(nj_mains, mains)
        if m in cats: cats[m].append(idx)
    return {
        "counts": {str(k): len(v) for k,v in cats.items()},
        "rows": {str(k): v for k,v in cats.items()}
    }

# --------------------------
# Public entry points
# --------------------------

def handle_run(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Phase-1:
      - Build 50-row batch per game
      - Compute hit tables and echo back
    """
    if payload.get("phase") != "phase1":
        return {"ok": False, "error": "Unsupported phase"}

    # Parse LATEST_* (strings like "[[mains..], bonus]" or "[[mains..], null]")
    def _parse_latest(x) -> Optional[Tuple[List[int], Optional[int]]]:
        try:
            if isinstance(x, str):
                obj = eval(x, {}, {})  # inputs are controlled from our UI; still keep minimal eval
            else:
                obj = x
            mains = [int(n) for n in obj[0]]
            bonus = None if obj[1] is None else int(obj[1])
            return (mains, bonus)
        except Exception:
            return None

    L_MM = _parse_latest(payload.get("LATEST_MM"))
    L_PB = _parse_latest(payload.get("LATEST_PB"))
    L_IJP = _parse_latest(payload.get("LATEST_IL_JP"))
    L_IM1 = _parse_latest(payload.get("LATEST_IL_M1"))
    L_IM2 = _parse_latest(payload.get("LATEST_IL_M2"))

    # Build batches
    batch_mm: List[str] = []
    batch_pb: List[str] = []
    batch_il: List[str] = []

    if L_MM:
        batch_mm = _build_batch_mm_pb(
            L_MM[0], L_MM[1] or 0,
            payload.get("HIST_MM_BLOB",""),
            payload.get("FEED_MM",""),
            "MM"
        )

    if L_PB:
        batch_pb = _build_batch_mm_pb(
            L_PB[0], L_PB[1] or 0,
            payload.get("HIST_PB_BLOB",""),
            payload.get("FEED_PB",""),
            "PB"
        )

    # IL single batch used for JP/M1/M2 hits
    if any([L_IJP, L_IM1, L_IM2]):
        batch_il = _build_batch_il(
            payload.get("HIST_IL_JP_BLOB",""),
            payload.get("HIST_IL_M1_BLOB",""),
            payload.get("HIST_IL_M2_BLOB",""),
            payload.get("FEED_IL",""),
        )

    # Hit tables
    mm_hits = _hits_mm_pb(batch_mm, *(L_MM or ([0,0,0,0,0],0)))
    pb_hits = _hits_mm_pb(batch_pb, *(L_PB or ([0,0,0,0,0],0)))

    il_jp_hits = _hits_il(batch_il, L_IJP[0]) if L_IJP else {"counts":{}, "rows":{}}
    il_m1_hits = _hits_il(batch_il, L_IM1[0]) if L_IM1 else {"counts":{}, "rows":{}}
    il_m2_hits = _hits_il(batch_il, L_IM2[0]) if L_IM2 else {"counts":{}, "rows":{}}

    res: Dict[str, Any] = {
        "ok": True,
        "phase": "phase1",
        "echo": {
            # batches back to UI
            "BATCH_MM": batch_mm,
            "BATCH_PB": batch_pb,
            "BATCH_IL": batch_il,
            # hit tables
            "HITS_MM": mm_hits,
            "HITS_PB": pb_hits,
            "HITS_IL_JP": il_jp_hits,
            "HITS_IL_M1": il_m1_hits,
            "HITS_IL_M2": il_m2_hits,
        }
    }
    return res

def handle_confirm(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {"ok": True, "phase": "confirm", "echo": payload}
