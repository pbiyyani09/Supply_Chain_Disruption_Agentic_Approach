# ChainWatch — Claude Code Instructions

## Project overview

ChainWatch is a 4-agent supply chain disruption early warning system. It is a capstone project for the Kaggle × Google "5-Day AI Agents Intensive" course (June 2026). **All LLM work uses Google AI Studio (Gemini), not Anthropic.**

---

## Non-negotiable rules

### Always use `google-genai`, never `anthropic`

```python
# CORRECT
from google import genai
from google.genai import types
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

# WRONG — do not introduce this
import anthropic
```

### Always use `gemini-2.0-flash` as the default model

Read the model from env: `os.getenv("GEMINI_MODEL", "gemini-2.0-flash")`  
Never hardcode a model string other than the default fallback.

### Use JSON mode for structured agent outputs

```python
# Agents 1 and 2 always use this
config=types.GenerateContentConfig(
    response_mime_type="application/json",
    temperature=0.1,
)
```

### Use Google Search grounding for Impact Analyst web research

```python
# Agent 3 only — replaces Tavily
config=types.GenerateContentConfig(
    tools=[types.Tool(google_search=types.GoogleSearch())],
)
```

Never add Tavily, DuckDuckGo, or other search integrations.

---

## How to run the project

```bash
# Install
pip install -r requirements.txt

# Seed demo data (Red Sea crisis scenario)
python -m scripts.seed_demo

# Start API backend (port 8000) — includes APScheduler
uvicorn api.main:app --reload

# Start dashboard (port 8501)
streamlit run dashboard/app.py

# Run full pipeline manually
curl -X POST http://localhost:8000/scan

# Run tests
pytest tests/ -v
```

---

## Project structure at a glance

```
agents/         — 4 pipeline agents (signal_monitor, risk_scorer, impact_analyst, alert_dispatcher)
data/           — data fetchers (GDELT, NewsAPI, NOAA) + geo matching
db/             — SQLAlchemy models + CRUD (suppliers, events, risk_scores, alerts)
api/            — FastAPI backend + APScheduler + REST routes
dashboard/      — Streamlit app + Pydeck map + Plotly charts + Gemini chat
prompts/        — System prompt text files (one per agent + chat)
tests/          — Unit + integration tests (Gemini calls are mocked)
scripts/        — seed_demo.py for Red Sea crisis scenario
```

---

## Environment variables

All config lives in `.env` (copy from `.env.example`):

| Variable | Required | Notes |
|---|---|---|
| `GOOGLE_API_KEY` | Yes | From aistudio.google.com/apikey |
| `GEMINI_MODEL` | No | Defaults to `gemini-2.0-flash` |
| `NEWS_API_KEY` | Yes | newsapi.org free tier |
| `SLACK_WEBHOOK_URL` | Yes for alerts | Slack Incoming Webhooks |
| `GMAIL_CREDENTIALS_FILE` | No | `credentials.json` from Google Cloud Console |
| `DATABASE_URL` | No | Defaults to `sqlite:///./chainwatch.db` |
| `HIGH_RISK_THRESHOLD` | No | Defaults to `7` |
| `ALERT_COOLDOWN_HOURS` | No | Defaults to `24` |
| `SCAN_INTERVAL_MINUTES` | No | Defaults to `30` |

---

## Database

SQLAlchemy ORM with 4 tables. SQLite in dev, PostgreSQL in prod via one-line env change.

```
suppliers     — name, country_code, product_category, tier, lat, lng
events        — source, headline, url (dedup key), category, affected_countries (JSON), severity_hint
risk_scores   — event_id FK, supplier_id FK, score (1–10), impact_window, reasoning
alerts        — risk_score_id FK, level (HIGH/MEDIUM/LOW), brief, alternatives, dispatched_via
```

`init_db()` in `db/database.py` creates all tables — called on FastAPI startup.

---

## Agent pipeline flow

```
APScheduler (30 min)
  → signal_monitor.run_signal_monitor()     # fetch + keyword filter + Gemini classify → events table
  → risk_scorer.run_risk_scorer()           # geo-match + Gemini batch score → risk_scores table
  → if score >= 7:
      impact_analyst.write_brief_for_score()  # Gemini + Google Search → brief text
      alert_dispatcher.dispatch_alert()       # cooldown check → Slack + Gmail → alerts table
```

The same flow runs on `POST /scan` for manual triggers.

---

## Conventions

- All Gemini calls have `try/except` and return safe defaults on failure — never crash the pipeline
- Supplier batching: max 5 per Gemini call in the risk scorer (`BATCH_SIZE = 5`)
- Keyword pre-filter in `data/sources.py` runs before any event hits the DB or LLM
- Country codes are always ISO 3166-1 alpha-2 (2 letters uppercase). Aliases in `geo_matcher.py`
- Cooldown dedup: `db/crud.py:alert_in_cooldown()` checks `(supplier_id, category)` within 24h
- URL field in `events` is the deduplication key — checked with `event_exists()` before any insert

---

## Do not add

- Any Anthropic/OpenAI/LangChain provider imports
- Tavily, SerpAPI, or other search APIs (Gemini Search grounding covers this)
- SendGrid (Gmail API is the email channel)
- Any new dependencies not in `requirements.txt` without discussion
- Comments explaining what code does — only add comments for non-obvious WHY reasons

---

## Testing approach

Gemini API calls are mocked in all tests (`@patch("agents.signal_monitor._client")`).  
Integration tests in `test_pipeline_e2e.py` use an in-memory SQLite DB.  
Run with: `pytest tests/ -v`

---

## Known TODOs (from session handoff)

- Wire `/risk-scores` API endpoint for the Plotly timeline chart in `dashboard/components/replay.py`
- Gmail auth uses `run_local_server()` — needs adjustment for Docker/headless deploy
- GDELT `timespan=30min` param needs verification on Day 1

See `HANDOFF.md` for the full day-by-day plan and checklist.
