# app.py
from __future__ import annotations
import os, json, re, traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from flask import (
    Flask, request, render_template, jsonify, send_from_directory
)

# ──────────────────────────────────────────────────────────────────────────────
# Flask setup
# ──────────────────────────────────────────────────────────────────────────────
app = Flask(__name__, template_folder="templates", static_folder="static")

# Where we save CSVs/feeds and buy_session_*.json files
DATA_DIR = Path(os.environ.get("DATA_DIR", "/tmp"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
(BUY_DIR := DATA_DIR / "buylists").mkdir(parents=True, exist_ok=True)

# ──────────────────────────────────────────────────────────────────────────────
# Jinja filters used by templates
# ──────────────────────────────────────────────────────────────────────────────
@app.template_filter("rjust")
def jinja_rjust(value, width: int = 0, fillchar: str = " "):
    s = "" if value is None else str(value)
    try:
        w = int(width)
    except Exception:
        w = 0
    f = (str(fillchar) or " ")[0]
    return s.rjust(w, f)

@app.template_filter("pad2")
def jinja_pad2(value):
    return ("" if value is None else str(value)).rjust(2, "0")

# ──────────────────────────────────────────────────────────────────────────────
# Import core safely (so the site still loads even if core has a bug)
# ──────────────────────────────────────────────────────────────────────────────
try:
    import lottery_core as core  # must expose run_phase_1_and_2 / confirm_phase_3
    IMPORT_ERR = None
except Exception as e:
    core = None  # type: ignore
    IMPORT_ERR = f"Failed to import lottery_core.py: {e}\n\n{traceback.format_exc()}"

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────
_NUM = r"-?\d+"
_LIST = rf"\[\s*(?:{_NUM}\s*(?:,\s*{_NUM}\s*)*)?\]"
_TUP  = rf"\(\s*({_LIST})\s*,\s*({_NUM})\s*\)"

def _clean(s: str) -> str:
    return (s or "").strip()

def parse_main_list(s: str) -> Optional[List[int]]:
    """
    Accepts forms like:
      [1,2,3,4,5]   or  1,2,3,4,5  or  "1 2 3 4 5"
    Returns list[int] or None if empty.
    """
    s = _clean(s)
    if not s:
        return None
    if s.startswith("[") and s.endswith("]"):
        s = s[1:-1]
    s = s.replace(";", ",").replace("|", ",").replace("/", ",")
    s = re.sub(r"\s+", ",", s)
    nums = [x for x in (p.strip() for p in s.split(",")) if x]
    try:
        out = [int(x) for x in nums]
    except Exception:
        return None
    return out or None

def parse_combo_with_bonus(s: str) -> Optional[Tuple[List[int], int]]:
    """
    Accepts:
      ([10,14,34,40,43], 5)
      [10,14,34,40,43],5
      10,14,34,40,43; 5
    """
    s = _clean(s)
    if not s:
        return None
    # Try strict tuple pattern first
    m = re.fullmatch(_TUP, s.replace(" ", ""))
    if m:
        mains_raw, bonus_raw = m.group(1), m.group(2)
        mains = parse_main_list(mains_raw)
        if mains is None:
            return None
        return (mains, int(bonus_raw))
    # Fallback: split on last comma/space/semicolon
    parts = re.split(r"[,\s;]+", s)
    if len(parts) < 2:
        return None
    *main_parts, bonus_part = parts
    mains = parse_main_list(",".join(main_parts))
    if mains is None:
        return None
    try:
        bonus = int(bonus_part)
    except Exception:
        return None
    return (mains, bonus)

def recent_buy_files(limit: int = 20) -> List[str]:
    files = sorted((p for p in BUY_DIR.glob("buy_session_*.json")),
                   key=lambda p: p.stat().st_mtime,
                   reverse=True)
    return [str(p) for p in files[:limit]]

def _render_safe(res: Optional[Dict[str, Any]] = None, error: Optional[str] = None):
    return render_template("report.html",
                           res=res,
                           error=error or IMPORT_ERR,
                           recent_files=[Path(p).name for p in recent_buy_files()])

def _need_core():
    if core is None:
        return _render_safe(error="Core module (lottery_core.py) did not import. "
                                  "Open the page to see the error at the top.")
    return None

# ──────────────────────────────────────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────────────────────────────────────
@app.get("/")
def home():
    """Main UI."""
    return _render_safe()

@app.get("/health")
def health():
    return jsonify(ok=True)

@app.post("/upload")
def upload_files():
    """
    Optional CSV/txt uploads. Saves under DATA_DIR and returns filenames.
    Accepts up to these field names (all optional):
      mm_hist, pb_hist, il_hist (CSV)
      mm_feed, pb_feed, il_feed (txt)
    """
    files = {}
    for key in ["mm_hist", "pb_hist", "il_hist", "mm_feed", "pb_feed", "il_feed"]:
        f = request.files.get(key)
        if not f or f.filename == "":
            continue
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", f.filename)
        dest = DATA_DIR / safe_name
        f.save(dest)
        files[key] = str(dest)
    return jsonify(saved=files, data_dir=str(DATA_DIR))

@app.post("/run12")
def run12():
    """Run Phase 1 & 2 with form values; saves a buy_session_*.json in DATA_DIR/buylists."""
    need = _need_core()
    if need: return need

    # Read latest jackpots (NJ) from form
    latest_mm = parse_combo_with_bonus(request.form.get("LATEST_MM", ""))
    latest_pb = parse_combo_with_bonus(request.form.get("LATEST_PB", ""))
    latest_il_jp = parse_main_list(request.form.get("LATEST_IL_JP", ""))
    latest_il_m1 = parse_main_list(request.form.get("LATEST_IL_M1", ""))
    latest_il_m2 = parse_main_list(request.form.get("LATEST_IL_M2", ""))

    # Simulation settings
    try:
        runs = int(request.form.get("runs", "100"))
    except Exception:
        runs = 100
    quiet = request.form.get("quiet", "on") in ("on", "true", "1")

    # Optional uploaded feed/history paths (not required)
    cfg: Dict[str, Any] = {
        "DATA_DIR": str(DATA_DIR),
        "BUY_DIR": str(BUY_DIR),
        "runs": runs,
        "quiet": quiet,
        # LATEST_* (NJ)
        "LATEST_MM": latest_mm,
        "LATEST_PB": latest_pb,
        "LATEST_IL_JP": latest_il_jp,
        "LATEST_IL_M1": latest_il_m1,
        "LATEST_IL_M2": latest_il_m2,
        # Uploaded files (UI may or may not send them)
        "mm_hist_csv": request.form.get("mm_hist_csv") or None,
        "pb_hist_csv": request.form.get("pb_hist_csv") or None,
        "il_hist_csv": request.form.get("il_hist_csv") or None,
        "mm_feed_txt": request.form.get("mm_feed_txt") or None,
        "pb_feed_txt": request.form.get("pb_feed_txt") or None,
        "il_feed_txt": request.form.get("il_feed_txt") or None,
    }

    try:
        res = core.run_phase_1_and_2(cfg)  # type: ignore[attr-defined]
    except Exception as e:
        return _render_safe(error=f"run_phase_1_and_2 crashed: {e}\n\n{traceback.format_exc()}")

    return _render_safe(res=res)

@app.post("/confirm3")
def confirm3():
    """Phase 3 confirmation against a specific saved buy_session_*.json and NWJ values."""
    need = _need_core()
    if need: return need

    # Which saved file?
    fname = request.form.get("saved_file") or ""
    if fname and not fname.startswith("/"):
        # allow passing just the filename from the dropdown
        fname = str(BUY_DIR / fname)

    # NWJ fields — each optional; if omitted, core may fallback to LATEST_* if configured
    nwj_mm   = parse_combo_with_bonus(request.form.get("NWJ_MM", ""))
    nwj_pb   = parse_combo_with_bonus(request.form.get("NWJ_PB", ""))
    nwj_il_jp  = parse_main_list(request.form.get("NWJ_IL_JP", ""))
    nwj_il_m1  = parse_main_list(request.form.get("NWJ_IL_M1", ""))
    nwj_il_m2  = parse_main_list(request.form.get("NWJ_IL_M2", ""))

    # Whether to also recall Phase1/2 headings printed in that saved file
    recall_p12 = request.form.get("recall_p12", "on") in ("on", "true", "1")

    nwj: Dict[str, Any] = {
        "MM": nwj_mm, "PB": nwj_pb,
        "IL_JP": nwj_il_jp, "IL_M1": nwj_il_m1, "IL_M2": nwj_il_m2,
        "recall_p12": recall_p12,
    }

    try:
        res = core.confirm_phase_3(saved_file=fname, nwj=nwj)  # type: ignore[attr-defined]
    except Exception as e:
        return _render_safe(error=f"confirm_phase_3 crashed: {e}\n\n{traceback.format_exc()}")

    return _render_safe(res=res)

# Serve saved JSONs if you want to download them from the UI
@app.get("/buylists/<path:name>")
def get_buylist(name: str):
    return send_from_directory(str(BUY_DIR), name, as_attachment=True)

# ──────────────────────────────────────────────────────────────────────────────
# Error pages
# ──────────────────────────────────────────────────────────────────────────────
@app.errorhandler(500)
def err_500(e):
    return _render_safe(error=f"500 Internal Server Error:\n\n{e}\n\n{traceback.format_exc()}"), 500

@app.errorhandler(404)
def err_404(e):
    return _render_safe(error="404 Not Found"), 404

# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Local dev
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=True)
