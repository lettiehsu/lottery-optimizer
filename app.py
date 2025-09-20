# app.py — JSON-only safe mode to surface real errors
from __future__ import annotations

import os, sys, glob, json, ast, traceback
from typing import Any, Dict, List, Optional, Tuple
from flask import Flask, request, jsonify, Response

app = Flask(__name__)
app.config.update(PROPAGATE_EXCEPTIONS=True)

DATA_DIR = os.getenv("DATA_DIR", "/tmp")
BUY_DIR = os.path.join(DATA_DIR, "buylists")
os.makedirs(BUY_DIR, exist_ok=True)

# ---------- always show REAL errors (no HTML) ----------
@app.errorhandler(Exception)
def handle_any_error(e):
    tb = traceback.format_exc()
    print("UNCAUGHT ERROR:", e, file=sys.stderr)
    print(tb, file=sys.stderr)
    # Always return JSON so we see the message
    return jsonify({
        "ok": False,
        "path": request.path,
        "error": f"{e.__class__.__name__}: {e}",
        "trace": tb
    }), 500

# ---------- lazy import core so app boots even if it has issues ----------
def import_core():
    try:
        import lottery_core as core  # must expose run_phase_1_and_2, confirm_phase_3
        return core, None
    except Exception as e:
        return None, f"Failed to import lottery_core.py: {e}\n\n{traceback.format_exc()}"

# ---------- helpers ----------
def parse_literal(s: str):
    """Parse inputs like:
       "([10,14,34,40,43], 5)" or "[10,14,34,40,43], 5"
       or "[1,4,5,10,18,49]" -> list
    """
    if s is None:
        return None
    s = s.strip()
    if not s:
        return None
    try:
        return ast.literal_eval(s)
    except Exception:
        # allow "[...], bonus" (without outer tuple)
        if "]" in s and s.count("]") == 1 and "," in s.split("]")[-1]:
            left, right = s.split("]", 1)
            left += "]"
            mains = ast.literal_eval(left)
            bonus = int(right.strip().lstrip(",").strip())
            return (mains, bonus)
        raise

def recent_files(limit: int = 10) -> List[str]:
    paths = sorted(glob.glob(os.path.join(BUY_DIR, "buy_session_*.json")), reverse=True)
    return [os.path.basename(p) for p in paths[:limit]]

# ---------- routes ----------
@app.get("/health")
def health():
    return jsonify({"ok": True, "python": sys.version.split()[0], "buy_dir": BUY_DIR})

@app.get("/")
def home():
    return Response(
        "Lottery Optimizer API (safe mode)\n\n"
        "POST /run_json with form fields LATEST_* to generate & simulate.\n"
        "POST /confirm_json with saved_path & NWJ_* to confirm.\n"
        "GET  /recent for recent saved buy files.\n"
        "GET  /health to check service.\n",
        mimetype="text/plain"
    )

@app.get("/recent")
def recent():
    return jsonify({"ok": True, "files": recent_files(), "dir": BUY_DIR})

@app.post("/run_json")
def run_json():
    core, err = import_core()
    if err:
        return jsonify({"ok": False, "where": "import", "error": err}), 500
    f = request.form
    cfg = {
        "LATEST_MM":   parse_literal(f.get("LATEST_MM", "")),
        "LATEST_PB":   parse_literal(f.get("LATEST_PB", "")),
        "LATEST_IL_JP": parse_literal(f.get("LATEST_IL_JP", "")),
        "LATEST_IL_M1": parse_literal(f.get("LATEST_IL_M1", "")),
        "LATEST_IL_M2": parse_literal(f.get("LATEST_IL_M2", "")),
        "runs":        int(f.get("runs", "100") or "100"),
        "quiet":       (f.get("quiet", "on") == "on"),
        "DATA_DIR":    DATA_DIR,
        "BUY_DIR":     BUY_DIR,
    }
    res = core.run_phase_1_and_2(cfg)
    return jsonify({"ok": True, "res": res})

@app.post("/confirm_json")
def confirm_json():
    core, err = import_core()
    if err:
        return jsonify({"ok": False, "where": "import", "error": err}), 500
    f = request.form
    saved_input = (f.get("saved_path", "") or "").strip()
    # allow bare filename or absolute path
    saved_path = (
        os.path.join(BUY_DIR, os.path.basename(saved_input))
        if saved_input and not os.path.isabs(saved_input)
        else saved_input
    )
    nwj = {
        "NWJ_MM":     parse_literal(f.get("NWJ_MM", "")),
        "NWJ_PB":     parse_literal(f.get("NWJ_PB", "")),
        "NWJ_IL_JP":  parse_literal(f.get("NWJ_IL_JP", "")),
        "NWJ_IL_M1":  parse_literal(f.get("NWJ_IL_M1", "")),
        "NWJ_IL_M2":  parse_literal(f.get("NWJ_IL_M2", "")),
        "also_recall": (f.get("also_recall", "on") == "on"),
    }
    res = core.confirm_phase_3(saved_path, nwj)
    return jsonify({"ok": True, "res": res})

# ---------- local debug ----------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=True)
