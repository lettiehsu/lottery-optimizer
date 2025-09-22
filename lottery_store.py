# lottery_core.py
# ------------------------------------------------------------
# Core for Phase 1 / 2 / 3 compatible with your UI.
# - Phase 1 accepts either:
#     (A) new style: dates only (mm_date, pb_date, il_jp_date, il_m1_date, il_m2_date)
#         and will fetch rows from lottery_store, build LATEST_* strings,
#         and assemble history blobs from the store (hist_*_from).
#     (B) old style: LATEST_* strings + HIST_*_BLOB strings.
#   It saves a normalized Phase-1 JSON to /tmp for Phase-2.
# - Phase 2 reads the Phase-1 JSON, (placeholder) returns bands and echo data.
# - Phase 3 accepts NWJ (string or JSON) and saves a confirmation JSON.
# - recent_files() lists recent /tmp files for the UI.
# ------------------------------------------------------------

from __future__ import annotations

import os
import re
import json
import ast
import glob
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# try to use the CSV-backed store for fetch-by-date and history
try:
    import lottery_store as _store
except Exception:
    _store = None

_TMP = "/tmp"

# ----------------------------- helpers ----------------------------- #

def _coerce_latest(val: Any, *, allow_null_bonus: bool = True) -> Tuple[List[int], Optional[int]]:
    """
    Accepts:
      - string: '[[n1,..], bonus]' or '[[..6..], null]'
      - list/tuple: [[...], bonus]
    Returns: (mains, bonus)
    """
    if isinstance(val, (list, tuple)):
        if len(val) != 2 or not isinstance(val[0], (list, tuple)):
            raise ValueError("LATEST_* must be [[...], bonus]")
        mains = [int(x) for x in val[0]]
        bonus = val[1]
        if bonus is None:
            if not allow_null_bonus:
                raise ValueError("Bonus cannot be null for this game")
        else:
            bonus = int(bonus)
        return mains, bonus

    if isinstance(val, str):
        s = val.strip()
        if not s:
            raise ValueError("LATEST_* is empty")
        try:
            parsed = json.loads(s)
        except Exception:
            parsed = ast.literal_eval(s)
        return _coerce_latest(parsed, allow_null_bonus=allow_null_bonus)

    raise ValueError("LATEST_* must be a JSON string or a 2-element list")


# history blob line patterns your UI shows
_re_line_mm = re.compile(r"^\s*(\d{2}-\d{2}-\d{2})\s+(\d{1,2}-\d{1,2}-\d{1,2}-\d{1,2}-\d{1,2})\s+\d{1,2}\s*$")
_re_line_il = re.compile(r"^\s*(\d{2}-\d{2}-\d{2})\s+(\d{1,2}-\d{1,2}-\d{1,2}-\d{1,2}-\d{1,2}-\d{1,2})\s*$")

def _parse_hist_blob_mm(blob: str) -> List[List[int]]:
    rows: List[List[int]] = []
    for line in (blob or "").splitlines():
        m = _re_line_mm.match(line.strip())
        if not m:
            continue
        mains = [int(x) for x in m.group(2).split("-")]
        if len(mains) == 5:
            rows.append(mains)
    return rows

def _parse_hist_blob_il(blob: str) -> List[List[int]]:
    rows: List[List[int]] = []
    for line in (blob or "").splitlines():
        m = _re_line_il.match(line.strip())
        if not m:
            continue
        mains = [int(x) for x in m.group(2).split("-")]
        if len(mains) == 6:
            rows.append(mains)
    return rows

def _percentile(sorted_vals: List[float], p: float) -> float:
    n = len(sorted_vals)
    if n == 0:
        return 0.0
    if n == 1:
        return float(sorted_vals[0])
    if p <= 0:   return float(sorted_vals[0])
    if p >= 1:   return float(sorted_vals[-1])
    idx = (n - 1) * p
    i = int(idx)
    frac = idx - i
    return float(sorted_vals[i] * (1 - frac) + sorted_vals[i + 1] * frac)

def _sum_band_from_hist(rows: List[List[int]]) -> Tuple[int, int]:
    if not rows:
        return (0, 0)
    sums = sorted(sum(r) for r in rows)
    lo = int(round(_percentile(sums, 0.25)))
    hi = int(round(_percentile(sums, 0.75)))
    return (lo, hi)

def _fmt_mm_pb_row(row: Dict[str, Any]) -> str:
    # -> "[[mains...], bonus]"
    a,b,c,d,e = row["mains"]
    bb = row["bonus"]
    return f"[[{a},{b},{c},{d},{e}],{bb}]"

