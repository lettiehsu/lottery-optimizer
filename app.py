# app.py
# Flask app wiring: history upload/slice/autofill + Phase 1/2/3 endpoints.

from __future__ import annotations
import os, io, json
from datetime import datetime
from flask import Flask, request, jsonify, render_template, send_file
import lottery_store as store

# Your existing core model functions (must already exist)
# Provide stubs if absent to avoid crashes.
try:
    import lottery_core as core
    HAS_CORE = True
except Exception as e:
    core = None
    HAS_CORE = False
    CORE_ERR = str(e)

app = Flask(__name__, static_folder="static", template_folder="templates")

@app.get("/")
def index():
    return render_template("index.html")

@app.get("/health")
def health():
    return jsonify({
        "ok": True,
        "core_loaded": bool(HAS_CORE),
        "store_loaded": True,
        "fetch_loaded": True,
        "core_err": None if HAS_CORE else CORE_ERR,
        "fetch_err": None,
        "store_err": None
    })

# ---------- BULK IMPORT CSV ----------
@app.post("/hist_upload")
def hist_upload():
    """
    Multipart form-data:
      file: CSV (game,draw_date,tier,n1..n6,bonus)
      overwrite: "1"|"0"  (default 1)
    """
    f = request.files.get("file")
    if not f:
        return jsonify({"ok": False, "detail": "No file uploaded"}), 400
    overwrite = (request.form.get("overwrite", "1") == "1")
    tmp_path = os.path.join(store.DATA_DIR, f"upload_{datetime.now().timestamp()}.csv")
    os.makedirs(store.DATA_DIR, exist_ok=True)
    f.save(tmp_path)
    try:
        out = store.import_csv(tmp_path, overwrite=overwrite)
        return jsonify({"ok": True, **out})
    except Exception as e:
        return jsonify({"ok": False, "detail": str(e)}), 400
    finally:
        try: os.remove(tmp_path)
        except Exception: pass

# ---------- SHOW BLOB ----------
@app.get("/hist_blob")
def hist_blob():
    """
    Query: game=MM|PB|IL
    Returns concatenated lines (date \t mains [bonus for MM/PB])
    For IL, includes only JP tier here (use /history_slice for tiered blobs)
    """
    game = (request.args.get("game") or "").upper()
    if game not in ("MM", "PB", "IL"):
        return jsonify({"ok": False, "detail": "invalid game"}), 400

    if game == "IL":
        tiers = ("JP","M1","M2")
        parts = []
        for t in tiers:
            rows = store.get_hist_slice("IL", t, pivot_date="", limit=20)
            lines = []
            for r in rows:
                nums = [r["n1"], r["n2"], r["n3"], r["n4"], r["n5"], r["n6"]]
                mains = "-".join(str(int(x)) for x in nums if x!="")
                lines.append(f'{r["draw_date"]}\t{mains}')
            parts.append(f"[{t}]\n" + "\n".join(lines))
        return jsonify({"ok": True, "blob": "\n\n".join(parts)})

    # MM/PB
    rows = store.get_hist_slice(game, "", pivot_date="", limit=20)
    lines = []
    for r in rows:
        nums = [r["n1"], r["n2"], r["n3"], r["n4"], r["n5"]]
        mains = "-".join(str(int(x)) for x in nums if x!="")
        bonus = r.get("bonus") or ""
        lines.append(f'{r["draw_date"]}\t{mains} {bonus}')
    return jsonify({"ok": True, "blob": "\n".join(lines)})

# ---------- SAVE current NJ to history ----------
@app.post("/hist_add")
def hist_add():
    data = request.get_json(force=True) or {}
    dates = data.get("dates") or {}
    added = []

    def eval_pair(x):
        # expect [[mains...], bonus]
        if not x:
            return None, None
        mains = x[0] if isinstance(x[0], list) else []
        bonus = x[1] if len(x) > 1 else None
        return mains, bonus

    if data.get("LATEST_MM"):
        mains, bonus = eval_pair(data["LATEST_MM"])
        store.add_mm(mains=mains, bonus=bonus, draw_date=dates.get("MM"))
        added.append("MM")

    if data.get("LATEST_PB"):
        mains, bonus = eval_pair(data["LATEST_PB"])
        store.add_pb(mains=mains, bonus=bonus, draw_date=dates.get("PB"))
        added.append("PB")

    if data.get("LATEST_IL_JP"):
        mains, _ = eval_pair(data["LATEST_IL_JP"])
        store.add_il("JP", mains=mains, draw_date=dates.get("IL_JP"))
        added.append("IL_JP")

    if data.get("LATEST_IL_M1"):
        mains, _ = eval_pair(data["LATEST_IL_M1"])
        store.add_il("M1", mains=mains, draw_date=dates.get("IL_M1"))
        added.append("IL_M1")

    if data.get("LATEST_IL_M2"):
        mains, _ = eval_pair(data["LATEST_IL_M2"])
        store.add_il("M2", mains=mains, draw_date=dates.get("IL_M2"))
        added.append("IL_M2")

    return jsonify({"ok": True, "added": added})

