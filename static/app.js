import io
import os
from flask import Flask, request, jsonify, render_template, send_from_directory
import lottery_store as store

app = Flask(__name__, static_folder="static", template_folder="templates")


@app.get("/")
def home():
    return render_template("index.html")


@app.get("/health")
def health():
    ok_core = True
    ok_store = True
    core_err = None
    store_err = None
    try:
        assert hasattr(store, "import_csv") or hasattr(store, "import_csv_io")
    except Exception as e:
        ok_store = False
        store_err = str(e)
    return jsonify({
        "ok": ok_core and ok_store,
        "core_loaded": ok_core,
        "store_loaded": ok_store,
        "core_err": core_err,
        "store_err": store_err,
    })


# ---------- CSV Import ----------
@app.post("/store/import_csv")
def store_import_csv():
    try:
        overwrite = request.args.get("overwrite", "0") in ("1", "true", "True")
        if "file" not in request.files:
            return jsonify({"ok": False, "error": "No file part"}), 400

        f = request.files["file"]
        if not f.filename:
            return jsonify({"ok": False, "error": "Empty filename"}), 400

        raw = f.read()
        try:
            text = raw.decode("utf-8")
        except Exception:
            text = raw.decode("latin-1")

        buf = io.StringIO(text)

        if hasattr(store, "import_csv_io"):
            stats = store.import_csv_io(buf, overwrite=overwrite)
        elif hasattr(store, "import_csv"):
            try:
                stats = store.import_csv(buf, overwrite=overwrite)
            except TypeError:
                stats = store.import_csv(text, overwrite=overwrite)
        else:
            return jsonify({"ok": False, "error": "lottery_store missing import function"}), 500

        return jsonify({
            "ok": True,
            "added": int(stats.get("added", 0)),
            "updated": int(stats.get("updated", 0)),
            "total": int(stats.get("total", stats.get("added", 0) + stats.get("updated", 0))),
        })
    except Exception as e:
        return jsonify({"ok": False, "error": type(e).__name__, "detail": str(e)}), 500


# ---------- Retrieve a single row by (game, date, optional tier) ----------
@app.get("/store/get_by_date")
def store_get_by_date():
    game = request.args.get("game", "").strip()
    date = request.args.get("date", "").strip()
    tier = request.args.get("tier", "").strip()  # "", "JP", "M1", "M2"
    try:
        row = store.get_by_date(game, date, tier)
        if not row:
            return jsonify({"ok": False, "error": "not_found"}), 404
        return jsonify({"ok": True, "row": row, "game": game, "date": store._norm_date(date), "tier": tier or None})
    except Exception as e:
        return jsonify({"ok": False, "error": type(e).__name__, "detail": str(e)}), 400


# ---------- History (20) from a starting date ----------
@app.get("/store/get_history")
def store_get_history():
    game = request.args.get("game", "").strip()   # "MM", "PB", "IL"
    tier = request.args.get("tier", "").strip()   # "", "JP", "M1", "M2" (IL only)
    since = request.args.get("from", "").strip()  # mm/dd/yyyy (3rd newest JP etc.)
    limit = int(request.args.get("limit", 20))
    try:
        items = store.get_history(game, since, tier=tier, limit=limit)
        return jsonify({"ok": True, "rows": items})
    except Exception as e:
        return jsonify({"ok": False, "error": type(e).__name__, "detail": str(e)}), 400


# Static files (served by Flask in dev; on Render your platform may do this)
@app.get("/static/<path:filename>")
def static_files(filename):
    return send_from_directory("static", filename)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)
