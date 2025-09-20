# app.py
from __future__ import annotations
import os, glob, json, traceback, ast
from datetime import datetime
from typing import Any, Dict, Tuple, List, Optional
from flask import Flask, render_template, request, jsonify

# ───────────────────────────────────────────────────────────────────────────────
# App setup
# ───────────────────────────────────────────────────────────────────────────────
app = Flask(__name__, template_folder="templates", static_folder="static")

# Jinja filters used by report.html
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

# Global error handler (pretty JSON for API routes)
@app.errorhandler(Exception)
def handle_any_error(e):
    tb = traceback.format_exc()
    # Log to Render logs
    print("UNCAUGHT ERROR:", e)
    print(tb)
    if request.path in ("/run", "/confirm", "/recent"):
        return jsonify({"ok": False, "error": f"{e.__class__.__name__}: {e}\n{tb}"}), 500
    return f"Template rendering error.\n\nTRACEBACK:\n{tb}\n\nRES:\nNone\n\nORIGINAL ERROR:\nNone", 500

# ───────────────────────────────────────────────────────────────────────────────
# Import your core logic safely
# ───────────────────────────────────────────────────────────────────────────────
try:
    import lottery_core as core
    CORE_OK = True
    IMPORT_ERR = None
except Exception as e:
    CORE_OK = False
    IMPORT_ERR = f"Failed to import lottery_core.py: {e}\n\n{traceback.format_exc()}"

# Minimal fallbacks so the UI still loads if core is missing
def _fallback_run_phase_1_and_2(cfg: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "phase1": {"mm": {"batch": [], "hits_lines": []},
                   "pb": {"batch": [], "hits_lines": []},
                   "il": {"batch": [], "hits_lines": []}},
        "phase2": {"mm": {"totals": {}, "top_positions": []},
                   "pb": {"totals": {}, "top_positions": []},
                   "il": {"totals": {}, "top_positions": []}},
        "buy_lists": {"mm": [], "pb": [], "il": []},
        "saved_path": os.path.join(_data_dir(), "buylists", f"buy_session_{datetime.now():%Y%m%d_%H%M%S}.json"),
        "_note": "Core not loaded — showing empty stub result."
    }

def _fallback_confirm(saved_file: str, nwj: Dict[str, Any], recall_headings: bool) -> Dict[str, Any]:
    return {
        "phase3": {"mm": {"totals": {}, "rows": []},
                   "pb": {"totals": {}, "rows": []},
                   "il": {"totals": {}, "rows": []}},
        "used_file": saved_file,
        "_note": "Core not loaded — showing empty stub confirmation."
    }

# Choose the actual entrypoints (core or fallback)
RUN_FN = core.run_phase_1_and_2 if CORE_OK else _fallback_run_phase_1_and_2
CONFIRM_FN = core.confirm_phase_3 if CORE_OK else _fallback_confirm

# ───────────────────────────────────────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────────────────────────────────────
def _data_dir() -> str:
    # Writable dir on Render (defaults to /tmp)
    root = os.environ.get("DATA_DIR", "/tmp")
    os.makedirs(root, exist_ok=True)
    os.makedirs(os.path.join(root, "buylists"), exist_ok=True)
    return root

def _recent_buylists(limit: int = 12) -> List[str]:
    base = os.path.join(_data_dir(), "buylists", "buy_session_*.json")
    files = sorted(glob.glob(base), reverse=True)
    return files[:limit]

def _parse_list(text: str) -> List[int]:
    """
    Accepts formats like:
      "[1,2,3,4,5]"   "1,2,3,4,5"   "(1,2,3,4,5)"  with spaces ok.
    Returns List[int].
    """
    if not text:
        return []
    s = text.strip()
    if not s:
        return []
    # Remove outer parentheses if present
    if s[0] in "([{" and s[-1] in ")]}":
        s = s[1:-1]
    if not s:
        return []
    parts = [p.strip() for p in s.split(",") if p.strip() != ""]
    return [int(p) for p in parts]