# ---------- Autofill (local history) ----------
@app.get("/autofill")
def autofill():
    try:
        n = int(request.args.get("n", "3"))
        if n < 1: n = 1
        mm = store.get_latest("MM", n)
        pb = store.get_latest("PB", n)
        il_jp = store.get_latest_il("JP", n)
        il_m1 = store.get_latest_il("M1", n)
        il_m2 = store.get_latest_il("M2", n)

        def nth(lst, k): return lst[k-1] if len(lst) >= k else None
        return jsonify({
            "MM": nth(mm, n),
            "PB": nth(pb, n),
            "IL": {
                "JP": nth(il_jp, n),
                "M1": nth(il_m1, n),
                "M2": nth(il_m2, n),
            }
        })
    except Exception as e:
        return jsonify({"ok": False, "detail": str(e)}), 500

# ---------- History slice (pivot → 20 rows) ----------
@app.post("/history_slice")
def history_slice():
    data = request.get_json(force=True) or {}
    game = (data.get("game") or "").upper()
    tier = (data.get("tier") or "").upper()
    pivot = (data.get("pivot_date") or "").strip()
    limit = int(data.get("limit") or 20)

    rows = store.get_hist_slice(game, tier, pivot, limit)
    out_rows = []
    lines = []
    for r in rows:
        if game == "IL":
            nums = [r["n1"], r["n2"], r["n3"], r["n4"], r["n5"], r["n6"]]
            mains = "-".join(str(int(x)) for x in nums if x!="")
            lines.append(f'{r["draw_date"]}\t{mains}')
        else:
            nums = [r["n1"], r["n2"], r["n3"], r["n4"], r["n5"]]
            mains = "-".join(str(int(x)) for x in nums if x!="")
            bonus = r.get("bonus") or ""
            lines.append(f'{r["draw_date"]}\t{mains} {bonus}')
        out_rows.append(r)
    return jsonify({"ok": True, "rows": out_rows, "blob": "\n".join(lines)})

# ---------- 3rd newest dates for Phase-1 autofill ----------
@app.get("/third_newest_dates")
def third_newest_dates():
    td = store.top_dates_by_game()

    def pick(lst, idx):
        if not lst or len(lst) <= idx: return ""
        dt = lst[idx]
        try:
            return dt.strftime("%-m/%-d/%Y")
        except Exception:
            return dt.strftime("%m/%d/%Y")

    return jsonify({
        "ok": True,
        "phase1": {
            "MM": pick(td["MM"], 2),
            "PB": pick(td["PB"], 2),
            "IL_JP": pick(td["IL_JP"], 2),
            "IL_M1": pick(td["IL_M1"], 2),
            "IL_M2": pick(td["IL_M2"], 2),
        },
        "phase2": {
            "MM": pick(td["MM"], 1),
            "PB": pick(td["PB"], 1),
            "IL_JP": pick(td["IL_JP"], 1),
            "IL_M1": pick(td["IL_M1"], 1),
            "IL_M2": pick(td["IL_M2"], 1),
        },
        "phase3": {
            "MM": pick(td["MM"], 0),
            "PB": pick(td["PB"], 0),
            "IL_JP": pick(td["IL_JP"], 0),
            "IL_M1": pick(td["IL_M1"], 0),
            "IL_M2": pick(td["IL_M2"], 0),
        }
    })

# ---------- Phase 1/2/3 pass-through ----------
@app.post("/run_json")
def run_json():
    if not HAS_CORE or not hasattr(core, "handle_run"):
        return jsonify({"ok": False, "detail": "lottery_core.handle_run not found"}), 500
    data = request.get_json(force=True) or {}
    return jsonify(core.handle_run(data))

@app.post("/run_phase2")
def run_phase2():
    if not HAS_CORE or not hasattr(core, "run_phase2"):
        return jsonify({"ok": False, "detail": "lottery_core.run_phase2 not found"}), 500
    data = request.get_json(force=True) or {}
    saved_path = data.get("saved_path") or ""
    return jsonify(core.run_phase2(saved_path))

@app.post("/confirm_json")
def confirm_json():
    if not HAS_CORE or not hasattr(core, "handle_confirm"):
        return jsonify({"ok": False, "detail": "lottery_core.handle_confirm not found"}), 500
    data = request.get_json(force=True) or {}
    return jsonify(core.handle_confirm(data))

# ---------- Recent files (core-generated) ----------
@app.get("/recent")
def recent():
    if not HAS_CORE or not hasattr(core, "recent_files"):
        return jsonify({"ok": True, "files": []})
    return jsonify({"ok": True, "files": core.recent_files()})

# ---------- CSV export (optional) ----------
@app.get("/hist_csv")
def hist_csv():
    game = (request.args.get("game") or "").upper()
    if game not in ("MM","PB","IL"):
        return jsonify({"ok": False, "detail":"invalid game"}), 400

    # filter rows
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["game","draw_date","tier","n1","n2","n3","n4","n5","n6","bonus"])
    for r in store.ROWS:
        if r["game"] != game: continue
        w.writerow([r["game"], r["draw_date"], r.get("tier",""),
                    r["n1"], r["n2"], r["n3"], r["n4"], r["n5"], r.get("n6",""), r.get("bonus","")])
    buf.seek(0)
    return send_file(io.BytesIO(buf.getvalue().encode("utf-8")),
                     mimetype="text/csv",
                     as_attachment=True,
                     download_name=f"history_{game}.csv")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "10000")))
