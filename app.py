# app.py
from __future__ import annotations
from flask import Flask, render_template, request, jsonify
import os, traceback, json, glob, datetime as dt

# -----------------------------------------------------------------------------
# Flask setup
# -----------------------------------------------------------------------------
app = Flask(__name__, template_folder="templates", static_folder="static")

# Small helper: pad loop indices to 2 digits (01, 02, …)
@app.template_filter("pad2")
def pad2_filter(x):
    try:
        return f"{int(x):02d}"
    except Exception:
        return str(x)

# Jinja filter: right-justify a string (backup if you want to use it)
@app.template_filter("rjust")
def rjust_filter(s, width=0, fillchar=" "):
    s = "" if s is None else str(s)
    try:
        w = int(width)
    except Exception:
        w = 0
    f = str(fillchar)[0] if fillchar else " "
    return s.rjust(w, f)

# -----------------------------------------------------------------------------
# Import lottery_core safely
# -----------------------------------------------------------------------------
try:
    import lottery_core as core
except Exception as e:
    core = None
    IMPORT_ERR = f"Failed to import lottery_core.py: {e}\n\n{traceback.format_exc()}"
else:
    IMPORT_ERR = None

# -----------------------------------------------------------------------------
# Config / storage
# -----------------------------------------------------------------------------
DATA_DIR = os.environ.get("DATA_DIR", "/tmp")
BUY_DIR = os.path.join(DATA_DIR, "buylists")
os.makedirs(BUY_DIR, exist_ok=True)

ALLOWED_TEXT = {".txt", ".csv"}

def _recent_buylists(limit: int = 10):
    patt = os.path.join(BUY_DIR, "buy_session_*.json")
    files = sorted(glob.glob(patt), reverse=True)
    return [os.path.basename(p) for p in files[:limit]]

def _render_safe(res=None, error=None):
    try:
        return render_template(
            "report.html",
            res=res,
            error=error or IMPORT_ERR,
            data_dir=DATA_DIR,
            recent=_recent_buylists(20),
        )
    except Exception as e:
        # If template ever errors, show a plain page
        return f"""<h1>Template rendering error.</h1>
<pre>ERROR: {e}</pre>
<pre>TRACEBACK:\n{traceback.format_exc()}</pre>
<pre>RES:\n{repr(res)}</pre>
<pre>ORIGINAL ERROR:\n{error}</pre>""", 500

# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------
@app.route("/", methods=["GET"])
def index():
    return _render_safe(res=None, error=None)

@app.route("/upload", methods=["POST"])
def upload():
    """
    Optional helper to stash your CSV/txt inputs on the server.
    We just save them into DATA_DIR; lottery_core can read them if you make it.
    """
    if IMPORT_ERR:
        return _render_safe(error=IMPORT_ERR)

    saved = []
    try:
        for field in ("mm_hist", "pb_hist", "il_hist", "mm_feed", "pb_feed", "il_feed"):
            file = request.files.get(field)
            if not file or file.filename == "":
                continue
            name = os.path.basename(file.filename)
            _, ext = os.path.splitext(name)
            # keep any text-y file; you can harden this as you like
            if ext.lower() not in ALLOWED_TEXT:
                continue
            dst = os.path.join(DATA_DIR, name)
            file.save(dst)
            saved.append(dst)

        msg = {"uploaded": saved, "data_dir": DATA_DIR}
        return _render_safe(res={"upload": msg}, error=None)
    except Exception as e:
        return _render_safe(res=None, error=f"Upload failed: {e}\n\n{traceback.format_exc()}")

