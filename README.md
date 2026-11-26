# AIHiveHQ

Multi-agent Streamlit apps sharing a common workforce hub. Each app can run in demo mode without an OpenAI API key (scripted responses). Data is stored in local SQLite databases.

## Layout

| Path | What it is |
|------|------------|
| `aihive_coach/` | Coach app (Streamlit entrypoint `app.py`), coaching + action plans, shared shell for other agents |
| `tutor/` | Tutor agent (lessons, study sessions) |
| `marketing/` | Marketing agent (campaign briefs) |
| `voice/` | Voice assistant (standalone Streamlit app) |
| `workforce/` | Workforce hub registry and hub page |
| `benchmarks/` | Tutor GED-math benchmark harness and items |
| `requirements-dev.txt` | Dev/test dependencies for the whole repo |
| `pytest.ini` | Root pytest config (`e2e` marker registered) |

## Setup

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
```

For browser E2E tests only:

```bash
playwright install chromium
```

## Running apps

From the repo root (so imports resolve):

```bash
# Workforce hub / Coach shell (includes Tutor, Marketing, etc. via navigation)
PYTHONPATH=. streamlit run aihive_coach/app.py

# Voice assistant (separate app)
PYTHONPATH=. streamlit run voice/app.py
```

Leave `OPENAI_API_KEY` unset to use demo mode.

## Tests

```bash
# Fast unit/integration suite (skips Playwright/Streamlit E2E)
unset OPENAI_API_KEY
PYTHONPATH=. python -m pytest -q -m "not e2e"

# Full suite including E2E (requires Playwright browsers)
PYTHONPATH=. python -m pytest -q

# E2E only
PYTHONPATH=. python -m pytest -q -m e2e
```

E2E tests are marked automatically when the filename starts with `test_e2e`. CI runs only `-m "not e2e"` on `ubuntu-latest` with Python 3.11 and no secrets.
