# lottery_core.py
# ------------------------------------------------------------
# Core logic for Phase 1 / Phase 3 used by your Flask app.
# - Accepts LATEST_* as string or JSON (e.g., [[...], 5] or "[[...],5]")
# - Parses history blobs to compute middle-50% sum bands (25th–75th pct)
# - Saves a Phase-1 state file into /tmp and returns the path
# - Minimal Phase-3 confirm stub and recent_files helper
# ------------------------------------------------------------

from __future__ import annotations

import os
import re
import json
import ast
import glob
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


# ----------------------------- Utilities ----------------------------- #

def _coerce_latest(val: Any, *, allow_null_bonus: bool = True) -> Tuple[List[int], Optional[int]]:
    """
    Accepts:
      - string: '[[n1,n2,n3,n4,n5], 12]'  or  '[[a,b,c,d,e,f], null]' (IL)
      - list/tuple: [[...], bonus]         # already parsed JSON or form->JSON
    Returns: (mains:list[int], bonus:int|None)
    """
    # Already parsed list/tuple?
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

    # String → parse JSON first, fallback to literal_eval
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


def _percentile(sorted_vals: List[float], p: float) -> float:
    """Simple percentile (0..1), linear interpolation."""
    n = len(sorted_vals)
    if n == 0:
        return 0.0
    if n == 1:
        return float(sorted_vals[0])
    if p <= 0:
        return float(sorted_vals[0])
    if p >= 1:
        return float(sorted_vals[-1])
    idx = (n - 1) * p
    i = int(idx)
    frac = idx - i
    return float(sorted_vals[i] * (1 - frac) + sorted_vals[i + 1] * frac)


# History line patterns:
#  - MM/PB:  "mm-dd-yy  a-b-c-d-e  MB"
#  - ILx:    "mm-dd-yy  A-B-C-D-E-F"   (no bonus number)
_re_line_mm = re.compile(r"^\s*(\d{2}-\d{2}-\d{2})\s+(\d{1,2}-\d{1,2}-\d{1,2}-\d{1,2}-\d{1,2})\s+\d{1,2}\s*$")
_re_line_il = re.compile(r"^\s*(\d{2}-\d{2}-\d{2})\s+(\d{1,2}-\d{1,2}-\d{1,2}-\d{1,2}-\d{1,2}-\d{1,2})\s*$")

def _parse_hist_blob_mm(blob: str) -> List[List[int]]:
    """Parse MM/PB blob lines → list of main-5 rows (ints)."""
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
    """Parse IL (JP/M1/M2) blob lines → list of main-6 rows (ints)."""
    rows: List[List[int]] = []
    for line in (blob or "").splitlines():
        m = _re_line_il.match(line.strip())
        if not m:
            continue
        mains = [int(x) for x in m.group(2).split("-")]
        if len(mains) == 6:
            rows.append(mains)
    return rows

def _sum_band_from_hist(rows: List[List[int]]) -> Tuple[int, int]:
    """Given rows of mains, compute 25th–75th percentile of sums."""
    if not rows:
        return (0, 0)
    sums = sorted(sum(r) for r in rows)
    lo = int(round(_percentile(sums, 0.25)))
    hi = int(round(_percentile(sums, 0.75)))
    return (lo, hi)


# ----------------------------- Phase-1 ----------------------------- #

