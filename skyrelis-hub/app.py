"""
Skyrelis Agentic Security Readiness Check
Navvai, September 2026. v2, revised against the six category scorecard.

Flask service on the standard Navvai Render pattern. Serves the check at /
and keeps the facilitator read off the public page: it lives at /ops behind
ADMIN_KEY, computed here rather than in the browser.
"""

import os
import io
import logging
import csv
import json
import uuid
from datetime import datetime, timezone

from flask import Flask, render_template, request, jsonify, Response, abort

app = Flask(__name__)

# Under gunicorn, Flask's own logger does not reach the worker's handlers, so
# every completion would be invisible in the Render log stream. Attach them.
_gunicorn = logging.getLogger("gunicorn.error")
if _gunicorn.handlers:
    app.logger.handlers = _gunicorn.handlers
    app.logger.setLevel(_gunicorn.level)
else:
    logging.basicConfig(level=logging.INFO)
    app.logger.setLevel(logging.INFO)

ADMIN_KEY = os.environ.get("ADMIN_KEY", "")
SHOW_CONCEPT = os.environ.get("SHOW_CONCEPT_BANNER", "false").strip().lower() == "true"
SCORECARD_URL = os.environ.get("SCORECARD_URL", "https://skyrelis.com/agent-scorecard-ungated")
BOOK_URL = os.environ.get("BOOK_URL", "https://skyrelis.com/contact")

MAX_ROWS = 5000
REQUESTED_DIR = os.environ.get("DATA_DIR") or "/var/data"
HERE = os.path.dirname(os.path.abspath(__file__))


def pick_data_dir():
    """Storage is a convenience, never a startup dependency.

    Try the requested directory, then a directory beside app.py, then /tmp.
    Return None if none of them work. The app serves either way: a check
    still scores, still renders and still logs, it just is not recorded.
    """
    for label, path in (("requested", REQUESTED_DIR),
                        ("beside app.py", os.path.join(HERE, "data")),
                        ("temp", "/tmp/skyrelis-check")):
        try:
            os.makedirs(path, exist_ok=True)
            probe = os.path.join(path, ".writetest")
            with open(probe, "w") as f:
                f.write("ok")
            os.remove(probe)
            if path != REQUESTED_DIR:
                print("[storage] %s unusable, falling back to %s (%s)" % (REQUESTED_DIR, path, label), flush=True)
            return path
        except Exception as e:
            print("[storage] cannot use %s (%s): %s" % (path, label, e), flush=True)
    print("[storage] no writable location. Checks will score but will not be recorded.", flush=True)
    return None


DATA_DIR = pick_data_dir()
STORE = os.path.join(DATA_DIR, "checks.json") if DATA_DIR else None


def storage_state():
    """disk, ephemeral or none.

    Writable is not the same as persistent. On Render the container
    filesystem is writable everywhere, so /var/data can be created and
    written to whether or not a disk is attached, and the records would
    quietly vanish on the next deploy. A Render disk is a real mount, so
    that is the thing to test for.
    """
    if not DATA_DIR:
        return "none"
    try:
        return "disk" if os.path.ismount(DATA_DIR) else "ephemeral"
    except Exception:
        return "ephemeral"


STORAGE_STATE = storage_state()

# The six scorecard categories and their weights, mirrored from the front end
# only for labelling the CSV. The scoring itself is done in the browser with
# the scorecard's own formula and sent here already calculated.
CAT_ORDER = ["inventory", "visibility", "autonomy", "data", "runtime", "audit"]
CAT_NAMES = {
    "inventory": "Agent inventory and control boundary",
    "visibility": "Tool and action visibility",
    "autonomy": "Autonomy and approval boundaries",
    "data": "Sensitive data exposure",
    "runtime": "Runtime policy enforcement",
    "audit": "Audit ready evidence",
}


# ----------------------------------------------------------------- storage
def read_rows():
    if not STORE:
        return []
    try:
        with open(STORE, "r", encoding="utf-8") as f:
            rows = json.load(f)
        return rows if isinstance(rows, list) else []
    except Exception:
        return []


def write_rows(rows):
    if not STORE:
        raise RuntimeError("no writable storage")
    tmp = STORE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(rows[:MAX_ROWS], f, indent=1)
    os.replace(tmp, STORE)


def weak_label(weak):
    """The front end sends the weakest answers as category keys.

    Printed straight into the page that renders as a Python list, so turn it
    into the category names. A number (an older row) is left as it was.
    """
    if weak is None or weak == "":
        return ""
    if isinstance(weak, (int, float)):
        return "%s answer%s" % (int(weak), "" if int(weak) == 1 else "s")
    if isinstance(weak, str):
        return weak
    try:
        names = [CAT_NAMES.get(str(k), str(k)) for k in weak]
    except TypeError:
        return str(weak)
    names = [n for n in names if n]
    if len(names) > 3:
        return ", ".join(names[:3]) + " and %d more" % (len(names) - 3)
    return ", ".join(names)


def answer_for(row, qid):
    for a in row.get("answers") or []:
        if a.get("id") == qid:
            return a
    return None


