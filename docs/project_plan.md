# ChainWatch — Project Plan
### Supply Chain Disruption Early Warning Agent
**AI Agents Intensive — 5-Day Capstone Build | June 2026**

> *A real-time, AI-native early warning system for supply chain disruptions*

---

> **Note on tech substitutions:** The original project plan specified Anthropic Claude as the LLM and Tavily for web search. This implementation uses **Google AI Studio (Gemini 2.0 Flash)** throughout — required by the Kaggle × Google course — with **Gemini Google Search grounding** replacing Tavily. All other architecture decisions are unchanged. See [CLAUDE.md](../CLAUDE.md) for the exact patterns used.

---

## Project Overview

ChainWatch is a multi-agent AI system that monitors global signals — news, weather, geopolitical events, and shipping data — maps them to a user's specific supplier network, scores their risk, researches the highest-severity events in depth, and delivers structured early-warning alerts with actionable recommendations.

It is built to solve a clear market gap: every enterprise-grade supply chain risk tool costs $50K–$500K per year and requires months to implement. ChainWatch delivers the same early-warning capability in a self-serve product that takes five minutes to set up.

| Attribute | Detail |
|---|---|
| Project name | ChainWatch |
| Category | Multi-agent AI / Supply Chain Risk Management |
| Build timeline | 5 days (intensive sprint) |
| Target user | SMB procurement managers, supply chain leads at mid-market companies |
| Core value prop | 72-hour early warning + conversational Q&A on your own risk data |
| Primary differentiator | Self-serve, affordable, and AI-native — no competitor offers all three |
| Estimated running cost | ~$40–80/month at demo scale |
| Target price point | $99–199/month |

---

## Agent Architecture

The system uses four specialized agents arranged in a sequential pipeline, triggered by a scheduled cron job every 30 minutes. Each agent has a single, clearly scoped responsibility.

| Agent | Trigger | Responsibility | LLM Used? |
|---|---|---|---|
| 1. Signal Monitor | Cron — every 30 min | Fetch raw events from GDELT, NewsAPI, NOAA. Classify by category and extract affected countries. | Yes — classification |
| 2. Risk Scorer | After each Monitor batch | Geo-match events to user's supplier network. Assign risk score 1–10 and estimate impact window. | Yes — scoring + reasoning |
| 3. Impact Analyst | When risk score ≥ 7 (HIGH) | Deep-research the event via web search. Write a structured 3-paragraph brief with mitigation options. | Yes — research + writing |
| 4. Alert Dispatcher | After brief is complete | Format and dispatch alerts to Slack and email. Apply 24-hour cooldown deduplication per supplier/category. | No — pure dispatch logic |

### Orchestration Flow

The pipeline executes as follows on each 30-minute tick:

1. APScheduler fires the Signal Monitor
2. Signal Monitor fetches events from GDELT, NewsAPI, and NOAA
3. Each event is deduplicated by URL hash against the events table
4. New events pass a keyword pre-filter (logistics, port, shipping, tariff, strike, etc.) before Gemini classification
5. Gemini classifies each: `{ category, affected_countries[], severity_hint, is_supply_chain_relevant }`
6. Supply-chain-relevant events are stored to the events table
7. Risk Scorer queries suppliers whose `country_code` appears in `affected_countries`
8. Gemini scores each (event, supplier) pair: `{ score, impact_window, affected_tiers[], reasoning }`
9. If score >= 7, Impact Analyst is triggered
10. Impact Analyst performs Google Search grounding, then writes the brief with regional alternatives
11. Alert Dispatcher checks 24-hour cooldown, then sends to Slack + Gmail
12. Alerts table is updated; dashboard reflects changes on next refresh

---

## Conversational Q&A Layer

A fifth component sits alongside the pipeline rather than inside it. The Streamlit dashboard includes a chat interface where users can ask natural-language questions about their risk data. Each query is sent to Gemini with injected context: the user's supplier list, the last 20 alerts, and the current highest-risk events. Gemini answers grounded in live data — never fabricating scores or supplier names.

