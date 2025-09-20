import os, traceback, json
from flask import Flask, request, jsonify, render_template, send_from_directory

# ---- Settings ----
SAFE_MODE = int(os.getenv("SAFE_MODE", "0") or "0")  # keep at 0 for full features
DATA_DIR = os.getenv("DATA_DIR", "/tmp")

# ---- App ----
app = Flask(__name__, static_folder="static", template_folder="templates")

# ---- Try load core ----
CORE_ERR = None
try:
    import lottery_core as core
except Exception as e:
    CORE_ERR = f"{e.__class__.__name__}: {e}"

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/health")
def health():
    return jsonify({"ok": True, "core_loaded": CORE_ERR is None, "err": CORE_ERR})

@app.route("/static/<path:path>")
def serve_static(path):
    return send_from_directory("static", path)

@app.post("/run_json")
def run_json():
    if SAFE_MODE:
        return jsonify({"ok": False, "error": "SAFE_MODE is on"}), 400
    if CORE_ERR:
        return jsonify({"ok": False, "error": CORE_ERR}), 500
    try:
        payload = request.get_json(silent=True) or {}
        result = core.handle_run(payload, DATA_DIR)
        return jsonify(result)
    except Exception as e:
        return jsonify({"ok": False, "error": e.__class__.__name__, "detail": str(e)}), 400

@app.post("/confirm_json")
def confirm_json():
    if SAFE_MODE:
        return jsonify({"ok": False, "error": "SAFE_MODE is on"}), 400
    if CORE_ERR:
        return jsonify({"ok": False, "error": CORE_ERR}), 500
    try:
        payload = request.get_json(silent=True) or {}
        result = core.handle_confirm(payload, DATA_DIR)
        return jsonify(result)
    except Exception as e:
        return jsonify({"ok": False, "error": e.__class__.__name__, "detail": str(e)}), 400

@app.get("/recent")
def recent():
    if CORE_ERR:
        return jsonify({"ok": False, "error": CORE_ERR}), 500
    try:
        return jsonify(core.list_recent(DATA_DIR))
    except Exception:
        return jsonify({"ok": False, "error": "list error"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "10000")), debug=False)
