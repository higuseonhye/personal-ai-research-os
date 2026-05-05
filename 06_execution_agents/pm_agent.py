"""Enterprise AI PM agent: interpret problem, KPIs, PRD-style requirements (JSON-only)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from shared.llm_client import json_llm_complete_dict
from shared.schemas import PMAgentOutput


def _fallback_pm(problem: str) -> dict[str, Any]:
    return {
        "interpreted_problem": (
            "Operationalize the stated business problem into measurable support outcomes "
            "and scoped ML-assisted workflows."
        ),
        "kpis": [
            "cost_per_ticket",
            "deflection_rate",
            "csat_or_dsat_delta",
            "average_handle_time",
            "escalation_rate_to_human",
        ],
        "product_requirements": [
            "Role-based access to transcripts and model outputs",
            "Audit trail for every generated customer reply",
            "Configurable confidence thresholds for auto-send vs human review",
            "Offline evaluation harness on historical tickets",
            "Canary rollout with kill switch",
        ],
    }


def pm_agent(problem: str) -> dict[str, Any]:
    system = (
        "You are an enterprise AI product manager. Return ONLY JSON with keys: "
        "interpreted_problem, kpis, product_requirements. "
        "interpreted_problem is one concise string. kpis and product_requirements are arrays of short strings."
    )
    user = f"Business problem:\n{problem.strip()}"
    fb = _fallback_pm(problem)
    return json_llm_complete_dict(system, user, PMAgentOutput, fallback_builder=fb)
