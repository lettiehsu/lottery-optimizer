from __future__ import annotations

import os
import json
import glob
from datetime import datetime
from flask import Flask, request, jsonify, render_template, send_from_directory

# ---------- Flask setup ----------
app = Flask(__name__, static_folder="static", template_folder="templates")

# ---------- Optional: wire in your modules ----------
# lottery_store holds CSV import + history lookups
try:
    import lottery_store as store
    STORE_OK = True
except Exception as e:
    store = None
    STORE_OK = False
    STORE_ERR = f"{type(e).__name__}: {e}"

# lottery_core holds Phase 1/2/3 logic
try:
    import lottery_core as core
    CORE_OK = True
except Exception as e:
    core = None
    CORE_OK = False
    CORE_ERR = f"{type(e).__name__}: {e}"

# ---------- Home ----------
@app.get("/")
def index():
    # Renders templates/index.html
    return render_template("index.html")


# ---------- Static (optional explicit route; Flask serves /static by default) ----------
@app.get("/static/<path:filename>")
def static_files(filename: str):
    return send_from_directory(app.static_folder, filename)


# =====================================================
#                CSV / HISTORY endpoints
# =====================================================

@app.post("/store/import_csv")
def store_import_csv():
    if not STORE_OK:
        return jsonify({"ok": False, "error": "store_not_loaded", "detail": STORE_ERR}), 500

    f = request.files.get("file")
    if not f:
        return jsonify({"ok": False, "error": "no_file"}), 400

    overwrite = request.form.get("overwrite", "false").lower() in ("1", "true", "yes", "on")
    text = f.read().decode("utf-8", errors="replace")
    try:
        stats = store.import_csv(text, overwrite=overwrite)
        return jsonify({"ok": True, **stats})
    except Exception as e:
        return jsonify({"ok": False, "error": type(e).__name__, "detail": str(e)}), 400


@app.get("/store/get_by_date")
def store_get_by_date():
    if not STORE_OK:
        return jsonify({"ok": False, "error": "store_not_loaded", "detail": STORE_ERR}), 500

    game = request.args.get("game", "").strip()
    date = request.args.get("date", "").strip()  # expected mm/dd/yyyy
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

    game = request.args.get("game", "").strip()
    start = request.args.get("from", "").strip()  # mm/dd/yyyy
    limit = int(request.args.get("limit", "20"))
    if not game or not start:
        return jsonify({"ok": False, "error": "missing_params"}), 400
    try:
        hist = store.get_history(game, start_date=start, limit=limit)
        # Expect store.get_history to return {"rows":[...], "blob":"..." }
        return jsonify({"ok": True, **hist})
    except Exception as e:
        return jsonify({"ok": False, "error": type(e).__name__, "detail": str(e)}), 400


# =====================================================
#                Phase 1 / 2 / 3 API
# =====================================================

@app.post("/run_json")
def run_json():
    if not CORE_OK or not hasattr(core, "handle_run"):
        return jsonify({"ok": False, "error": "core_not_loaded", "detail": (CORE_ERR if not CORE_OK else "handle_run missing")}), 500

    # Accept either JSON or form
    payload = request.get_json(silent=True) or dict(request.form)
    try:
        res = core.handle_run(payload)
        return jsonify(res)
    except Exception as e:
        return jsonify({"ok": False, "error": type(e).__name__, "detail": str(e)}), 400


@app.post("/confirm_json")
def confirm_json():
    if not CORE_OK or not hasattr(core, "handle_confirm"):
        return jsonify({"ok": False, "error": "core_not_loaded", "detail": (CORE_ERR if not CORE_OK else "handle_confirm missing")}), 500

    payload = request.get_json(silent=True) or dict(request.form)
    try:
        res = core.handle_confirm(payload)
        return jsonify(res)
    except Exception as e:
        return jsonify({"ok": False, "error": type(e).__name__, "detail": str(e)}), 400


@app.get("/recent")
def recent():
    # Either use core.recent_files() if present, or list tmp files as a fallback
    if CORE_OK and hasattr(core, "recent_files"):
        try:
            return jsonify({"ok": True, "files": core.recent_files()})
        except Exception as e:
            return jsonify({"ok": False, "error": type(e).__name__, "detail": str(e)}), 400

    files = sorted(glob.glob("/tmp/lotto_phase*.json"))[-20:]
    return jsonify({"ok": True, "files": files})


@app.get("/health")
def health():
    return jsonify({
        "ok": True,
        "core_loaded": CORE_OK,
        "core_err": None if CORE_OK else CORE_ERR,
        "store_loaded": STORE_OK,
        "store_err": None if STORE_OK else STORE_ERR,
        "fetch_loaded": True,   # kept for compatibility with your earlier UI
        "fetch_err": None
    })


# ---------- Entrypoint ----------
if __name__ == "__main__":
    # For local debug only; Render will use gunicorn with your config
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=True)
