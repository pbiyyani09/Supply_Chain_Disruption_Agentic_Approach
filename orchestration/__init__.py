"""LangGraph orchestration for the ChainWatch pipeline (Phase 5).

Replaces the hardcoded sequential call-chain with a typed ``StateGraph`` that has
a conditional HIGH-risk branch and per-node retries, and traces cleanly in
Arize Phoenix via the LangChain instrumentor.
"""
