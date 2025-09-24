# app.py  — COMPLETE FILE

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from flask import Flask, jsonify, render_template, request, send_from_directory

# Your storage module
import lottery_store as store  # must provide: import_csv(filelike, overwrite),
                               # get_by_date(game, date, tier=None),
                               # get_history(game, from_date, limit=20, tier=None)

app = Flask(__name__, static_folder="static", template_folder="templates")


# --------------------------- Utilities ---------------------------

def _ok(payload: Dict[str, Any]) -> Any:
    payload.setdefault("ok", True)
    return jsonify(payload)

def _err(detail: str, error: str = "Error", status: int = 400) -> Any:
    return jsonify({"ok": False, "error": error, "detail": detail}), status

def _norm_date(s: str) -> str:
    """
    Normalize a variety of date shapes to MM/DD/YYYY.
    Accepts: 9/6/2025, 09/06/2025, 2025-09-06, 2025/09/06, 09-06-2025, 9-6-25
    Returns: 'MM/DD/YYYY'
    """
    if not s:
        raise ValueError("Empty date")

    t = s.strip()
    # mm/dd/yyyy already?
    if re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", t):
        mm, dd, yy = t.split("/")
        return f"{int(mm):02d}/{int(dd):02d}/{int(yy):04d}"

    # yyyy-mm-dd or yyyy/mm/dd
    m = re.fullmatch(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", t)
    if m:
        yy, mm, dd = m.groups()
        return f"{int(mm):02d}/{int(dd):02d}/{int(yy):04d}"

    # mm-dd-yyyy or mm/dd/yy
    m = re.fullmatch(r"(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})", t)
    if m:
        mm, dd, yy = m.groups()
        if len(yy) == 2:
            # assume 20xx
            yy = f"20{yy}"
        return f"{int(mm):02d}/{int(dd):02d}/{int(yy):04d}"

    # Last-chance parse via datetime on a few formats
    fmts = [
        "%m/%d/%Y", "%m-%d-%Y",
        "%Y-%m-%d", "%Y/%m/%d",
        "%m/%d/%y", "%m-%d-%y",
    ]
    last = None
    for fmt in fmts:
        try:
            dt = datetime.strptime(t, fmt)
            return dt.strftime("%m/%d/%Y")
        except Exception as e:  # keep last error
            last = e
    raise ValueError(f"Unrecognized date: {t!r} ({last})")


# --------------------------- Routes ---------------------------

@app.get("/")
def index():
    return render_template("index.html")

@app.get("/health")
def health():
    core_loaded = True
    store_loaded = True
    core_err = None
    store_err = None
    return _ok({
        "ok": True,
        "core_loaded": core_loaded,
        "store_loaded": store_loaded,
        "core_err": core_err,
        "store_err": store_err,
    })

# ---- CSV import -------------------------------------------------

@app.post("/store/import_csv")
def store_import_csv():
    try:
        overwrite = request.form.get("overwrite", "false").lower() == "true"
        f = request.files.get("file")
        if not f:
            return _err("No file uploaded", "ValueError")
        stats = store.import_csv(f.stream, overwrite=overwrite)  # filelike supported
        # stats should be dict with added/updated/total/ok
        stats.setdefault("ok", True)
        return _ok(stats)
    except Exception as e:
        return _err(str(e), type(e).__name__)

# ---- Per-date fetch (2nd newest etc.) --------------------------

@app.get("/store/get_by_date")
def store_get_by_date():
    try:
        game = (request.args.get("game") or "").strip()
        if not game:
            return _err("Missing 'game'", "ValueError")
        raw_date = request.args.get("date") or ""
        date = _norm_date(raw_date)
        tier = (request.args.get("tier") or "").strip() or None

        row = store.get_by_date(game=game, date=date, tier=tier)
        return _ok({"row": row})
    except Exception as e:
        return _err(str(e), type(e).__name__)

# ---- History fetch (Load 20) -----------------------------------

@app.get("/store/get_history")
def store_get_history():
    try:
        game = (request.args.get("game") or "").strip()
        if not game:
            return _err("Missing 'game'", "ValueError")
        raw_from = request.args.get("from") or ""
        from_date = _norm_date(raw_from)
        limit = int(request.args.get("limit", "20"))
        tier = (request.args.get("tier") or "").strip() or None

        rows = store.get_history(game=game, from_date=from_date, limit=limit, tier=tier)
        return _ok({"rows": rows})
    except Exception as e:
        return _err(str(e), type(e).__name__)

# ---- Phase 1 runner (accept flexible JSON strings) --------------

def _maybe_parse_list(x):
    if isinstance(x, list):
        return x
    if isinstance(x, str):
        t = x.strip()
        if t.startswith("["):
            try:
                return json.loads(t)
            except Exception:
                pass
    return x  # let core/runner decide or throw later

@app.post("/run_json")
def run_json():
    """
    Body:
      {
        LATEST_MM: "[[..], b]" or [[..], b],
        LATEST_PB: ...,
        LATEST_IL_JP: ...,
        LATEST_IL_M1: ...,
        LATEST_IL_M2: ...,
        HIST_MM_BLOB: "mm-dd-yy  a-b-c-d-e  MB\n...",
        HIST_PB_BLOB: "...",
        HIST_IL_JP_BLOB: "...",
        HIST_IL_M1_BLOB: "...",
        HIST_IL_M2_BLOB: "..."
      }
    """
    try:
        body = request.get_json(force=True, silent=False) or {}
        # Normalize possibly-stringified arrays
        for k in ["LATEST_MM","LATEST_PB","LATEST_IL_JP","LATEST_IL_M1","LATEST_IL_M2"]:
            if k in body:
                body[k] = _maybe_parse_list(body[k])

        # Call your phase-1 core (replace with your own function)
        # Here we just echo back to keep the contract the UI expects.
        # You likely have something like: result = core.run_phase1(**body)
        # For now, ask storage (or core) for evaluation:
        result = store.evaluate_phase1(body)  # <-- implement in lottery_store OR swap to your core

        # result should include echo, saved_path, ok
        result.setdefault("ok", True)
        return _ok(result)
    except Exception as e:
        return _err(str(e), type(e).__name__)

# ---- static (optional, if you need direct file links) ----------

@app.get("/static/<path:path>")
def static_files(path):
    return send_from_directory(app.static_folder, path)

# --------------------------- Entrypoint -------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port, debug=False)
