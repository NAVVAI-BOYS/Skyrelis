# Skyrelis Agent Control Check

Seven questions placing a prospect on two axes: where their agent rules live, and how those rules change. Built by Navvai as an example, September 2026.

Runs as a Flask web service on the standard Navvai Render pattern.

---

## Deploy on Render

1. Push this folder to a GitHub repo (for example `NAVVAI-BOYS/SKYRELIS-CHECK`).
2. Render, New, **Web Service**. Not a Static Site.
3. Connect the repo and set:

| Setting | Value |
|---|---|
| Runtime | **Python 3** (not Docker) |
| Root Directory | `skyrelis-check` |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `gunicorn app:app` |
| Health Check Path | `/healthz` |

4. Environment variables:

| Key | Value | Needed |
|---|---|---|
| `ADMIN_KEY` | any long random string you pick | Yes. Without it `/ops` returns 401 for everyone including you. |
| `SHOW_CONCEPT_BANNER` | `true` or `false` | Optional, defaults to `true` |
| `ANTHROPIC_API_KEY` | leave blank | Reserved slot, nothing in this build calls it |

5. Add a **persistent disk** mounted at `/opt/render/project/src/skyrelis-check/data`, 1GB. Without it, Render wipes the recorded answers on every deploy and restart.

`render.yaml` in this folder does all of the above if you deploy as a Blueprint instead.

---

## The URLs

| URL | Who it is for |
|---|---|
| `/` | The prospect. The check itself. |
| `/?ref=acme-maya` | Same check, but the record gets labelled `acme-maya` |
| `/ops?key=ADMIN_KEY` | Damarie. Every completion with the booking read. |
| `/api/checks.csv?key=ADMIN_KEY` | Spreadsheet of all completions |
| `/api/checks?key=ADMIN_KEY` | Raw JSON |
| `/healthz` | Render health check |

### Labelling a live call

The check never asks for a name or an email, which is the point of it. So on an intro call, open it as `/?ref=company-name` before screen sharing. The record then carries that label and `/ops` can tell one prospect from another. Anyone arriving at the plain `/` is recorded with a blank ref.

---

## Two things that changed for deployment

**The facilitator read is no longer on the check.** On a private link it sat one click under the result. On a public URL that would show every visitor the qualification logic, so it moved to `/ops` behind `ADMIN_KEY` and is computed server side. The check does not link to it.

**It now records answers.** Nothing identifying is captured: no name, no email, no IP. Each row holds the seven answers, the two axis scores, the position and the `ref` label if one was set. That is what turns completions into the industry picture Jaz wants.

---

## The booking rule

Lives in one function, `facilitator_read()` in `app.py`. Change it there and it changes on `/ops`, in the CSV and in the JSON at once.

Book the recording when all three hold:

1. At least one agent acts without a person approving each step
2. The position is anything other than Control plane
3. Either per customer rules are built by hand, or a restriction needs a release

Everything else stays friendly and unbooked.

A strong signal is flagged separately: per customer rules built by hand **and** rules rebuilt when the model changes. That combination is Skyrelis's pitch in the prospect's own words.

---

## Before this goes in front of real prospects

- [ ] Check it against the existing Skyrelis Agentic Security Scorecard. Some of this may already exist there in a better form.
- [ ] Get the real Skyrelis logo and typeface. The colours come from the spec, but the mark is plain text on purpose, because inventing a client mark is worse than leaving it blank.
- [ ] Agree the seven questions and the four box names with Jaz and Dave. They are a first pass.
- [ ] Decide whether it sits on skyrelis.com or on a Navvai URL. Dave owns their website.
- [ ] Turn `SHOW_CONCEPT_BANNER` to `false` once it stops being an example.
- [ ] Add a privacy line if it goes on their domain. Their site carries a cookie banner and a privacy policy, so a page that records anything should say so in their words, not mine.

---

## Running it locally

```bash
cd skyrelis-check
pip install -r requirements.txt
ADMIN_KEY=localtest python app.py
# check      http://localhost:5000/
# operator   http://localhost:5000/ops?key=localtest
```
