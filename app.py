# app.py — wiring for Phases 1/2/3 + history endpoints (BLOB view & CSV export)
from __future__ import annotations
import os
from flask import Flask, request, jsonify, render_template

# --- Core import (Phase 1/2/3 logic) ---
core_err = None
lotto = None
try:
    import lottery_core as lotto
except Exception as e:
    core_err = f"{type(e).__name__}: {e}"

# --- History store (SQLite) ---
store_err = None
try:
    import lottery_store as store
except Exception as e:
    store = None
    store_err = f"{type(e).__name__}: {e}"

app = Flask(__name__, static_folder="static", template_folder="templates")

# Initialize DB on startup (non-fatal if it fails; you can add a Render Disk later)
if store and not store_err:
    try:
        store.init_db()
    except Exception as e:
        store_err = f"{type(e).__name__}: {e}"

@app.get("/")
def index():
    # Render UI; fallback to a tiny text page if template missing
    try:
        return render_template("index.html")
    except Exception:
        msg = []
        msg.append("Lottery Optimizer API")
        msg.append("")
        msg.append("POST /run_json       -> Phase 1")
        msg.append("POST /run_phase2     -> Phase 2")
        msg.append("POST /confirm_json   -> Phase 3")
        msg.append("GET  /recent         -> recent saved files")
        msg.append("GET  /hist_blob?game=MM|PB|IL")
        msg.append("POST /hist_add       -> save LATEST_* to DB")
        msg.append("GET  /hist_csv?game=MM|PB|IL&limit=1000")
        msg.append("GET  /health         -> status")
        return ("\n".join(msg), 200, {"Content-Type": "text/plain; charset=utf-8"})

@app.get("/health")
def health():
    return jsonify({
        "ok": True,
        "core_loaded": lotto is not None and core_err is None,
        "core_err": core_err,
        "store_loaded": store is not None and store_err is None,
        "store_err": store_err
    })

# -------------------- Phase 1 --------------------
@app.post("/run_json")
def run_json():
    if core_err:
        return jsonify({"ok": False, "error": "CoreImportError", "detail": core_err}), 500
    try:
        payload = request.get_json(force=True, silent=False) or {}
    except Exception as e:
        return jsonify({"ok": False, "error": type(e).__name__, "detail": str(e)}), 400

    try:
        result = lotto.handle_run(payload)  # expected in lottery_core.py
    except AttributeError:
        return jsonify({"ok": False, "error": "MissingFunction", "detail": "lottery_core.handle_run not found"}), 500
    except Exception as e:
        return jsonify({"ok": False, "error": type(e).__name__, "detail": str(e)}), 500

    return jsonify(result), (200 if result.get("ok") else 400)

