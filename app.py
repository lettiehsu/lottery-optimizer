# app.py
from __future__ import annotations
import os, glob, json, traceback, ast
from datetime import datetime
from typing import Any, Dict, Tuple, List, Optional

from flask import Flask, render_template, request, jsonify

# ------------------------------------------------------------------------------
# App setup
# ------------------------------------------------------------------------------
app = Flask(__name__, template_folder="templates", static_folder="static")

# Jinja filters
@app.template_filter("rjust")
def rjust_filter(value, width=0, fillchar=" "):
    s = "" if value is None else str(value)
    try:
        w = int(width)
    except Exception:
        w = 0
    f = (str(fillchar) or " ")[0]
    return s.rjust(w, f)

@app.template_filter("pad2")
def pad2_filter(value):
    return ("" if value is None else str(value)).rjust(2, "0")

# ------------------------------------------------------------------------------
# Import lottery_core safely
# ------------------------------------------------------------------------------
try:
    import lottery_core as core  # your heavy logic lives here
    IMPORT_ERR = None
except Exception as e:
    core = None
    IMPORT_ERR = f"Failed to import lottery_core.py: {e}\n\n{traceback.format_exc()}"

# ------------------------------------------------------------------------------
# Directories
# ------------------------------------------------------------------------------
DATA_DIR = os.getenv("DATA_DIR", "/tmp")
BUY_DIR = os.path.join(DATA_DIR, "buylists")
os.makedirs(BUY_DIR, exist_ok=True)

# ------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------
def _clean(s: str) -> str:
    return (s or "").strip()

def parse_list_or_pair(text: str) -> Any:
    """
    Accepts forms like:
      [1,2,3]                -> list
      ([10,14,34,40,43], 5)  -> tuple(list, int)
      "[10,14,34,40,43],5"   -> also works
    Returns Python object or raises ValueError.
    """
    t = _clean(text)
    if not t:
        raise ValueError("empty")

    # Allow users to paste without outer tuple for MM/PB (we add parens)
    if t.startswith("[") and t.endswith("]") and "," in t:
        # plain list
        return ast.literal_eval(t)

    # If they paste like: [..],5 (missing outer parens), fix it
    if t.count("[") == 1 and t.count("]") == 1 and t.find("]") < len(t) - 1 and "," in t:
        t = f"({t})"

    # Now try safe eval
    try:
        return ast.literal_eval(t)
    except Exception as e:
        raise ValueError(f"could not parse '{text}': {e}")

def ok_json(payload: dict) -> Any:
    return jsonify({"ok": True, **payload})

def err_json(msg: str) -> Any:
    return jsonify({"ok": False, "error": msg})

def _human_err(e: Exception) -> str:
    return f"{e.__class__.__name__}: {e}"

# ------------------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------------------
@app.get("/")
def home():
    # The page can render even if lottery_core failed to import;
    # the form will show a banner with the import error.
    return render_template("report.html", import_err=IMPORT_ERR)

@app.get("/recent")
def recent():
    files = sorted(glob.glob(os.path.join(BUY_DIR, "buy_session_*.json")), reverse=True)
    names = [os.path.relpath(p, DATA_DIR) for p in files][:10]
    return ok_json({"files": names})

@app.post("/run")
def run_phase12():
    if core is None:
        return err_json("Core not available. Check lottery_core.py import error on the page.")

    try:
        # Parse latest jackpots
        latest_mm = parse_list_or_pair(request.form.get("LATEST_MM", ""))
        latest_pb = parse_list_or_pair(request.form.get("LATEST_PB", ""))
        latest_il_jp = parse_list_or_pair(request.form.get("LATEST_IL_JP", ""))
        latest_il_m1 = parse_list_or_pair(request.form.get("LATEST_IL_M1", ""))
        latest_il_m2 = parse_list_or_pair(request.form.get("LATEST_IL_M2", ""))

        # Runs / quiet flag
        try:
            runs = int(request.form.get("runs", "100").strip() or "100")
        except Exception:
            runs = 100
        quiet = request.form.get("quiet", "off") == "on"

        # Build config expected by your core
        config = {
            "LATEST_MM": latest_mm,
            "LATEST_PB": latest_pb,
            "LATEST_IL_JP": latest_il_jp,
            "LATEST_IL_M1": latest_il_m1,
            "LATEST_IL_M2": latest_il_m2,
            "runs": runs,
            "quiet": quiet,
            "SAVE_DIR": BUY_DIR,
        }

        res = core.run_phase_1_and_2(config)
        # To help the UI show the saved file path consistently, normalize to DATA_DIR-relative
        saved_path = res.get("saved_path")
        if saved_path and saved_path.startswith(DATA_DIR):
            res["saved_path_rel"] = os.path.relpath(saved_path, DATA_DIR)
        else:
            res["saved_path_rel"] = saved_path

        return ok_json({"result": res})

    except Exception as e:
        return err_json(f"Phase 1 & 2 error — {_human_err(e)}\n{traceback.format_exc()}")

@app.post("/confirm")
def confirm_phase3():
    if core is None:
        return err_json("Core not available. Check lottery_core.py import error on the page.")

    try:
        # file path: allow DATA_DIR-relative or absolute
        rel = _clean(request.form.get("saved_path", ""))
        if not rel:
            raise ValueError("Saved buy list path is required.")
        # If they pasted only the filename, treat it relative to BUY_DIR
        if rel.startswith("/"):
            full_path = rel
        else:
            # Make rel relative to DATA_DIR
            full_path = os.path.join(DATA_DIR, rel)

        # NWJ fields (any can be empty)
        nwj_mm = _clean(request.form.get("NWJ_MM", ""))
        nwj_pb = _clean(request.form.get("NWJ_PB", ""))
        nwj_il_jp = _clean(request.form.get("NWJ_IL_JP", ""))
        nwj_il_m1 = _clean(request.form.get("NWJ_IL_M1", ""))
        nwj_il_m2 = _clean(request.form.get("NWJ_IL_M2", ""))

        def _maybe_parse(text):
            return parse_list_or_pair(text) if _clean(text) else None

        nwj = {
            "NWJ_MM": _maybe_parse(nwj_mm),   # expect (list, bonus) tuple
            "NWJ_PB": _maybe_parse(nwj_pb),   # expect (list, bonus) tuple
            "NWJ_IL_JP": _maybe_parse(nwj_il_jp),  # expect list
            "NWJ_IL_M1": _maybe_parse(nwj_il_m1),  # expect list
            "NWJ_IL_M2": _maybe_parse(nwj_il_m2),  # expect list
        }

        recall = request.form.get("recall_headings", "off") == "on"

        res = core.confirm_phase_3(full_path, nwj, recall_phase12=recall)

        return ok_json({"result": res})

    except Exception as e:
        return err_json(f"Phase 3 error — {_human_err(e)}\n{traceback.format_exc()}")

# ------------------------------------------------------------------------------
# Run locally
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    # For local debugging only
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=True)
