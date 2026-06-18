# ChainWatch — Session Handoff

**Date:** 2026-06-17  
**Course:** Kaggle × Google 5-Day AI Agents Intensive  
**Session goal achieved:** Full project scaffolded, Google AI Studio substitutions applied throughout.

---

## What Was Built This Session

The entire project skeleton was created from scratch based on the ChainWatch project plan PDF, adapted to use Google AI Studio (Gemini 2.0 Flash) instead of Anthropic Claude throughout.

### Files created (44 total)

```
requirements.txt          — google-genai, fastapi, streamlit, apscheduler, slack-sdk, gmail api
.env.example              — all required keys with comments
.gitignore                — updated with *.db, credentials.json, token.json

db/
  models.py               — SQLAlchemy ORM: Supplier, Event, RiskScore, Alert
  database.py             — engine + SessionLocal + init_db()
  crud.py                 — full CRUD: suppliers, events, risk_scores, alerts + cooldown logic

data/
  sources.py              — GDELT, NewsAPI, NOAA fetchers + keyword pre-filter
  geo_matcher.py          — ISO code → lat/lng + supplier lookup
  country_centroids.json  — lat/lng for all ~200 countries
  seed_suppliers.csv      — 9 demo suppliers (TW, CN, VN, MX, DE, IN, BD, KR, MY)

prompts/
  classify_event.txt      — Agent 1 system prompt (JSON mode, ISO codes only)
  score_risk.txt          — Agent 2 system prompt (batch scoring, 1–10 scale)
  write_brief.txt         — Agent 3 system prompt (3-para structure, anti-hallucination)
  chat_context.txt        — Chat Q&A template (injects suppliers + alerts + events)

agents/
  signal_monitor.py       — Gemini JSON classification + dedup + DB store
  risk_scorer.py          — Gemini batch scoring (5 suppliers/call) + threshold logic
  impact_analyst.py       — Gemini + Google Search grounding → 3-para brief
  alert_dispatcher.py     — 24h cooldown + Slack Block Kit + Gmail API

api/
  main.py                 — FastAPI app + /scan endpoint + startup/shutdown hooks
  scheduler.py            — APScheduler wiring (30-min pipeline cron)
  routes/suppliers.py     — GET /suppliers, POST /suppliers/upload-csv
  routes/events.py        — GET /events, GET /events/range
  routes/alerts.py        — GET /alerts, GET /alerts/unread-count, POST /alerts/{id}/read

dashboard/
  app.py                  — Streamlit main: 5 tabs + sidebar + cache + CSV upload
  components/risk_map.py  — Pydeck ScatterplotLayer, color-coded by max risk score
  components/alert_feed.py — Expandable alert cards sorted by severity
  components/chat.py      — Gemini multi-turn chat with live context injection
  components/replay.py    — Date-range slider + Plotly event histogram + timeline

scripts/
  seed_demo.py            — Seeds 9 suppliers + 6 Red Sea crisis events (Dec 2023)

tests/
  test_classifier.py      — Unit tests for Gemini classifier (mocked)
  test_risk_scorer.py     — Unit tests for batch scorer (mocked)
  test_pipeline_e2e.py    — Integration tests against in-memory SQLite

Dockerfile                — Multi-stage: builder + slim runtime
docker-compose.yml        — api + dashboard services, SQLite volume
README.md                 — Full setup guide, architecture diagram, cost table
```

---

## Current State

### What works (code is complete and ready to run)
- All 44 files are written and internally consistent
- Database schema is fully defined — `init_db()` creates all 4 tables
- The full pipeline flow is wired: signal_monitor → risk_scorer → impact_analyst → alert_dispatcher
- The `/scan` endpoint triggers the full pipeline manually
- Demo seed data covers the Red Sea crisis scenario exactly as specced

### What is NOT done yet (requires your action)
- **No API keys filled in** — `.env` file must be created from `.env.example`
- **No packages installed** — `pip install -r requirements.txt` not yet run
- **No database created** — `init_db()` runs on first API startup
- **No Gmail OAuth flow completed** — requires `credentials.json` download + first-run browser auth
- **Tests not run** — they are written but not verified against the live SDK