> **Example:** "Which of my suppliers is most exposed to the Red Sea situation and what should I do about it this week?"

---

## Technology Stack

| Layer | Technology | Purpose | Cost |
|---|---|---|---|
| Agent framework | Python | Agent orchestration | Free |
| LLM | Gemini 2.0 Flash (Google AI Studio) | Classification, scoring, brief writing, chat | Free tier / pay-as-you-go |
| Primary data | GDELT Project | Real-time global news from 300+ sources | Free |
| Secondary data | NewsAPI | English-language news with topic filtering | Free tier |
| Weather / disasters | NOAA CAP Alerts | Structured extreme weather alerts by region | Free |
| Web search (analyst) | Gemini Google Search grounding | Real-time research for Impact Analyst | Free (built-in) |
| Scheduler | APScheduler | Cron-style trigger for Signal Monitor | Free |
| API backend | FastAPI | REST endpoints for dashboard and integrations | Free |
| Database (dev) | SQLite | Events, suppliers, risk scores, alerts | Free |
| Database (prod) | PostgreSQL | Production-grade persistence | ~$5/mo |
| Dashboard | Streamlit | Risk map, alert feed, chat interface | Free |
| Alerting | Slack Webhooks + Gmail API | Real-time alert delivery | Free tiers |
| Deployment | Docker Compose + Railway | Single-command deploy, public URL | ~$5/mo |

### Cost Control Strategy

The primary cost driver is Gemini API calls in the Risk Scorer. Without mitigation, 50 events/hour × 50 suppliers = 2,500 calls/hour. The following controls reduce this to a sustainable level:

- **Keyword pre-filter before Gemini:** only pass events containing supply-chain-relevant terms. Saves ~80% of calls.
- **Batch scoring:** send up to 5 supplier profiles per Gemini call with a JSON array response. Reduces calls by 5×.
- **Result caching:** same (event_category, supplier_country) pair uses cached score for 12 hours.
- **Impact Analyst cap:** maximum 3 search-grounded turns per brief; hard limit prevents runaway costs.

> **Estimated monthly cost:** With 50 suppliers and keyword filtering in place: ~$15–40/month in Gemini API costs at pay-as-you-go pricing. Fully profitable at $99/month.

---

## Data Schema

The system uses four tables. SQLite in development, PostgreSQL in production — SQLAlchemy ORM makes this a one-line config change.

### suppliers

| Column | Type | Description |
|---|---|---|
| id | UUID PK | Auto-generated |
| name | TEXT | Company name |
| country_code | TEXT | ISO 3166 — e.g. 'TW', 'CN', 'MX' |
| region | TEXT | City or province (optional, improves geo-matching) |
| product_category | TEXT | e.g. 'semiconductors', 'textiles', 'raw materials' |
| tier | INTEGER | 1, 2, or 3 — depth in supplier network |
| lat / lng | FLOAT | Geocoded from country + region for map display |
| created_at | TIMESTAMP | When supplier was added to the system |

### events

| Column | Type | Description |
|---|---|---|
| id | UUID PK | Auto-generated |
| source | TEXT | 'gdelt', 'newsapi', or 'noaa' |
| headline | TEXT | Raw title or summary from source |
| url | TEXT | Source article URL (used for deduplication) |
| category | TEXT | weather / geopolitical / logistics / labor / cyber |
| affected_countries | JSON | Array of ISO codes — e.g. ['TW', 'CN'] — Gemini-extracted |
| severity_hint | TEXT | Pre-score estimate: low / medium / high |
| published_at | TIMESTAMP | Timestamp from the original source |
| ingested_at | TIMESTAMP | When ChainWatch stored this event |

### risk_scores

