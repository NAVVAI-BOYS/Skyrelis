# Skyrelis Agentic Security Readiness Check

Seven questions, one per area of the six category Agentic Security Readiness Scorecard, weighted exactly as the full assessment weights them. Built by Navvai, September 2026.

## Brand colours, sampled from the logo

The spec document gave a teal and navy palette. The supplied logo is blue and gold, and the logo is the authority, so the app was retoned to it.

| Token | Value | Sampled from |
|---|---|---|
| `--teal` (primary accent) | `#47ABFF` | the blue mark in the lockup |
| `--gold` (CTA fill) | `#F9C002` | the Skyrelis wordmark |
| `--navy` | `#2C395C` | the navy dots in the square icon |
| `--amber` (medium risk) | `#E7B844` | the gold path in the square icon |

Gold stays bright in both themes because it is a fill that should match the wordmark. Amber is theme aware because it carries meaning as text and borders. Red stays a legibility lift of the spec alert colour.

## What this is

The first version scored two invented axes (where agent rules live, how they change), which between them covered about 55 percent of the real scorecard's weight. Sensitive data exposure, audit evidence, tool and action visibility and agent inventory were not represented at all.

v2 keeps the format Dave wanted kept (seven taps, no email, the moving dot) and replaces the scoring underneath:

- Every question maps to exactly one scorecard category, shown on screen with its real weight
- Runtime policy enforcement keeps two questions because it carries 30 percent
- The 0 to 100 score uses the scorecard's own formula: (rating - 1) / 4 x weight, summed
- The five band names come from the scorecard: Early experimentation, Fragmented control, Partial governance, Strong direction, Governed autonomy
- The quadrant axes are now derived from category averages: runtime control on the horizontal, the other five categories averaged on the vertical
- The top right quadrant is Governed autonomy, the scorecard's own top tier name, replacing the invented term Control plane

Weights used: agent inventory 5, tool and action visibility 15, autonomy and approval boundaries 25, sensitive data exposure 20, runtime policy enforcement 30, audit ready evidence 5.

Runs as a Flask web service on the standard Navvai Render pattern.

---

## Deploy on Render

### If this is just so Jaz and Dave can see it

You do not need the disk and you do not need `ADMIN_KEY`. Deploy as a Web Service with `pip install -r requirements.txt` and `gunicorn app:app`, set nothing else, and send them the URL.

The check runs and scores exactly the same. Every completion still lands in the Render log stream as one `CHECK ref=...` line, so you can see whether they finished it. Nothing is kept between restarts, `/api/config` reports `"storage":"ephemeral"`, and `/ops` returns 401 because no key is set. Add the disk and the key later, in the service's settings, on the day it starts taking real prospects. Nothing in the app changes.

### If you already have the service at skyrelis.onrender.com

Push this folder's contents to the same repo and Render redeploys. Then check two settings that changed in this version:

- Environment variable `DATA_DIR` set to `/var/data`
- A disk mounted at `/var/data`, 1GB, under the service's Disks tab

Without the disk the app still runs and still scores, it just cannot keep records, and `/ops` will tell you so in a banner.

### If you are deploying fresh

**Put these files at the ROOT of the repo, not inside a subfolder.** `render.yaml` is only read when it sits at the repo root. That is what broke a previous Navvai deploy: the zip was unpacked into a subfolder, the blueprint was never read, no disk was created, and the service crashed on boot.

Then either:

**A. Blueprint, does everything for you**
New, Blueprint, point it at the repo. `render.yaml` sets the runtime, commands, health check, all five environment variables and the disk.

**B. By hand**

| Setting | Value |
|---|---|
| Type | **Web Service**, not a Static Site |
| Runtime | **Python 3**, not Docker |
| Root Directory | leave blank if the files are at the repo root |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `gunicorn app:app` |
| Health Check Path | `/healthz` |

Then add a disk under Disks: any name, mount path `/var/data`, 1GB.

### Environment variables

| Key | Value | Needed |
|---|---|---|
| `ADMIN_KEY` | a long random string you pick | **Yes.** Without it `/ops` returns 401 to everyone including you |
| `DATA_DIR` | `/var/data` | Yes, and it must match the disk mount path |
| `SHOW_CONCEPT_BANNER` | `false` | Optional, already the default |
| `SCORECARD_URL` | link behind "Take the full scorecard" | Optional, defaults to the ungated scorecard |
| `BOOK_URL` | link behind "Talk it through with us" | Optional, defaults to skyrelis.com/contact |

### Check it came up

- `/healthz` returns `ok`
- `/api/config` returns `"storage":"disk"`. That is a real test: it reports `disk` only when `DATA_DIR` is an actual mount point, because on Render every path is writable whether or not a disk is attached, and a writable path with no disk behind it loses every record on the next deploy. `ephemeral` means the disk is missing or `DATA_DIR` does not match its mount path. `none` means nothing is writable at all.
- `/ops?key=YOUR_KEY` loads and shows no orange or red banner

Storage is deliberately never a startup dependency. If the disk is missing the app still serves, still scores, still logs every completion to the Render log stream, and says plainly on `/ops` that records are not being kept.

## The flow

1. **Before we score.** One unscored screen asking which kinds of agent they run: enterprise operated, platform based, vendor controlled, browser and endpoint, or none yet. This is the executive brief's own framework, which Dave flagged as missing from the first version. Choosing "none yet" ends the check politely, which also restores the qualifying step v1 had.
2. **Seven questions**, one per scorecard category, runtime getting two.
3. **The result.** Weighted score, band, category table, quadrant position, weakest answers, a scoring note for vendor run agents, this check versus the full scorecard, and the two calls to action.

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

Book when the score is **below 75**, meaning they are not already in the stronger half, **and** at least one of:

1. Runtime policy enforcement averages below 3.5 out of 5. That is the thing the platform actually fixes.
2. They run vendor controlled agents and cannot get proof from the vendor.

Score 75 or above is interesting for an episode and weak as a commercial lead: worth having, worth not chasing. A low score with healthy runtime and vendor proof means the weakness sits somewhere Skyrelis does not lead on, so it asks a follow up rather than booking.

A strong signal is flagged separately: runtime enforcement slow **and** sensitive data exposure uncontrolled at the same time. That pair is the escalation story in the prospect's own answers.

---

## Before this goes in front of real prospects

- [x] **The logo is in.** Extracted from the supplied asset by alpha keying it off its black ground, so the antialiasing survives and nothing was redrawn. The lockup is the mark plus the wordmark with the tagline dropped, since a tagline does not belong in a 26px masthead. Embedded as base64 so there is no external request. The square icon asset is the favicon.
- [ ] **The typeface.** Still Archivo and Inter. If Skyrelis has a brand face, send it and it is a one line change.
- [ ] **Confirm the two links.** `SCORECARD_URL` points at the ungated scorecard named in the memo. `BOOK_URL` is a guess and should be whatever Jaz wants, probably her Calendly.
- [ ] **Sign off the question wording.** The categories, weights, formula and band names are Skyrelis's. The wording of the seven questions and the line under each answer is still Navvai's.
- [ ] **A privacy line,** if this sits on skyrelis.com. The site carries a cookie banner and a policy, so a page that records anything should say so in their words.
- [ ] Decide whether it sits on skyrelis.com or on a Navvai URL. Dave owns their website.

---

## Running it locally

```bash
cd skyrelis-check
pip install -r requirements.txt
ADMIN_KEY=localtest python app.py
# check      http://localhost:5000/
# operator   http://localhost:5000/ops?key=localtest
```
