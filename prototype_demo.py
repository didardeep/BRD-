"""
Standalone launcher for the AI-assisted BRD Studio PROTOTYPE (demo only).

Does NOT import or modify app.py. It only serves:
  templates/prototype.html, static/prototype.js, static/prototype.css
  (plus the existing static/style.css, read-only)

Run:   python prototype_demo.py            -> http://127.0.0.1:5050
       python prototype_demo.py --port 8080
"""
import argparse
import webbrowser
from pathlib import Path
from threading import Timer

from flask import Flask, render_template

BASE_DIR = Path(__file__).resolve().parent

demo = Flask(__name__,
             template_folder=str(BASE_DIR / "templates"),
             static_folder=str(BASE_DIR / "static"))
demo.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0


@demo.get("/")
def prototype():
    return render_template("prototype.html")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="BRD Studio AI prototype (demo)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=5050)
    ap.add_argument("--no-browser", action="store_true", help="don't open a browser tab")
    args = ap.parse_args()

    url = f"http://{args.host}:{args.port}/"
    print(f"\n  BRD Studio AI prototype running at {url}\n")
    if not args.no_browser:
        Timer(1.0, lambda: webbrowser.open(url)).start()
    demo.run(host=args.host, port=args.port, debug=False, use_reloader=False)
