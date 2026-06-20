"""Offline RAG-quality evaluation with Ragas (Gemini judge + Google embeddings).

Measures context precision/recall, faithfulness, and response relevancy over a
curated golden set. Heavy/offline: requires the ``evals`` dependency group and a
``GOOGLE_API_KEY``; skipped in normal unit CI.

    uv sync --group evals
    GOOGLE_API_KEY=... python -m evals.run_ragas
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_GOLDEN_PATH = Path(__file__).parent / "golden_set.json"
_REQUIRED_FIELDS = ("user_input", "retrieved_contexts", "response", "reference")


def build_samples(path: Path = _GOLDEN_PATH) -> list[dict]:
    """Load and validate the golden set into Ragas-shaped samples.

    Pure (no Ragas import) so it is unit-testable without the heavy dependency.

    Args:
        path: Path to the golden-set JSON file.

    Returns:
        A list of sample dicts each containing the required Ragas fields.

    Raises:
        ValueError: if any record is missing a required field.
    """
    records = json.loads(Path(path).read_text())
    samples = []
    for i, rec in enumerate(records):
        missing = [f for f in _REQUIRED_FIELDS if f not in rec]
        if missing:
            raise ValueError(f"golden_set record {i} missing fields: {missing}")
        samples.append({f: rec[f] for f in _REQUIRED_FIELDS})
    return samples


def run_evaluation(samples: list[dict]) -> dict:
    """Run Ragas metrics over ``samples`` using a Gemini judge + Google embeddings.

    Args:
        samples: Output of :func:`build_samples`.

    Returns:
        A mapping of metric name to mean score.

    Raises:
        ImportError: if the ``evals`` dependency group (ragas) is not installed.
    """
    import os

    from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
    from ragas import EvaluationDataset, evaluate
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import LangchainLLMWrapper
    from ragas.metrics import (
        Faithfulness,
        LLMContextPrecisionWithReference,
        LLMContextRecall,
        ResponseRelevancy,
    )

    judge = LangchainLLMWrapper(
        ChatGoogleGenerativeAI(model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"), temperature=0.0)
    )
    embeddings = LangchainEmbeddingsWrapper(
        GoogleGenerativeAIEmbeddings(model="models/embedding-001")
    )

    dataset = EvaluationDataset.from_list(samples)
    result = evaluate(
        dataset=dataset,
        metrics=[
            LLMContextPrecisionWithReference(),
            LLMContextRecall(),
            Faithfulness(),
            ResponseRelevancy(),
        ],
        llm=judge,
        embeddings=embeddings,
    )
    df = result.to_pandas()
    metric_cols = [c for c in df.columns if c not in _REQUIRED_FIELDS]
    return {col: float(df[col].mean()) for col in metric_cols}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    items = build_samples()
    logger.info("[Ragas] Loaded %d golden samples", len(items))
    try:
        scores = run_evaluation(items)
        logger.info("[Ragas] Scores: %s", json.dumps(scores, indent=2))
    except ImportError:
        logger.error("Ragas not installed. Run: uv sync --group evals")
