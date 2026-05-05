"""Deployable system architecture from decomposition + SOTA methods (JSON-only)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from shared.llm_client import json_llm_complete_dict
from shared.schemas import ArchitectureOutput


def _fallback_architecture(
    problem_decomposition: dict[str, Any],
    sota_context: dict[str, Any],
) -> dict[str, Any]:
    subs = problem_decomposition.get("technical_subproblems") or []
    papers = sota_context.get("papers") or []
    titles = ", ".join(str(p.get("title", "")) for p in papers[:3])
    return {
        "system_design": (
            "Deploy a ticket ingestion service, hybrid retriever over knowledge articles, "
            "LLM draft generator with policy checks, and human escalation router. "
            f"Ground components in: {titles or 'standard RAG + reranker patterns'}."
        ),
        "components": [
            "ingestion_and_feature_store",
            "hybrid_retriever_bm25_dense",
            "cross_encoder_reranker",
            "grounded_response_llm",
            "human_in_the_loop_escalation",
            "observability_and_eval_service",
        ],
        "data_flow": [
            "ticket -> preprocess -> intent + routing metadata",
            "query -> hybrid retrieval -> top_k passages -> rerank -> prompt pack",
            "prompt pack -> constrained generation -> policy filter -> CRM reply",
            "low_confidence -> escalation queue -> agent desktop",
        ],
        "model_choice": "Dense retriever + cross-encoder rerank + mid-size instruction model with tool calling",
        "tradeoffs": [
            "Higher rerank latency vs better precision@k",
            "Strong grounding vs higher token cost",
            "Full automation vs compliance risk",
        ],
        "baseline_vs_sota": (
            "Baseline: BM25 + prompt-only LLM. SOTA path: hybrid retrieval + late interaction rerank "
            f"aligned to subproblems: {json.dumps(subs, ensure_ascii=False)}"
        ),
    }


def generate_architecture(
    problem_decomposition: dict[str, Any],
    sota_context: dict[str, Any],
) -> dict[str, Any]:
    system = (
        "You are a principal ML engineer. Produce a deployable architecture (not theory). "
        "Return ONLY JSON with keys: system_design, components, data_flow, model_choice, tradeoffs, baseline_vs_sota. "
        "system_design and model_choice and baseline_vs_sota are strings. "
        "components, data_flow, tradeoffs are arrays of short strings suitable for engineering tickets."
    )
    user = json.dumps(
        {"problem_decomposition": problem_decomposition, "sota_context": sota_context},
        ensure_ascii=False,
    )
    fb = _fallback_architecture(problem_decomposition, sota_context)
    return json_llm_complete_dict(system, user, ArchitectureOutput, fallback_builder=fb)
