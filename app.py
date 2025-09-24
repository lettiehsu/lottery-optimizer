# app.py — COMPLETE

from __future__ import annotations

import io
import json
import os
import re
from datetime import datetime
from typing import Any, Dict

from flask import Flask, jsonify, render_template, request, send_from_directory

import lottery_store as store  # your storage module

app = Flask(__name__, static_folder="static", template_folder="templates")


# --------------------------- helpers ---------------------------

def _ok(payload: Dict[str, Any], status: int = 200):
    payload.setdefault("ok", True)
    return jsonify(payload), status

def _err(detail: str, err_type: str = "Error", status: int = 400):
    return jsonify({"ok": False, "error": err_type, "detail": detail}), status

def _norm_date(s: str) -> str:
    if not s:
        raise ValueError("Empty date")
    t = s.strip()
    if re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", t):
        m, d, y = t.split("/")
        return f"{int(m):02d}/{int(d):02d}/{int(y):04d}"
    m = re.fullmatch(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", t)
    if m:
        y, mo, d = m.groups()
        return f"{int(mo):02d}/{int(d):02d}/{int(y):04d}"
    m = re.fullmatch(r"(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})", t)
    if m:
        mo, d, y = m.groups()
        if len(y) == 2:
            y = f"20{y}"
        return f"{int(mo):02d}/{int(d):02d}/{int(y):04d}"
    for fmt in ("%m/%d/%Y","%m-%d-%Y","%Y-%m-%d","%Y/%m/%d","%m/%d/%y","%m-%d-%y"):
        try:
            return datetime.strptime(t, fmt).strftime("%m/%d/%Y")
        except Exception:
            pass
    raise ValueError(f"Unrecognized date: {t!r}")


# --------------------------- routes ---------------------------

@app.get("/")
def index():
    return render_template("index.html")

@app.get("/health")
def health():
    try:
        # a light ping to confirm module import works
        _ = hasattr(store, "get_by_date")
        return _ok({"core_loaded": True, "store_loaded": True, "core_err": None, "store_err": None})
    except Exception as e:
        return _ok({"core_loaded": False, "store_loaded": False, "core_err": str(e), "store_err": str(e)})

# ---- CSV upload (robust) ----
@app.post("/store/import_csv")
def import_csv():
    """
    Expects multipart/form-data with:
      - file: the CSV file
      - overwrite: 'true' | 'false'
    """
    try:
        if "file" not in request.files:
            return _err("No file field named 'file' in upload.", "ValueError")
        f = request.files["file"]
        overwrite = (request.form.get("overwrite", "false").lower() == "true")

        # Read into BytesIO so we can pass a file-like either way
        buf = io.BytesIO(f.read())
        buf.seek(0)

        # Support both store.import_csv and store.import_csv_io
        if hasattr(store, "import_csv"):
            stats = store.import_csv(buf, overwrite=overwrite)
        elif hasattr(store, "import_csv_io"):
            stats = store.import_csv_io(buf, overwrite=overwrite)
        else:
            return _err("lottery_store is missing import_csv(_io).", "AttributeError")

        # Expect stats like {"added": N, "updated": M, "total": T, "ok": True}
        stats = stats or {}
        stats.setdefault("ok", True)
        return _ok(stats)
    except Exception as e:
        return _err(str(e), type(e).__name__)

# ---- per-date retrieval ----
@app.get("/store/get_by_date")
def get_by_date():
    try:
        game = (request.args.get("game") or "").strip()
        if not game:
            return _err("Missing 'game'", "ValueError")
        date = _norm_date(request.args.get("date") or "")
        tier = (request.args.get("tier") or "").strip() or None
        row = store.get_by_date(game=game, date=date, tier=tier)
        return _ok({"row": row})
    except Exception as e:
        return _err(str(e), type(e).__name__)

# ---- history retrieval (Load 20) ----
@app.get("/store/get_history")
def get_history():
    try:
        game = (request.args.get("game") or "").strip()
        if not game:
            return _err("Missing 'game'", "ValueError")
        from_date = _norm_date(request.args.get("from") or "")
        limit = int(request.args.get("limit") or 20)
        tier = (request.args.get("tier") or "").strip() or None
        rows = store.get_history(game=game, from_date=from_date, limit=limit, tier=tier)
        return _ok({"rows": rows})
    except Exception as e:
        return _err(str(e), type(e).__name__)

# ---- phase runner passthrough (optional, unchanged) ----
@app.post("/run_json")
def run_json():
    try:
        body = request.get_json(force=True, silent=False) or {}
        # If your core lives elsewhere, call it here. For now, echo.
        if hasattr(store, "evaluate_phase1"):
            res = store.evaluate_phase1(body)
        else:
            res = {"echo": body}
        res.setdefault("ok", True)
        return _ok(res)
    except Exception as e:
        return _err(str(e), type(e).__name__)

@app.get("/static/<path:path>")
def static_files(path):
    return send_from_directory(app.static_folder, path)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")), debug=False)