### Known gaps to address during the 5-day sprint
1. `dashboard/app.py` risk timeline tab passes an empty `[]` for raw risk scores — needs a `/risk-scores` API endpoint wired in (Day 4)
2. `alert_dispatcher.py` Gmail auth uses `run_local_server()` which opens a browser — fine for local dev, needs a workaround (service account or pre-generated token) for Docker/Railway
3. GDELT `timespan=30min` parameter may not be supported in all GDELT API versions — test on Day 1 and fall back to `timespan=1h` if needed
4. The `api/routes/__init__.py` is empty — FastAPI discovers routes via `app.include_router()` in `main.py`, which is correct

---

## Google AI Studio Substitutions (key decisions)

| What the plan said | What was built instead | Why |
|---|---|---|
| `anthropic` SDK, `claude-sonnet-4-6` | `google-genai` SDK, `gemini-2.0-flash` | Kaggle course uses Google AI Studio |
| Tavily web search ($10/mo) | Gemini Google Search grounding (built-in) | No extra key, no extra cost, better integration |
| SendGrid email | Gmail API (Google OAuth2) | Fits Google ecosystem, free quota |
| `ANTHROPIC_API_KEY` | `GOOGLE_API_KEY` | Single key from aistudio.google.com |

### Critical Gemini SDK patterns used throughout

```python
# 1. JSON mode (Agents 1 & 2) — no regex, no post-processing
from google import genai
from google.genai import types
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

response = client.models.generate_content(
    model="gemini-2.0-flash",
    contents=prompt,
    config=types.GenerateContentConfig(
        response_mime_type="application/json",
        temperature=0.1,
    ),
)
result = json.loads(response.text)

# 2. Google Search grounding (Agent 3) — replaces Tavily
response = client.models.generate_content(
    model="gemini-2.0-flash",
    contents=prompt,
    config=types.GenerateContentConfig(
        tools=[types.Tool(google_search=types.GoogleSearch())],
        system_instruction=system_prompt,
        temperature=0.3,
    ),
)

# 3. Multi-turn chat (dashboard) — stateful contents list
contents = [types.Content(role="user", parts=[types.Part(text=msg)]) for msg in history]
```

---

## Pre-Work Checklist (complete before Day 1 coding)