# -------------------- Phase 2 --------------------
@app.post("/run_phase2")
def run_phase2():
    if core_err:
        return jsonify({"ok": False, "error": "CoreImportError", "detail": core_err}), 500
    try:
        payload = request.get_json(force=True, silent=False) or {}
        p1_path = (payload.get("saved_path") or "").strip()
        if not p1_path:
            return jsonify({"ok": False, "error": "ValueError", "detail": "saved_path is required"}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": type(e).__name__, "detail": str(e)}), 400

    try:
        result = lotto.run_phase2(p1_path)  # expected in lottery_core.py
    except AttributeError:
        return jsonify({"ok": False, "error": "MissingFunction", "detail": "lottery_core.run_phase2 not found"}), 500
    except Exception as e:
        return jsonify({"ok": False, "error": type(e).__name__, "detail": str(e)}), 500

    return jsonify(result), (200 if result.get("ok") else 400)

# -------------------- Phase 3 --------------------
@app.post("/confirm_json")
def confirm_json():
    if core_err:
        return jsonify({"ok": False, "error": "CoreImportError", "detail": core_err}), 500
    try:
        payload = request.get_json(force=True, silent=False) or {}
        # be robust to .trim() mishaps
        p2_path = str(payload.get("saved_path") or "").strip()
    except Exception as e:
        return jsonify({"ok": False, "error": type(e).__name__, "detail": str(e)}), 400

    if not p2_path:
        return jsonify({"ok": False, "error": "ValueError", "detail": "saved_path is required"}), 400

    nwj = payload.get("NWJ")
    try:
        result = lotto.handle_confirm(p2_path, nwj)  # expected in lottery_core.py
    except AttributeError:
        return jsonify({"ok": False, "error": "MissingFunction", "detail": "lottery_core.handle_confirm not found"}), 500
    except Exception as e:
        return jsonify({"ok": False, "error": type(e).__name__, "detail": str(e)}), 500

    return jsonify(result), (200 if result.get("ok") else 400)

# -------------------- Recent --------------------
@app.get("/recent")
def recent():
    if core_err:
        return jsonify({"ok": False, "error": "CoreImportError", "detail": core_err}), 500
    try:
        files = lotto.list_recent()  # expected in lottery_core.py
        return jsonify({"ok": True, "files": files}), 200
    except AttributeError:
        return jsonify({"ok": False, "error": "MissingFunction", "detail": "lottery_core.list_recent not found"}), 500
    except Exception as e:
        return jsonify({"ok": False, "error": type(e).__name__, "detail": str(e)}), 500

# ================== History endpoints ==================

@app.post("/hist_add")
def hist_add():
    """
    Save current LATEST_* into the SQLite history.
    Body can include any of:
      LATEST_MM: [[..5..], bonus]
      LATEST_PB: [[..5..], bonus]
      LATEST_IL_JP: [[..6..], null]
      LATEST_IL_M1: [[..6..], null]
      LATEST_IL_M2: [[..6..], null]
    Optional: draw_date (YYYY-MM-DD). If absent, today's UTC date is used.
    """
    if not store or store_err:
        return jsonify({"ok": False, "error": "StoreUnavailable", "detail": store_err or "lottery_store not loaded"}), 500
    try:
        payload = request.get_json(force=True, silent=False) or {}
    except Exception as e:
        return jsonify({"ok": False, "error": type(e).__name__, "detail": str(e)}), 400

    draw_date = str(payload.get("draw_date") or "").strip() or None
    added = []

    try:
        mm = payload.get("LATEST_MM")
        if isinstance(mm, (list, tuple)) and len(mm) == 2 and isinstance(mm[0], (list, tuple)) and len(mm[0]) == 5:
            store.add_mm([int(x) for x in mm[0]], int(mm[1]), draw_date)
            added.append("MM")
        pb = payload.get("LATEST_PB")
        if isinstance(pb, (list, tuple)) and len(pb) == 2 and isinstance(pb[0], (list, tuple)) and len(pb[0]) == 5:
            store.add_pb([int(x) for x in pb[0]], int(pb[1]), draw_date)
            added.append("PB")
        il_jp = payload.get("LATEST_IL_JP")
        if isinstance(il_jp, (list, tuple)) and len(il_jp) == 2 and isinstance(il_jp[0], (list, tuple)) and len(il_jp[0]) == 6:
            store.add_il([int(x) for x in il_jp[0]], "JP", draw_date)
            added.append("IL_JP")
        il_m1 = payload.get("LATEST_IL_M1")
        if isinstance(il_m1, (list, tuple)) and len(il_m1) == 2 and isinstance(il_m1[0], (list, tuple)) and len(il_m1[0]) == 6:
            store.add_il([int(x) for x in il_m1[0]], "M1", draw_date)
            added.append("IL_M1")
        il_m2 = payload.get("LATEST_IL_M2")
        if isinstance(il_m2, (list, tuple)) and len(il_m2) == 2 and isinstance(il_m2[0], (list, tuple)) and len(il_m2[0]) == 6:
            store.add_il([int(x) for x in il_m2[0]], "M2", draw_date)
            added.append("IL_M2")
    except Exception as e:
        return jsonify({"ok": False, "error": type(e).__name__, "detail": str(e)}), 400

    return jsonify({"ok": True, "added": added})

@app.get("/hist_blob")
def hist_blob():
    """
    Return HIST_*_BLOB text (top 20 newest) for verification.
    Query: ?game=MM|PB|IL
    """
    if not store or store_err:
        return jsonify({"ok": False, "error": "StoreUnavailable", "detail": store_err or "lottery_store not loaded"}), 500
    game = (request.args.get("game") or "").upper()
    if game == "MM":
        return jsonify({"ok": True, "blob": store.mm_blob(20)})
    if game == "PB":
        return jsonify({"ok": True, "blob": store.pb_blob(20)})
    if game == "IL":
        return jsonify({"ok": True, "blob": store.il_blob(20)})
    return jsonify({"ok": False, "error": "ValueError", "detail": "game must be MM, PB, or IL"}), 400

@app.get("/hist_csv")
def hist_csv():
    """
    Download CSV of stored history.
    Query: ?game=MM|PB|IL&limit=1000
    """
    if not store or store_err:
        return jsonify({"ok": False, "error": "StoreUnavailable", "detail": store_err or "lottery_store not loaded"}), 500
    game = (request.args.get("game") or "").upper()
    limit = int(request.args.get("limit") or "1000")
    if game not in ("MM", "PB", "IL"):
        return jsonify({"ok": False, "error": "ValueError", "detail": "game must be MM, PB, or IL"}), 400
    try:
        csv_text = store.export_csv(game, limit)
        return (csv_text, 200, {
            "Content-Type": "text/csv; charset=utf-8",
            "Content-Disposition": f'attachment; filename="{game}_history.csv"'
        })
    except Exception as e:
        return jsonify({"ok": False, "error": type(e).__name__, "detail": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port, debug=True)
