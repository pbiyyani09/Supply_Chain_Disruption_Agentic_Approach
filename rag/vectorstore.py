"""Local vector store backed by ``sqlite-vec`` in a dedicated SQLite file.

Design rationale (Phase 2):
  * **Adapter / fail-safe** — wraps ``sqlite-vec`` behind a small project-shaped
    surface (``upsert`` / ``query``). If the extension cannot be loaded (some
    stdlib ``sqlite3`` builds disable extension loading), every operation becomes
    a logged no-op and RAG simply stays inactive — never crashing the pipeline.
  * **Per-operation connections** — a fresh connection per call keeps the store
    safe across the FastAPI/APScheduler thread pool without a shared, non
    thread-safe handle. Volume is low (a few ops per scan), so the cost is
    negligible.
  * One ``vec0`` virtual table per document ``kind`` (events / briefs / kb), each
    with a cosine-distance embedding column and an auxiliary ``content`` column.
"""
from __future__ import annotations

import logging
import sqlite3

from rag.config import embedding_dim, vector_db_path

logger = logging.getLogger(__name__)

KINDS = ("events", "briefs", "kb")

# None = not yet probed; True/False = sqlite-vec load succeeded/failed.
_available: bool | None = None


def _connect() -> sqlite3.Connection | None:
    """Open a connection with the sqlite-vec extension loaded, or return None."""
    global _available
    try:
        import sqlite_vec

        conn = sqlite3.connect(vector_db_path())
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        _ensure_tables(conn)
        _available = True
        return conn
    except Exception as exc:  # pragma: no cover - depends on platform sqlite build
        if _available is not False:
            logger.warning("[VectorStore] sqlite-vec unavailable (%s) — RAG storage disabled", exc)
        _available = False
        return None


def _ensure_tables(conn: sqlite3.Connection) -> None:
    """Create the per-kind ``vec0`` virtual tables if they do not exist."""
    dim = embedding_dim()
    for kind in KINDS:
        conn.execute(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS vec_{kind} USING vec0("
            f"doc_id TEXT PRIMARY KEY, +content TEXT, "
            f"embedding FLOAT[{dim}] distance_metric=cosine)"
        )


def upsert(kind: str, doc_id: str, content: str, embedding: list[float]) -> bool:
    """Insert or replace one document's embedding.

    Args:
        kind: One of :data:`KINDS`.
        doc_id: Stable unique id (e.g. event/risk-score id, or a KB chunk key).
        content: The raw text (stored for retrieval display).
        embedding: The document embedding vector.

    Returns:
        True on success, False when the store is unavailable or on error.
    """
    if kind not in KINDS or not doc_id or not embedding:
        return False
    conn = _connect()
    if conn is None:
        return False
    try:
        from sqlite_vec import serialize_float32

        conn.execute(f"DELETE FROM vec_{kind} WHERE doc_id = ?", (doc_id,))
        conn.execute(
            f"INSERT INTO vec_{kind}(doc_id, content, embedding) VALUES (?, ?, ?)",
            (doc_id, content, serialize_float32(embedding)),
        )
        conn.commit()
        return True
    except Exception as exc:
        logger.warning("[VectorStore] upsert failed (%s)", exc)
        return False
    finally:
        conn.close()


def query(kind: str, embedding: list[float], k: int = 5) -> list[dict]:
    """K-nearest-neighbour search within one document kind.

    Args:
        kind: One of :data:`KINDS`.
        embedding: The query embedding vector.
        k: Number of neighbours to return.

    Returns:
        A list of ``{"kind", "doc_id", "content", "distance"}`` dicts ordered by
        ascending cosine distance; ``[]`` when unavailable or on error.
    """
    if kind not in KINDS or not embedding:
        return []
    conn = _connect()
    if conn is None:
        return []
    try:
        from sqlite_vec import serialize_float32

        rows = conn.execute(
            f"SELECT doc_id, content, distance FROM vec_{kind} "
            f"WHERE embedding MATCH ? AND k = ? ORDER BY distance",
            (serialize_float32(embedding), k),
        ).fetchall()
        return [{"kind": kind, "doc_id": r[0], "content": r[1], "distance": r[2]} for r in rows]
    except Exception as exc:
        logger.warning("[VectorStore] query failed (%s)", exc)
        return []
    finally:
        conn.close()
