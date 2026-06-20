# Architecture

## Pipeline (LangGraph)

Both the scheduled tick (`api/scheduler.py`) and the manual `POST /scan`
(`api/main.py`) delegate to `orchestration.graph.run_pipeline`, which invokes a
typed `StateGraph`:

```
START → signal → econ_weather → score ─┬─(HIGH ≥ 7)→ impact_dispatch → forecast → END
                                       └─(none)──────────────────────→ forecast → END
```

| Node | Agent | Gemini? | Augmentations |
|---|---|---|---|
| `signal` | Signal Monitor | classify | Tavily full-text extraction → richer classification |
| `econ_weather` | — | classify (weather) | FRED/Yahoo indicators, Open-Meteo events |
| `score` | Risk Scorer | batch score | RAG priors, Tavily per-supplier context, MEDIUM elevation |
| `impact_dispatch` | Impact Analyst + Dispatcher | brief | Google Search grounding + Tavily + RAG + Gemma faithfulness judge |
| `forecast` | Forecaster | 6-horizon forecast | seasonal calendar, economic signals |

The conditional edge after `score` is the key structural change from v2.0's
hardcoded sequence: impact analysis only runs when a HIGH-risk score exists.

## Retrieval (RAG)

```
query ─► [RAG-Fusion] expand to N sub-queries ─► embed (gemini-embedding-001)
      ─► sqlite-vec KNN per kind (events | briefs | kb) ─► Reciprocal Rank Fusion
      ─► [Rerank] cross-encoder | Gemma ─► top-k context ─► prompt
```

- **Store**: `rag.vectorstore` — `sqlite-vec` `vec0` tables in a dedicated
  SQLite file (`VECTOR_DB_PATH`), decoupled from the ORM database so retrieval
  works even when the main DB is PostgreSQL.
- **Corpus**: institutional memory (past events + briefs + risk reasoning) plus
  the static knowledge base (industry profiles, playbooks, seasonal windows),
  seeded by `scripts/backfill_index.py`.
- **Composition**: `rag.retrieval.retrieve_best` chains fusion → rerank; with
  both flags off it equals plain vector search, so call sites are unconditional.

## Guardrails & evals

- **Output guardrail** — every agent passes Gemini output through a Pydantic
  `response_schema` and `schemas.parse_object`/`parse_list`, clamping numeric
  ranges and coercing enums before any value reaches downstream code.
- **Input guardrail** — `guardrails.injection.guard_scraped_text` screens all
  scraped web text (regex now; optional local-Gemma classifier) before it enters
  a prompt.
- **Second-opinion judge** — `guardrails.judge` uses a local Gemma model to audit
  HIGH-risk briefs for faithfulness and triggers one regeneration if flagged.
- **Offline evals** — `evals/run_ragas.py` scores the golden set on context
  precision/recall, faithfulness, and response relevancy (Gemini judge + Google
  embeddings).

## Observability

`observability.setup_observability()` runs once per entry point. When
`PHOENIX_ENABLED=true` it registers an OpenTelemetry tracer and auto-instruments
`google-genai` and LangChain/LangGraph, so each `run_pipeline` call produces one
trace with nested node → Gemini spans (including token counts that were
previously discarded).

## Design principles

The codebase follows SOLID with a light touch: a **Factory** for model clients
(`providers`), the **Strategy** pattern for rerankers (`rag.rerank`) behind the
`interfaces.Reranker` Protocol, **Adapter** wrappers for Tavily and the vector
store, and the existing **Repository** layer (`db.crud`). Abstractions are
introduced only where there is more than one implementation.
