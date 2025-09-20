# lottery_core.py — safe boot version (no heavy math yet)
from __future__ import annotations
import os, json, datetime as dt
from typing import Dict, List, Tuple, Optional

# Where we save files on Render
DATA_DIR = os.environ.get("DATA_DIR", "/data")
BUY_DIR = os.path.join(DATA_DIR, "buylists")
os.makedirs(BUY_DIR, exist_ok=True)

def _now_stamp() -> str:
    return dt.datetime.utcnow().strftime("%Y%m%d_%H%M%S")

def _parse_latest(s: str, expect_bonus: bool) -> Optional[Tuple[List[int], Optional[int]]]:
    """
    Accepts "10,14,34,40,43;5" (with ;bonus) or "10,14,34,40,43" (no bonus).
    Returns (mains, bonus|None) or None if empty.
    """
    if not s or not s.strip():
        return None
    s = s.strip().strip("[](){} ").replace(" ", "")
    if ";" in s:
        mains_str, bonus_str = s.split(";", 1)
        mains = [int(x) for x in mains_str.split(",") if x]
        bonus = int(bonus_str) if expect_bonus else None
        return (mains, bonus)
    else:
        mains = [int(x) for x in s.split(",") if x]
        bonus = None
        if expect_bonus:
            # allow trailing ",b" style too
            if len(mains) >= 6:
                *m, b = mains
                return (m, int(b))
        return (mains, bonus)

def _blank_phase1_block():
    return {
        "batch": [],        # list of strings to print (50 rows normally)
        "hits_lines": [],   # list of strings like "row #07: 3-ball"
    }

def _blank_phase2_stats():
    return {
        "mm": {"totals": {}, "top_positions": []},
        "pb": {"totals": {}, "top_positions": []},
        "il": {"totals": {}, "top_positions": []},
    }

def _fmt_mm_pb_row(mains: List[int], bonus: Optional[int]) -> str:
    mains_txt = " ".join(f"{n:02d}" for n in mains)
    btxt = f"{bonus:02d}" if bonus is not None else "--"
    return f"{mains_txt}   {btxt}"

def _fmt_il_row(mains: List[int]) -> str:
    return " ".join(f"{n:02d}" for n in mains)

def run_phase_1_and_2(config: Dict) -> Dict:
    """
    Returns a printable structure the UI expects.
    This SAFE version:
      - echoes your LATEST_* inputs as a fake 'batch' so pages render
      - writes a tiny buy list JSON to /data/buylists/
    """
    # Parse LATEST_* from form (strings)
    latest_mm = _parse_latest(config.get("LATEST_MM",""), expect_bonus=True)
    latest_pb = _parse_latest(config.get("LATEST_PB",""), expect_bonus=True)
    latest_il_jp = _parse_latest(config.get("LATEST_IL_JP",""), expect_bonus=False)
    latest_il_m1 = _parse_latest(config.get("LATEST_IL_M1",""), expect_bonus=False)
    latest_il_m2 = _parse_latest(config.get("LATEST_IL_M2",""), expect_bonus=False)

    # Phase 1 “batches” (dummy: just a few rows so page renders)
    mm_block = _blank_phase1_block()
    pb_block = _blank_phase1_block()
    il_block = _blank_phase1_block()

    if latest_mm:
        mm_block["batch"] = [
            f"01. {_fmt_mm_pb_row(latest_mm[0], latest_mm[1])}",
            "02. 01 02 03 04 05   01",
            "03. 06 07 08 09 10   02",
        ]
    if latest_pb:
        pb_block["batch"] = [
            f"01. {_fmt_mm_pb_row(latest_pb[0], latest_pb[1])}",
            "02. 11 12 13 14 15   03",
            "03. 21 22 23 24 25   04",
        ]
    if latest_il_jp:
        il_block["batch"] = [
            f"01. {_fmt_il_row(latest_il_jp[0])}",
            "02. 01 02 03 04 05 06",
            "03. 07 08 09 10 11 12",
        ]
        # Fake hits so the section shows something
        il_block["hits_lines"] = ["  row #01: 3-ball"]

    # Phase 2 stats (dummy)
    phase2 = _blank_phase2_stats()
    phase2["il"]["totals"] = {"3": 1, "4": 0, "5": 0, "6": 0}
    phase2["il"]["top_positions"] = [(1, 1), (2, 0), (3, 0)]

    # “Buy lists” — fabricate a few rows, save them, and return the path
    mm_buy = [([1,2,3,4,5], 1), ([6,7,8,9,10], 2)]
    pb_buy = [([1,3,5,7,9], 2), ([2,4,6,8,10], 3)]
    il_buy = [[1,2,3,4,5,6], [7,8,9,10,11,12], [3,13,23,33,43,49]]

    payload = {
        "timestamp": _now_stamp(),
        "LATEST_MM": latest_mm,
        "LATEST_PB": latest_pb,
        "LATEST_IL_JP": latest_il_jp,
        "LATEST_IL_M1": latest_il_m1,
        "LATEST_IL_M2": latest_il_m2,
        "MM": [[m,b] for (m,b) in mm_buy],
        "PB": [[m,b] for (m,b) in pb_buy],
        "IL": il_buy,
    }
    saved_path = os.path.join(BUY_DIR, f"buy_session_{_now_stamp()}.json")
    try:
        with open(saved_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
    except Exception as e:
        saved_path = f"<save error: {e}>"

    return {
        "phase1": {"mm": mm_block, "pb": pb_block, "il": il_block},
        "phase2": phase2,
        "buy_lists": {"mm": mm_buy, "pb": pb_buy, "il": il_buy},
        "saved_path": saved_path,
    }

def confirm_phase_3(saved_file: str, nwj: Dict, recall_phase12_from_file: bool = True) -> Dict:
    """
    Loads the saved buy list JSON and compares against NWJ_* you provide.
    SAFE version: just loads and echoes. No scoring logic yet.
    """
    full = saved_file
    if not os.path.isabs(full):
        full = os.path.join(BUY_DIR, os.path.basename(saved_file))
    if not os.path.exists(full):
        return {"error": f"Saved buy list not found: {full}"}
    with open(full, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Just echo back what we got
    out = {
        "loaded_file": full,
        "tickets_counts": {
            "MM": len(data.get("MM", [])),
            "PB": len(data.get("PB", [])),
            "IL": len(data.get("IL", [])),
        },
        "nwj": nwj,
        "recall_phase12": None,
        "details": {
            "message": "SAFE confirm: scoring disabled in this boot version."
        }
    }
    if recall_phase12_from_file:
        out["recall_phase12"] = {
            "LATEST_MM": data.get("LATEST_MM"),
            "LATEST_PB": data.get("LATEST_PB"),
            "LATEST_IL_JP": data.get("LATEST_IL_JP"),
            "LATEST_IL_M1": data.get("LATEST_IL_M1"),
            "LATEST_IL_M2": data.get("LATEST_IL_M2"),
        }
    return out
