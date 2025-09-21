from __future__ import annotations
from flask import Flask, request, jsonify, render_template_string
import csv, io, traceback, datetime

app = Flask(__name__)

# -----------------------------------------------------------------------------
# Simple in-memory store (replace with your DB or file-backed store as needed)
# -----------------------------------------------------------------------------
_store = {
    "MM": {},     # date -> {"mains":[...], "bonus":int}
    "PB": {},
    "IL_JP": {},  # date -> {"mains":[...]}
    "IL_M1": {},
    "IL_M2": {},
}

def _date_key(d: datetime.date) -> str:
    return d.strftime("%Y-%m-%d")

def upsert_mm(date: datetime.date, mains: list[int], bonus: int|None, overwrite=False):
    key = _date_key(date)
    existed = key in _store["MM"]
    if not existed or overwrite:
        _store["MM"][key] = {"mains": mains, "bonus": bonus}
        return "updated" if existed else "added"

def upsert_pb(date: datetime.date, mains: list[int], bonus: int|None, overwrite=False):
    key = _date_key(date)
    existed = key in _store["PB"]
    if not existed or overwrite:
        _store["PB"][key] = {"mains": mains, "bonus": bonus}
        return "updated" if existed else "added"

def upsert_il(date: datetime.date, tier: str, mains: list[int], overwrite=False):
    tier = tier.upper()
    bucket = {"JP": "IL_JP", "M1": "IL_M1", "M2": "IL_M2"}[tier]
    key = _date_key(date)
    existed = key in _store[bucket]
    if not existed or overwrite:
        _store[bucket][key] = {"mains": mains}
        return "updated" if existed else "added"

def parse_mdyyyy(s: str) -> datetime.date:
    # accept m/d/yyyy or mm/dd/yyyy
    return datetime.datetime.strptime(s.strip(), "%m/%d/%Y").date()

# -----------------------------------------------------------------------------
# CSV importer for the *combined* master file
# Schema (headers case-insensitive):
#   date, game, tier, n1, n2, n3, n4, n5, n6, bonus
# game: MM|PB|IL
# tier: JP|M1|M2 (IL only)
# bonus: blank/null for IL
# -----------------------------------------------------------------------------
def import_master_csv(csv_text: str, overwrite: bool = False):
    rdr = csv.DictReader(io.StringIO(csv_text))
    added = updated = total = 0
    for row in rdr:
        total += 1
        date = parse_mdyyyy(row["date"])
        game = (row["game"] or "").strip().upper()
        tier = (row.get("tier") or "").strip().upper()
        nums = [int(row[k]) for k in ("n1","n2","n3","n4","n5") if row.get(k)]
        n6   = row.get("n6")
        if n6 and n6.strip():
            nums.append(int(n6))
        bonus = row.get("bonus")
        if bonus is not None and str(bonus).strip() == "":
            bonus = None

        if game == "MM":
            mb = int(bonus) if bonus not in (None, "", "null", "None") else None
            ch = upsert_mm(date, nums, mb, overwrite=overwrite)
        elif game == "PB":
            pb = int(bonus) if bonus not in (None, "", "null", "None") else None
            ch = upsert_pb(date, nums, pb, overwrite=overwrite)
        elif game == "IL":
            if tier not in ("JP", "M1", "M2"):
                continue
            ch = upsert_il(date, tier, nums, overwrite=overwrite)
        else:
            continue

        if ch == "added": added += 1
        elif ch == "updated": updated += 1

    return {"ok": True, "total": total, "added": added, "updated": updated}

# -----------------------------------------------------------------------------
# Store routes
# -----------------------------------------------------------------------------
@app.post("/store/import_csv")
def store_import_csv():
    """Accept the combined master CSV and load it into the store."""
    try:
        f = request.files.get("csv")
        if not f:
            return jsonify({"ok": False, "error": "No file provided"}), 400
        overwrite = request.form.get("overwrite") in ("1", "true", "on", "yes")
        csv_text = f.read().decode("utf-8", errors="ignore")
        res = import_master_csv(csv_text, overwrite=overwrite)
        return jsonify(res)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"ok": False, "error": type(e).__name__, "detail": str(e)}), 500

@app.get("/store/get_by_date")
def store_get_by_date():
    """Return the single row (preview) for a given game and date (mm/dd/yyyy)."""
    try:
        game = request.args.get("game", "").strip().upper()
        date = parse_mdyyyy(request.args["date"])
        key = _date_key(date)
        if game not in _store:
            return jsonify({"ok": False, "error": "bad game"}), 400
        row = _store[game].get(key)
        return jsonify({"ok": True, "row": row})
    except Exception as e:
        return jsonify({"ok": False, "error": type(e).__name__, "detail": str(e)}), 500

