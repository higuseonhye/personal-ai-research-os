"""
Lightweight "research" layer — hard-coded use_case → method hints.

Not a summarizer or web RAG; a stub for demos and future corpus wiring.
"""

from __future__ import annotations

_USE_CASE_HINTS: dict[str, list[str]] = {
    "RAG_QA": [
        "hybrid_retrieval",
        "dense_passage_retrieval",
        "reranker",
        "chunk_optimization",
        "prompt_grounding_guard",
    ],
    "Workflow_Automation": [
        "workflow_orchestrator",
        "evaluation_harness",
    ],
    "Classification": [
        "supervised_classifier",
        "chunk_optimization",
        "evaluation_harness",
    ],
}


def retrieve_method_hints(use_case: str) -> list[str]:
    return list(_USE_CASE_HINTS.get(use_case, _USE_CASE_HINTS["RAG_QA"]))


def research_snapshot(use_case: str) -> dict[str, list[str]]:
    return {
        "use_case": use_case,
        "method_hints": retrieve_method_hints(use_case),
        "note": "MVP static map — replace with your research store when ready.",
    }
