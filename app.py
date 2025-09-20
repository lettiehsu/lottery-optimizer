from flask import Flask, render_template_string

app = Flask(__name__)

HOME = """
<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <title>Lottery Optimizer</title>
    <style>
      body { font-family: system-ui, Arial, sans-serif; max-width: 860px; margin: 40px auto; line-height: 1.4; }
      pre { background:#111; color:#eee; padding:12px; border-radius:8px; overflow:auto; }
      a.btn { display:inline-block; padding:10px 14px; background:#2ea44f; color:white; border-radius:8px; text-decoration:none; }
      .muted { color:#777; }
    </style>
  </head>
  <body>
    <h1>Lottery Optimizer</h1>
    <p class="muted">MM / PB / Illinois Lotto — generate · simulate · confirm</p>
    <p>This is a deployment smoke test. If you can see this page online, your app is running.</p>
    <p>Next step: we’ll wire routes to run your generator/simulator and upload CSVs.</p>
    <pre>app.py is alive ✅</pre>
  </body>
</html>
"""

@app.get("/")
def index():
    return render_template_string(HOME)

# Placeholder routes you’ll fill next:
# @app.post("/run")      -> trigger Phase 1 & 2 with current NJ + feeds
# @app.post("/confirm")  -> confirm Phase 3 using CONFIRM_FROM_FILE + NWJ

if __name__ == "__main__":
    # Allows local testing:  python app.py  then open http://127.0.0.1:5000
    app.run(host="0.0.0.0", port=5000, debug=True)
