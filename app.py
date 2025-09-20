# app.py
from __future__ import annotations
from flask import Flask, render_template, request, jsonify
import os, json, traceback, datetime as dt
from werkzeug.utils import secure_filename

# ──────────────────────────────────────────────────────────────────────────────
# Flask / templating
# ──────────────────────────────────────────────────────────────────────────────
app = Flask(__name__, template_folder="templates", static_folder="static")

# Jinja filter: right-justify strings like Python's str.rjust
@app.template_filter("rjust")
def rjust_filter(s, width=0, fillchar=" "):
    s = "" if s is None else str(s)
    try:
        w = int(width)
    except Exception:
        w = 0
    f = str(fillchar)[0] if fillchar else " "
    return s.rjust(w, f)

# Optional: zero-pad 2 digits
@app.template_filter("pad2")
def pad2(n):
    try:
        return f"{int(n):02d}"
    except Exception:
        return str(n)

# ──────────────────────────────────────────────────────────────────────────────
# Import lottery_core safely
# ──────────────────────────────────────────────────────────────────────────────
try:
    import lottery_core as core
except Exception as e:
    core = None
    IMPORT_ERR = f"Failed to import lottery_core.py: {e}\n\n{traceback.format_exc()}"
else:
    IMPORT_ERR = None

# ──────────────────────────────────────────────────────────────────────────────
# Config / storage dirs
# ──────────────────────────────────────────────────────────────────────────────
DATA_DIR = os.environ.get("DATA_DIR", "/tmp")
BUY_DIR  = os.path.join(DATA_DIR, "buylists")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(BUY_DIR,  exist_ok=True)

ALLOWED_TXT = {"txt", "csv"}

