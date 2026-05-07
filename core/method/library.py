"""Small reusable method vocabulary for composition (8 blocks, MVP)."""

from __future__ import annotations

from typing import Any

METHOD_BY_ID: dict[str, dict[str, Any]] = {
    "hybrid_retrieval": {
        "name": "hybrid_retrieval",
        "use_case": "RAG",
        "strength": "robust to noisy or uneven corpora",
        "tradeoff": "higher latency and indexing surface area",
    },
    "dense_passage_retrieval": {
        "name": "dense_passage_retrieval",
        "use_case": "RAG",
        "strength": "strong semantic matching for paraphrases",
        "tradeoff": "embedding and index upkeep cost",
    },
    "reranker": {
        "name": "reranker",
        "use_case": "RAG",
        "strength": "top-k precision for grounding answers",
        "tradeoff": "added latency vs. retriever-only stack",
    },
    "chunk_optimization": {
        "name": "chunk_optimization",
        "use_case": "RAG / NLP",
        "strength": "better boundaries for retrieval or labeling",
        "tradeoff": "offline tuning and versioning of chunk policies",
    },
    "prompt_grounding_guard": {
        "name": "prompt_grounding_guard",
        "use_case": "RAG",
        "strength": "cite-or-abstain behavior to tame hallucinations",
        "tradeoff": "prompt maintenance and refusal UX",
    },
    "workflow_orchestrator": {
        "name": "workflow_orchestrator",
        "use_case": "Automation",
        "strength": "durable retries, SLA-aware routing across tools",
        "tradeoff": "state/idempotency engineering",
    },
    "supervised_classifier": {
        "name": "supervised_classifier",
        "use_case": "Classification",
        "strength": "predictable taxonomy coverage with calibrated scores",
        "tradeoff": "labeling cadence and drift monitoring",
    },
    "evaluation_harness": {
        "name": "evaluation_harness",
        "use_case": "Cross-cutting",
        "strength": "gates releases with regression-visible metrics",
        "tradeoff": "dataset / judge upkeep",
    },
}


def list_methods() -> list[dict[str, Any]]:
    return [METHOD_BY_ID[k] for k in sorted(METHOD_BY_ID)]