- [ ] Get `GOOGLE_API_KEY` from [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
- [ ] Get `NEWS_API_KEY` from [newsapi.org](https://newsapi.org) (free tier, 100 req/day)
- [ ] Create Slack app + `#alerts` channel + copy webhook URL to `.env`
- [ ] Create Slack demo workspace if you don't have one
- [ ] (Optional) Download `credentials.json` from Google Cloud Console for Gmail
- [ ] Create `.env` from `.env.example` and fill in all keys
- [ ] Run: `pip install -r requirements.txt`
- [ ] Verify: `python -c "from google import genai; print('OK')"`
- [ ] Verify API key: `python -c "from google import genai; import os; from dotenv import load_dotenv; load_dotenv(); c = genai.Client(api_key=os.getenv('GOOGLE_API_KEY')); r = c.models.generate_content(model='gemini-2.0-flash', contents='ping'); print(r.text)"`
- [ ] Run: `python -m scripts.seed_demo` (seeds 9 suppliers + 6 Red Sea events)

---

## Day-by-Day Plan With Checkboxes

### Day 1 — Signal ingestion + Gemini classification

- [ ] Run `scripts/seed_demo.py` — verify suppliers and events appear in DB
- [ ] Test `data/sources.py` manually: `from data.sources import fetch_gdelt_events; print(fetch_gdelt_events(5))`
- [ ] Test `agents/signal_monitor.py` manually: `python -m agents.signal_monitor`
- [ ] Verify 20+ events classified per hour by checking `sqlite3 chainwatch.db "SELECT COUNT(*) FROM events"`
- [ ] Run unit tests: `pytest tests/test_classifier.py -v`
- [ ] **Fix if needed:** GDELT `timespan` param, NewsAPI response shape, NOAA XML namespace

**Deliverable:** Live event feed classifying events to SQLite — visible with `sqlite3 chainwatch.db`

---

### Day 2 — Supplier graph + risk scoring

- [ ] Start FastAPI: `uvicorn api.main:app --reload`
- [ ] Upload CSV via API: `curl -X POST http://localhost:8000/suppliers/upload-csv -F "file=@data/seed_suppliers.csv"`
- [ ] Verify suppliers at `http://localhost:8000/suppliers/`
- [ ] Test `agents/risk_scorer.py`: `python -m agents.risk_scorer`
- [ ] Verify scores in DB: `sqlite3 chainwatch.db "SELECT supplier_id, score, impact_window FROM risk_scores LIMIT 10"`
- [ ] Run unit tests: `pytest tests/test_risk_scorer.py -v`
- [ ] **Add if missing:** `/risk-scores` route for timeline chart in dashboard

**Deliverable:** Risk scores per supplier per event in DB with 1–10 score and reasoning

---

### Day 3 — Impact Analyst + Alert Dispatcher

- [ ] Test `agents/impact_analyst.py` on a seeded HIGH event manually
- [ ] Verify Slack alert arrives in `#alerts` channel
- [ ] Test full pipeline: `curl -X POST http://localhost:8000/scan`
- [ ] Check alerts table: `sqlite3 chainwatch.db "SELECT level, brief FROM alerts LIMIT 3"`
- [ ] Verify 24h cooldown works (run scan twice — second should not re-alert)
- [ ] Test Gmail send (or confirm it's skipped gracefully if unconfigured)
- [ ] Run: `pytest tests/test_pipeline_e2e.py -v`

**Deliverable:** Full end-to-end alert in Slack with Gemini-written brief and alternative regions

---

### Day 4 — Dashboard + chat Q&A

- [ ] Start Streamlit: `streamlit run dashboard/app.py`
- [ ] Verify supplier map loads with color-coded dots
- [ ] Upload CSV via sidebar upload widget
- [ ] Verify alert feed shows HIGH alerts with expandable briefs
- [ ] Test chat with 5 questions (see demo script in README)
- [ ] Wire risk timeline: add `/risk-scores` API endpoint + update `replay.py`
- [ ] Test replay mode with Dec 2023 date range

**Deliverable:** Streamlit dashboard on localhost with risk map, alert feed, timeline, chat

---

### Day 5 — Polish + deploy

- [ ] Fix any broken UI flows found on Day 4
- [ ] Write `Dockerfile` test: `docker-compose up --build`
- [ ] Deploy to Railway (or Google Cloud Run): set all env vars
- [ ] Smoke-test live URL: upload CSV → scan → alert fires
- [ ] Record Loom: 3-minute demo following the script in README
- [ ] Make GitHub repo public
- [ ] Verify README renders on GitHub with all links working

**Deliverable:** Live public URL + recorded demo + clean public GitHub repo

---

## How to Verify Each Agent in Isolation

```bash
# Agent 1 — Signal Monitor
python -m agents.signal_monitor

# Agent 2 — Risk Scorer (runs on whatever events are already in DB)
python -m agents.risk_scorer

# Full pipeline (all 4 agents)
curl -X POST http://localhost:8000/scan

# Check what's in the DB
sqlite3 chainwatch.db "SELECT source, category, severity_hint, headline FROM events ORDER BY ingested_at DESC LIMIT 10"
sqlite3 chainwatch.db "SELECT score, impact_window, reasoning FROM risk_scores ORDER BY scored_at DESC LIMIT 5"
sqlite3 chainwatch.db "SELECT level, brief FROM alerts ORDER BY created_at DESC LIMIT 3"
```

---

## Architecture Decisions Worth Remembering

| Decision | Rationale |
|---|---|
| Keyword pre-filter before Gemini | Saves ~80% of API calls — only relevant events hit the LLM |
| Batch 5 suppliers per Gemini call | Reduces scoring calls by 5× — key cost control |
| 24h cooldown per (supplier_id, category) | Prevents alert spam for ongoing events |
| `UniqueConstraint("event_id", "supplier_id")` in `risk_scores` | Never score the same pair twice |
| `response_mime_type="application/json"` | Forces Gemini to return clean JSON without markdown fences |
| `url` field as dedup key in `events` | URL hash deduplication before any DB insert |
| Google Search grounding over Tavily | No extra API key, no rate limits to manage, native to Gemini |
| SQLite → PostgreSQL via one-line config | `DATABASE_URL` env var switches the ORM target transparently |

---

## Next Steps Summary

The scaffolding is complete. The next work is:

1. **Fill `.env`** with real keys (this is the Day 0 blocker)
2. **Install dependencies** and verify the Gemini hello-world works
3. **Run `seed_demo.py`** to have data immediately available
4. **Start Day 1** by running `signal_monitor.py` and watching events appear in SQLite