def _fmt_il_row(row: Dict[str, Any]) -> str:
    # -> "[[n1..n6], null]"
    a,b,c,d,e,f = row["mains"]
    return f"[[{a},{b},{c},{d},{e},{f}],null]"

def _hist_blob_from_store(game: str, from_date: str, limit: int = 20) -> str:
    if not _store:
        return ""
    res = _store.get_history(game, from_date, limit=limit)
    return res.get("blob", "") if isinstance(res, dict) else ""


# ----------------------------- Phase 1 ----------------------------- #

def handle_run(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Phase-1 adapter:
      New style (preferred):
        mm_date, pb_date, il_jp_date, il_m1_date, il_m2_date (MM/DD/YYYY)
        hist_mm_from, hist_pb_from, hist_iljp_from, hist_ilm1_from, hist_ilm2_from (optional)
      Old style (fallback):
        LATEST_MM, LATEST_PB, LATEST_IL_JP, LATEST_IL_M1, LATEST_IL_M2 (strings)
        HIST_MM_BLOB, HIST_PB_BLOB, HIST_IL_BLOB_[JP|M1|M2] (strings)
    Saves normalized Phase-1 json to /tmp and returns bands + saved_path.
    """
    latest = {}
    hblobs = {}

    # ---------- Try new style (dates + store lookup) ----------
    use_new = any(k in payload for k in ("mm_date","pb_date","il_jp_date","il_m1_date","il_m2_date"))
    if use_new and _store:
        def need(k):
            v = (payload.get(k) or "").strip()
            if not v:
                raise ValueError(f"Pick dates to fetch: missing {k}")
            return v

        mm_date  = need("mm_date")
        pb_date  = need("pb_date")
        il_jp_dt = need("il_jp_date")
        il_m1_dt = need("il_m1_date")
        il_m2_dt = need("il_m2_date")

        r_mm = _store.get_by_date("MM", mm_date)
        r_pb = _store.get_by_date("PB", pb_date)
        r_jp = _store.get_by_date("IL", il_jp_dt,  tier="JP")
        r_m1 = _store.get_by_date("IL", il_m1_dt, tier="M1")
        r_m2 = _store.get_by_date("IL", il_m2_dt, tier="M2")

        if not all([r_mm, r_pb, r_jp, r_m1, r_m2]):
            missing = [n for n,r in [("MM",r_mm),("PB",r_pb),("IL_JP",r_jp),("IL_M1",r_m1),("IL_M2",r_m2)] if not r]
            return {"ok": False, "error": "not_found", "detail": f"Missing in store: {', '.join(missing)}"}

        latest["LATEST_MM"]    = _fmt_mm_pb_row(r_mm)
        latest["LATEST_PB"]    = _fmt_mm_pb_row(r_pb)
        latest["LATEST_IL_JP"] = _fmt_il_row(r_jp)
        latest["LATEST_IL_M1"] = _fmt_il_row(r_m1)
        latest["LATEST_IL_M2"] = _fmt_il_row(r_m2)

        # history blobs (top-down newest first)
        hblobs["HIST_MM_BLOB"]    = _hist_blob_from_store("MM",    payload.get("hist_mm_from")   or mm_date)
        hblobs["HIST_PB_BLOB"]    = _hist_blob_from_store("PB",    payload.get("hist_pb_from")   or pb_date)
        hblobs["HIST_IL_JP_BLOB"] = _hist_blob_from_store("IL_JP", payload.get("hist_iljp_from") or il_jp_dt)
        hblobs["HIST_IL_M1_BLOB"] = _hist_blob_from_store("IL_M1", payload.get("hist_ilm1_from") or il_m1_dt)
        hblobs["HIST_IL_M2_BLOB"] = _hist_blob_from_store("IL_M2", payload.get("hist_ilm2_from") or il_m2_dt)

    else:
        # ---------- Old style (already-built strings) ----------
        for k in ("LATEST_MM","LATEST_PB","LATEST_IL_JP","LATEST_IL_M1","LATEST_IL_M2"):
            v = payload.get(k)
            if not isinstance(v, str):
                return {"ok": False, "error": "ValueError", "detail": f"{k} must be a string like '[[..], b]' or '[[..], null]'"}
            latest[k] = v

        # optional history
        if isinstance(payload.get("HIST_MM_BLOB"), str): hblobs["HIST_MM_BLOB"] = payload["HIST_MM_BLOB"]
        if isinstance(payload.get("HIST_PB_BLOB"), str): hblobs["HIST_PB_BLOB"] = payload["HIST_PB_BLOB"]
        # IL blobs may be split by tier
        for t in ("JP","M1","M2"):
            tk = f"HIST_IL_{t}_BLOB"
            alt = f"HIST_IL_BLOB_{t}"
            if isinstance(payload.get(tk), str):
                hblobs[f"HIST_IL_{t}_BLOB"] = payload[tk]
            elif isinstance(payload.get(alt), str):
                hblobs[f"HIST_IL_{t}_BLOB"] = payload[alt]

    # ---------- compute simple bands from history ----------
    mm_rows  = _parse_hist_blob_mm(hblobs.get("HIST_MM_BLOB",""))
    pb_rows  = _parse_hist_blob_mm(hblobs.get("HIST_PB_BLOB",""))
    il_rows  = []
    il_rows += _parse_hist_blob_il(hblobs.get("HIST_IL_JP_BLOB",""))
    il_rows += _parse_hist_blob_il(hblobs.get("HIST_IL_M1_BLOB",""))
    il_rows += _parse_hist_blob_il(hblobs.get("HIST_IL_M2_BLOB",""))

    bands = {
        "MM": list(_sum_band_from_hist(mm_rows)),
        "PB": list(_sum_band_from_hist(pb_rows)),
        "IL": list(_sum_band_from_hist(il_rows)),
    }

    # ---------- save normalized Phase-1 state ----------
    out = {
        "phase": "phase1",
        "latest": latest,   # strings LATEST_* → compatible with any older Phase-2 code
        "history": hblobs,
        "bands": bands,
        "ts": datetime.utcnow().isoformat(timespec="seconds")+"Z",
    }
    save_path = os.path.join(_TMP, f"lotto_phase1_{datetime.utcnow().strftime('%Y-%m-%d_%H-%M-%S')}.json")
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    return {"ok": True, "phase": "phase1", "bands": bands, "saved_path": save_path}


# ----------------------------- Phase 2 (minimal placeholder) ----------------------------- #

def handle_phase2(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Minimal Phase-2 placeholder that just reads Phase-1 file and echoes bands + latest.
    Your project likely has a richer Phase-2; if so, keep yours instead.
    """
    p1_path = (payload.get("saved_phase1_path") or payload.get("phase1_path") or "").strip()
    if not p1_path or not os.path.exists(p1_path):
        return {"ok": False, "error": "FileNotFoundError", "detail": "saved_phase1_path not found"}

    with open(p1_path, "r", encoding="utf-8") as f:
        p1 = json.load(f)

    # Normally you'd run 100× regeneration stats and build buy lists here.
    # We just pass through the bands and latest to keep your UI moving.
    res = {
        "ok": True,
        "phase": "phase2",
        "bands": p1.get("bands", {}),
        "latest": p1.get("latest", {}),
        "note": "Minimal Phase-2 placeholder. Replace with your real simulation to compute stats & buy lists.",
    }
    save_path = os.path.join(_TMP, f"lotto_phase2_{datetime.utcnow().strftime('%Y-%m-%d_%H-%M-%S')}.json")
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    res["saved_path"] = save_path
    return res


# ----------------------------- Phase 3 (confirm) ----------------------------- #

def handle_confirm(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Confirmation stub: accepts NWJ for MM/PB/IL (string or JSON),
    and optionally the Phase-2 path to attach.
    """
    # Phase-2 (optional)
    p2_path = (payload.get("saved_phase2_path") or payload.get("phase2_path") or "").strip()
    p2_loaded = bool(p2_path and os.path.exists(p2_path))

    # NWJ (accept strings or arrays)
    try:
        mm, _   = _coerce_latest(payload.get("LATEST_MM"), allow_null_bonus=False)
        pb, _   = _coerce_latest(payload.get("LATEST_PB"), allow_null_bonus=False)
        iljp, _ = _coerce_latest(payload.get("LATEST_IL_JP"), allow_null_bonus=True)
        ilm1, _ = _coerce_latest(payload.get("LATEST_IL_M1"), allow_null_bonus=True)
        ilm2, _ = _coerce_latest(payload.get("LATEST_IL_M2"), allow_null_bonus=True)
    except Exception as e:
        return {"ok": False, "error": "ValueError", "detail": str(e)}

    result = {
        "ok": True,
        "phase": "phase3",
        "nwj": {"MM": mm, "PB": pb, "IL": {"JP": iljp, "M1": ilm1, "M2": ilm2}},
        "phase2_loaded": p2_loaded,
    }
    save_path = os.path.join(_TMP, f"lotto_phase3_{datetime.utcnow().strftime('%Y-%m-%d_%H-%M-%S')}.json")
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    result["saved_path"] = save_path
    return result


# ----------------------------- Misc ----------------------------- #

def recent_files(limit: int = 30) -> List[str]:
    files = sorted(glob.glob(os.path.join(_TMP, "lotto_phase*.json")))
    return files[-int(limit):]