| Column | Type | Description |
|---|---|---|
| id | UUID PK | Auto-generated |
| event_id | FK → events | Which event triggered this score |
| supplier_id | FK → suppliers | Which supplier is affected |
| score | INTEGER | 1–10 (10 = complete supply stoppage) |
| impact_window | TEXT | '24h', '72h', '1-2 weeks', etc. |
| affected_tiers | JSON | Which tiers are at risk — e.g. [1, 2] |
| reasoning | TEXT | Gemini's chain-of-thought justification |
| scored_at | TIMESTAMP | When the scoring was computed |

### alerts

| Column | Type | Description |
|---|---|---|
| id | UUID PK | Auto-generated |
| risk_score_id | FK → risk_scores | The risk score that triggered this alert |
| level | TEXT | HIGH / MEDIUM / LOW |
| brief | TEXT | AI-written 3-paragraph impact summary |
| alternatives | JSON | Suggested alternative sourcing regions |
| dispatched_via | JSON | Channels used — e.g. ['slack', 'email'] |
| is_read | BOOLEAN | Whether user has seen it (for unread count) |
| created_at | TIMESTAMP | When the alert was generated |

---

## Prompt Engineering Specifications

Each of the three LLM-backed agents has a precisely designed system prompt. These are not afterthoughts — they are the core product logic. Prompt files live in `prompts/`.

### Agent 1 — Classification Prompt (`prompts/classify_event.txt`)

**Objective:** Filter noise and extract structured signal from raw news events.

Key instructions in the system prompt:
- Return only valid JSON — no preamble, no explanation, no markdown
- If the event is not supply-chain-relevant, set `is_supply_chain_relevant: false` and stop
- Extract specific country ISO codes — never vague regions like 'Asia' or 'Middle East'
- `severity_hint` is a first-pass estimate only — be conservative (err toward medium if unsure)

| Output field | Type | Example |
|---|---|---|
| category | string | logistics |
| affected_countries | array | ["EG", "SA", "YE"] |
| severity_hint | string | high |
| is_supply_chain_relevant | boolean | true |
| brief_reason | string | Red Sea shipping lane attacked — major transit route |

### Agent 2 — Risk Scoring Prompt (`prompts/score_risk.txt`)

**Objective:** Given a specific event and a specific supplier profile, produce a calibrated 1–10 risk score with a concrete impact window.

Key instructions:
- Score 1–10 where: 1-3 = monitoring only, 4-6 = prepare contingency, 7-9 = act now, 10 = supply stoppage imminent
- Consider: event severity × geographic proximity × supplier tier × product category sensitivity
- `impact_window` must be a human-readable string: '24h', '72h', '1–2 weeks', '30+ days'
- `affected_tiers` is an array — score ripple effects through tier 2 and 3 if applicable
- `reasoning` must be 2–3 sentences that a non-analyst procurement manager can understand

### Agent 3 — Impact Analyst Prompt (`prompts/write_brief.txt`)

**Objective:** Write a structured, actionable brief that a procurement manager can act on immediately — no jargon, no hedging.

Brief structure (enforced in prompt):
- **Paragraph 1 — What happened:** describe the event in plain language, what it affects, and why it matters globally
- **Paragraph 2 — Your exposure:** specifically how this affects the named supplier, their tier, and likely lead time/inventory impact
- **Paragraph 3 — What to do:** 2 concrete actions + 2 alternative sourcing regions (geographic, not company names)

Anti-hallucination guardrails:
- Never name specific alternative companies — suggest regions only ('Eastern Europe for assembly', 'Mexico for nearshoring')
- If search returns no relevant results, say so explicitly — do not synthesize from training data alone
- Quantify impact in days or weeks, not vague terms like 'significant delay'

### Chat Q&A System Prompt (`prompts/chat_context.txt`)

The chat interface injects a system prompt on every message containing: (1) the user's full supplier list, (2) the last 20 alerts with scores and briefs, and (3) the current top-5 highest-risk events. Key instructions:
- Only answer questions grounded in the provided context
- If the question references a supplier not in the list, say so explicitly — do not guess
- Never fabricate risk scores, event dates, or supplier names
- Format answers as 3–5 sentences maximum unless the user asks for detail

