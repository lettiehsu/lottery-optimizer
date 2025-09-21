# app.py — Flask API for Lottery Optimizer (works with the new lottery_core.py)

import os
from flask import Flask, request, jsonify, send_from_directory, render_template

from lottery_core import (
    run_phase1,
    run_phase2,
    run_phase3,
    list_recent_files,
    health as core_health,
)

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(APP_ROOT, "static")
TEMPLATES_DIR = os.path.join(APP_ROOT, "templates")

app = Flask(__name__, static_folder="static", template_folder="templates")


# ----------------------------- UI ---------------------------------
@app.route("/", methods=["GET"])
def home():
    """
    Render the single-page UI (templates/index.html).
    """
    # If you don't have templates/index.html, comment the next line and uncomment the return below.
    return render_template("index.html")

    # Fallback (plain text) if you prefer not to use a template:
    # return (
    #     "Lottery Optimizer API (UI not found)\n\n"
    #     "POST /run_json with form fields LATEST_* to generate & simulate.\n"
    #     "POST /confirm_json with saved_path & NWJ_* to confirm.\n"
    #     "GET  /recent for recent saved buy files.\n"
    #     "GET  /health to check service.\n"
    # )


# --------------------------- JSON API ------------------------------
@app.route("/run_json", methods=["POST"])
def run_json():
    """
    Phase router:
      - Phase 1: expects the LATEST_*, FEED_*, HIST_*_BLOB fields in JSON body.
      - Phase 2: expects {"phase": "phase2", "saved_path": "<from phase1>"}.
    """
    try:
        data = request.get_json(force=True, silent=False) or {}
    except Exception as e:
        return jsonify({"ok": False, "error": type(e).__name__, "detail": str(e)}), 400

    phase = (data.get("phase") or "").lower()

    # Phase 2
    if phase == "phase2":
        saved_path = data.get("saved_path")
        if not saved_path:
            return jsonify({"ok": False, "error": "ValueError", "detail": "Missing saved_path for phase2"}), 400
        out = run_phase2(saved_path)
        return jsonify(out), (200 if out.get("ok") else 400)

    # Default to Phase 1 if phase not specified (or explicitly phase1)
    out = run_phase1(data)
    return jsonify(out), (200 if out.get("ok") else 400)


@app.route("/confirm_json", methods=["POST"])
def confirm_json():
    """
    Phase 3: confirm buy lists vs newest jackpot (NWJ).
      Body: {"saved_path": "<phase2 json>", "NWJ": {...optional...}}
    """
    try:
        data = request.get_json(force=True, silent=False) or {}
    except Exception as e:
        return jsonify({"ok": False, "error": type(e).__name__, "detail": str(e)}), 400

    saved_path = data.get("saved_path")
    if not saved_path:
        return jsonify({"ok": False, "error": "ValueError", "detail": "Missing saved_path"}), 400

    nwj = data.get("NWJ") or None
    out = run_phase3(saved_path, nwj)
    return jsonify(out), (200 if out.get("ok") else 400)


@app.route("/recent", methods=["GET"])
def recent():
    files = list_recent_files()
    return jsonify({"ok": True, "files": files})


@app.route("/health", methods=["GET"])
def health():
    # Ask the core if it loaded; include a friendly message if template missing.
    h = core_health()
    return jsonify(h)


# -------------------------- Static files --------------------------
@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(STATIC_DIR, filename)


# -------------------------- Entrypoint ----------------------------
if __name__ == "__main__":
    # Local dev run: `python app.py`
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port, debug=bool(os.environ.get("DEBUG")))
