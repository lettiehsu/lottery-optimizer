from __future__ import annotations
import os, io, json, subprocess, shlex
from datetime import datetime
from flask import Flask, request, render_template, send_file, redirect, url_for, flash

# ── basic settings
APP_KEY = os.getenv("APP_KEY", "")           # optional: set in Render → Environment
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
BUY_DIR  = os.path.join(BASE_DIR, "buylists")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(BUY_DIR,  exist_ok=True)

# ── import your core (with 2 small adapter functions you’ll paste below)
import lottery_core as core

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "dev-secret")  # for flash()

def require_key():
    if APP_KEY and request.headers.get("X-App-Key") != APP_KEY:
        return "Unauthorized (missing/invalid X-App-Key)", 401

@app.route("/", methods=["GET"])
def index():
    # list recent buy_session files (sorted newest first)
    recent = sorted(
        [f for f in os.listdir(BUY_DIR) if f.startswith("buy_session_") and f.endswith(".json")],
        reverse=True
    )[:20]
    return render_template("index.html", recent=recent)

# ────────────────────────────────────────────────────────────────────────────────
# Upload CSVs for histories & feeds
# ────────────────────────────────────────────────────────────────────────────────
@app.route("/upload", methods=["POST"])
def upload():
    if (resp := require_key()):
        return resp

    # You can upload any of these (all optional)
    mapping = {
        "hist_mm": "hist_mm.csv",
        "hist_pb": "hist_pb.csv",
        "hist_il": "hist_il.csv",
        "feed_mm": "feed_mm.txt",
        "feed_pb": "feed_pb.txt",
        "feed_il": "feed_il.txt",
    }
    saved = []
    for form_key, filename in mapping.items():
        file = request.files.get(form_key)
        if file and file.filename:
            path = os.path.join(DATA_DIR, filename)
            file.save(path)
            saved.append(filename)
    if not saved:
        flash("No files selected.")
    else:
        flash(f"Uploaded: {', '.join(saved)}")
    return redirect(url_for("index"))

# ────────────────────────────────────────────────────────────────────────────────
# Phase 1 & 2 — generate + simulate
# ────────────────────────────────────────────────────────────────────────────────
@app.route("/run", methods=["POST"])
def run_generate_sim():
    if (resp := require_key()):
        return resp

    # NJ inputs (all optional; your core has defaults if omitted)
    payload = {
        "LATEST_MM": request.form.get("LATEST_MM", "").strip(),
        "LATEST_PB": request.form.get("LATEST_PB", "").strip(),
        "LATEST_IL_JP": request.form.get("LATEST_IL_JP", "").strip(),
        "LATEST_IL_M1": request.form.get("LATEST_IL_M1", "").strip(),
        "LATEST_IL_M2": request.form.get("LATEST_IL_M2", "").strip(),
        "runs": int(request.form.get("runs", "100") or 100),
        "quiet": request.form.get("quiet", "on") == "on",
    }

    # Call into your core adapter
    report_text, saved_json_path = core.web_phase12(DATA_DIR, BUY_DIR, payload)

    # show the nicely formatted page, with a download of the raw text
    return render_template("report.html",
                           title="Phase 1 & 2 — Results",
                           pre=report_text,
                           saved_json=os.path.basename(saved_json_path) if saved_json_path else None)

# ────────────────────────────────────────────────────────────────────────────────
# Phase 3 — confirm a specific saved buy list against NWJ
# ────────────────────────────────────────────────────────────────────────────────
@app.route("/confirm", methods=["POST"])
def confirm():
    if (resp := require_key()):
        return resp

    filename = request.form.get("confirm_file")  # e.g. buy_session_20250920_000900.json
    if not filename:
        flash("Please choose a saved buy list file.")
        return redirect(url_for("index"))

    nwj = {
        "NWJ_MM": request.form.get("NWJ_MM", "").strip(),
        "NWJ_PB": request.form.get("NWJ_PB", "").strip(),
        "NWJ_IL_JP": request.form.get("NWJ_IL_JP", "").strip(),
        "NWJ_IL_M1": request.form.get("NWJ_IL_M1", "").strip(),
        "NWJ_IL_M2": request.form.get("NWJ_IL_M2", "").strip(),
        "recall_phase12": request.form.get("recall_phase12", "on") == "on",
    }

    # Call into your core adapter
    report_text = core.web_phase3(DATA_DIR, BUY_DIR, filename, nwj)

    return render_template("report.html",
                           title="Phase 3 — Confirmation",
                           pre=report_text,
                           saved_json=filename)

# ────────────────────────────────────────────────────────────────────────────────
# Download helper (raw file)
# ────────────────────────────────────────────────────────────────────────────────
@app.route("/download/<path:fname>", methods=["GET"])
def download(fname):
    # security: serve only from buylists/
    safe = os.path.normpath(fname)
    if ".." in safe or safe.startswith("/"):
        return "Invalid filename", 400
    full = os.path.join(BUY_DIR, safe)
    if not os.path.exists(full):
        return "Not found", 404
    return send_file(full, as_attachment=True)

# ────────────────────────────────────────────────────────────────────────────────
# Health
# ────────────────────────────────────────────────────────────────────────────────
@app.route("/health", methods=["GET"])
def health():
    return {"ok": True, "time": datetime.utcnow().isoformat()}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "10000")))