@app.route("/run_phase12", methods=["POST"])
def run_phase12():
    if IMPORT_ERR:
        return _render_safe(error=IMPORT_ERR)
    if core is None or not hasattr(core, "run_phase_1_and_2"):
        return _render_safe(error="lottery_core.run_phase_1_and_2 is missing.")

    try:
        # Parse simple inputs from the form
        def parse_mm_pb(text):
            # "[10,14,34,40,43],5"  ->  ([..], 5)
            text = (text or "").strip()
            if not text:
                return None
            mains_s, bonus_s = text.split("]")
            mains_s = mains_s.strip().lstrip("[").strip()
            mains = [int(x) for x in mains_s.split(",") if x.strip()]
            bonus = int(bonus_s.strip().lstrip(","))
            return (mains, bonus)

        def parse_il(text):
            # "[1,4,5,10,18,49]" -> [..]
            text = (text or "").strip()
            if not text:
                return None
            arr = text.strip().lstrip("[").rstrip("]")
            return [int(x) for x in arr.split(",") if x.strip()]

        cfg = {
            "LATEST_MM": parse_mm_pb(request.form.get("LATEST_MM")),
            "LATEST_PB": parse_mm_pb(request.form.get("LATEST_PB")),
            "LATEST_IL_JP": parse_il(request.form.get("LATEST_IL_JP")),
            "LATEST_IL_M1": parse_il(request.form.get("LATEST_IL_M1")),
            "LATEST_IL_M2": parse_il(request.form.get("LATEST_IL_M2")),
            "runs": int(request.form.get("runs") or 100),
            "quiet": bool(request.form.get("quiet")),
            "save_dir": BUY_DIR,
            "data_dir": DATA_DIR,
        }

        res = core.run_phase_1_and_2(cfg)
        # Attach where we saved things (for the template display)
        res = res or {}
        res.setdefault("saved_path", None)
        return _render_safe(res=res, error=None)

    except Exception as e:
        return _render_safe(res=None, error=f"Phase 1/2 failed: {e}\n\n{traceback.format_exc()}")

@app.route("/confirm_phase3", methods=["POST"])
def confirm_phase3():
    if IMPORT_ERR:
        return _render_safe(error=IMPORT_ERR)
    if core is None or not hasattr(core, "confirm_phase_3"):
        return _render_safe(error="lottery_core.confirm_phase_3 is missing.")

    try:
        saved_file = request.form.get("saved_file") or ""
        if saved_file and not os.path.isabs(saved_file):
            saved_file = os.path.join(BUY_DIR, os.path.basename(saved_file))

        def parse_mm_pb(text):
            text = (text or "").strip()
            if not text:
                return None
            mains_s, bonus_s = text.split("]")
            mains_s = mains_s.strip().lstrip("[").strip()
            mains = [int(x) for x in mains_s.split(",") if x.strip()]
            bonus = int(bonus_s.strip().lstrip(","))
            return (mains, bonus)

        def parse_il(text):
            text = (text or "").strip()
            if not text:
                return None
            arr = text.strip().lstrip("[").rstrip("]")
            return [int(x) for x in arr.split(",") if x.strip()]

        nwj = {
            "NWJ_MM": parse_mm_pb(request.form.get("NWJ_MM")),
            "NWJ_PB": parse_mm_pb(request.form.get("NWJ_PB")),
            "NWJ_IL_JP": parse_il(request.form.get("NWJ_IL_JP")),
            "NWJ_IL_M1": parse_il(request.form.get("NWJ_IL_M1")),
            "NWJ_IL_M2": parse_il(request.form.get("NWJ_IL_M2")),
        }
        recall = bool(request.form.get("recall_headings"))

        res = core.confirm_phase_3(saved_file, nwj, recall_headings=recall)
        return _render_safe(res=res, error=None)

    except Exception as e:
        return _render_safe(res=None, error=f"Phase 3 failed: {e}\n\n{traceback.format_exc()}")

# -----------------------------------------------------------------------------
# Health
# -----------------------------------------------------------------------------
@app.route("/healthz")
def health():
    return jsonify(ok=True, ts=dt.datetime.utcnow().isoformat())

# -----------------------------------------------------------------------------
# Local run
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    # Local dev: python app.py
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)
