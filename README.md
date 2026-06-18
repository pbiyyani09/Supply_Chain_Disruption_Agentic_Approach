# ChainWatch — Supply Chain Disruption Early Warning Agent

> AI Agents Intensive — 5-Day Capstone | Kaggle × Google  
> **Powered by Google AI Studio (Gemini 2.0 Flash)**

A real-time, multi-agent system that monitors global signals, maps them to your supplier network, scores risk with Gemini, and delivers structured early-warning alerts with actionable briefs.

---

## Google AI Studio Integration

This project runs entirely on **Google AI Studio** — the same platform used throughout the Kaggle course. Every LLM call goes through the `google-genai` SDK with `gemini-2.0-flash`.

| Original Plan | Google AI Studio Replacement | Benefit |
|---|---|---|
| Claude claude-sonnet-4-6 | **Gemini 2.0 Flash** | Faster, cheaper, native Google integration |
| Tavily web search | **Gemini Google Search grounding** | Built-in — no extra API key, no extra cost |
| SendGrid email | **Gmail API** | Google OAuth2 — fits the course ecosystem |
| (no change) | GDELT, NewsAPI, NOAA | Free data sources remain the same |

### Key Gemini Features Used

1. **`response_mime_type="application/json"`** — Forces structured JSON output from Signal Monitor and Risk Scorer without post-processing hacks.
2. **`tools=[types.Tool(google_search=types.GoogleSearch())]`** — Native Google Search grounding in the Impact Analyst replaces Tavily entirely.
3. **Multi-turn chat** — Conversational Q&A uses stateful `contents` history passed on every turn.

---

## Architecture

```
                        ┌─────────────────────────────────────┐
                        │   APScheduler (every 30 min)        │
                        └──────────────┬──────────────────────┘
                                       │
                        ┌──────────────▼──────────────────────┐
          Agent 1       │         Signal Monitor              │
                        │  GDELT + NewsAPI + NOAA → Gemini    │
                        │  classify → store to events table   │
                        └──────────────┬──────────────────────┘
                                       │ new supply-chain events
                        ┌──────────────▼──────────────────────┐
          Agent 2       │           Risk Scorer               │
                        │  geo-match suppliers → Gemini score │
                        │  batch 5 suppliers/call → 1–10      │
                        └──────────────┬──────────────────────┘
                                       │ score ≥ 7
                        ┌──────────────▼──────────────────────┐
          Agent 3       │         Impact Analyst              │
                        │  Gemini + Google Search grounding   │
                        │  3-paragraph procurement brief      │
                        └──────────────┬──────────────────────┘
                                       │ brief complete
                        ┌──────────────▼──────────────────────┐
          Agent 4       │        Alert Dispatcher             │
                        │  24h cooldown → Slack + Gmail       │
                        └─────────────────────────────────────┘

          Chat Q&A      Streamlit chat → Gemini (context-injected)
```

---

## Quick Start

### 1. Pre-work (before Day 1)

```bash
git clone https://github.com/pbiyyani09/Supply_Chain_Disruption_Agentic_Approach.git
cd Supply_Chain_Disruption_Agentic_Approach
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in your keys
```

**Required API keys:**

