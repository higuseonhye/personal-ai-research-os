"""Detect failures from eval signals and propose architecture updates (JSON-only)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from shared.llm_client import json_llm_complete_dict
from shared.schemas import IterationOutput


def _fallback_iterate(
    system_output: dict[str, Any],
    eval_result: dict[str, Any],
) -> dict[str, Any]:
    risks = eval_result.get("deployment_risks") or []
    fps = [str(r) for r in risks]
    if not fps:
        fps = ["Limited evidence on worst-case escalations and long-tail intents"]
    return {
        "failure_points": fps,
        "improvement_iterations": [
            "Add active learning loop on escalated tickets",
            "Tighten reranker threshold and expand gold passage set",
            "Introduce second-stage critic model for policy violations",
        ],
        "architecture_updates": [
            "Insert cache for hot FAQ clusters",
            "Split retriever index by product line to reduce noise",
            "Add synthetic stress tests for PII leakage before prod",
        ],
    }


def evaluate_and_iterate(system_output: dict[str, Any], eval_result: dict[str, Any]) -> dict[str, Any]:
    system = (
        "You run an enterprise AI evaluation loop. Return ONLY JSON with keys: "
        "failure_points, improvement_iterations, architecture_updates — each an array of short actionable strings. "
        "Base recommendations strictly on the provided architecture and evaluation objects."
    )
    user = json.dumps({"system_output": system_output, "eval_result": eval_result}, ensure_ascii=False)
    fb = _fallback_iterate(system_output, eval_result)
    return json_llm_complete_dict(system, user, IterationOutput, fallback_builder=fb)
