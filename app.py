# app.py
from flask import Flask, render_template, request, jsonify
import os, json, traceback

app = Flask(__name__, template_folder="templates", static_folder="static")

# Jinja filter: right-justify numbers as strings
@app.template_filter("rjust")
def rjust_filter(value, width=0, fillchar=" "):
    s = "" if value is None else str(value)
    try:
        w = int(width)
    except Exception:
        w = 0
    f = (str(fillchar) or " ")[0]
    return s.rjust(w, f)

# Try to import core; keep page alive if it fails
try:
    import lottery_core as core
    IMPORT_ERR = None
except Exception as e:
    core = None
    IMPORT_ERR = f"Failed to import lottery_core.py: {e}\n\n{traceback.format_exc()}"

def _render_safe(res=None, error=None):
    """Render the report page even when errors happen."""
    try:
        return render_template("report.html", res=res, error=error, import_err=IMPORT_ERR)
    except Exception as e:
        # Last-ditch fallback: show a plain page but still with some info
        return f"""
        <h1>Lottery Optimizer — Report</h1>
        <p><strong>Template rendering error.</strong></p>
        <pre>{traceback.format_exc()}</pre>
        <hr/>
        <h3>RES:</h3>
        <pre>{res!r}</pre>
        <h3>ORIGINAL ERROR:</h3>
        <pre>{error!r}</pre>
        """, 200, {"Content-Type":"text/html; charset=utf-8"}

@app.get("/")
def index():
    return _render_safe()

@app.post("/run-phase12")
def run_phase12():
    try:
        if IMPORT_ERR:
            raise RuntimeError(IMPORT_ERR)
        payload = request.form.to_dict()
        # core function returns a dict
        res = core.run_phase_1_and_2(payload)
        return _render_safe(res=res)
    except Exception as e:
        return _render_safe(error=f"{e}\n\n{traceback.format_exc()}")

@app.post("/confirm-phase3")
def confirm_phase3():
    try:
        if IMPORT_ERR:
            raise RuntimeError(IMPORT_ERR)
        payload = request.form.to_dict()
        res = core.confirm_phase_3(payload)
        return _render_safe(res=res)
    except Exception as e:
        return _render_safe(error=f"{e}\n\n{traceback.format_exc()}")

# Render-friendly JSON (optional)
@app.post("/api/run-phase12")
def api_run_phase12():
    try:
        if IMPORT_ERR:
            raise RuntimeError(IMPORT_ERR)
        payload = request.get_json(force=True) or {}
        res = core.run_phase_1_and_2(payload)
        return jsonify({"ok": True, "result": res})
    except Exception as e:
        return jsonify({"ok": False, "error": f"{e}", "trace": traceback.format_exc()}), 400

@app.post("/api/confirm-phase3")
def api_confirm_phase3():
    try:
        if IMPORT_ERR:
            raise RuntimeError(IMPORT_ERR)
        payload = request.get_json(force=True) or {}
        res = core.confirm_phase_3(payload)
        return jsonify({"ok": True, "result": res})
    except Exception as e:
        return jsonify({"ok": False, "error": f"{e}", "trace": traceback.format_exc()}), 400

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