| Key | Where to get it |
|---|---|
| `GOOGLE_API_KEY` | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) |
| `NEWS_API_KEY` | [newsapi.org](https://newsapi.org) (free tier) |
| `SLACK_WEBHOOK_URL` | [api.slack.com/apps](https://api.slack.com/apps) → Incoming Webhooks |
| Gmail | Download `credentials.json` from Google Cloud Console |

### 2. Verify Google AI Studio connection

```python
python -c "
from google import genai
import os
from dotenv import load_dotenv
load_dotenv()
client = genai.Client(api_key=os.getenv('GOOGLE_API_KEY'))
r = client.models.generate_content(model='gemini-2.0-flash', contents='Say hello')
print(r.text)
"
```

### 3. Seed demo data

```bash
python -m scripts.seed_demo
```

Loads 9 suppliers and 6 Red Sea crisis events (Dec 2023 – Jan 2024).

### 4. Run the pipeline

```bash
# Terminal 1 — FastAPI backend (includes APScheduler)
uvicorn api.main:app --reload

# Terminal 2 — Streamlit dashboard
streamlit run dashboard/app.py
```

Open [http://localhost:8501](http://localhost:8501).

### 5. Trigger a manual scan

Click **"Run Manual Scan"** in the dashboard sidebar, or:

```bash
curl -X POST http://localhost:8000/scan
```

### 6. Docker (single command)

```bash
cp .env.example .env   # fill in keys first
docker-compose up --build
# Dashboard: http://localhost:8501   API docs: http://localhost:8000/docs
```

---

## Project Structure

```
chainwatch/
├── agents/
│   ├── signal_monitor.py     # Agent 1 — fetch + classify (Gemini JSON mode)
│   ├── risk_scorer.py        # Agent 2 — geo-match + score (Gemini batch)
│   ├── impact_analyst.py     # Agent 3 — brief writing (Gemini + Google Search)
│   └── alert_dispatcher.py   # Agent 4 — Slack + Gmail dispatch
├── data/
│   ├── sources.py            # GDELT, NewsAPI, NOAA fetchers
│   ├── geo_matcher.py        # ISO code → supplier matching
│   ├── country_centroids.json
│   └── seed_suppliers.csv
├── db/
│   ├── models.py             # SQLAlchemy ORM (SQLite dev / PostgreSQL prod)
│   ├── database.py
│   └── crud.py
├── api/
│   ├── main.py               # FastAPI app + /scan endpoint
│   ├── scheduler.py          # APScheduler pipeline wiring
│   └── routes/               # suppliers, events, alerts
├── dashboard/
│   ├── app.py                # Streamlit main
│   └── components/
│       ├── risk_map.py       # Pydeck world map
│       ├── alert_feed.py     # Severity-sorted alert list
│       ├── chat.py           # Gemini Q&A with live context
│       └── replay.py         # Date-range replay + timeline chart
├── prompts/
│   ├── classify_event.txt    # Agent 1 system prompt
│   ├── score_risk.txt        # Agent 2 system prompt
│   ├── write_brief.txt       # Agent 3 system prompt
│   └── chat_context.txt      # Chat Q&A system prompt template
├── tests/
├── scripts/
│   └── seed_demo.py          # Seeds Red Sea scenario
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

---

## Cost Estimate (Google AI Studio)

| Component | Calls/hour | Est. cost/month |
|---|---|---|
| Signal Monitor (classify) | ~10 after keyword filter | ~$0.50 |
| Risk Scorer (5 suppliers/call) | ~10 calls | ~$1.00 |
| Impact Analyst (HIGH only) | ~1–3 | ~$1.50 |
| Chat Q&A | On demand | ~$2–5 |
| **Total** | | **~$5–15/month** |

Gemini 2.0 Flash: ~$0.075/1M input, $0.30/1M output tokens.  
Google AI Studio **free tier**: 60 RPM / 1M TPM — sufficient for demo scale.

---

## 5-Day Build Plan

| Day | Focus | Deliverable |
|---|---|---|
| Mon | Signal ingestion + Gemini classification | 20+ events/hour in SQLite |
| Tue | Supplier graph + Gemini risk scoring | Risk scores per supplier per event |
| Wed | Impact Analyst (Gemini + Google Search) + Alert Dispatcher | Full alert in Slack with AI brief |
| Thu | Streamlit dashboard + Gemini chat Q&A | Dashboard on localhost |
| Fri | Polish + seed demo + Docker + deploy | Live public URL + Loom demo |

---

## Demo Script (3 min)

**Min 1:** Upload `seed_suppliers.csv` live. 9 suppliers appear on world map, all green. *"That's it. You're now being monitored."*

**Min 2:** Replay tab → Dec 18 2023 → load events. Watch Risk Scorer assign 9/10 to TaiwanSemi Corp. Slack alert arrives. Read the Gemini-written brief aloud.

**Min 3:** Chat: *"Which of my suppliers is most exposed to the Red Sea situation and what should I do this week?"* Show grounded Gemini answer. Close: *"This is what it looks like when every procurement manager has a Gemini-powered risk analyst."*

---

## Running Tests

```bash
pytest tests/ -v
```

---

*Built for the [5-Day AI Agents Intensive](https://www.kaggle.com/competitions/5-day-ai-agents-intensive-vibecoding-course-with-google) — Kaggle × Google, June 2026*