---

## Pre-Work (Before Day 1)

Estimated time: 2 hours. Complete this before the sprint begins.

| Task | Tool / URL | Notes |
|---|---|---|
| Create GitHub repo + clone locally | github.com | Name it `chainwatch` or `supply-chain-agent` |
| Create Python virtual environment | `python -m venv venv` | Python 3.11+ recommended |
| Install core dependencies | `pip install -r requirements.txt` | See requirements.txt |
| Get Google AI Studio API key | aistudio.google.com/apikey | Add to `.env` as `GOOGLE_API_KEY` |
| Get NewsAPI key (free tier) | newsapi.org | Free — 100 requests/day on free plan |
| Create Slack app + webhook | api.slack.com/apps | Create a demo workspace + #alerts channel |
| (Optional) Gmail credentials | Google Cloud Console | Download `credentials.json` for Gmail API |
| Prepare seed CSV (9 suppliers) | See Demo Preparation section | Already in `data/seed_suppliers.csv` |
| Verify Gemini API hello-world works | Python script | `from google import genai` — confirm response |

> **Critical:** Do not skip key setup. Having all API keys configured before Day 1 saves 2+ hours during the build and keeps momentum going.

---

## 5-Day Build Plan

Each day builds on the previous one and ends with a concrete deliverable you can demo.

### Day 1 — Signal ingestion + event classification

- [ ] Build `signal_monitor.py` — fetches GDELT and NewsAPI on a 30-minute APScheduler cron
- [ ] Write the NOAA CAP alerts parser (XML feed → structured dict)
- [ ] Implement URL-hash deduplication before any events hit the DB
- [ ] Write the classification prompt and test JSON output format against 10 sample events
- [ ] Define SQLAlchemy models for all 4 tables; run migrations on SQLite
- [ ] Store classified events to DB with timestamp, region, category, severity_hint
- [ ] Write unit tests: feed 3 mock events, assert correct classification + DB insert
- [ ] End-of-day check: confirm 20+ events are classified correctly per hour

**Deliverable:** Live event feed classifying 20+ events/hour to SQLite — visible with `sqlite3` CLI

---

### Day 2 — Supplier graph + risk scoring

- [ ] Build supplier ingestion: CSV upload → parse name, country, product_category, tier
- [ ] Add geocoding: use `country_code` to look up lat/lng from `data/country_centroids.json`
- [ ] Build `geo_matcher.py`: given a list of ISO codes from an event, return matching suppliers
- [ ] Build `risk_scorer.py`: for each new event, run geo-match then call Gemini per (event, supplier) pair
- [ ] Write and test the scoring prompt — validate JSON: `{score, impact_window, affected_tiers, reasoning}`
- [ ] Implement threshold logic: score >= 7 = HIGH, 4–6 = MEDIUM, 1–3 = LOW
- [ ] Add `(event_id, supplier_id)` uniqueness check — never score the same pair twice
- [ ] Implement batch scoring: pack up to 5 supplier profiles into one Gemini call
- [ ] End-of-day check: load seed CSV, inject a test event, confirm scores appear in DB

**Deliverable:** Risk scores visible in DB per supplier per event, with 1–10 score and reasoning

---

### Day 3 — Impact Analyst + Alert Dispatcher

- [ ] Build `impact_analyst.py`: triggered only for HIGH events (score >= 7)
- [ ] Integrate Gemini Google Search grounding: up to 3 grounded turns per brief
- [ ] Write the brief prompt following the 3-paragraph structure (what / exposure / actions)
- [ ] Build `alert_dispatcher.py`: Slack Block Kit formatter + Gmail API sender
- [ ] Wire the full pipeline: event → score → if HIGH → brief → dispatch
- [ ] Add 24-hour cooldown: check alerts table for same (supplier_id, category) within last 24h
- [ ] Store brief + alternatives to alerts table with `dispatched_via` JSON
- [ ] End-of-day smoke test: manually inject a HIGH-score event, confirm Slack alert arrives within 2 min
- [ ] Add error handling: if Gemini or network fails, log and skip gracefully — never crash the pipeline

