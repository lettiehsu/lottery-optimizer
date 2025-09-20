# app.py
from __future__ import annotations

import os
import glob
import json
import ast
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
)

# ------------------------------------------------------------------------------
# App setup
# ------------------------------------------------------------------------------
app = Flask(__name__, template_folder="templates", static_folder="static")

# Writable data dir (Render Free/Starter: use /tmp)
DATA_DIR = os.getenv("DATA_DIR", "/tmp")
BUY_DIR = os.path.join(DATA_DIR, "buylists")
os.makedirs(BUY_DIR, exist_ok=True)

# ------------------------------------------------------------------------------
# Jinja filters used by templates
# ------------------------------------------------------------------------------
@app.template_filter("rjust")
def rjust_filter(value, width: int = 0, fillchar: str = " "):
    s = "" if value is None else str(value)
    try:
        w = int(width)
    except Exception:
        w = 0
    f = (str(fillchar) or " ")[0]
    return s.rjust(w, f)

@app.template_filter("pad2")
def pad2_filter(value):
    # zero-pad to width 2 (e.g., loop.index | pad2 -> "01")
    s = "" if value is None else str(value)
    return s.rjust(2, "0")

# ------------------------------------------------------------------------------
# Import lottery_core safely (do not crash the app if it's missing)
# ------------------------------------------------------------------------------
try:
    import lottery_core as core  # must define run_phase_1_and_2(...) and confirm_phase_3(...)
except Exception as e:
    core = None  # type: ignore
    IMPORT_ERR = f"Failed to import lottery_core.py: {e}\n\n{traceback.format_exc()}"
else:
    IMPORT_ERR = None

# ------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------
def parse_literal(s: str):
    """
    Accepts:
      - "([10,14,34,40,43], 5)"
      - "[1,4,5,10,18,49]"
      - "[10,14,34,40,43], 5"   (we coerce to tuple)
      - "([10,14,34,40,43],5)"  (spaces optional)
    Returns Python object or None for empty.
    """
    if s is None:
        return None
    s = s.strip()
    if not s:
        return None
    try:
        return ast.literal_eval(s)
    except Exception:
        # Try to coerce "[...], bonus" into "([...], bonus)"
        if "]" in s and s.count("]") == 1 and "," in s.split("]")[-1]:
            left, right = s.split("]", 1)
            left += "]"
            try:
                mains = ast.literal_eval(left)
                bonus = int(right.strip().lstrip(",").strip())
                return (mains, bonus)
            except Exception:
                pass
        # Give up → raise (caller catches and shows JSON trace)
        raise

def list_recent_buyfiles(limit: int = 10) -> List[str]:
    # Glob all buy_session_*.json in BUY_DIR; return newest first (just basenames to show)
    paths = sorted(glob.glob(os.path.join(BUY_DIR, "buy_session_*.json")), reverse=True)
    return [os.path.basename(p) for p in paths[:limit]]

# ------------------------------------------------------------------------------
# Error handler (so you can see the real traceback while we debug)
# ------------------------------------------------------------------------------
@app.errorhandler(Exception)
def handle_any_error(e):
    tb = traceback.format_exc()
    # For programmatic endpoints return JSON; for others render a simple text page
    if request.path in ("/run", "/confirm", "/recent"):
        return jsonify({"ok": False, "error": f"{e.__class__.__name__}: {e}", "trace": tb}), 500
    return f"Template rendering error.\n\nTRACEBACK:\n{tb}\n\nRES:\nNone\n\nORIGINAL ERROR:\n{e}", 500

# ------------------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------------------
@app.get("/")
def home():
    # Render empty report page with the form; show import error if any
    return render_template(
        "report.html",
        res=None,
        error=None,
        import_err=IMPORT_ERR,
        recent=list_recent_buyfiles(),
        buy_dir=BUY_DIR,
    )

@app.get("/health")
def health():
    return "OK", 200

@app.get("/recent")
def recent():
    return jsonify({"ok": True, "files": list_recent_buyfiles()})

# --------------------------- RUN PHASE 1 & 2 ----------------------------
@app.post("/run")
def run_phase12():
    if IMPORT_ERR:
        return jsonify({"ok": False, "where": "import", "error": IMPORT_ERR}), 500
    if core is None:
        return jsonify({"ok": False, "where": "import", "error": "core is None"}), 500

    try:
        form = request.form
        cfg = {
            "LATEST_MM": parse_literal(form.get("LATEST_MM", "")),
            "LATEST_PB": parse_literal(form.get("LATEST_PB", "")),
            "LATEST_IL_JP": parse_literal(form.get("LATEST_IL_JP", "")),
            "LATEST_IL_M1": parse_literal(form.get("LATEST_IL_M1", "")),
            "LATEST_IL_M2": parse_literal(form.get("LATEST_IL_M2", "")),
            "runs": int(form.get("runs", "100") or "100"),
            "quiet": (form.get("quiet", "on") == "on"),
            # Allow core to know where to save
            "DATA_DIR": DATA_DIR,
            "BUY_DIR": BUY_DIR,
        }

        res = core.run_phase_1_and_2(cfg)  # must return a dict
        # Render HTML report
        return render_template(
            "report.html",
            res=res,
            error=None,
            import_err=None,
            recent=list_recent_buyfiles(),
            buy_dir=BUY_DIR,
        )
    except Exception as e:
        return jsonify({
            "ok": False,
            "where": "run_phase12",
            "error": f"{e.__class__.__name__}: {e}",
            "trace": traceback.format_exc(),
        }), 500

# ------------------------------ CONFIRM PHASE 3 ---------------------------
@app.post("/confirm")
def confirm_phase3():
    if IMPORT_ERR:
        return jsonify({"ok": False, "where": "import", "error": IMPORT_ERR}), 500
    if core is None:
        return jsonify({"ok": False, "where": "import", "error": "core is None"}), 500

    try:
        form = request.form
        saved_path_in = (form.get("saved_path", "") or "").strip()

        # Allow user to type just filename; expand to full path in BUY_DIR
        if saved_path_in and not os.path.isabs(saved_path_in):
            saved_path = os.path.join(BUY_DIR, os.path.basename(saved_path_in))
        else:
            saved_path = saved_path_in

        nwj = {
            "NWJ_MM": parse_literal(form.get("NWJ_MM", "")),
            "NWJ_PB": parse_literal(form.get("NWJ_PB", "")),
            "NWJ_IL_JP": parse_literal(form.get("NWJ_IL_JP", "")),
            "NWJ_IL_M1": parse_literal(form.get("NWJ_IL_M1", "")),
            "NWJ_IL_M2": parse_literal(form.get("NWJ_IL_M2", "")),
            "also_recall": (form.get("also_recall", "on") == "on"),
        }

        res = core.confirm_phase_3(saved_path, nwj)  # must return a dict

        return render_template(
            "report.html",
            res=res,
            error=None,
            import_err=None,
            recent=list_recent_buyfiles(),
            buy_dir=BUY_DIR,
        )
    except Exception as e:
        return jsonify({
            "ok": False,
            "where": "confirm_phase3",
            "error": f"{e.__class__.__name__}: {e}",
            "trace": traceback.format_exc(),
        }), 500

# ------------------------------------------------------------------------------
# Local run
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    # For local testing only
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=True)
