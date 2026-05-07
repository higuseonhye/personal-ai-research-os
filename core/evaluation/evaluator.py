"""Targets the OS will optimize against (MVP placeholders)."""

from __future__ import annotations

from typing import Any


def evaluation_targets(structured: dict[str, Any], requirement: dict[str, Any]) -> dict[str, str]:
    use_case = structured.get("use_case") or "RAG_QA"
    constraints = [str(x).lower() for x in (requirement.get("constraints") or [])]
    goal_l = str(requirement.get("goal", "")).lower()
    metrics = list(structured.get("metrics") or [])

    if use_case == "RAG_QA":
        want_high_acc = "high accuracy" in goal_l or "accuracy" in metrics
        acc = ">=90%" if want_high_acc else ">=85%"
        lat = "<1.5s" if "low latency" in constraints else "<2s"
        return {"accuracy_target": acc, "latency_target": lat}

    if use_case == "Workflow_Automation":
        return {"accuracy_target": ">=99% success without manual rewind", "latency_target": "<5s per hop (p95)"}

    return {"accuracy_target": ">=88% macro-F1", "latency_target": "<500ms p95 inference"}
