# app.py
from __future__ import annotations

import os
import json
import re
import traceback
from typing import Optional, Tuple, List, Dict

from flask import Flask, render_template, request

# ------------------------------------------------------------------------------
# Flask setup
# ------------------------------------------------------------------------------
app = Flask(__name__, template_folder="templates", static_folder="static")

# Right-justify filter for Jinja (simple & safe)
@app.template_filter("rjust")
def rjust_filter(s, width=0, fillchar=" "):
    s = "" if s is None else str(s)
    try:
        w = int(width)
    except Exception:
        w = 0
    f = str(fillchar)[0] if fillchar else " "
    return s.rjust(w, f)

# ------------------------------------------------------------------------------
# Import lottery_core safely (don’t crash the app if it’s missing/broken)
# ------------------------------------------------------------------------------
try:
    import lottery_core as core  # must expose run_phase_1_and_2() and confirm_phase_3()
    IMPORT_ERR = None
except Exception as e:
    core = None
    IMPORT_ERR = f"Failed to import lottery_core.py: {e}\n\n{traceback.format_exc()}"

# ------------------------------------------------------------------------------
# Paths
# ------------------------------------------------------------------------------
DATA_DIR = os.environ.get("DATA_DIR", "/tmp")
BUY_DIR = os.path.join(DATA_DIR, "buylists")
os.makedirs(BUY_DIR, exist_ok=True)

# ------------------------------------------------------------------------------
# Parsing helpers (extremely forgiving)
# ------------------------------------------------------------------------------

def _strip_brackets(s: str) -> str:
    s = s.strip()
    if s.startswith("(") and s.endswith(")"):
        s = s[1:-1]
    return s

def parse_mm_pb_pair(txt: str) -> Optional[Tuple[List[int], int]]:
    """
    Accepts:
      "[10,14,34,40,43],5"
      "([10,14,34,40,43],5)"
      "[10, 14, 34, 40, 43] , 5"
    Returns (list_of_5, bonus) or None
    """
    if not txt or not txt.strip():
        return None
    try:
        t = _strip_brackets(txt)
        # find the last comma (splits list and bonus)
        i = t.rfind(",")
        if i == -1:
            raise ValueError("No comma found between mains and bonus.")
        mains_part = t[:i].strip()
        bonus_part = t[i+1:].strip()

        # mains_part should contain [ ... ]
        m = re.search(r"\[(.*?)\]", mains_part)
        if not m:
            raise ValueError("Could not find [ ... ] mains list.")
        nums = [int(x) for x in re.split(r"[,\s]+", m.group(1).strip()) if x.strip()]

        bonus = int(re.sub(r"[^\d]", "", bonus_part))
        return (nums, bonus)
    except Exception:
        raise

def parse_il_list(txt: str) -> Optional[List[int]]:
    """
    Accepts:
      "[1,4,5,10,18,49]" or "1,4,5,10,18,49"
    Returns list or None
    """
    if not txt or not txt.strip():
        return None
    s = txt.strip()
    m = re.search(r"\[(.*?)\]", s)
    if m:
        s = m.group(1)
    nums = [int(x) for x in re.split(r"[,\s]+", s.strip()) if x.strip()]
    return nums

def parse_int(txt: str, default: int) -> int:
    try:
        return int(str(txt).strip())
    except Exception:
        return default

def is_checked(field_val: Optional[str]) -> bool:
    return bool(field_val)

# ------------------------------------------------------------------------------
# Utility
# ------------------------------------------------------------------------------

def list_recent_buy_files(n: int = 20) -> List[str]:
    if not os.path.isdir(BUY_DIR):
        return []
    files = []
    for name in os.listdir(BUY_DIR):
        path = os.path.join(BUY_DIR, name)
        if os.path.isfile(path) and name.startswith("buy_session_") and name.endswith(".json"):
            files.append(path)
    files.sort(reverse=True)
    return files[:n]

def render_safe(res: Optional[dict] = None, error: Optional[str] = None):
    return render_template(
        "report.html",
        res=res,
        error=error or IMPORT_ERR,
        data_dir=DATA_DIR,
        recent=list_recent_buy_files(),
    )

# ------------------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------------------

@app.get("/")
def index():
    return render_safe()

