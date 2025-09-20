# app.py (boot-safe scaffold)
import os
from flask import Flask, render_template, request, jsonify

app = Flask(__name__, static_folder="static", template_folder="templates")

# Environment
SAFE_MODE = os.getenv("SAFE_MODE", "0") == "1"   # default OFF for UI
DATA_DIR = os.getenv("DATA_DIR", "/tmp") or "/tmp"
os.makedirs(DATA_DIR, exist_ok=True)

# Try to import core without crashing the server
core_err = None
try:
    import lottery_core as core
except Exception as e:
    core = None
    core_err = f"{type(e).__name__}: {e}"

@app.get("/health")
def health():
    status = {"ok": True, "core_loaded": core is not None, "err": core_err}
    return jsonify(status), 200

@app.get("/")
def home():
    if SAFE_MODE or core is None:
        # Text help if SAFE_MODE on or core failed to load
        lines = [
            "Lottery Optimizer API (safe mode)" if SAFE_MODE else "Lottery Optimizer API (core not loaded)",
            "",
            "POST /run_json with form fields LATEST_* to generate & simulate.",
            "POST /confirm_json with saved_path & NWJ to confirm.",
            "GET  /recent for recent saved buy files.",
            "GET  /health to check service.",
            "",
        ]
        if core_err:
            lines.append(f"[core import error] {core_err}")
        return "\n".join(lines), 200, {"Content-Type": "text/plain; charset=utf-8"}
    return render_template("index.html")

@app.get("/recent")
def recent():
    if core is None:
        return jsonify({"error": "core not loaded", "detail": core_err}), 500
    return jsonify(core.list_recent(DATA_DIR)), 200

@app.post("/run_json")
def run_json():
    if core is None:
        return jsonify({"error": "core not loaded", "detail": core_err}), 500
    # Accept both JSON and form-encoded
    payload = request.get_json(silent=True) or request.form.to_dict(flat=True)
    try:
        result = core.handle_run(payload, DATA_DIR)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": type(e).__name__, "detail": str(e)}), 400

@app.post("/confirm_json")
def confirm_json():
    if core is None:
        return jsonify({"error": "core not loaded", "detail": core_err}), 500
    payload = request.get_json(silent=True) or request.form.to_dict(flat=True)
    try:
        result = core.handle_confirm(payload, DATA_DIR)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": type(e).__name__, "detail": str(e)}), 400

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
