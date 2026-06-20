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

### Use schema-validated structured outputs (v3.0)

Pass a Pydantic model as `response_schema` and validate via the helpers in
`schemas.py` (`parse_object` / `parse_list`). This replaces fragile
`json.loads(response.text)` and enforces enums + numeric bounds before any value
reaches downstream code.

```python
from schemas import EventClassification, parse_object

config=types.GenerateContentConfig(
    response_mime_type="application/json",
    response_schema=EventClassification,
    temperature=0.1,
)
result = parse_object(response, EventClassification).model_dump()
```

Construct the Gemini client via the `providers.py` factory
(`get_gemini_client()` / `get_model_name()`), not `genai.Client(...)` directly —
one construction point keeps configuration and Phoenix instrumentation in one place.

### Web research boundary (v3.0 — Tavily is now allowed)

Two complementary web-research mechanisms, used for different jobs:

- **Gemini Google Search grounding** stays the in-brief web tool in the
  **Impact Analyst** (`tools=[types.Tool(google_search=types.GoogleSearch())]`).
- **Tavily** (`data/tavily_research.py`) provides **full-article content
  extraction** and **deep live search** for the Signal Monitor (full text vs
  headline-only), Risk Scorer (supplier-specific context), and as brief
  augmentation. Tavily is opt-in via `TAVILY_ENABLED` and degrades to a no-op
  without `TAVILY_API_KEY`. Scraped text passes the input guardrail
  (`guardrails/injection.py`) before reaching any Gemini prompt.

> This reverses the earlier "never add Tavily" rule. DuckDuckGo/SerpAPI/other
> search APIs remain disallowed — Tavily + Gemini grounding cover web research.

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

# Run full pipeline manually (LangGraph orchestration)
curl -X POST http://localhost:8000/scan

# Run tests (mocked Gemini/Tavily/Ollama)
pytest tests/ -v          # or: make test
```

### v3.0 extras

```bash
# Seed RAG institutional memory (events + briefs + KB) — needs RAG_ENABLED=true
RAG_ENABLED=true python -m scripts.backfill_index

# Build the navigable documentation PDF (cover + TOC + bookmarks)
uv sync --group docs && make docs-pdf      # → site/ChainWatch-Documentation.pdf

# Offline RAG-quality eval (Ragas; Gemini judge + Google embeddings)
uv sync --group evals && python -m evals.run_ragas

# Full stack incl. Phoenix (traces, :6006) + Ollama (Gemma) via Docker
docker compose up --build
docker compose exec ollama ollama pull gemma3:4b   # first run only
RUN_SCAN=1 python -m scripts.e2e_smoke             # end-to-end smoke
```

Optional dependency groups (kept out of the lean default install): `viz`
(Phoenix server), `rerank` (sentence-transformers/Torch), `evals` (ragas),
`docs` (mkdocs). Heavy/optional features are all flag-gated and degrade to
no-ops when off.

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
| `PHOENIX_ENABLED` | No | `true` to enable Arize Phoenix tracing (default off) |
| `PHOENIX_PROJECT_NAME` | No | Phoenix project name (default `chainwatch`) |
| `PHOENIX_COLLECTOR_ENDPOINT` | No | Phoenix collector URL (default SDK endpoint / `:6006`) |
| `TAVILY_ENABLED` | No | `true` to enable Tavily scraping (Phase 1, default off) |
| `TAVILY_API_KEY` | No | Tavily key; without it Tavily is a no-op |

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

Orchestrated as a LangGraph `StateGraph` in `orchestration/graph.py` (v3.0):

```
START → signal → econ_weather → score ─┬─(HIGH ≥7)→ impact_dispatch → forecast → END
                                       └─(none)─────────────────────→ forecast → END
```

- `signal` — fetch + (optional Tavily full-text) + Gemini classify → events
- `econ_weather` — FRED/Yahoo indicators + Open-Meteo weather events
- `score` — geo-match + Gemini batch score (+ RAG priors, Tavily MEDIUM elevation)
- `impact_dispatch` — Gemini + Google Search brief (+ RAG/Tavily/Gemma judge) → Slack/Gmail
- `forecast` — 6-horizon probability forecasts per supplier

Both the APScheduler tick (`api/scheduler.py`) and `POST /scan` (`api/main.py`) call
`orchestration.graph.run_pipeline(industry)`, wrapped in one Phoenix trace.

---

## Conventions

- All Gemini calls have `try/except` and return safe defaults on failure — never crash the pipeline
- Gemini outputs are validated through `schemas.py` Pydantic models (`response_schema` + `parse_object`/`parse_list`) — no raw `json.loads`
- Gemini client comes from the `providers.py` factory; observability is initialised once via `observability.setup_observability()` at each entry point
- Supplier batching: max 5 per Gemini call in the risk scorer (`BATCH_SIZE = 5`)
- Keyword pre-filter in `data/sources.py` runs before any event hits the DB or LLM
- Country codes are always ISO 3166-1 alpha-2 (2 letters uppercase). Aliases in `geo_matcher.py`
- Cooldown dedup: `db/crud.py:alert_in_cooldown()` checks `(supplier_id, category)` within 24h
- URL field in `events` is the deduplication key — checked with `event_exists()` before any insert

---

## Do not add

- Any Anthropic/OpenAI provider imports (LangChain/LangGraph **are** allowed — Gemini via `langchain-google-genai`; self-hosted Gemma via Ollama is also allowed)
- SerpAPI, DuckDuckGo, or other search APIs (Tavily + Gemini Search grounding cover web research)
- SendGrid (Gmail API is the email channel)
- Any new runtime dependencies not in `requirements.txt` without discussion
- Inline comments explaining *what* code does — only WHY. (Public-API **docstrings** describing purpose/args/returns ARE required as of v3.0.)

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
