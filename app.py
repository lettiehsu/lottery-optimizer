# app.py
from flask import Flask, render_template, request, jsonify
import os, traceback

app = Flask(__name__, template_folder="templates", static_folder="static")

@app.template_filter("rjust")
def rjust_filter(s, width=0, fillchar=" "):
    # Jinja filter to right-justify strings (like Python's str.rjust)
    s = "" if s is None else str(s)
    try:
        w = int(width)
    except Exception:
        w = 0
    f = str(fillchar)[0] if fillchar else " "
    return s.rjust(w, f)


# ── Import lottery_core safely ────────────────────────────────────────────────
try:
    import lottery_core as core
except Exception as e:
    core = None
    IMPORT_ERR = f"Failed to import lottery_core.py: {e}\n\n{traceback.format_exc()}"
else:
    IMPORT_ERR = None

def _field(name: str) -> str:
    return (request.form.get(name) or "").strip()

def _render_safe(res=None, error=None):
    """Render report.html; if template errors, fall back to plain text."""
    try:
        return render_template("report.html", res=res, error=error)
    except Exception as te:
        tb = traceback.format_exc()
        return (
            "Template rendering error.\n\n"
            f"ERROR: {te}\n\n"
            f"TRACEBACK:\n{tb}\n\n"
            f"RES:\n{res}\n\n"
            f"ORIGINAL ERROR:\n{error}"
        ), 500, {"Content-Type": "text/plain; charset=utf-8"}

@app.route("/", methods=["GET"])
def home():
    if IMPORT_ERR:
        return _render_safe(res=None, error=IMPORT_ERR)
    return _render_safe(res=None, error=None)

@app.route("/run", methods=["POST"])
def run():
    if IMPORT_ERR:
        return _render_safe(res=None, error=IMPORT_ERR)

    try:
        # ----- Phase 1/2 inputs (strings are OK; core parses them) -------------
        latest_mm    = _field("latest_mm")      # "10,14,34,40,43|5" or "([10,14,34,40,43], 5)"
        latest_pb    = _field("latest_pb")      # "14,15,32,42,49|1"
        latest_il_jp = _field("latest_il_jp")   # "1,4,5,10,18,49"
        latest_il_m1 = _field("latest_il_m1")   # "6,8,10,18,26,27"
        latest_il_m2 = _field("latest_il_m2")   # "2,18,21,27,43,50"

        hist_mm_blob = _field("hist_mm")        # 20 lines "a-b-c-d-e bb"
        hist_pb_blob = _field("hist_pb")
        hist_il_blob = _field("hist_il")        # 20 lines "a-b-c-d-e-f"

        feed_mm = _field("feed_mm")             # “Top 8 hot numbers: …”
        feed_pb = _field("feed_pb")
        feed_il = _field("feed_il")

        # Provide minimal safe defaults if the form left them blank
        if not latest_mm:    latest_mm = "10,14,34,40,43|5"
        if not latest_pb:    latest_pb = "14,15,32,42,49|1"
        if not latest_il_jp: latest_il_jp = "1,4,5,10,18,49"
        if not latest_il_m1: latest_il_m1 = "6,8,10,18,26,27"
        if not latest_il_m2: latest_il_m2 = "2,18,21,27,43,50"

        if not hist_mm_blob:
            hist_mm_blob = "17-18-21-42-64 07\n06-43-52-64-65 22\n06-14-36-58-62 24\n07-17-35-40-64 23\n13-31-32-44-45 21\n07-12-30-40-69 17\n18-30-44-48-50 12\n10-19-24-49-68 10\n04-17-27-34-69 16\n01-08-31-56-67 23\n02-06-08-14-49 12\n12-27-42-59-65 02\n18-27-29-33-70 22\n17-30-34-63-67 11\n14-21-25-49-52 07\n22-41-42-59-69 17\n11-43-54-55-63 03\n06-10-24-35-43 01\n12-23-24-31-56 01\n04-06-38-44-62 24"
        if not hist_pb_blob:
            hist_pb_blob = "28-37-42-50-53 19\n02-24-45-53-64 05\n26-28-41-53-64 09\n11-23-44-61-62 17\n03-16-29-61-69 22\n08-23-25-40-53 05\n03-18-22-27-33 17\n09-12-22-41-61 25\n16-19-34-37-64 22\n11-14-34-47-51 18\n31-59-62-65-68 05\n15-46-61-63-64 01\n23-40-49-65-69 23\n04-11-40-44-50 04\n06-16-33-40-62 02\n07-14-23-24-60 14\n15-27-43-45-53 09\n08-09-19-31-38 21\n06-18-34-35-36 02\n04-15-35-50-64 08"
        if not hist_il_blob:
            hist_il_blob = "05-06-14-15-48-49\n01-08-12-27-30-43\n05-07-20-26-34-40\n11-12-29-42-44-47\n01-16-20-29-30-49\n12-14-20-21-23-43\n06-07-11-15-41-50\n05-12-18-19-34-47\n05-09-14-18-22-23\n02-11-15-17-32-34\n09-17-20-24-41-44\n01-04-06-13-17-27\n03-26-31-36-41-45\n09-12-16-17-25-44\n09-17-22-30-42-45\n04-12-31-32-39-40\n14-17-19-32-34-42\n03-10-11-30-36-41\n04-18-31-39-45-48\n03-06-11-16-32-36"

        if not feed_mm:
            feed_mm = "Top 8 hot numbers: 10, 40, 6, 17, 24, 18, 16, 49\nTop 8 overdue numbers: 53, 3, 5, 15, 51, 9, 66, 37\nTop 3 hot Mega Ball numbers: 1, 24, 2\nTop 3 overdue Mega Ball numbers: 4, 6, 15"
        if not feed_pb:
            feed_pb = "Top 8 hot numbers: 23, 61, 35, 28, 43, 62, 64, 52\nTop 8 overdue numbers: 66, 39, 20, 10, 56, 30, 17, 32\nTop 3 hot Power Ball numbers: 25, 5, 2\nTop 3 overdue Power Ball numbers: 16, 26, 7"
        if not feed_il:
            feed_il = "Top 8 hot numbers: 17, 20, 22, 14, 5, 1, 6, 3\nTop 8 overdue numbers: 28, 35, 46, 38, 33, 37, 39, 25"

        # ----- Phase 3 (optional) ---------------------------------------------
        confirm_file = _field("confirm_file")
        nwj_mm    = _field("nwj_mm")      # "a,b,c,d,e|b"
        nwj_pb    = _field("nwj_pb")
        nwj_il_jp = _field("nwj_il_jp")   # "a,b,c,d,e,f"
        nwj_il_m1 = _field("nwj_il_m1")
        nwj_il_m2 = _field("nwj_il_m2")

        # Run Phase 1 & 2
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

        # Run Phase 3 if any NWJ or file is provided
        if confirm_file or any([nwj_mm, nwj_pb, nwj_il_jp, nwj_il_m1, nwj_il_m2]):
            if not hasattr(core, "confirm_phase_3"):
                raise RuntimeError("lottery_core.confirm_phase_3(...) not found.")
            res["phase3"] = core.confirm_phase_3(
                saved_file=confirm_file,
                nwj={"mm": nwj_mm, "pb": nwj_pb, "il_jp": nwj_il_jp, "il_m1": nwj_il_m1, "il_m2": nwj_il_m2},
            )

        return _render_safe(res=res, error=None)

    except Exception as e:
        tb = traceback.format_exc()
        return _render_safe(res=None, error=f"{e}\n\n{tb}")