@app.get("/store/get_history")
def store_get_history():
    """Return a blob of up to N rows starting at (or before) a given date, newest -> older."""
    try:
        game = request.args.get("game", "").strip().upper()
        if game not in _store:
            return jsonify({"ok": False, "error": "bad game"}), 400
        from_str = request.args.get("from")
        limit = int(request.args.get("limit", "20"))
        if from_str:
            from_date = parse_mdyyyy(from_str)
            cutoff_key = _date_key(from_date)
        else:
            cutoff_key = None

        items = sorted(_store[game].items(), key=lambda kv: kv[0], reverse=True)
        blob_lines = []
        count = 0
        for k, v in items:
            if cutoff_key and k > cutoff_key:
                # we want from the given date downward; skip newer
                continue
            mains = v["mains"]
            if game in ("MM", "PB"):
                bonus = v.get("bonus")
                line = f"{'-'.join(f'{n:02d}' for n in mains)} {bonus:02d}" if bonus is not None \
                       else f"{'-'.join(f'{n:02d}' for n in mains)}"
            else:
                line = f"{'-'.join(f'{n:02d}' for n in mains)}"
            blob_lines.append(line)
            count += 1
            if count >= limit:
                break

        return jsonify({"ok": True, "blob": "\n".join(blob_lines)})
    except Exception as e:
        return jsonify({"ok": False, "error": type(e).__name__, "detail": str(e)}), 500

# -----------------------------------------------------------------------------
# Minimal index & health so you can test right away
# -----------------------------------------------------------------------------
INDEX_HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Lottery Optimizer</title>
  <style>
    body { font-family: system-ui, sans-serif; margin: 20px; }
    pre { background:#f6f8fa; padding:8px; border-radius:6px; }
    .card { border:1px solid #e5e7eb; border-radius:8px; padding:12px; margin-bottom:16px; }
    .row { display:flex; gap:16px; }
    .col { flex:1; }
  </style>
</head>
<body>
  <h1>Lottery Optimizer — CSV Upload Test</h1>

  <div class="card">
    <h3>Bulk import history (CSV)</h3>
    <input id="upload_csv" type="file" />
    <label><input id="upload_over" type="checkbox" checked /> Overwrite existing data</label>
    <button id="upload_btn">Import CSV</button>
    <pre id="upload_result"></pre>
  </div>

  <div class="row">
    <div class="card col">
      <h3>Test: get_by_date</h3>
      <div>Example: /store/get_by_date?game=MM&date=09/16/2025</div>
      <pre id="test1">Use your UI Phase-1 to call these routes.</pre>
    </div>
    <div class="card col">
      <h3>Test: get_history</h3>
      <div>Example: /store/get_history?game=IL_JP&from=09/15/2025&limit=20</div>
      <pre id="test2">Hook to your "Load 20" buttons.</pre>
    </div>
  </div>

  <!-- put this <script> at end so 'static/app.js' can find the elements -->
  <!-- If your project serves static files differently, adjust the path -->
  <script>
    // attach ids expected by static/app.js to avoid nulls, even in this bare index
    if(!document.getElementById("upload_csv")){
      const i=document.createElement("input"); i.type="file"; i.id="upload_csv"; document.body.appendChild(i);
    }
    if(!document.getElementById("upload_over")){
      const i=document.createElement("input"); i.type="checkbox"; i.id="upload_over"; document.body.appendChild(i);
    }
    if(!document.getElementById("upload_btn")){
      const b=document.createElement("button"); b.id="upload_btn"; b.textContent="Import CSV"; document.body.appendChild(b);
    }
    if(!document.getElementById("upload_result")){
      const p=document.createElement("pre"); p.id="upload_result"; document.body.appendChild(p);
    }
  </script>
  <!-- Load your real app.js -->
  <script src="/static/app.js"></script>
</body>
</html>
"""

@app.get("/")
def index():
    return render_template_string(INDEX_HTML)

@app.get("/health")
def health():
    return jsonify({
        "ok": True,
        "core_loaded": True,
        "store_loaded": True,
        "fetch_loaded": True,
        "core_err": None,
        "store_err": None,
        "fetch_err": None
    })

# If running locally:  python app.py
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
