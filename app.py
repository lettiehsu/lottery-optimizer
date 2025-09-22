#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from datetime import datetime
from flask import Flask, request, jsonify, render_template, send_from_directory
from lottery_core import (
    DEFAULT_INPUTS,
    run_phase_1,
    run_phase_2,
    run_phase_3,
    normalize_inputs,
)
from lottery_store import save_buy_lists, list_recent_files, load_buy_lists
from csv_ingest import (
    csv_import_from_stream,
    csv_list_meta,
    csv_latest_for_game,
    csv_history20_for_game,
)

APP_NAME = "Lottery Optimizer (MM / PB / IL)"

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024  # 8 MB uploads

# ---------- Web UI ----------

@app.route("/")
def index():
    return render_template("index.html", app_name=APP_NAME, defaults=DEFAULT_INPUTS)

@app.route("/static/<path:filename>")
def custom_static(filename):
    return send_from_directory("static", filename)

# ---------- Health & recent ----------

@app.route("/health")
def health():
    return jsonify({"ok": True, "service": APP_NAME})

@app.route("/recent")
def recent():
    return jsonify({"files": list_recent_files(limit=50)})

# ---------- CSV ingest + retrieval ----------

@app.route("/csv/import", methods=["POST"])
def csv_import():
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "No file field named 'file'"}), 400
    f = request.files["file"]
    if not f or not f.filename:
        return jsonify({"ok": False, "error": "Empty upload"}), 400
    meta = csv_import_from_stream(f.stream, filename=f.filename)
    return jsonify({"ok": True, "meta": meta})

@app.route("/csv/list", methods=["GET"])
def csv_list():
    return jsonify({"ok": True, "meta": csv_list_meta()})

@app.route("/csv/latest", methods=["GET"])
def csv_latest():
    """
    Query:
      game=MM|PB|IL
      asof=MM/DD/YYYY
      tier=JP|M1|M2 (for IL)
      offset=1|2|3... (1=newest)
    """
    game = (request.args.get("game") or "").upper().strip()
    asof = request.args.get("asof") or ""
    tier = request.args.get("tier") or "JP"
    offset = int(request.args.get("offset") or "1")
    try:
        out = csv_latest_for_game(game, asof, offset=offset, tier=tier)
        return jsonify({"ok": True, "data": out})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

@app.route("/csv/history20", methods=["GET"])
def csv_history20():
    """
    Query:
      game=MM|PB|IL
      asof=MM/DD/YYYY   (ending date; usually the 3rd-newest date)
      tier=JP|M1|M2     (for IL)
    Returns: HIST_*_BLOB
    """
    game = (request.args.get("game") or "").upper().strip()
    asof = request.args.get("asof") or ""
    tier = request.args.get("tier") or "JP"
    try:
        blob = csv_history20_for_game(game, asof, tier=tier)
        return jsonify({"ok": True, "blob": blob})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

# ---------- Phase runners ----------

def _read_payload():
    if request.method == "POST" and request.content_type and "application/json" in request.content_type:
        payload = request.get_json(silent=True) or {}
    else:
        payload = request.form.to_dict() if request.form else {}
    return payload or {}

@app.route("/run_json", methods=["POST"])
def run_json():
    payload = _read_payload()
    phase = (payload.get("phase") or "eval").strip().lower()
    user_inputs = normalize_inputs(**payload)

    if phase == "eval":
        out = run_phase_1(user_inputs)
    elif phase == "predict":
        out = run_phase_2(user_inputs)
        stamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        saved_path = save_buy_lists(out["buy_lists"], suffix=stamp)
        out["saved_path"] = saved_path
    else:
        return jsonify({"ok": False, "error": f"Unknown phase '{phase}'"}), 400

    return jsonify(out)

@app.route("/confirm_json", methods=["POST"])
def confirm_json():
    payload = _read_payload()
    saved_path = (payload.get("saved_path") or "").strip()
    if not saved_path:
        return jsonify({"ok": False, "error": "saved_path is required"}), 400

    try:
        buy_lists = load_buy_lists(saved_path)
    except FileNotFoundError:
        return jsonify({"ok": False, "error": f"File not found: {saved_path}"}), 404

    user_inputs = normalize_inputs(**payload)
    out = run_phase_3(buy_lists, user_inputs)
    out["saved_path"] = saved_path
    return jsonify(out)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")), debug=False)