# --------------------------------------------------------- the booking rule
def facilitator_read(row):
    """The single source of truth for whether a recording gets booked.

    Book when the score is below 75, meaning they are not already in the
    stronger half, AND at least one of:
      1. runtime control is below 3.5 out of 5, which is the thing the
         platform actually fixes
      2. they cannot get proof from a vendor running agents on their behalf

    Everything else stays friendly and unbooked.
    """
    score = row.get("score")
    score = 0 if score is None else int(score)
    runtime = (row.get("cats") or {}).get("runtime")
    data_avg = (row.get("cats") or {}).get("data")

    q6 = answer_for(row, "q6")
    vendor_gap = bool(q6 and (q6.get("rating") or 5) <= 2.4)

    slow_runtime = runtime is not None and runtime < 3.5
    book = score < 75 and (slow_runtime or vendor_gap)
    strong = (runtime is not None and runtime < 3) and (data_avg is not None and data_avg <= 2.4)

    if book:
        why = ("Score is in the lower half and the gap is in something the platform "
               "addresses directly. There is a specific thing to talk about on air.")
    elif score >= 75:
        why = ("Already in the stronger half. Interesting for an episode, weak as a "
               "commercial lead. Worth having, worth not chasing.")
    else:
        why = ("Score is low but runtime enforcement and vendor proof both came back "
               "healthy. The weakness sits somewhere the platform does not lead on, "
               "so ask a follow up rather than booking.")

    return {
        "book": book,
        "strong": strong,
        "verdict": "Book the recording" if book else "Not yet",
        "why": why,
        "vendor_gap": vendor_gap,
        "slow_runtime": slow_runtime,
        "strong_note": ("Runtime enforcement is slow and sensitive data exposure is "
                        "uncontrolled at the same time. That pair is the escalation "
                        "story, in their own answers."),
    }


# ------------------------------------------------------------------ routes
@app.route("/")
def index():
    return render_template("index.html", show_concept=SHOW_CONCEPT, capture=True,
                           scorecard_url=SCORECARD_URL, book_url=BOOK_URL)


@app.route("/api/check", methods=["POST"])
def api_check():
    body = request.get_json(silent=True) or {}
    row = {
        "id": uuid.uuid4().hex[:12],
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ref": str(body.get("ref") or "")[:80],
        "estate": body.get("estate") or [],
        "estate_names": body.get("estateNames") or [],
        "score": body.get("score"),
        "band": str(body.get("band") or ""),
        "quad": str(body.get("quad") or ""),
        "quad_name": str(body.get("quadName") or ""),
        "x": body.get("x"),
        "y": body.get("y"),
        "weak": body.get("weak"),
        "cats": body.get("cats") or {},
        "answers": body.get("answers") or [],
    }
    stored = True
    try:
        rows = read_rows()
        rows.insert(0, row)
        write_rows(rows)
    except Exception as e:
        stored = False
        app.logger.warning("CHECK not stored: %s", e)

    r = facilitator_read(row)
    app.logger.info(
        "CHECK ref=%s score=%s band=%s quad=%s -> %s",
        row["ref"] or "-", row["score"], row["band"], row["quad_name"], r["verdict"],
    )
    return jsonify(ok=True, id=row["id"], stored=stored)


def require_key():
    if not ADMIN_KEY or request.args.get("key") != ADMIN_KEY:
        abort(401)


@app.route("/ops")
def ops():
    require_key()
    rows = read_rows()
    enriched = [dict(r, read=facilitator_read(r), weak_label=weak_label(r.get("weak")))
                for r in rows]
    booked = sum(1 for r in enriched if r["read"]["book"])
    scores = [r.get("score") for r in rows if isinstance(r.get("score"), (int, float))]
    avg = round(sum(scores) / len(scores)) if scores else 0
    return render_template("ops.html", rows=enriched, total=len(rows), booked=booked,
                           avg=avg, cat_order=CAT_ORDER, cat_names=CAT_NAMES,
                           storage_state=STORAGE_STATE, data_dir=DATA_DIR or "none",
                           requested_dir=REQUESTED_DIR,
                           key=request.args.get("key", ""))


@app.route("/api/checks")
def api_checks():
    require_key()
    return jsonify([dict(r, read=facilitator_read(r)) for r in read_rows()])


@app.route("/api/checks.csv")
def api_checks_csv():
    require_key()
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["at", "ref", "score", "band", "quadrant",
                "visibility_governance_5", "runtime_control_5"]
               + [CAT_NAMES[c] for c in CAT_ORDER]
               + ["vendor_proof_gap", "slow_runtime", "verdict"])
    for r in read_rows():
        cats = r.get("cats") or {}
        rd = facilitator_read(r)
        w.writerow([
            r.get("at", ""), r.get("ref", ""), r.get("score", ""),
            r.get("band", ""), r.get("quad_name", ""),
            r.get("y", ""), r.get("x", ""),
        ] + [cats.get(c, "") for c in CAT_ORDER]
          + [rd["vendor_gap"], rd["slow_runtime"], rd["verdict"]])
    return Response(
        out.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=agentic-readiness-check.csv"},
    )


@app.route("/healthz")
def healthz():
    return "ok"


@app.route("/api/config")
def api_config():
    return jsonify(storage=STORAGE_STATE, data_dir=DATA_DIR or None,
                   admin_key_set=bool(ADMIN_KEY), concept_banner=SHOW_CONCEPT)


@app.errorhandler(401)
def unauthorised(_e):
    return Response("Not authorised. Add ?key=ADMIN_KEY to the URL.", status=401)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
