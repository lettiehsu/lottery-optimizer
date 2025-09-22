from __future__ import annotations
import os
from flask import Flask, request, jsonify, render_template

import lottery_store as store  # <- the file below

app = Flask(__name__, static_folder="static", template_folder="templates")


@app.get("/")
def index():
    return render_template("index.html")


# ---------------- CSV / history API ----------------

@app.post("/store/import_csv")
def store_import_csv():
    """
    Accepts multipart/form-data with:
      - file: the CSV
      - overwrite: "true"/"false"
    Returns JSON: {"ok": true, "added": N, "updated": M, "total": K}
    """
    f = request.files.get("file")
    if not f:
        return jsonify({"ok": False, "error": "no_file"}), 400

    overwrite = str(request.form.get("overwrite", "false")).lower() in ("1", "true", "yes", "on")
    try:
        text = f.read().decode("utf-8", errors="replace")
        stats = store.import_csv(text, overwrite=overwrite)
        return jsonify({"ok": True, **stats})
    except Exception as e:
        return jsonify({"ok": False, "error": type(e).__name__, "detail": str(e)}), 400


@app.get("/store/get_by_date")
def store_get_by_date():
    """
    /store/get_by_date?game=MM|PB|IL_JP|IL_M1|IL_M2&date=MM/DD/YYYY
    -> {"ok": true, "row": {"mains":[..], "bonus": <num|null>}}
    """
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
    """
    /store/get_history?game=MM|PB|IL_JP|IL_M1|IL_M2&from=MM/DD/YYYY&limit=20
    -> {"ok": true, "rows":[...], "blob":"..."}
    """
    game = (request.args.get("game") or "").strip()
    start = (request.args.get("from") or "").strip()
    limit = int(request.args.get("limit", "20"))
    if not game or not start:
        return jsonify({"ok": False, "error": "missing_params"}), 400
    try:
        out = store.get_history(game, start_date=start, limit=limit)
        return jsonify({"ok": True, **out})
    except Exception as e:
        return jsonify({"ok": False, "error": type(e).__name__, "detail": str(e)}), 400


# ---------------- Phase 1 passthrough ----------------

@app.post("/run_json")
def run_json():
    """
    Pass Phase-1 payload to your core. While you finish core wiring,
    this endpoint just echos & saves the payload path for the UI.
    Replace with: import lottery_core as core; res = core.handle_run(payload)
    """
    payload = request.get_json(silent=True) or {}
    # Save a copy so the UI shows a saved_path
    import json, time
    path = f"/tmp/lotto_1_{time.strftime('%Y-%m-%d_%H-%M-%S')}.json"
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(payload, fp, ensure_ascii=False, indent=2)
    return jsonify({"ok": True, "saved_path": path, "echo": payload})


@app.get("/health")
def health():
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=True)