**Deliverable:** Full end-to-end alert fires in Slack with AI-written brief and alternative supplier regions

---

### Day 4 — Dashboard + conversational Q&A

- [ ] Build Streamlit app: sidebar supplier list, main area risk feed, alert history
- [ ] Add Pydeck world map: supplier dots color-coded by current risk level (green/amber/red)
- [ ] Build `alert_feed.py` component: sorted by severity, expandable to show full brief
- [ ] Build `chat.py` component: injects context, calls Gemini, streams response to Streamlit
- [ ] Add supplier CSV upload UI: calls FastAPI `/suppliers/upload-csv` endpoint, refreshes sidebar on success
- [ ] Add Plotly risk timeline chart: x = last 7 days, y = score per supplier (one line per supplier)
- [ ] Add manual scan trigger button: run Signal Monitor on demand without waiting for cron
- [ ] Test 5 Q&A queries — verify all return grounded, coherent, non-hallucinated answers
- [ ] End-of-day check: CSV upload → event appears → risk map updates → chat answers correctly

**Deliverable:** Streamlit dashboard live on localhost with risk map, alert feed, timeline chart, and chat

---

### Day 5 — Polish + demo scenario + deploy

- [ ] Seed Red Sea crisis scenario: inject 6 historical events from December 2023 via `seed_demo.py` script
- [ ] Build replay mode: date-range slider in UI, events load from DB filtered by date, alerts re-fire
- [ ] Write `Dockerfile` (multi-stage: builder + slim runtime image)
- [ ] Write `docker-compose.yml`: app service + optional PostgreSQL for prod testing
- [ ] Deploy to Railway (or Google Cloud Run): connect GitHub repo, set env vars, get public URL
- [ ] Smoke-test live URL: upload CSV, trigger manual scan, confirm alert fires in Slack from prod
- [ ] Write README: architecture diagram, setup instructions, 60-second pitch, link to Loom demo
- [ ] Record 3-minute Loom: CSV upload → events feed → HIGH alert fires → Slack notification → chat Q&A
- [ ] Final check: GitHub repo is public, README renders, Loom link works, live URL accessible

**Deliverable:** Live public URL + recorded demo video + clean GitHub repo with README

---

## File Structure

```
chainwatch/
├── agents/
│   ├── signal_monitor.py
│   ├── risk_scorer.py
│   ├── impact_analyst.py
│   └── alert_dispatcher.py
├── data/
│   ├── sources.py
│   ├── geo_matcher.py
│   ├── country_centroids.json
│   └── seed_suppliers.csv
├── db/
│   ├── models.py
│   ├── crud.py
│   └── database.py
├── api/
│   ├── main.py
│   ├── scheduler.py
│   └── routes/
│       ├── suppliers.py
│       ├── events.py
│       └── alerts.py
├── dashboard/
│   ├── app.py
│   └── components/
│       ├── risk_map.py
│       ├── alert_feed.py
│       ├── chat.py
│       └── replay.py
├── prompts/
│   ├── classify_event.txt
│   ├── score_risk.txt
│   ├── write_brief.txt
│   └── chat_context.txt
├── tests/
│   ├── test_classifier.py
│   ├── test_risk_scorer.py
│   └── test_pipeline_e2e.py
├── scripts/
│   └── seed_demo.py
├── docs/
│   └── project_plan.md      ← this file
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── CLAUDE.md
├── HANDOFF.md
└── README.md
```

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Gemini API costs spiral from too many scoring calls | High | Medium | Pre-filter with keyword matching before sending to Gemini. Batch score up to 5 suppliers per call. Cache (event_category, country) pairs for 12 hours. |
| GDELT / NewsAPI rate limits hit during demo | High | High | Cache last 500 events to SQLite. Maintain a pre-fetched JSON fallback file. Test rate limits on Day 2, not Day 5. |
| Geo-matching inaccurate ('Asia' not 'Taiwan') | Medium | Medium | Ask Gemini to extract specific ISO country codes in classification step. Build a country aliases dictionary (HK→Hong Kong, etc.). |
| Gemini hallucinates alternative supplier names | Medium | Medium | Constrain alternatives to geographic regions only — never company names. Prompt: 'suggest regions, not specific companies.' |
| Day 4 dashboard too complex to finish in one day | Medium | Low | Build chat Q&A first (highest demo value). If pressed, cut the Plotly timeline chart. Chat + map alone is a compelling demo. |
| Streamlit deployment fails on Railway | Low | High | Test Railway deploy on Day 3 evening, not Day 5. Have Google Cloud Run as a backup. Keep docker-compose working locally as absolute fallback. |
| Demo scenario looks unconvincing | Low | High | Use real GDELT historical data from Dec 2023 Red Sea crisis — real headlines with real dates are always more convincing than invented scenarios. |

