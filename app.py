from flask import Flask, request, render_template_string
import os, json, csv, io, traceback
from datetime import datetime

# ---- import your core
try:
    import lottery_core as core
except Exception as e:
    core = None

APP_TITLE = "Lottery Optimizer"
app = Flask(__name__)

DATA_DIR = os.environ.get("DATA_DIR", "/tmp")
os.makedirs(os.path.join(DATA_DIR, "uploads"), exist_ok=True)
os.makedirs(os.path.join(DATA_DIR, "buylists"), exist_ok=True)

# ---------- tiny helpers

def parse_nums(text):
    """
    Accepts formats like:
      [1,2,3,4,5]
      (1,2,3,4,5)
      1,2,3,4,5
      1 2 3 4 5
    Returns list[int].
    """
    if text is None: return []
    t = text.strip()
    if not t: return []
    # strip wrappers
    if t[0] in "[(" and t[-1] in "])":
        t = t[1:-1]
    # split on comma or space
    parts = [p for chunk in t.split(",") for p in chunk.split()]
    out = []
    for p in parts:
        p = p.strip()
        if not p: continue
        out.append(int(p))
    return out

def parse_latest_row(text):
    """
    For MM/PB: " [10,14,34,40,43],5 " OR "10,14,34,40,43|5"
    For IL:    " [1,4,5,10,18,49] " (bonus None)
    Returns: (mains_list, bonus_or_None)
    """
    if not text: return ([], None)
    t = text.strip()
    if "|" in t:
        a, b = t.split("|", 1)
        return (parse_nums(a), int(b))
    if "]" in t and "," in t:
        # like "[10,14,34,40,43],5"
        try:
            left, right = t.split("]", 1)
            mains = parse_nums(left + "]")
            right = right.replace(",", "").strip()
            bonus = int(right) if right else None
            return (mains, bonus)
        except Exception:
            pass
    # fallback: only mains (IL)
    return (parse_nums(t), None)

def save_textfile(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)

# ---------- UI

INDEX_HTML = """
<!doctype html>
<title>{{title}}</title>
<link rel="stylesheet" href="https://unpkg.com/mvp.css">
<main>
  <h1>{{title}}</h1>
  <p>MM / PB / Illinois Lotto — <em>generate · simulate · confirm</em></p>

  <section>
    <h2>1) Upload optional CSV & feeds</h2>
    <form action="/upload" method="post" enctype="multipart/form-data">
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px">
        <div>
          <label>MM history CSV (optional)<input type="file" name="mm_csv"></label>
          <label>MM feed (txt)<input type="file" name="mm_feed"></label>
        </div>
        <div>
          <label>PB history CSV (optional)<input type="file" name="pb_csv"></label>
          <label>PB feed (txt)<input type="file" name="pb_feed"></label>
        </div>
        <div>
          <label>IL history CSV (optional)<input type="file" name="il_csv"></label>
          <label>IL feed (txt)<input type="file" name="il_feed"></label>
        </div>
      </div>
      <button>Upload</button>
    </form>
    <p><small>Files are saved under <code>{{data_dir}}</code> on the server.</small></p>
  </section>

  <section>
    <h2>2) Run Phase 1 & 2</h2>
    <form action="/run" method="post">
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px">
        <label>LATEST_MM (e.g. "[10,14,34,40,43],5")
          <input name="latest_mm" value="{{ex_latest_mm}}">
        </label>
        <label>LATEST_PB (e.g. "[14,15,32,42,49],1")
          <input name="latest_pb" value="{{ex_latest_pb}}">
        </label>
        <label>LATEST_IL_JP (e.g. "[1,4,5,10,18,49]") 
          <input name="latest_il_jp" value="{{ex_latest_il_jp}}">
        </label>
        <label>LATEST_IL_M1
          <input name="latest_il_m1" value="{{ex_latest_il_m1}}">
        </label>
        <label>LATEST_IL_M2
          <input name="latest_il_m2" value="{{ex_latest_il_m2}}">
        </label>
        <label>Runs
          <input name="runs" value="100">
        </label>
      </div>
      <label><input type="checkbox" name="quiet" checked> Quiet progress (10/100 etc.)</label>
      <button>Run Phase 1 & 2</button>
    </form>
    <p><small>Generates a 50-row batch for each game, prints Phase-1 hits, runs sims, and saves a <code>buy_session_*.json</code>.</small></p>
  </section>

  <section>
    <h2>3) Confirm Phase 3</h2>
    <form action="/confirm" method="post">
      <label>Saved buy list
        <select name="saved_file">
          <option value="">— choose —</option>
          {% for f in recent %}
          <option value="{{f}}">{{f}}</option>
          {% endfor %}
        </select>
      </label>
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px">
        <label>NWJ_MM (e.g. "[m1..], bonus")<input name="nwj_mm"></label>
        <label>NWJ_PB<input name="nwj_pb"></label>
        <label>NWJ_IL_JP<input name="nwj_il_jp"></label>
        <label>NWJ_IL_M1<input name="nwj_il_m1"></label>
        <label>NWJ_IL_M2<input name="nwj_il_m2"></label>
      </div>
      <label><input type="checkbox" name="recall" checked> Also recall Phase 1/2 headings from the saved file</label>
      <button>Confirm Phase 3</button>
    </form>
  </section>

  <section>
    <h3>Recent buy lists</h3>
    {% if not recent %}
      <p><em>None yet.</em></p>
    {% else %}
      <ul>
        {% for f in recent %}
          <li>{{f}}</li>
        {% endfor %}
      </ul>
    {% endif %}
  </section>

  {% if out %}
  <hr>
  <h2>Result</h2>
  <pre style="white-space:pre-wrap">{{out}}</pre>
  {% endif %}

</main>
"""