@app.route("/health", methods=["GET"])
def health():
    if IMPORT_ERR:
        return jsonify(ok=False, error=IMPORT_ERR), 500
    return jsonify(ok=True)

@app.route("/debug_sanity", methods=["GET"])
def debug_sanity():
    """
    Quick JSON sanity check: runs Phase 1/2 with built-in defaults.
    Doesn’t touch templates. If this works, the stack is OK and any 500s are in your form/template inputs.
    """
    if IMPORT_ERR:
        return jsonify(ok=False, error=IMPORT_ERR), 500

    try:
        res = core.run_phase_1_and_2(
            latest_mm="10,14,34,40,43|5",
            latest_pb="14,15,32,42,49|1",
            latest_il_jp="1,4,5,10,18,49",
            latest_il_m1="6,8,10,18,26,27",
            latest_il_m2="2,18,21,27,43,50",
            hist_mm_blob="17-18-21-42-64 07\n06-43-52-64-65 22\n06-14-36-58-62 24\n07-17-35-40-64 23\n13-31-32-44-45 21\n07-12-30-40-69 17\n18-30-44-48-50 12\n10-19-24-49-68 10\n04-17-27-34-69 16\n01-08-31-56-67 23\n02-06-08-14-49 12\n12-27-42-59-65 02\n18-27-29-33-70 22\n17-30-34-63-67 11\n14-21-25-49-52 07\n22-41-42-59-69 17\n11-43-54-55-63 03\n06-10-24-35-43 01\n12-23-24-31-56 01\n04-06-38-44-62 24",
            hist_pb_blob="28-37-42-50-53 19\n02-24-45-53-64 05\n26-28-41-53-64 09\n11-23-44-61-62 17\n03-16-29-61-69 22\n08-23-25-40-53 05\n03-18-22-27-33 17\n09-12-22-41-61 25\n16-19-34-37-64 22\n11-14-34-47-51 18\n31-59-62-65-68 05\n15-46-61-63-64 01\n23-40-49-65-69 23\n04-11-40-44-50 04\n06-16-33-40-62 02\n07-14-23-24-60 14\n15-27-43-45-53 09\n08-09-19-31-38 21\n06-18-34-35-36 02\n04-15-35-50-64 08",
            hist_il_blob="05-06-14-15-48-49\n01-08-12-27-30-43\n05-07-20-26-34-40\n11-12-29-42-44-47\n01-16-20-29-30-49\n12-14-20-21-23-43\n06-07-11-15-41-50\n05-12-18-19-34-47\n05-09-14-18-22-23\n02-11-15-17-32-34\n09-17-20-24-41-44\n01-04-06-13-17-27\n03-26-31-36-41-45\n09-12-16-17-25-44\n09-17-22-30-42-45\n04-12-31-32-39-40\n14-17-19-32-34-42\n03-10-11-30-36-41\n04-18-31-39-45-48\n03-06-11-16-32-36",
            feed_mm="Top 8 hot numbers: 10, 40, 6, 17, 24, 18, 16, 49\nTop 8 overdue numbers: 53, 3, 5, 15, 51, 9, 66, 37\nTop 3 hot Mega Ball numbers: 1, 24, 2\nTop 3 overdue Mega Ball numbers: 4, 6, 15",
            feed_pb="Top 8 hot numbers: 23, 61, 35, 28, 43, 62, 64, 52\nTop 8 overdue numbers: 66, 39, 20, 10, 56, 30, 17, 32\nTop 3 hot Power Ball numbers: 25, 5, 2\nTop 3 overdue Power Ball numbers: 16, 26, 7",
            feed_il="Top 8 hot numbers: 17, 20, 22, 14, 5, 1, 6, 3\nTop 8 overdue numbers: 28, 35, 46, 38, 33, 37, 39, 25",
        )
        return jsonify(ok=True, res=res)
    except Exception as e:
        return jsonify(ok=False, error=f"{e}", traceback=traceback.format_exc()), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)
