# Scripts

## `capture_mobile_proof.py`

Reusable Playwright capture for Coach + Tutor mobile proof screenshots.

- **Requires:** local Streamlit app in demo mode (`OPENAI_API_KEY` unset), Playwright Chromium
- **Writes to:** `/tmp/aihive_screenshots` by default (never commit PNGs)
- **Viewports:** Coach `375x667`, Tutor `390` wide

```bash
unset OPENAI_API_KEY
PYTHONPATH=. streamlit run aihive_coach/app.py --server.port=8501 --server.headless=true

PYTHONPATH=. python scripts/capture_mobile_proof.py --base-url http://localhost:8501
```

Options: `--only landing|plan|privacy|tutor|all`, `--out DIR`.
