# app.py — minimal, solid wiring for all 3 phases
from __future__ import annotations
import os
from datetime import datetime
from flask import Flask, request, jsonify, render_template

# Try to import the core once at start
core_err = None
lotto = None
try:
    import lottery_core as lotto
except Exception as e:
    core_err = f"{type(e).__name__}: {e}"

app = Flask(__name__, static_folder="static", template_folder="templates")


@app.get("/")
def index():
    # Show an ultra-compact API landing as fallback if template missing
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
        msg.append("GET  /health         -> service status")
        return ("\n".join(msg), 200, {"Content-Type": "text/plain; charset=utf-8"})


@app.get("/health")
def health():
    return jsonify({
        "ok": True,
        "core_loaded": lotto is not None and core_err is None,
        "err": core_err
    })


@app.post("/run_json")
def run_json():
    """
    Phase 1 — Evaluate vs NJ and save Phase-1 state.
    Expects JSON with strings for FEED_*, HIST_* and LATEST_* inputs (exactly as UI sends).
    """
    if core_err:
        return jsonify({"ok": False, "error": "CoreImportError", "detail": core_err}), 500
    try:
        payload = request.get_json(force=True, silent=False) or {}
    except Exception as e:
        return jsonify({"ok": False, "error": type(e).__name__, "detail": str(e)}), 400

    try:
        # Your core should expose handle_run(payload) -> dict(with ok, bands, eval_vs_NJ, saved_path)
        result = lotto.handle_run(payload)
    except AttributeError:
        return jsonify({"ok": False, "error": "MissingFunction", "detail": "lottery_core.handle_run not found"}), 500
    except Exception as e:
        return jsonify({"ok": False, "error": type(e).__name__, "detail": str(e)}), 500

    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@app.post("/run_phase2")
def run_phase2():
    """
    Phase 2 — Run N×50 regenerations and build stats & buy lists.
    Expects JSON: { "saved_path": "/tmp/lotto_phase1_...json" }
    """
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
        # Your core should expose run_phase2(path) -> dict(with ok, agg_hits, buy_lists, bands, saved_path)
        result = lotto.run_phase2(p1_path)
    except AttributeError:
        return jsonify({"ok": False, "error": "MissingFunction", "detail": "lottery_core.run_phase2 not found"}), 500
    except Exception as e:
        return jsonify({"ok": False, "error": type(e).__name__, "detail": str(e)}), 500

    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@app.post("/confirm_json")
def confirm_json():
    """
    Phase 3 — Confirm buy lists against NWJ.
    Expects JSON: { "saved_path": "/tmp/lotto_phase2_...json", "NWJ": { ...optional... } }
    NWJ can include any subset: LATEST_MM, LATEST_PB, LATEST_IL_JP, LATEST_IL_M1, LATEST_IL_M2
    """
    if core_err:
        return jsonify({"ok": False, "error": "CoreImportError", "detail": core_err}), 500
    try:
        payload = request.get_json(force=True, silent=False) or {}
        p2_path = (payload.get("saved_path") or "").trim()
    except AttributeError:
        # werkzeug ImmutableMultiDict has no trim; guard older payloads
        payload = request.get_json(force=True, silent=False) or {}
        p2_path = str(payload.get("saved_path") or "").strip()
    except Exception as e:
        return jsonify({"ok": False, "error": type(e).__name__, "detail": str(e)}), 400

    if not p2_path:
        return jsonify({"ok": False, "error": "ValueError", "detail": "saved_path is required"}), 400

    nwj = payload.get("NWJ")  # optional dict

    try:
        # Your core should expose handle_confirm(path, nwj_dict_or_none) -> dict(with ok, confirm_hits)
        result = lotto.handle_confirm(p2_path, nwj)
    except AttributeError:
        return jsonify({"ok": False, "error": "MissingFunction", "detail": "lottery_core.handle_confirm not found"}), 500
    except Exception as e:
        return jsonify({"ok": False, "error": type(e).__name__, "detail": str(e)}), 500

    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@app.get("/recent")
def recent():
    """
    Returns recent saved files (from /tmp or configured data dir).
    """
    if core_err:
        return jsonify({"ok": False, "error": "CoreImportError", "detail": core_err}), 500
    try:
        files = lotto.list_recent()
        return jsonify({"ok": True, "files": files}), 200
    except AttributeError:
        return jsonify({"ok": False, "error": "MissingFunction", "detail": "lottery_core.list_recent not found"}), 500
    except Exception as e:
        return jsonify({"ok": False, "error": type(e).__name__, "detail": str(e)}), 500


if __name__ == "__main__":
    # Local dev
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port, debug=True)
