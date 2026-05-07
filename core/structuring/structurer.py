"""Map requirement into a structured problem for research and composition."""

from __future__ import annotations

from typing import Any


def structure_requirement(requirement: dict[str, Any]) -> dict[str, Any]:
    problem = (requirement.get("problem") or "").lower()
    constraints = [str(c).lower() for c in (requirement.get("constraints") or [])]
    goal = str(requirement.get("goal") or "").lower()

    if "classification" in problem:
        use_case = "Classification"
        base_challenges = ["label noise", "concept drift"]
        metrics = ["precision_recall", "calibration"]

    elif "workflow" in problem or "automation" in problem:
        use_case = "Workflow_Automation"
        base_challenges = ["partial failures", "integration brittleness"]
        metrics = ["reliability", "latency"]

    elif "document qa" in problem or " qa" in f" {problem}" or problem.endswith("qa"):
        use_case = "RAG_QA"
        base_challenges = ["hallucination", "staleness"]
        metrics = ["accuracy", "latency", "groundedness"]

    else:
        use_case = "RAG_QA"
        base_challenges = ["ambiguous requirements", "metric gap"]
        metrics = ["accuracy", "latency"]

    challenges = list(dict.fromkeys(base_challenges))
    if "noisy data" in constraints and "noisy data" not in challenges:
        challenges.insert(0, "noisy data")
    challenges = list(dict.fromkeys(challenges))[:5]

    if "low latency" in constraints and "latency" not in metrics:
        metrics.append("latency")
    if "high accuracy" in goal and "accuracy" not in metrics:
        metrics.insert(0, "accuracy")

    return {
        "use_case": use_case,
        "key_challenges": challenges[:5],
        "metrics": list(dict.fromkeys(metrics))[:5],
    }
