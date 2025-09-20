# app.py
from __future__ import annotations

import os
import glob
import json
import ast
import sys
import traceback
from typing import Any, Dict, List, Optional, Tuple
from flask import Flask, render_template, request, jsonify, Response

# ------------------------------------------------------------------------------
# App setup
# ------------------------------------------------------------------------------
app = Flask(__name__, template_folder="templates", static_folder="static")
app.config.update(
    TEMPLATES_AUTO_RELOAD=True,
    PROPAGATE_EXCEPTIONS=True,
)

DATA_DIR = os.getenv("DATA_DIR", "/tmp")
BUY_DIR = os.path.join(DATA_DIR, "buylists")
os.makedirs(BUY_DIR, exist_ok=True)

# ------------------------------------------------------------------------------
# Global error handler — ALWAYS shows the real traceback
# ------------------------------------------------------------------------------
@app.errorhandler(Exception)
def handle_any_error(e):
    tb = traceback.format_exc()
    # Log to server logs
    print("UNCAUGHT ERROR:", e, file=sys.stderr)
    print(tb, file=sys.stderr)

    # JSON for API routes
    if request.path in ("/run_json", "/confirm_json", "/recent", "/health"):
        return jsonify({
            "ok": False,
            "where": request.path,
            "error": f"{e.__class__.__name__}: {e}",
            "trace": tb,
        }), 500

    # Plain text for everything else (avoids Flask default HTML)
    return Response(f"ERROR at {request.path}:\n\n{e.__class__.__name__}: {e}\n\n{tb}",
                    status=500, mimetype="text/plain")

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
    s = "" if value is None else str(value)
    return s.rjust(2, "0")

# ------------------------------------------------------------------------------
# Import lottery_core safely
# ------------------------------------------------------------------------------
try:
    import lottery_core as core  # must expose run_phase_1_and_2(config) and confirm_phase_3(saved, nwj)
except Exception as e:
    core = None  # type: ignore
    IMPORT_ERR = f"Failed to import lottery_core.py: {e}\n\n{traceback.format_exc()}"
else:
    IMPORT_ERR = None

# ------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------
def parse_literal(s: str):
    """Parse inputs like:
       - "([10,14,34,40,43], 5)"
       - "[1,4,5,10,18,49]"
       - "[10,14,34,40,43], 5" (coerced to tuple)
    """
    if s is None:
        return None
    s = s.strip()
    if not s:
        return None
    try:
        return ast.literal_eval(s)
    except Exception:
        if "]" in s and s.count("]") == 1 and "," in s.split("]")[-1]:
            left, right = s.split("]", 1)
            left += "]"
            mains = ast.literal_eval(left)
            bonus = int(right.strip().lstrip(",").strip())
            return (mains, bonus)
        raise

def list_recent_buyfiles(limit: int = 10) -> List[str]:
    paths = sorted(glob.glob(os.path.join(BUY_DIR, "buy_session_*.json")), reverse=True)
    return [os.path.basename(p) for p in paths[:limit]]

def _render_safe(res: Optional[dict], err_text: Optional[str]) -> Response:
    """Render report.html; if template fails, show plain-text traceback."""
    try:
        return render_template(
            "report.html",
            res=res,
            error=err_text,
            import_err=IMPORT_ERR,
            recent=list_recent_buyfiles(),
            buy_dir=BUY_DIR,
        )
    except Exception:
        tb = traceback.format_exc()
        txt = "Template rendering error.\n\nTRACEBACK:\n" + tb + "\n\nRES:\n" + repr(res) + "\n\nORIGINAL ERROR:\n" + str(err_text)
        return Response(txt, status=500, mimetype="text/plain")

# ------------------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------------------
@app.get("/")
def home():
    return _render_safe(res=None, err_text=None)

@app.get("/health")
def health():
    return jsonify({"ok": True})

@app.get("/recent")
def recent():
    return jsonify({"ok": True, "files": list_recent_buyfiles(), "dir": BUY_DIR})

# --------------------------- JSON DEBUG ROUTES ---------------------------
@app.post("/run_json")
def run_phase12_json():
    if IMPORT_ERR:
        return jsonify({"ok": False, "where": "import", "error": IMPORT_ERR}), 500
    if core is None:
        return jsonify({"ok": False, "where": "import", "error": "core is None"}), 500

    f = request.form
    cfg = {
        "LATEST_MM": parse_literal(f.get("LATEST_MM", "")),
        "LATEST_PB": parse_literal(f.get("LATEST_PB", "")),
        "LATEST_IL_JP": parse_literal(f.get("LATEST_IL_JP", "")),
        "LATEST_IL_M1": parse_literal(f.get("LATEST_IL_M1", "")),
        "LATEST_IL_M2": parse_literal(f.get("LATEST_IL_M2", "")),
        "runs": int(f.get("runs", "100") or "100"),
        "quiet": (f.get("quiet", "on") == "on"),
        "DATA_DIR": DATA_DIR,
        "BUY_DIR": BUY_DIR,
    }
    res = core.run_phase_1_and_2(cfg)
    return jsonify({"ok": True, "res": res})

@app.post("/confirm_json")
def confirm_phase3_json():
    if IMPORT_ERR:
        return jsonify({"ok": False, "where": "import", "error": IMPORT_ERR}), 500
    if core is None:
        return jsonify({"ok": False, "where": "import", "error": "core is None"}), 500

    f = request.form
    saved_input = (f.get("saved_path", "") or "").strip()
    saved_path = (
        os.path.join(BUY_DIR, os.path.basename(saved_input))
        if saved_input and not os.path.isabs(saved_input)
        else saved_input
    )
    nwj = {
        "NWJ_MM": parse_literal(f.get("NWJ_MM", "")),
        "NWJ_PB": parse_literal(f.get("NWJ_PB", "")),
        "NWJ_IL_JP": parse_literal(f.get("NWJ_IL_JP", "")),
        "NWJ_IL_M1": parse_literal(f.get("NWJ_IL_M1", "")),
        "NWJ_IL_M2": parse_literal(f.get("NWJ_IL_M2", "")),
        "also_recall": (f.get("also_recall", "on") == "on"),
    }
    res = core.confirm_phase_3(saved_path, nwj)
    return jsonify({"ok": True, "res": res})

# --------------------------- FORM BUTTON ROUTES --------------------------
@app.post("/run")
def run_phase12():
    j = run_phase12_json()
    if j.status_code != 200:
        payload = j.get_json(silent=True) or {}
        return _render_safe(res=None, err_text=json.dumps(payload, indent=2))
    payload = j.get_json(silent=True) or {}
    return _render_safe(res=payload.get("res"), err_text=None)

@app.post("/confirm")
def confirm_phase3():
    j = confirm_phase3_json()
    if j.status_code != 200:
        payload = j.get_json(silent=True) or {}
        return _render_safe(res=None, err_text=json.dumps(payload, indent=2))
    payload = j.get_json(silent=True) or {}
    return _render_safe(res=payload.get("res"), err_text=None)

# ------------------------------------------------------------------------------
# Local debug
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=True)