@app.post("/run_phase12")
def run_phase12():
    # If core failed to import, don’t crash: show the error in the page.
    if not core:
        return render_safe(error=IMPORT_ERR)

    try:
        # Read form fields (all optional)
        latest_mm_txt = request.form.get("LATEST_MM", "")
        latest_pb_txt = request.form.get("LATEST_PB", "")
        latest_il_jp_txt = request.form.get("LATEST_IL_JP", "")
        latest_il_m1_txt = request.form.get("LATEST_IL_M1", "")
        latest_il_m2_txt = request.form.get("LATEST_IL_M2", "")
        runs_txt = request.form.get("runs", "100")
        quiet_flag = is_checked(request.form.get("quiet"))

        # Parse
        latest_mm = parse_mm_pb_pair(latest_mm_txt) if latest_mm_txt.strip() else None
        latest_pb = parse_mm_pb_pair(latest_pb_txt) if latest_pb_txt.strip() else None
        latest_il_jp = parse_il_list(latest_il_jp_txt) if latest_il_jp_txt.strip() else None
        latest_il_m1 = parse_il_list(latest_il_m1_txt) if latest_il_m1_txt.strip() else None
        latest_il_m2 = parse_il_list(latest_il_m2_txt) if latest_il_m2_txt.strip() else None
        runs = parse_int(runs_txt, 100)

        # Build config for lottery_core
        config = {
            "LATEST_MM": latest_mm,
            "LATEST_PB": latest_pb,
            "LATEST_IL_JP": latest_il_jp,
            "LATEST_IL_M1": latest_il_m1,
            "LATEST_IL_M2": latest_il_m2,
            "runs": runs,
            "quiet": quiet_flag,
            "DATA_DIR": DATA_DIR,
        }

        # Call your engine
        result = core.run_phase_1_and_2(config)

        # Ensure JSON-serializable (debug help)
        json.dumps(result, default=str)

        return render_safe(res=result)
    except Exception as e:
        err = f"Phase 1/2 crashed: {e}\n\n{traceback.format_exc()}"
        return render_safe(error=err)

@app.post("/confirm_phase3")
def confirm_phase3():
    if not core:
        return render_safe(error=IMPORT_ERR)

    try:
        saved_file_sel = request.form.get("saved_file", "").strip()
        saved_file_txt = request.form.get("saved_file", "").strip()
        # Accept either the select’s value or the typed path
        saved_file = saved_file_sel or saved_file_txt

        # NWJ fields
        nwj_mm_txt = request.form.get("NWJ_MM", "")
        nwj_pb_txt = request.form.get("NWJ_PB", "")
        nwj_il_jp_txt = request.form.get("NWJ_IL_JP", "")
        nwj_il_m1_txt = request.form.get("NWJ_IL_M1", "")
        nwj_il_m2_txt = request.form.get("NWJ_IL_M2", "")
        recall = is_checked(request.form.get("recall_headings"))

        # Parse (MM/PB expect mains+bonus; IL expect 6 mains only)
        nwj = {
            "NWJ_MM": parse_mm_pb_pair(nwj_mm_txt) if nwj_mm_txt.strip() else None,
            "NWJ_PB": parse_mm_pb_pair(nwj_pb_txt) if nwj_pb_txt.strip() else None,
            "NWJ_IL_JP": (parse_il_list(nwj_il_jp_txt), None) if nwj_il_jp_txt.strip() else None,
            "NWJ_IL_M1": (parse_il_list(nwj_il_m1_txt), None) if nwj_il_m1_txt.strip() else None,
            "NWJ_IL_M2": (parse_il_list(nwj_il_m2_txt), None) if nwj_il_m2_txt.strip() else None,
        }

        result = core.confirm_phase_3(saved_file=saved_file, nwj=nwj, recall_headings=recall)
        json.dumps(result, default=str)
        return render_safe(res=result)
    except Exception as e:
        err = f"Phase 3 crashed: {e}\n\n{traceback.format_exc()}"
        return render_safe(error=err)

# ------------------------------------------------------------------------------
# Health
# ------------------------------------------------------------------------------
@app.get("/health")
def health():
    return {"ok": True, "data_dir": DATA_DIR, "import_error": IMPORT_ERR is None}

# ------------------------------------------------------------------------------
# App entry (Render/Gunicorn uses 'app')
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)