def _parse_tuple_mm_pb(text: str) -> Optional[Tuple[List[int], int]]:
    """
    Accepts:
      "[10,14,34,40,43],5"
      "([10,14,34,40,43], 5)"
      "10,14,34,40,43 | 5"
    Returns ([mains], bonus) or None if empty.
    """
    if not text or not text.strip():
        return None
    s = text.strip()
    # Try python literal first: ([...], 5)
    try:
        val = ast.literal_eval(s)
        if isinstance(val, tuple) and len(val) == 2:
            mains, bonus = val
            return (list(mains), int(bonus))
    except Exception:
        pass
    # Try split on '|' or last comma section
    if "|" in s:
        left, right = s.split("|", 1)
        return (_parse_list(left), int(right.strip()))
    # Last comma portion considered bonus
    if s.count("]") >= 1 and s.rfind("]") != -1:
        r = s.rfind("]")
        left, right = s[:r+1], s[r+1:]
        return (_parse_list(left), int(right.replace(",", " ").strip()))
    # Fallback: split by comma and take last as bonus
    parts = [p.strip() for p in s.split(",") if p.strip()]
    if len(parts) >= 2:
        bonus = int(parts[-1])
        mains = [int(x) for x in parts[:-1]]
        return (mains, bonus)
    raise ValueError(f"Could not parse MM/PB tuple from: {text!r}")

def _parse_list_only(text: str) -> Optional[List[int]]:
    """
    Illinois Lotto style (no bonus):
      "[1,4,5,10,18,49]"
    Returns list or None if empty.
    """
    if not text or not text.strip():
        return None
    return _parse_list(text)

def _cfg_from_form(form: Dict[str, str]) -> Dict[str, Any]:
    return {
        "LATEST_MM": _parse_tuple_mm_pb(form.get("LATEST_MM", "")),
        "LATEST_PB": _parse_tuple_mm_pb(form.get("LATEST_PB", "")),
        "LATEST_IL_JP": _parse_list_only(form.get("LATEST_IL_JP", "")),
        "LATEST_IL_M1": _parse_list_only(form.get("LATEST_IL_M1", "")),
        "LATEST_IL_M2": _parse_list_only(form.get("LATEST_IL_M2", "")),
        "runs": int(form.get("runs") or "100"),
        "quiet": ("quiet" in form),
        # Optional CSV/feed uploads are handled inside lottery_core (if you add that support)
    }

def _nwj_from_form(form: Dict[str, str]) -> Dict[str, Any]:
    return {
        "NWJ_MM": _parse_tuple_mm_pb(form.get("NWJ_MM", "")),
        "NWJ_PB": _parse_tuple_mm_pb(form.get("NWJ_PB", "")),
        "NWJ_IL_JP": _parse_list_only(form.get("NWJ_IL_JP", "")),
        "NWJ_IL_M1": _parse_list_only(form.get("NWJ_IL_M1", "")),
        "NWJ_IL_M2": _parse_list_only(form.get("NWJ_IL_M2", "")),
        "recall_headings": (form.get("recall_headings") == "on"),
    }

# ───────────────────────────────────────────────────────────────────────────────
# Routes
# ───────────────────────────────────────────────────────────────────────────────
@app.route("/", methods=["GET"])
def home():
    # Show the form and (optionally) latest error
    return render_template(
        "report.html",
        res=None,
        error=None,
        import_err=IMPORT_ERR,
        recent=_recent_buylists()
    )

@app.route("/run", methods=["POST"])
def run_phase_1_2():
    # Basic API key (optional)
    app_key = os.environ.get("APP_KEY")
    if app_key and request.headers.get("X-App-Key") != app_key:
        return jsonify({"ok": False, "error": "Unauthorized (bad X-App-Key)"}), 401

    cfg = _cfg_from_form(request.form)
    # Hand-off to core
    result = RUN_FN(cfg)
    # Save a small “result echo” for easy rendering
    return jsonify({"ok": True, "res": result})

@app.route("/confirm", methods=["POST"])
def confirm_phase_3():
    # Basic API key (optional)
    app_key = os.environ.get("APP_KEY")
    if app_key and request.headers.get("X-App-Key") != app_key:
        return jsonify({"ok": False, "error": "Unauthorized (bad X-App-Key)"}), 401

    saved_file = request.form.get("saved_path", "").strip()
    if not saved_file:
        # Try to pick the newest one
        candidates = _recent_buylists(1)
        if not candidates:
            return jsonify({"ok": False, "error": "No saved buy list found."}), 400
        saved_file = candidates[0]

    nwj = _nwj_from_form(request.form)
    result = CONFIRM_FN(saved_file, nwj, nwj.get("recall_headings", True))
    return jsonify({"ok": True, "res": result})

@app.route("/recent", methods=["GET"])
def recent_files():
    return jsonify({"ok": True, "files": _recent_buylists()})

# Convenience route to re-render the report page with JSON payload
@app.route("/report", methods=["POST"])
def report_page():
    payload = request.get_json(silent=True) or {}
    res = payload.get("res")
    error = payload.get("error")
    return render_template("report.html", res=res, error=error, import_err=IMPORT_ERR, recent=_recent_buylists())

# ───────────────────────────────────────────────────────────────────────────────
# Entry point
# ───────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # For local dev
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)
