# Skyrelis Agentic Security Hub

Single file front end served by a small Flask app, so it can be deployed as a
Render Web Service using the standard Navvai pattern.

## Render settings

- Type: Web Service (not Static Site)
- Runtime: Python 3 (not Docker)
- Root Directory: skyrelis-hub
- Build command: pip install -r requirements.txt
- Start command: gunicorn app:app
- Environment variables: ADMIN_KEY (required), ANTHROPIC_API_KEY (reserved, unused in this build)

## Endpoints

- `/` the app
- `POST /api/lead` written by the app when someone completes the gate
- `GET /api/leads?key=ADMIN_KEY` raw JSON
- `GET /api/leads.csv?key=ADMIN_KEY` spreadsheet of completions
- `/healthz`

## Notes

- `templates/index.html` is the whole front end. It also runs standalone from disk,
  where the lead post fails silently by design.
- Storage is `data/leads.json`. Render's disk is ephemeral, so add a persistent disk
  or move to Postgres before the campaign scales.
