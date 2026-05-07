"""Turn composed strategy into an ordered execution plan."""

from __future__ import annotations

from typing import Any

_METHOD_STEPS: dict[str, str] = {
    "hybrid_retrieval": "Apply hybrid retrieval (sparse + dense fusion)",
    "dense_passage_retrieval": "Implement dense passage retrieval over embeddings",
    "reranker": "Install cross-encoder / reranker on candidate passages",
    "chunk_optimization": "Tune chunking policy and document ingestion",
    "prompt_grounding_guard": "Add cite-or-abstain prompts + safety checks",
    "workflow_orchestrator": "Model durable workflow orchestration with retries",
    "supervised_classifier": "Train and serve supervised classifier with monitoring",
    "evaluation_harness": "Build regression evaluation harness and dashboards",
}


def _readable(method_ids: list[str]) -> str:
    return ", ".join(m.replace("_", " ") for m in method_ids)


def _architecture_line(use_case: str, methods: list[str]) -> str:
    if use_case == "RAG_QA":
        base = "Retrieval-augmented generation service with managed vector index"
    elif use_case == "Workflow_Automation":
        base = "Event-driven automation mesh with governed tool calls"
    else:
        base = "Supervised decisioning pipeline with monitoring hooks"

    if methods:
        return f"{base}; composed methods -> {_readable(methods)}"
    return base


def build_architecture(use_case: str, strategy: list[str]) -> str:
    return _architecture_line(use_case, strategy)


def build_execution_plan(use_case: str, strategy: list[str]) -> list[str]:
    """Ordered checklist mixing foundations with selected methods."""

    strategy = [m for m in strategy if m in _METHOD_STEPS]

    if use_case == "RAG_QA":
        plan: list[str] = [
            "Provision vector database and ingestion workers",
            "Normalize and OCR documents as needed",
        ]
    elif use_case == "Workflow_Automation":
        plan = [
            "Map triggers, actors, SLAs",
            "Register integrations with secrets management",
        ]
    else:
        plan = [
            "Lock taxonomy / labeling rubric",
            "Prepare train/validation splits with safeguards",
        ]

    for mid in strategy:
        plan.append(_METHOD_STEPS[mid])

    if use_case == "RAG_QA":
        plan.extend(
            [
                "Connect LLM with retrieval context packaging",
                "Stand up evaluation datasets and nightly eval jobs",
            ]
        )
    elif use_case == "Workflow_Automation":
        plan.append("Wire observability, alerts, human-in-loop fallbacks")
    else:
        plan.append("Ship monitors for drift plus periodic recalibration")

    return plan
