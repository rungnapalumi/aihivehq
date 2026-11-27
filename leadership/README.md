# AIHive Leadership (MVP)

New business vertical: **AIHive Leadership**, flagship program **Leadership Expedition**.

| Path | What |
|---|---|
| `site/leadership/index.html` | `/leadership` landing page (3 programs) |
| `site/leadership/expedition/index.html` | `/leadership/expedition` program page, missions, journey, corporate inquiry form |
| `site/leadership/demo/index.html` | `/leadership/demo` interactive simulation + illustrative report |
| `site/leadership/assets/sim.js` | Deterministic simulation engine and report rubric (pure JS, also used by tests) |
| `site/leadership/assets/demo.js` | Demo UI (map, state, decisions, report rendering) |
| `site/leadership/assets/inquiry.js` | Form validation + submission |
| `leadership/inquiry.py` | Server-side validation, SQLite storage, notification hook (email not enabled) |
| `leadership/server.py` | Stdlib preview server: serves `site/` and `POST /api/leadership/inquiry` |
| `leadership/ARCHITECTURE.md` | Future data model (design only, not implemented) |

## Run locally

```bash
PORT=8000 python -m leadership.server      # http://localhost:8000/leadership/
env -u OPENAI_API_KEY PYTHONPATH=. python -m pytest -q leadership/tests
```

## Settings (environment variables)

| Variable | Default | Purpose |
|---|---|---|
| `LEADERSHIP_INQUIRY_TO` | `rungnapa@aihivehq.com` | Intended destination for inquiry notifications (stored with each inquiry) |
| `LEADERSHIP_DB_PATH` | `/tmp/aihive_leadership/inquiries.db` | SQLite file for inquiries |

**Email delivery is not implemented or enabled.** Inquiries are stored in SQLite and the API reports
`email_delivery: "not_enabled"`. On a free Render web service the disk is ephemeral, so stored
inquiries are lost on restart or redeploy. A persistent store and a tested email path are required
before taking real inquiries.

## Production note

`aihivehq.com` is a static site with no backend. If the Leadership pages are published there as-is,
the form will show its error message (with the contact email) because `/api/leadership/inquiry`
does not exist on a static host. Before launch, point the form's `data-endpoint` at a deployed backend.
