from __future__ import annotations

import os
import io
import json
import glob
from datetime import datetime
from flask import Flask, request, jsonify, render_template, send_from_directory

app = Flask(__name__, static_folder="static", template_folder="templates")

# ---------- store (CSV persistence & retrieval) ----------
try:
    import lottery_store as store
    STORE_OK, STORE_ERR = True, None
except Exception as e:
    store = None
    STORE_OK, STORE_ERR = False, f"{type(e).__name__}: {e}"

# ---------- core (Phase 1 logic) ----------
try:
    import lottery_core as core
    CORE_OK, CORE_ERR = True, None
except Exception as e:
    core = None
    CORE_OK, CORE_ERR = False, f"{type(e).__name__}: {e}"

# ---------- home ----------
@app.get("/")
def index():
    return render_template("index.html")

# (Flask already serves /static, this is just explicit)
@app.get("/static/<path:filename>")
def static_files(filename: str):
    return send_from_directory(app.static_folder, filename)

# ===================== STORE API ======================

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
        return jsonify({"ok": True, **stats})
    except Exception as e:
        return jsonify({"ok": False, "error": type(e).__name__, "detail": str(e)}), 400

@app.get("/store/get_by_date")
def store_get_by_date():
    if not STORE_OK:
        return jsonify({"ok": False, "error": "store_not_loaded", "detail": STORE_ERR}), 500
    game = (request.args.get("game") or "").strip()
    date = (request.args.get("date") or "").strip()
    tier = (request.args.get("tier") or "").strip()
    try:
        normalized = store._norm_date(date)
        row = store.get_by_date(game, date, tier)
        if row:
            return jsonify({"ok": True, "row": row, "game": game, "date": normalized, "tier": tier or None})
        available = store.dates_for(game, tier)
        near = store.nearest_dates(game, normalized, tier, n=3)
        return jsonify({
            "ok": False, "error": "not_found",
            "detail": {
                "message":"not_found",
                "looked_for":{"game":game,"date":normalized,"tier":tier},
                "available_dates_for_game_tier": available,
                "closest_dates": near
            }
        }), 404
    except Exception as e:
        return jsonify({"ok": False, "error": type(e).__name__, "detail": str(e)}), 400

@app.get("/store/get_history")
def store_get_history():
    if not STORE_OK:
        return jsonify({"ok": False, "error": "store_not_loaded", "detail": STORE_ERR}), 500
    game = (request.args.get("game") or "").strip()
    start = (request.args.get("from") or "").strip()
    tier = (request.args.get("tier") or "").strip()
    limit = int(request.args.get("limit", "20"))
    if not game or not start:
        return jsonify({"ok": False, "error": "missing_params"}), 400
    try:
        rows = store.get_history(game, since_date=start, tier=tier, limit=limit)
        return jsonify({"ok": True, "rows": rows})
    except Exception as e:
        return jsonify({"ok": False, "error": type(e).__name__, "detail": str(e)}), 400

@app.get("/store/debug_keys")
def store_debug_keys():
    if not STORE_OK:
        return jsonify({"ok": False, "error": "store_not_loaded", "detail": STORE_ERR}), 500
    try:
        return jsonify({"ok": True, "keys": store.list_keys()})
    except Exception as e:
        return jsonify({"ok": False, "error": type(e).__name__, "detail": str(e)}), 500

# ===================== PHASE 1 ======================

@app.post("/run_json")
def run_json():
    if not CORE_OK or not hasattr(core, "handle_run"):
        return jsonify({"ok": False, "error": "core_not_loaded", "detail": CORE_ERR or "handle_run missing"}), 500
    payload = request.get_json(silent=True) or dict(request.form)
    try:
        res = core.handle_run(payload)
        return jsonify(res)
    except Exception as e:
        return jsonify({"ok": False, "error": type(e).__name__, "detail": str(e)}), 400

# Compatibility: your UI also calls /recent for saved files
@app.get("/recent")
def recent():
    if CORE_OK and hasattr(core, "recent_files"):
        try:
            return jsonify({"ok": True, "files": core.recent_files()})
        except Exception as e:
            return jsonify({"ok": False, "error": type(e).__name__, "detail": str(e)}), 400
    files = sorted(glob.glob("/tmp/lotto_1_*.json"))[-20:]
    return jsonify({"ok": True, "files": files})

# ===================== HEALTH ======================

@app.get("/health")
def health():
    return jsonify({
        "ok": True,
        "core_loaded": CORE_OK, "core_err": CORE_ERR,
        "store_loaded": STORE_OK, "store_err": STORE_ERR
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT","5000")), debug=True)
