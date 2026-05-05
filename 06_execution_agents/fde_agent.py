"""FDE agent: deployment plan, infra, tooling, bottlenecks (JSON-only)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from shared.llm_client import json_llm_complete_dict
from shared.schemas import FDEAgentOutput


def _fallback_fde(system_design: dict[str, Any]) -> dict[str, Any]:
    sd = str(system_design.get("system_design", ""))[:400]
    return {
        "deployment_plan": [
            "Stage 0: shadow mode logging proposed replies without customer impact",
            "Stage 1: human-in-the-loop with retrieval citations enforced",
            "Stage 2: partial automation on narrow intent buckets",
            "Stage 3: expand coverage with continuous eval gates",
        ],
        "infrastructure": [
            "Vector index service (managed or self-hosted)",
            "GPU pool for rerank + generation",
            "Redis queue for async ticket processing",
            "Object store for artifacts and prompts",
        ],
        "tooling": [
            "Terraform/IaC for reproducible environments",
            "Prometheus + Grafana for latency and quality SLOs",
            "Feature flags for model version routing",
            "Notebook + pipeline for offline replay on tickets",
        ],
        "bottlenecks": [
            "Reranker GPU saturation under peak ticket load",
            "Stale knowledge base lowering grounded answer quality",
            "PII redaction latency in streaming paths",
            f"Design excerpt risk summary: {sd}",
        ],
    }


def fde_agent(system_design: dict[str, Any]) -> dict[str, Any]:
    system = (
        "You are a forward-deployed engineer. Convert architecture into an execution plan. "
        "Return ONLY JSON with keys: deployment_plan, infrastructure, tooling, bottlenecks — all arrays of strings."
    )
    user = json.dumps({"system_design": system_design}, ensure_ascii=False)
    fb = _fallback_fde(system_design)
    return json_llm_complete_dict(system, user, FDEAgentOutput, fallback_builder=fb)
