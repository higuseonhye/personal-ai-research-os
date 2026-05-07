"""Normalize raw natural language into a compact requirement record."""

from __future__ import annotations

import re
from typing import Any


def parse_requirement(text: str) -> dict[str, Any]:
    """
    Input: raw natural language.
    Output: { problem, constraints, goal } — short strings for demo / composition.
    """
    raw = (text or "").strip()
    lowered = raw.lower()

    constraints: list[str] = []
    if any(x in lowered for x in ("noisy data", "noisy corpus", "messy data", "dirty data")):
        constraints.append("noisy data")
    if any(x in lowered for x in ("low latency", "fast response", "real-time", "sub-second", "quick")):
        constraints.append("low latency")
    if any(x in lowered for x in ("pii", "privacy", "compliance", "gdpr", "hipaa")):
        constraints.append("privacy compliance")
    if any(x in lowered for x in ("access control", "rbac", "sso", "permissions")):
        constraints.append("access control")

    goal = "balanced quality and cost"
    if any(x in lowered for x in ("high accuracy", "accurate", "precision", "best answer")):
        goal = "high accuracy"
    if "high accuracy" in lowered and "low latency" in " ".join(constraints):
        goal = "high accuracy under latency pressure"

    # Core problem phrase (keep human-readable, not internal enums)
    problem = _infer_problem_phrase(lowered, raw)
    return {
        "problem": problem,
        "constraints": sorted(set(constraints)),
        "goal": goal,
    }


def _infer_problem_phrase(lowered: str, raw: str) -> str:
    if any(
        x in lowered
        for x in (
            "document qa",
            "qa system",
            "q&a",
            "question answer",
            "ask questions about documents",
        )
    ) or ("qa" in lowered and any(x in lowered for x in ("document", "documents", "knowledge"))):
        return "internal document QA" if "internal" in lowered else "document QA"

    if "classif" in lowered or "label" in lowered or "categorize" in lowered:
        return "document or record classification"

    if any(x in lowered for x in ("workflow", "automate", "automation", "orchestrat")):
        return "workflow automation"

    compact = re.sub(r"\s+", " ", lowered).strip()
    if len(compact) <= 120:
        return raw[:1].upper() + raw[1:] if raw else "unspecified AI system"
    return "complex enterprise AI initiative"
