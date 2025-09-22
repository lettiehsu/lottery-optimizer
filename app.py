from __future__ import annotations

import os
import io
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
    STORE_ERR = None
except Exception as e:
    store = None
    STORE_OK = False
    STORE_ERR = f"{type(e).__name__}: {e}"

# lottery_core holds Phase 1/2/3 logic
try:
    import lottery_core as core
    CORE_OK = True
    CORE_ERR = None
except Exception as e:
    core = None
    CORE_OK = False
    CORE_ERR = f"{type(e).__name__}: {e}"

# ---------- Home ----------
@app.get("/")
def index():
    # Renders templates/index.html
    return render_template("index.html")


# ---------- Static (Flask already serves /static; this is optional) ----------
@app.get("/static/<path:filename>")
def static_files(filename: str):
    return send_from_directory(app.static_folder, filename)


# =====================================================
#                CSV / HISTORY endpoints
# =====================================================

@app.post("/store/import_csv")
def store_import_csv():
    """
    Accepts multipart/form-data with:
      - file: CSV file (required)
      - overwrite: "1"/"true"/"yes"/"on" to overwrite (optional)
    Returns JSON: { ok, added, updated, total } or { ok:false, error, detail }.
    """
    if not STORE_OK:
        return jsonify({"ok": False, "error": "store_not_loaded", "detail": STORE_ERR}), 500
    try:
        f = request.files.get("file")
        if not f:
            return jsonify({"ok": False, "error": "no_file", "detail": "multipart field 'file' is missing"}), 400

        overwrite = request.form.get("overwrite", "false").lower() in ("1", "true", "yes", "on")

        raw = f.read()
        text = raw.decode("utf-8-sig", errors="ignore")  # tolerate BOM/newlines
        buf = io.StringIO(text)

        # Use file-like parser; also keep store.import_csv(text, ...) fallback available
        stats = store.import_csv_io(buf, overwrite=overwrite)
        if not isinstance(stats, dict):
            stats = {"ok": True, "added": 0, "updated": 0, "total": 0}
        if "ok" not in stats:
            stats["ok"] = True
        return jsonify(stats), (200 if stats.get("ok") else 400)
    except Exception as e:
        import traceback
        return jsonify({"ok": False, "error": type(e).__name__, "detail": "".join(traceback.format_exc())}), 500


@app.get("/store/get_by_date")
def store_get_by_date():
    """
    Query one row by game key + date (MM/DD/YYYY).
    game keys expected by the UI: MM, PB, IL_JP, IL_M1, IL_M2
    Returns { ok, row: {date, mains, bonus} } (bonus null for IL).
    """
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
    """
    Returns up to 'limit' rows newer→older starting at 'from' date (inclusive),
    and a HIST_* style "blob" string for the UI textarea.
    """
    if not STORE_OK:
        return jsonify({"ok": False, "error": "store_not_loaded", "detail": STORE_ERR}), 500

    game = request.args.get("game", "").strip()
    start = request.args.get("from", "").strip()  # mm/dd/yyyy
    limit = int(request.args.get("limit", "20"))
    if not game or not start:
        return jsonify({"ok": False, "error": "missing_params"}), 400
    try:
        hist = store.get_history(game, start_date=start, limit=limit)
        # hist shape: {"rows":[...], "blob":"..."}
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
    # Use core.recent_files() if present, else list tmp files
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
        "fetch_loaded": True,   # for older UI compatibility
        "fetch_err": None
    })


# ---------- Entrypoint ----------
if __name__ == "__main__":
    # For local debug only; Render uses gunicorn
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=True)
