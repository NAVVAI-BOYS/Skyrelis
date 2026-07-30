import os, json, csv, io
from datetime import datetime
from flask import Flask, render_template, request, jsonify, Response

app = Flask(__name__)
ADMIN_KEY = os.environ.get("ADMIN_KEY", "")
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
LEADS = os.path.join(DATA_DIR, "leads.json")
os.makedirs(DATA_DIR, exist_ok=True)

FIELDS = ["date","first","last","email","company","role","lane","score","stage",
          "inventory","tools","autonomy","data","runtime","audit","goal"]

def read_leads():
    try:
        with open(LEADS, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def write_leads(rows):
    with open(LEADS, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=1)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/lead", methods=["POST"])
def lead():
    body = request.get_json(silent=True) or {}
    body["received_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    body["ip"] = request.headers.get("X-Forwarded-For", request.remote_addr)
    rows = read_leads()
    rows.insert(0, body)
    write_leads(rows[:5000])
    app.logger.info("LEAD %s %s %s score=%s", body.get("email"), body.get("company"), body.get("role"), body.get("score"))
    return jsonify(ok=True)

def _auth():
    return ADMIN_KEY and request.args.get("key") == ADMIN_KEY

@app.route("/api/leads")
def leads():
    if not _auth():
        return jsonify(error="unauthorised"), 401
    return jsonify(read_leads())

@app.route("/api/leads.csv")
def leads_csv():
    if not _auth():
        return Response("unauthorised", status=401)
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(FIELDS)
    for r in read_leads():
        cats = r.get("cats") or {}
        w.writerow([r.get("date",""), r.get("first",""), r.get("last",""), r.get("email",""),
                    r.get("company",""), r.get("role",""), r.get("lane",""), r.get("score",""),
                    r.get("stage",""), cats.get("inventory",""), cats.get("tools",""),
                    cats.get("autonomy",""), cats.get("data",""), cats.get("runtime",""),
                    cats.get("audit",""), r.get("goal","")])
    return Response(out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=skyrelis-leads.csv"})

@app.route("/healthz")
def healthz():
    return "ok"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
