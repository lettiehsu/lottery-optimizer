from __future__ import annotations

import os
from flask import Flask, request, jsonify, render_template, send_from_directory

# Flask
app = Flask(__name__, static_folder="static", template_folder="templates")

# lottery_store for CSV + history
try:
    import lottery_store as store
    STORE_OK = True
    STORE_ERR = None
except Exception as e:
    store = None
    STORE_OK = False
    STORE_ERR = f"{type(e).__name__}: {e}"

# lottery_core (optional – if you have it already wired)
try:
    import lottery_core as core
    CORE_OK = True
    CORE_ERR = None
except Exception as e:
    core = None
    CORE_OK = False
    CORE_ERR = f"{type(e).__name__}: {e}"


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/static/<path:filename>")
def static_files(filename: str):
    return send_from_directory(app.static_folder, filename)


# --------------- CSV / HISTORY ----------------

@app.post("/store/import_csv")
def store_import_csv():
    if not STORE_OK:
        return jsonify({"ok": False, "error": "store_not_loaded", "detail": STORE_ERR}), 500
    f = request.files.get("file")
    if not f:
        return jsonify({"ok": False, "error": "no_file"}), 400
    overwrite = (request.form.get("overwrite", "false").lower() in ("1","true","yes","on"))
    text = f.read().decode("utf-8", errors="replace")
    try:
        stats = store.import_csv(text, overwrite=overwrite)
        return jsonify(stats)
    except Exception as e:
        return jsonify({"ok": False, "error": type(e).__name__, "detail": str(e)}), 400


@app.get("/store/get_by_date")
def store_get_by_date():
    if not STORE_OK:
        return jsonify({"ok": False, "error": "store_not_loaded", "detail": STORE_ERR}), 500
    game = (request.args.get("game") or "").strip()
    date = (request.args.get("date") or "").strip()
    if not game or not date:
        return jsonify({"ok": False, "error": "missing_params"}), 400
    try:
        row = store.get_by_date(game, date)
        if not row:
            return jsonify({"ok": False, "error": "not_found"}), 404
        return jsonify({"ok": True, "row": row})
    except Exception as e:
        return jsonify({"ok": False, "error": type(e).__name__, "detail": str(e)}), 400


@app.get("/store/get_history")
def store_get_history():
    if not STORE_OK:
        return jsonify({"ok": False, "error": "store_not_loaded", "detail": STORE_ERR}), 500
    game = (request.args.get("game") or "").strip()
    start = (request.args.get("from") or "").strip()
    limit = int(request.args.get("limit", "20"))
    if not game or not start:
        return jsonify({"ok": False, "error": "missing_params"}), 400
    try:
        res = store.get_history(game, start_date=start, limit=limit)
        return jsonify(res)
    except Exception as e:
        return jsonify({"ok": False, "error": type(e).__name__, "detail": str(e)}), 400


# --------------- HEALTH ----------------

@app.get("/health")
def health():
    return jsonify({
        "ok": True,
        "store_loaded": STORE_OK,
        "store_err": STORE_ERR,
        "core_loaded": CORE_OK,
        "core_err": CORE_ERR,
    })


# Only used for local debug; Render uses gunicorn
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=True)
