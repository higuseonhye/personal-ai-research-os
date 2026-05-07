"""Pick 2–4 concrete methods plus short rationale (rule-based MVP)."""

from __future__ import annotations

from typing import Any

from core.method.library import METHOD_BY_ID
from core.research.retriever import retrieve_method_hints


def compose_strategy(structured: dict[str, Any], requirement: dict[str, Any]) -> dict[str, Any]:
    use_case = structured.get("use_case") or "RAG_QA"
    hints = retrieve_method_hints(use_case)

    constraints = [str(x).lower() for x in (requirement.get("constraints") or [])]
    goal = str(requirement.get("goal") or "").lower()

    selected: list[str] = []

    def take(mid: str) -> None:
        if mid in METHOD_BY_ID and mid not in selected:
            selected.append(mid)

    if use_case == "RAG_QA":
        if "noisy data" in constraints:
            take("hybrid_retrieval")
            take("reranker")
            take("chunk_optimization")
        else:
            take("dense_passage_retrieval")
            take("chunk_optimization")

        if "high accuracy" in goal or "accuracy" in structured.get("metrics", []):
            take("reranker")
            take("prompt_grounding_guard")

        if "low latency" in constraints:
            selected = [m for m in selected if m != "reranker"]
            take("dense_passage_retrieval")

        for hint in hints:
            if len(selected) >= 4:
                break
            take(hint)

    elif use_case == "Workflow_Automation":
        take("workflow_orchestrator")
        take("evaluation_harness")

    else:  # Classification
        take("supervised_classifier")
        take("evaluation_harness")
        take("chunk_optimization")

    # Ensure breadth: pad from hints without exceeding four methods
    for hint in hints:
        if len(selected) >= 4:
            break
        take(hint)

    if len(selected) < 2:
        for hint in hints:
            take(hint)
            if len(selected) >= 2:
                break

    reasons: list[str] = []
    if use_case == "RAG_QA" and "noisy data" in constraints:
        reasons.append("hybrid fusion plus reranking stabilizes retrieval under corpus noise")
    if "high accuracy" in goal:
        reasons.append("reranking and grounding guardrails tighten answer quality")
    if "low latency" in constraints:
        reasons.append("latency shaping favors lean retrieve→generate lanes where safe")
    if use_case == "Workflow_Automation":
        reasons.append("orchestrator plus eval harness operationalizes reliability gates")
    if use_case == "Classification":
        reasons.append("supervised heads with chunk-aware featurization and eval slices cover drift")

    reason = "; ".join(reasons) if reasons else "baseline stack from curated research hints"

    return {"strategy": selected[:4], "reason": reason}