def list_recent_buylists():
    bdir = os.path.join(DATA_DIR, "buylists")
    if not os.path.isdir(bdir): return []
    files = [f for f in os.listdir(bdir) if f.startswith("buy_session_") and f.endswith(".json")]
    files.sort(reverse=True)
    return files[:20]

@app.get("/")
def index():
    return render_template_string(
        INDEX_HTML,
        title=APP_TITLE,
        data_dir=DATA_DIR,
        recent=list_recent_buylists(),
        out=None,
        ex_latest_mm="[10,14,34,40,43],5",
        ex_latest_pb="[14,15,32,42,49],1",
        ex_latest_il_jp="[1,4,5,10,18,49]",
        ex_latest_il_m1="[6,8,10,18,26,27]",
        ex_latest_il_m2="[2,18,21,27,43,50]",
    )

@app.post("/upload")
def upload():
    try:
        updir = os.path.join(DATA_DIR, "uploads")
        os.makedirs(updir, exist_ok=True)

        for key in ("mm_csv", "pb_csv", "il_csv", "mm_feed", "pb_feed", "il_feed"):
            f = request.files.get(key)
            if f and f.filename:
                path = os.path.join(updir, f.filename)
                f.save(path)
        msg = "Uploads saved to " + updir
        return render_template_string(INDEX_HTML, title=APP_TITLE, data_dir=DATA_DIR,
                                      recent=list_recent_buylists(), out=msg,
                                      ex_latest_mm="[10,14,34,40,43],5",
                                      ex_latest_pb="[14,15,32,42,49],1",
                                      ex_latest_il_jp="[1,4,5,10,18,49]",
                                      ex_latest_il_m1="[6,8,10,18,26,27]",
                                      ex_latest_il_m2="[2,18,21,27,43,50]")
    except Exception:
        app.logger.exception("Upload failed")
        return ("Upload failed:\n" + traceback.format_exc(), 500)

@app.post("/run")
def run12():
    try:
        if core is None:
            raise RuntimeError("lottery_core.py failed to import or is missing.")

        latest_mm = parse_latest_row(request.form.get("latest_mm",""))
        latest_pb = parse_latest_row(request.form.get("latest_pb",""))
        latest_il_jp = parse_latest_row(request.form.get("latest_il_jp",""))[0]
        latest_il_m1 = parse_latest_row(request.form.get("latest_il_m1",""))[0]
        latest_il_m2 = parse_latest_row(request.form.get("latest_il_m2",""))[0]
        runs = int(request.form.get("runs","100") or 100)
        quiet = bool(request.form.get("quiet"))

        cfg = dict(
            DATA_DIR=DATA_DIR,
            runs=runs,
            quiet=quiet,
            latest_mm=latest_mm,
            latest_pb=latest_pb,
            latest_il_jp=latest_il_jp,
            latest_il_m1=latest_il_m1,
            latest_il_m2=latest_il_m2,
        )
        result_text = core.run_phase_1_and_2(cfg)  # returns big string of the printouts
        return render_template_string(INDEX_HTML, title=APP_TITLE, data_dir=DATA_DIR,
                                      recent=list_recent_buylists(), out=result_text,
                                      ex_latest_mm="[10,14,34,40,43],5",
                                      ex_latest_pb="[14,15,32,42,49],1",
                                      ex_latest_il_jp="[1,4,5,10,18,49]",
                                      ex_latest_il_m1="[6,8,10,18,26,27]",
                                      ex_latest_il_m2="[2,18,21,27,43,50]")
    except Exception:
        app.logger.exception("Run Phase 1/2 failed")
        return ("Run failed:\n" + traceback.format_exc(), 500)

@app.post("/confirm")
def confirm():
    try:
        if core is None:
            raise RuntimeError("lottery_core.py failed to import or is missing.")

        saved = request.form.get("saved_file","").strip()
        nwj_mm = parse_latest_row(request.form.get("nwj_mm",""))
        nwj_pb = parse_latest_row(request.form.get("nwj_pb",""))
        nwj_il_jp = parse_latest_row(request.form.get("nwj_il_jp",""))[0]
        nwj_il_m1 = parse_latest_row(request.form.get("nwj_il_m1",""))[0]
        nwj_il_m2 = parse_latest_row(request.form.get("nwj_il_m2",""))[0]
        recall = bool(request.form.get("recall"))

        nwj = dict(MM=nwj_mm, PB=nwj_pb, IL_JP=nwj_il_jp, IL_M1=nwj_il_m1, IL_M2=nwj_il_m2, recall=recall)
        result_text = core.confirm_phase_3(saved, nwj, DATA_DIR)  # returns text
        return render_template_string(INDEX_HTML, title=APP_TITLE, data_dir=DATA_DIR,
                                      recent=list_recent_buylists(), out=result_text,
                                      ex_latest_mm="[10,14,34,40,43],5",
                                      ex_latest_pb="[14,15,32,42,49],1",
                                      ex_latest_il_jp="[1,4,5,10,18,49]",
                                      ex_latest_il_m1="[6,8,10,18,26,27]",
                                      ex_latest_il_m2="[2,18,21,27,43,50]")
    except Exception:
        app.logger.exception("Confirm Phase 3 failed")
        return ("Confirm failed:\n" + traceback.format_exc(), 500)

@app.get("/health")
def health():
    return {"ok": True}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
