from flask import Flask, render_template, request
import lottery_core as core

app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    return render_template("report.html", res=None)

@app.route("/run", methods=["POST"])
def run():
    # Pull fields (use .get to tolerate blanks)
    latest_mm = request.form.get("latest_mm", "").strip()
    latest_pb = request.form.get("latest_pb", "").strip()
    latest_il_jp = request.form.get("latest_il_jp", "").strip()
    latest_il_m1 = request.form.get("latest_il_m1", "").strip()
    latest_il_m2 = request.form.get("latest_il_m2", "").strip()

    hist_mm = request.form.get("hist_mm", "").strip()
    hist_pb = request.form.get("hist_pb", "").strip()
    hist_il = request.form.get("hist_il", "").strip()

    feed_mm = request.form.get("feed_mm", "").strip()
    feed_pb = request.form.get("feed_pb", "").strip()
    feed_il = request.form.get("feed_il", "").strip()

    confirm_file = request.form.get("confirm_file", "").strip()
    nwj_mm = request.form.get("nwj_mm", "").strip()
    nwj_pb = request.form.get("nwj_pb", "").strip()
    nwj_il_jp = request.form.get("nwj_il_jp", "").strip()
    nwj_il_m1 = request.form.get("nwj_il_m1", "").strip()
    nwj_il_m2 = request.form.get("nwj_il_m2", "").strip()

    # Run the core (your core already tolerates blanks)
    result = core.run_phase_1_and_2(
        latest_mm=latest_mm,
        latest_pb=latest_pb,
        latest_il_jp=latest_il_jp,
        latest_il_m1=latest_il_m1,
        latest_il_m2=latest_il_m2,
        hist_mm_blob=hist_mm,
        hist_pb_blob=hist_pb,
        hist_il_blob=hist_il,
        feed_mm=feed_mm,
        feed_pb=feed_pb,
        feed_il=feed_il,
    )

    # If the user provided NWJ and/or a saved file, also do Phase 3
    if confirm_file or any([nwj_mm, nwj_pb, nwj_il_jp, nwj_il_m1, nwj_il_m2]):
        confirm = core.confirm_phase_3(
            saved_file=confirm_file,
            nwj={
                "mm": nwj_mm,
                "pb": nwj_pb,
                "il_jp": nwj_il_jp,
                "il_m1": nwj_il_m1,
                "il_m2": nwj_il_m2,
            }
        )
        result["phase3"] = confirm

    return render_template("report.html", res=result)
