"""Stub SOTA paper retrieval from decomposition (replace with live RAG later)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def retrieve_relevant_sota(decomposition: dict[str, Any]) -> dict[str, Any]:
    """
    Return structured context: papers (title + one-line relevance), mapped_methods.
    """
    subs = decomposition.get("technical_subproblems") or []
    papers = [
        {
            "title": "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks",
            "venue": "NeurIPS",
            "year": "2020",
            "relevance": "Baseline enterprise RAG stack and evaluation framing.",
            "methods": ["enterprise_rag", "semantic_search"],
        },
        {
            "title": "ColBERT: Efficient and Effective Passage Search via Contextualized Late Interaction",
            "venue": "SIGIR",
            "year": "2020",
            "relevance": "High-recall retrieval + reranking for support deflection.",
            "methods": ["hybrid_search", "semantic_search"],
        },
        {
            "title": "Toolformer: Language Models Can Teach Themselves to Use Tools",
            "venue": "NeurIPS",
            "year": "2023",
            "relevance": "Grounded actions and safe tool use in agentic support workflows.",
            "methods": ["tool_use_systems", "agent_orchestration"],
        },
    ]
    mapped = [str(s) for s in subs]
    return {
        "papers": papers,
        "mapped_subproblems": mapped,
        "retrieval_mode": "stub_static",
    }
