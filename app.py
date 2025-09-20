# app.py
from flask import Flask, render_template, request
import os
import traceback

# Your core logic lives here
import lottery_core as core

app = Flask(__name__)

def _field(name: str) -> str:
    """Fetch a form field safely and trim whitespace."""
    return (request.form.get(name) or "").strip()

@app.route("/", methods=["GET"])
def home():
    # Render empty page with the form; results appear after POST /run
    return render_template("report.html", res=None, error=None)

@app.route("/run", methods=["POST"])
def run():
    """
    Handle the user submission:
      - Phase 1 & 2 always run using the provided NJ (LATEST_*) + history blobs + hot/overdue feeds.
      - If a filename and any NWJ_* values are provided, Phase 3 is also run.
    """
    try:
        # --- Inputs for Phase 1/2 (NJ + history + feeds) ----------------------
        latest_mm   = _field("latest_mm")     # e.g. "([10,14,34,40,43], 5)" or "10,14,34,40,43|5"
        latest_pb   = _field("latest_pb")     # e.g. "([14,15,32,42,49], 1)" or "14,15,32,42,49|1"
        latest_il_jp= _field("latest_il_jp")  # e.g. "1,4,5,10,18,49"
        latest_il_m1= _field("latest_il_m1")  # e.g. "6,8,10,18,26,27"
        latest_il_m2= _field("latest_il_m2")  # e.g. "2,18,21,27,43,50"

        hist_mm_blob = _field("hist_mm")      # 20-line blob, "a-b-c-d-e bb" lines
        hist_pb_blob = _field("hist_pb")
        hist_il_blob = _field("hist_il")      # 20-line blob, "a-b-c-d-e-f" lines

        feed_mm = _field("feed_mm")           # Lottery Defeated blobs (hot/overdue/bonus)
        feed_pb = _field("feed_pb")
        feed_il = _field("feed_il")

        # --- Optional Phase 3 inputs (AFTER the draw) -------------------------
        confirm_file = _field("confirm_file") # e.g. "buylists/buy_session_20250919_232850.json"

        # Accept NWJ as plain strings; lottery_core should parse them.
        nwj_mm    = _field("nwj_mm")          # e.g. "([2,7,25,30,44], 9)" or "2,7,25,30,44|9"
        nwj_pb    = _field("nwj_pb")
        nwj_il_jp = _field("nwj_il_jp")       # e.g. "2,7,25,30,44,49"
        nwj_il_m1 = _field("nwj_il_m1")
        nwj_il_m2 = _field("nwj_il_m2")

        # --- Run Phase 1 & 2 --------------------------------------------------
        res = core.run_phase_1_and_2(
            latest_mm=latest_mm,
            latest_pb=latest_pb,
            latest_il_jp=latest_il_jp,
            latest_il_m1=latest_il_m1,
            latest_il_m2=latest_il_m2,
            hist_mm_blob=hist_mm_blob,
            hist_pb_blob=hist_pb_blob,
            hist_il_blob=hist_il_blob,
            feed_mm=feed_mm,
            feed_pb=feed_pb,
            feed_il=feed_il,
        )

        # --- Run Phase 3 if requested -----------------------------------------
        if confirm_file or any([nwj_mm, nwj_pb, nwj_il_jp, nwj_il_m1, nwj_il_m2]):
            p3 = core.confirm_phase_3(
                saved_file=confirm_file,
                nwj={
                    "mm": nwj_mm,
                    "pb": nwj_pb,
                    "il_jp": nwj_il_jp,
                    "il_m1": nwj_il_m1,
                    "il_m2": nwj_il_m2,
                },
            )
            res["phase3"] = p3

        return render_template("report.html", res=res, error=None)

    except Exception as e:
        # Show a friendly error at the top of the page so users can fix inputs
        tb = traceback.format_exc()
        return render_template("report.html", res=None, error=f"{e}\n\n{tb}")

@app.route("/health", methods=["GET"])
def health():
    return {"ok": True}

if __name__ == "__main__":
    # For local testing: `python app.py` (Render will use gunicorn: app:app)
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)
