"""JSON-first scoring rubric for architecture / deployment readiness."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

DEFAULT_RUBRIC: dict[str, Any] = {
    "version": "1.0",
    "axes": [
        {"id": "technical_feasibility", "weight": 0.25, "description": "Can be built with known components"},
        {"id": "eval_coverage", "weight": 0.25, "description": "Metrics and offline harness cover risks"},
        {"id": "operational_fit", "weight": 0.2, "description": "Latency, cost, and staffing match constraints"},
        {"id": "safety_compliance", "weight": 0.2, "description": "PII, policy, and audit requirements addressed"},
        {"id": "iteration_path", "weight": 0.1, "description": "Clear path to improve from production signals"},
    ],
}


def score_against_rubric(artifact: dict[str, Any], rubric: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return per-axis string scores 0-1 and weighted rollup (all structured)."""
    r = rubric or DEFAULT_RUBRIC
    axes = r.get("axes") or []
    comps = artifact.get("components") or []
    trades = artifact.get("tradeoffs") or []
    base = min(1.0, 0.55 + 0.05 * min(len(comps), 6) + 0.02 * min(len(trades), 5))
    axis_scores: list[dict[str, str]] = []
    total = 0.0
    for ax in axes:
        aid = str(ax.get("id", ""))
        w = float(ax.get("weight", 0))
        s = max(0.0, min(1.0, base + (0.03 if aid == "eval_coverage" else 0.0)))
        axis_scores.append({"axis": aid, "score": f"{s:.2f}"})
        total += w * s
    return {
        "rubric_version": str(r.get("version", "")),
        "axis_scores": axis_scores,
        "rollup_score": f"{total:.2f}",
    }
