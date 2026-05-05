"""Map enterprise business problems to technical abstractions (JSON-only)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import sys

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import yaml

from shared.llm_client import json_llm_complete_dict
from shared.schemas import ProblemDecomposition


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_ontology_text() -> str:
    p = _repo_root() / "00_core" / "ontology" / "enterprise_problem_ontology.yaml"
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8")


def _heuristic_fallback(problem: str) -> dict[str, Any]:
    p = problem.lower()
    tech: list[str] = []
    if any(k in p for k in ("support", "ticket", "customer", "csat", "helpdesk")):
        tech.extend(
            [
                "cs_automation:intent_classification",
                "cs_automation:ticket_routing",
                "cs_automation:response_generation",
                "search_retrieval:enterprise_rag",
            ]
        )
    if any(k in p for k in ("search", "retriev", "rag", "knowledge")):
        tech.extend(["search_retrieval:hybrid_search", "search_retrieval:semantic_search"])
    if any(k in p for k in ("forecast", "demand", "churn", "recommend")):
        tech.extend(["decision_support:forecasting", "decision_support:recommendation_systems"])
    if any(k in p for k in ("agent", "workflow", "automat", "tool")):
        tech.extend(["workflow_automation:agent_orchestration", "workflow_automation:tool_use_systems"])
    if not tech:
        tech = [
            "cs_automation:intent_classification",
            "workflow_automation:agent_orchestration",
        ]
    return {
        "raw_problem": problem,
        "interpreted_goal": "Reduce operational cost while preserving or improving customer outcomes through ML-assisted support.",
        "technical_subproblems": list(dict.fromkeys(tech)),
        "constraints": [
            "Regulatory / privacy constraints on customer transcripts",
            "Latency SLOs for interactive support channels",
        ],
        "success_metrics": [
            "cost_per_ticket",
            "first_contact_resolution_rate",
            "customer_satisfaction_score",
            "average_handle_time",
        ],
        "assumptions": [
            "Labeled or weakly labeled ticket data is available or obtainable",
            "Human-in-the-loop remains acceptable for high-risk replies",
        ],
    }


def decompose_enterprise_problem(problem: str) -> dict[str, Any]:
    """
    Business → technical decomposition. Output matches ProblemDecomposition (JSON-only).
    """
    ontology = _load_ontology_text()
    system = (
        "You are an enterprise AI PM and forward-deployed engineer. "
        "Map the business problem to technical subproblems using ontology categories when applicable. "
        "Ontology (YAML):\n"
        f"{ontology}\n\n"
        "Return ONLY a JSON object with keys: "
        "raw_problem, interpreted_goal, technical_subproblems, constraints, success_metrics, assumptions. "
        "All values are strings or arrays of strings. technical_subproblems should use short imperative phrases "
        "or category:subproblem tags from the ontology where possible."
    )
    user = f"Enterprise problem:\n{problem.strip()}"
    fb = _heuristic_fallback(problem)
    fb["raw_problem"] = problem.strip() or fb["raw_problem"]
    return json_llm_complete_dict(system, user, ProblemDecomposition, fallback_builder=fb)
