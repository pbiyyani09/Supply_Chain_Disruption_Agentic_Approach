"""Retrieval-Augmented Generation layer for ChainWatch (Phase 2+).

Modules:
  * ``config``      — feature flag + model/dimension/path settings.
  * ``embeddings``  — Google ``gemini-embedding-001`` embedding calls.
  * ``vectorstore`` — local ``sqlite-vec`` store in a dedicated SQLite file.
  * ``retrieval``   — index + semantic search over events / briefs / knowledge base.
  * ``fusion``/``rerank`` — added in Phase 3.
"""
