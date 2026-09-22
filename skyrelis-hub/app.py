"""
Skyrelis Agent Control Check
Navvai, September 2026.

Flask service on the standard Navvai Render pattern. Serves the check at /
and keeps the facilitator read off the public page: it lives at /ops behind
ADMIN_KEY, computed here rather than in the browser.
"""

import os
import io
import csv
import json
import uuid
from datetime import datetime, timezone

from flask import Flask, render_template, request, jsonify, Response, abort

app = Flask(__name__)

ADMIN_KEY = os.environ.get("ADMIN_KEY", "")
SHOW_CONCEPT = os.environ.get("SHOW_CONCEPT_BANNER", "true").strip().lower() != "false"

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
STORE = os.path.join(DATA_DIR, "checks.json")
MAX_ROWS = 5000
os.makedirs(DATA_DIR, exist_ok=True)

BOX_NAMES = {
    "control": "Control plane",
    "locked": "Locked down",
    "patch": "Patchwork",
    "holes": "Black holes",
}


# ----------------------------------------------------------------- storage
def read_rows():
    try:
        with open(STORE, "r", encoding="utf-8") as f:
            rows = json.load(f)
        return rows if isinstance(rows, list) else []
    except Exception:
        return []


def write_rows(rows):
    tmp = STORE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(rows[:MAX_ROWS], f, indent=1)
    os.replace(tmp, STORE)


# --------------------------------------------------------- the booking rule
def facilitator_read(row):
    """The single source of truth for whether a recording gets booked.

    Book when all three hold:
      1. at least one agent acts without a person approving each step
      2. the position is anything other than Control plane
      3. either per customer rules are built by hand, or a restriction
         needs a release

    Everything else stays friendly and unbooked.
    """
    f = row.get("flags") or {}
    unattended = int(f.get("unattended") or 0)
    by_hand = bool(f.get("byHand"))
    slow = bool(f.get("slowChange"))
    rebuild = bool(f.get("rebuild"))
    box = row.get("box") or ""

    book = unattended >= 1 and box != "control" and (by_hand or slow)
    strong = by_hand and rebuild

    if book:
        why = ("All three conditions hold. The pain is live, the position is not "
               "already solved, and there is something specific to talk about.")
    elif unattended == 0:
        why = ("No unattended agents, so there is nothing for the platform to govern "
               "yet. Keep them warm and do not push the podcast.")
    elif box == "control":
        why = ("Already in the strong box. Interesting for an episode, weak as a "
               "commercial lead. Worth having, worth not chasing.")
    else:
        why = "Pain is present but nothing specific surfaced. Ask a follow up rather than booking."

    return {
        "book": book,
        "strong": strong,
        "verdict": "Book the recording" if book else "Not yet",
        "why": why,
        "strong_note": ("Building policy profiles by hand and rebuilding rules when the "
                        "model changes. That is the pitch, in their own words."),
    }


# ------------------------------------------------------------------ routes
@app.route("/")
def index():
    return render_template("index.html", show_concept=SHOW_CONCEPT)


@app.route("/api/check", methods=["POST"])
def api_check():
    body = request.get_json(silent=True) or {}
    row = {
        "id": uuid.uuid4().hex[:12],
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ref": str(body.get("ref") or "")[:80],
        "box": str(body.get("box") or ""),
        "box_name": str(body.get("boxName") or BOX_NAMES.get(body.get("box"), "")),
        "y": int(body.get("y") or 0),
        "x": int(body.get("x") or 0),
        "holes": int(body.get("holes") or 0),
        "flags": body.get("flags") or {},
        "answers": body.get("answers") or [],
    }
    rows = read_rows()
    rows.insert(0, row)
    write_rows(rows)

    r = facilitator_read(row)
    app.logger.info(
        "CHECK ref=%s box=%s y=%s x=%s -> %s",
        row["ref"] or "-", row["box_name"], row["y"], row["x"], r["verdict"],
    )
    return jsonify(ok=True, id=row["id"])


def require_key():
    if not ADMIN_KEY or request.args.get("key") != ADMIN_KEY:
        abort(401)


@app.route("/ops")
def ops():
    require_key()
    rows = read_rows()
    enriched = [dict(r, read=facilitator_read(r)) for r in rows]
    booked = sum(1 for r in enriched if r["read"]["book"])
    return render_template("ops.html", rows=enriched, total=len(rows),
                           booked=booked, key=request.args.get("key", ""))


@app.route("/api/checks")
def api_checks():
    require_key()
    return jsonify([dict(r, read=facilitator_read(r)) for r in read_rows()])


@app.route("/api/checks.csv")
def api_checks_csv():
    require_key()
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["at", "ref", "position", "rules_live_9", "rules_change_9",
                "black_holes", "unattended", "per_customer_by_hand",
                "change_needs_release", "rebuild_on_model_switch", "verdict"])
    for r in read_rows():
        f = r.get("flags") or {}
        w.writerow([
            r.get("at", ""), r.get("ref", ""), r.get("box_name", ""),
            r.get("y", ""), r.get("x", ""), r.get("holes", ""),
            f.get("unattended", ""), f.get("byHand", ""),
            f.get("slowChange", ""), f.get("rebuild", ""),
            facilitator_read(r)["verdict"],
        ])
    return Response(
        out.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=agent-control-check.csv"},
    )


@app.route("/healthz")
def healthz():
    return "ok"


@app.errorhandler(401)
def unauthorised(_e):
    return Response("Not authorised. Add ?key=ADMIN_KEY to the URL.", status=401)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