def handle_run(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Phase 1 — Evaluation entry.
    Required keys from UI:
      LATEST_MM, LATEST_PB               # [[..5..], mb]
      LATEST_IL_JP, LATEST_IL_M1, LATEST_IL_M2  # [[..6..], null]
    Optional:
      FEED_MM, FEED_PB, FEED_IL          # strings (not used here, just stored)
      HIST_MM_BLOB, HIST_PB_BLOB,
      HIST_IL_JP_BLOB, HIST_IL_M1_BLOB, HIST_IL_M2_BLOB
    """
    # Coerce newest jackpots (accept JSON or string)
    try:
        mm_mains, mm_mb = _coerce_latest(payload.get("LATEST_MM"), allow_null_bonus=False)
        pb_mains, pb_mb = _coerce_latest(payload.get("LATEST_PB"), allow_null_bonus=False)
        iljp_mains, _    = _coerce_latest(payload.get("LATEST_IL_JP"), allow_null_bonus=True)
        ilm1_mains, _    = _coerce_latest(payload.get("LATEST_IL_M1"), allow_null_bonus=True)
        ilm2_mains, _    = _coerce_latest(payload.get("LATEST_IL_M2"), allow_null_bonus=True)
    except Exception as e:
        return {"ok": False, "error": "ValueError", "detail": str(e)}

    # History blobs (top-down, newest first) → compute middle-50% sum bands
    mm_hist_rows  = _parse_hist_blob_mm(payload.get("HIST_MM_BLOB") or "")
    pb_hist_rows  = _parse_hist_blob_mm(payload.get("HIST_PB_BLOB") or "")
    iljp_hist_rows = _parse_hist_blob_il(payload.get("HIST_IL_JP_BLOB") or "")
    ilm1_hist_rows = _parse_hist_blob_il(payload.get("HIST_IL_M1_BLOB") or "")
    ilm2_hist_rows = _parse_hist_blob_il(payload.get("HIST_IL_M2_BLOB") or "")

    mm_band  = _sum_band_from_hist(mm_hist_rows)
    pb_band  = _sum_band_from_hist(pb_hist_rows)
    il_band  = _sum_band_from_hist(iljp_hist_rows + ilm1_hist_rows + ilm2_hist_rows)

    bands = {
        "MM": list(mm_band),
        "PB": list(pb_band),
        "IL": list(il_band),
    }

    # (Optional) you can compute “exact hit rows vs NJ” here if you want.
    # We’ll return empty stubs to keep the UI sections clean.
    exact_hits = {
        "MM": {"3": [], "3B": [], "4": [], "4B": [], "5": [], "5B": []},
        "PB": {"3": [], "3B": [], "4": [], "4B": [], "5": [], "5B": []},
        "IL": {"JP": {"3": [], "4": [], "5": [], "6": []},
               "M1": {"3": [], "4": [], "5": [], "6": []},
               "M2": {"3": [], "4": [], "5": [], "6": []}},
    }

    # Save Phase-1 state so Phase-2 can reuse it.
    state = {
        "ok": True,
        "phase": "phase1",
        "bands": bands,
        "latest": {
            "MM": {"mains": mm_mains, "mb": mm_mb},
            "PB": {"mains": pb_mains, "pb": pb_mb},
            "IL": {"JP": iljp_mains, "M1": ilm1_mains, "M2": ilm2_mains},
        },
        "feeds": {
            "MM": payload.get("FEED_MM") or "",
            "PB": payload.get("FEED_PB") or "",
            "IL": payload.get("FEED_IL") or "",
        },
        "history_blobs": {
            "HIST_MM_BLOB": payload.get("HIST_MM_BLOB") or "",
            "HIST_PB_BLOB": payload.get("HIST_PB_BLOB") or "",
            "HIST_IL_JP_BLOB": payload.get("HIST_IL_JP_BLOB") or "",
            "HIST_IL_M1_BLOB": payload.get("HIST_IL_M1_BLOB") or "",
            "HIST_IL_M2_BLOB": payload.get("HIST_IL_M2_BLOB") or "",
        },
        "exact_hits": exact_hits,
        "note": "Use saved_path for Phase 2.",
    }

    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out_path = f"/tmp/lotto_phase1_{ts}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

    return {
        "ok": True,
        "phase": "phase1",
        "bands": bands,
        "saved_path": out_path,
    }


# ----------------------------- Phase-3 (Confirm) ----------------------------- #

def handle_confirm(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Minimal Phase-3 stub: compare buy lists from Phase-2 vs NWJ.
    If you have a richer version already, keep yours instead.
    """
    # Try to read the Phase-2 file path (if provided)
    p2_path = (payload.get("phase2_path") or payload.get("saved_phase2_path") or "").strip()
    p2_data: Dict[str, Any] = {}
    if p2_path and os.path.exists(p2_path):
        try:
            with open(p2_path, "r", encoding="utf-8") as f:
                p2_data = json.load(f)
        except Exception:
            p2_data = {}

    # NWJ may come as strings or arrays; accept both like in Phase-1
    try:
        mm, _   = _coerce_latest(payload.get("LATEST_MM"), allow_null_bonus=False)
        pb, _   = _coerce_latest(payload.get("LATEST_PB"), allow_null_bonus=False)
        iljp, _ = _coerce_latest(payload.get("LATEST_IL_JP"), allow_null_bonus=True)
        ilm1, _ = _coerce_latest(payload.get("LATEST_IL_M1"), allow_null_bonus=True)
        ilm2, _ = _coerce_latest(payload.get("LATEST_IL_M2"), allow_null_bonus=True)
    except Exception as e:
        return {"ok": False, "error": "ValueError", "detail": str(e)}

    # Very light confirmation stub: just echo what we received.
    result = {
        "ok": True,
        "phase": "phase3",
        "nwj": {"MM": mm, "PB": pb, "IL": {"JP": iljp, "M1": ilm1, "M2": ilm2}},
        "phase2_loaded": bool(p2_data),
    }
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out_path = f"/tmp/lotto_phase3_{ts}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    result["saved_path"] = out_path
    return result


# ----------------------------- Helpers ----------------------------- #

def recent_files(limit: int = 30) -> List[str]:
    """List recent Phase JSON files from /tmp for the UI “GET /recent”."""
    files = sorted(glob.glob("/tmp/lotto_phase*.json"))
    return files[-limit:]