def _ok_ext(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_TXT

# ──────────────────────────────────────────────────────────────────────────────
# Helpers to parse tiny inputs coming from the form
# ──────────────────────────────────────────────────────────────────────────────
def _parse_list_ints(s: str) -> list[int]:
    """Parse '1,2,3,4' or '[1,2,3,4]' into [1,2,3,4]."""
    if not s:
        return []
    s = s.strip()
    try:
        # allow JSON-style
        if s.startswith("[") and s.endswith("]"):
            return [int(x) for x in json.loads(s)]
    except Exception:
        pass
    # fallback: split by comma
    parts = [p.strip() for p in s.split(",") if p.strip()]
    out = []
    for p in parts:
        try:
            out.append(int(p))
        except Exception:
            pass
    return out

def _parse_mm_pb_pair(s: str) -> tuple[list[int], int] | None:
    """
    Accepts:
      '[14,15,32,42,49],1'
      '([14,15,32,42,49],1)'
      '14,15,32,42,49 | 1'
    Returns (mains, bonus) or None.
    """
    if not s:
        return None
    raw = s.strip().strip("()")
    if "|" in raw:
        left, right = raw.split("|", 1)
        mains = _parse_list_ints(left)
        try:
            bonus = int(right.strip())
        except Exception:
            return None
        return (mains, bonus)
    if "," in raw and raw.count("[") == 1:
        # like '[..],1'
        left, right = raw.split("]", 1)
        mains = _parse_list_ints(left + "]")
        right = right.strip().lstrip(",").strip()
        try:
            bonus = int(right)
        except Exception:
            return None
        return (mains, bonus)
    # last resort: JSON
    try:
        j = json.loads(raw)
        if isinstance(j, list) and len(j) == 2 and isinstance(j[0], list):
            return ( [int(x) for x in j[0]], int(j[1]) )
    except Exception:
        pass
    return None

def _parse_il_list(s: str) -> list[int] | None:
    """Accept '[1,4,5,10,18,49]' -> list or '' -> None."""
    lst = _parse_list_ints(s or "")
    return lst or None

def _recent_buylists(n: int = 10) -> list[str]:
    try:
        files = [f for f in os.listdir(BUY_DIR) if f.startswith("buy_session_") and f.endswith(".json")]
        files.sort(reverse=True)
        return files[:n]
    except Exception:
        return []

# ──────────────────────────────────────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────────────────────────────────────
@app.route("/", methods=["GET"])
def index():
    return render_template(
        "report.html",
        res=None,
        error=IMPORT_ERR,
        recent=_recent_buylists(),
        data_dir=DATA_DIR,
    )

@app.post("/upload")
def upload():
    """Uploads optional history/feed files (just stores them)."""
    if IMPORT_ERR:
        return jsonify({"ok": False, "error": IMPORT_ERR}), 500

    saved = []
    for field in ["mm_hist", "pb_hist", "il_hist", "mm_feed", "pb_feed", "il_feed"]:
        f = request.files.get(field)
        if not f or f.filename == "":
            continue
        if not _ok_ext(f.filename):
            return jsonify({"ok": False, "error": f"Bad extension for {f.filename}"}), 400
        safe = secure_filename(f.filename)
        path = os.path.join(DATA_DIR, safe)
        f.save(path)
        saved.append(path)

    return jsonify({"ok": True, "saved": saved})

@app.post("/run_phase12")
def run_phase12():
    """Generate 50-row batches, print Phase-1 hits, simulate Phase-2, and save buy list JSON."""
    if IMPORT_ERR:
        return render_template("report.html", res=None, error=IMPORT_ERR, recent=_recent_buylists(), data_dir=DATA_DIR)

    # Pull LATEST_* from form
    latest_mm = _parse_mm_pb_pair(request.form.get("LATEST_MM", "").strip())
    latest_pb = _parse_mm_pb_pair(request.form.get("LATEST_PB", "").strip())
    latest_il_jp = _parse_il_list(request.form.get("LATEST_IL_JP", "").strip())
    latest_il_m1 = _parse_il_list(request.form.get("LATEST_IL_M1", "").strip())
    latest_il_m2 = _parse_il_list(request.form.get("LATEST_IL_M2", "").strip())

    runs = request.form.get("runs", "100").strip()
    try:
        runs = max(1, min(500, int(runs)))
    except Exception:
        runs = 100

    quiet = bool(request.form.get("quiet"))  # checkbox

    config = {
        "LATEST_MM": latest_mm,
        "LATEST_PB": latest_pb,
        "LATEST_IL_JP": latest_il_jp,
        "LATEST_IL_M1": latest_il_m1,
        "LATEST_IL_M2": latest_il_m2,
        "runs": runs,
        "quiet": quiet,
        "DATA_DIR": DATA_DIR,
        "BUY_DIR": BUY_DIR,
    }

    try:
        result = core.run_phase_1_and_2(config)
    except Exception as e:
        err = f"run_phase_1_and_2 crashed: {e}\n\n{traceback.format_exc()}"
        return render_template("report.html", res=None, error=err, recent=_recent_buylists(), data_dir=DATA_DIR)

    return render_template("report.html", res=result, error=None, recent=_recent_buylists(), data_dir=DATA_DIR)

@app.post("/confirm_phase3")
def confirm_phase3():
    """Confirmation-only vs NWJ for a previously saved JSON (exact tickets)."""
    if IMPORT_ERR:
        return render_template("report.html", res=None, error=IMPORT_ERR, recent=_recent_buylists(), data_dir=DATA_DIR)

    filename = request.form.get("saved_file", "").strip()
    saved_path = os.path.join(BUY_DIR, os.path.basename(filename)) if filename else ""

    # NWJ fields (all optional)
    nwj_mm = _parse_mm_pb_pair(request.form.get("NWJ_MM", "").strip())
    nwj_pb = _parse_mm_pb_pair(request.form.get("NWJ_PB", "").strip())
    nwj_il_jp = _parse_il_list(request.form.get("NWJ_IL_JP", "").strip())
    nwj_il_m1 = _parse_il_list(request.form.get("NWJ_IL_M1", "").strip())
    nwj_il_m2 = _parse_il_list(request.form.get("NWJ_IL_M2", "").strip())

    recall_headings = bool(request.form.get("recall_headings"))

    nwj = {
        "NWJ_MM": nwj_mm,
        "NWJ_PB": nwj_pb,
        "NWJ_IL_JP": nwj_il_jp,
        "NWJ_IL_M1": nwj_il_m1,
        "NWJ_IL_M2": nwj_il_m2,
        "recall_headings": recall_headings,
        "BUY_DIR": BUY_DIR,
    }

    try:
        result = core.confirm_phase_3(saved_path, nwj)
    except Exception as e:
        err = f"confirm_phase_3 crashed: {e}\n\n{traceback.format_exc()}"
        return render_template("report.html", res=None, error=err, recent=_recent_buylists(), data_dir=DATA_DIR)

    return render_template("report.html", res=result, error=None, recent=_recent_buylists(), data_dir=DATA_DIR)

# ──────────────────────────────────────────────────────────────────────────────
# Simple health route for Render
# ──────────────────────────────────────────────────────────────────────────────
@app.get("/healthz")
def healthz():
    return jsonify({"ok": True, "time": dt.datetime.utcnow().isoformat() + "Z"})

# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Local dev only
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=True)
