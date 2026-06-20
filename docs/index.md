# ChainWatch

ChainWatch is a multi-agent **supply-chain disruption early-warning system**. It
continuously ingests global signals (news, conflict, weather, economic
indicators, maritime congestion), scores supplier exposure with Google Gemini,
writes procurement briefs, dispatches alerts, and forecasts disruption
probability across six horizons.

This documentation is generated from the source docstrings — every public class
and function is described under **API Reference**, navigable from the table of
contents (and as PDF bookmarks in the exported PDF).

## What's in v3.0

| Capability | Module(s) | Flag |
|---|---|---|
| Schema-validated LLM outputs | [`schemas`](api/schemas.md) | always on |
| Gemini client factory | [`providers`](api/platform.md) | — |
| Arize Phoenix tracing | [`observability`](api/platform.md) | `PHOENIX_ENABLED` |
| Tavily full-text + deep search | [`data.tavily_research`](api/web.md) | `TAVILY_ENABLED` |
| Prompt-injection guardrail | [`guardrails.injection`](api/guardrails.md) | always on (scraped text) |
| Gemma faithfulness judge | [`guardrails.judge`](api/guardrails.md) | `JUDGE_ENABLED` |
| RAG over events/briefs/KB | [`rag`](api/rag.md) | `RAG_ENABLED` |
| RAG-Fusion + reranking | [`rag.fusion`, `rag.rerank`](api/rag.md) | `FUSION_ENABLED`, `RERANK_ENABLED` |
| LangGraph orchestration | [`orchestration.graph`](api/orchestration.md) | always on |

Every capability is **fail-safe and flag-gated**: when its flag is off (or an
optional dependency/service is missing) it degrades to a no-op and the core
pipeline behaves exactly as before.

## Run it

```bash
uv sync                                  # runtime + dev deps
RAG_ENABLED=true python -m scripts.backfill_index   # (optional) seed RAG memory
uvicorn api.main:app --reload            # API + scheduler on :8000
streamlit run dashboard/app.py           # dashboard on :8501
curl -X POST http://localhost:8000/scan  # run the pipeline once
```

See **[Architecture](architecture.md)** for how the pieces fit together.