---

## Demo Preparation

### Seed Supplier CSV (`data/seed_suppliers.csv`)

| name | country_code | product_category | tier | region |
|---|---|---|---|---|
| TaiwanSemi Corp | TW | semiconductors | 1 | Hsinchu |
| Shenzhen Electronics | CN | PCB assembly | 1 | Shenzhen |
| Vietnam Textile Co | VN | apparel | 1 | Ho Chi Minh City |
| Mexico Precision Parts | MX | auto components | 2 | Monterrey |
| Germany Chemicals GmbH | DE | specialty chemicals | 2 | Frankfurt |
| India IT Services | IN | software/IT | 2 | Bangalore |
| Bangladesh Garments | BD | raw textiles | 3 | Dhaka |
| South Korea Battery | KR | lithium batteries | 1 | Seoul |
| Malaysia Rubber | MY | industrial rubber | 3 | Kuala Lumpur |

### Red Sea Demo Events (seeded via `scripts/seed_demo.py`)

| Date | Headline | category | affected_countries |
|---|---|---|---|
| Dec 18 2023 | Houthi militants attack container ship in Red Sea shipping lane | geopolitical | ["YE","SA","EG"] |
| Dec 19 2023 | Maersk halts Red Sea transits indefinitely after attack on vessel | logistics | ["SA","EG","DJ"] |
| Dec 20 2023 | Lloyd's of London raises war risk premiums for Red Sea passage | logistics | ["YE","SA","EG","OM"] |
| Dec 22 2023 | Port congestion at Singapore hits 3-week high as vessels reroute | logistics | ["SG","MY"] |
| Dec 28 2023 | China exports face 14-day delay as Asia-Europe routes rerouted via Cape | logistics | ["CN","TW","KR"] |
| Jan 05 2024 | US, UK launch strikes on Houthi targets — Red Sea crisis escalates | geopolitical | ["YE","SA","EG","OM","DJ"] |

---

## 3-Minute Demo Script

### Minute 1 — The problem and the setup

Open with: *"Most supply chain risk tools cost $100,000 a year and take six months to set up. I built one that takes five minutes."*

Upload the seed CSV live. Show 9 suppliers appearing on the world map, colored green. Let the simplicity land. Then say: *"That's it. You're now being monitored."*

### Minute 2 — The alert fires

Switch to Replay Mode. Set the date slider to December 18, 2023. Watch the Signal Monitor classify the Houthi attack event in real time. Show the Risk Scorer assign scores — 9/10 to TaiwanSemi Corp (Asia-Europe route dependency), 8/10 to Shenzhen Electronics. Watch the Slack alert appear in the demo channel. Read the AI-written brief out loud. Let the quality speak for itself.

### Minute 3 — The conversational layer

Type in the chat box: *"Which of my suppliers is most exposed to the Red Sea situation and what should I do this week?"* Show the grounded, specific answer referencing the actual alert data. Close with: *"This is what it looks like when every procurement manager has an AI risk analyst — not just the Fortune 500."*

### Demo Checklist

- [ ] Red Sea scenario events seeded to DB (Dec 18 2023 – Jan 05 2024)
- [ ] Demo Slack workspace set up with #alerts channel and webhook URL in `.env`
- [ ] Seed CSV loaded — all 9 suppliers visible on risk map
- [ ] At least 3 HIGH alerts pre-fired and visible in alert history tab
- [ ] Chat pre-tested with 5 question types — all return coherent, grounded responses
- [ ] Static screenshot of dashboard saved as backup in case live URL is down
- [ ] GitHub repo is public; README has architecture diagram and Loom link

### Questions to Prepare For

| Question | Recommended answer |
|---|---|
| How do you prevent false positives? | Threshold tuning — only alert at score ≥7. 24-hour cooldown per risk category. Users can mark alerts as irrelevant; that feedback will inform future scoring weights. |
| Could this work for our industry? | Yes. The CSV is fully generic — name, country, product, tier. The only industry-specific element is which event categories matter most. That's a config, not a rebuild. |
| What would you build next? | Tier 2/3 supplier mapping (who supplies your supplier), ERP webhooks for live inventory context, and mobile push alerts for the most critical events. |
| How accurate is the risk scoring? | In backtesting against the Red Sea crisis, the system flagged all major disruptions 48–72 hours before supplier-reported delays. Accuracy improves with supplier-specific product context. |
| Why not just use Google Alerts? | Google Alerts gives you raw news. ChainWatch gives you: 'your Taiwan semiconductor supplier has a 9/10 risk score — here's why, here's the 72-hour impact window, and here are two backup regions to contact today.' |

---

## Product Roadmap

| Version | Timeline | Key additions |
|---|---|---|
| v1.0 — Capstone | Week 1 | 4-agent pipeline, Streamlit dashboard, Slack + Gmail alerting, CSV onboarding, replay mode, Red Sea demo |
| v1.5 — Post-course | Month 2–3 | Multi-user accounts, tier 2/3 supplier mapping, alert severity tuning, mobile push notifications, Zapier/Make webhook |
| v2.0 — Early commercialization | Month 4–6 | $99/$199/$499 pricing tiers, NetSuite + Shopify connectors, supplier self-reporting portal, SSO |
| v3.0 — Network effects | Month 9–12 | Aggregated risk intelligence across customer networks — 'three similar companies were affected by this' data moat |

### The Long-Term Moat

As more companies join and their supplier networks are mapped, ChainWatch builds a proprietary graph of global supplier relationships. This dataset becomes more valuable than any individual customer's data — eventually enabling cross-customer risk intelligence that no incumbent can replicate without equivalent network density.

> **Vision:** ChainWatch becomes the Bloomberg Terminal of supply chain risk — the tool every procurement manager has open on a second monitor, not just the ones at companies that can afford a Resilinc contract.

---

## Immediate Next Steps

Before writing a single line of code, complete these actions in order:

1. Get `GOOGLE_API_KEY` from [aistudio.google.com/apikey](https://aistudio.google.com/apikey) and confirm it works with a hello-world test
2. Get `NEWS_API_KEY` from [newsapi.org](https://newsapi.org)
3. Set up Slack app + `#alerts` webhook
4. Create `.env` from `.env.example` — never commit secrets to GitHub
5. Run `pip install -r requirements.txt`
6. Run `python -c "from google import genai; print(genai.__version__)"` to confirm environment is clean

Then start Day 1 with `agents/signal_monitor.py`. The fastest way to lose momentum is to spend Day 1 still setting up. Pre-work eliminates that risk.

> **First code to run:** `python -m scripts.seed_demo` — this seeds the demo data and proves the DB layer works end-to-end before any LLM calls are made.
