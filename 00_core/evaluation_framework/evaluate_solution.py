"""Heuristic + optional LLM evaluation of a proposed architecture (JSON-only)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from shared.llm_client import json_llm_complete_dict
from shared.schemas import EvaluationResult


def _load_rubric_module():
    p = Path(__file__).resolve().parent / "rubric.py"
    spec = importlib.util.spec_from_file_location("pa_eval_rubric", p)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)
    return mod


_rubric = _load_rubric_module()
score_against_rubric = _rubric.score_against_rubric


def _fallback_eval(architecture: dict[str, Any]) -> dict[str, Any]:
    rub = score_against_rubric(architecture)
    rollup = float(rub.get("rollup_score", "0.5"))
    return {
        "readiness_score": f"{rollup:.2f}",
        "deployment_risks": [
            "Knowledge drift if KB refresh is not automated",
            "Model update regressions without canary eval",
        ],
        "recommended_metrics": [
            "precision@k on internal retrieval QA set",
            "human_acceptance_rate_of_drafts",
            "policy_violation_rate_on_red_team_prompts",
        ],
        "verdict": "proceed_with_pilot" if rollup >= 0.65 else "iterate_before_pilot",
    }


def evaluate_solution(architecture: dict[str, Any]) -> dict[str, Any]:
    system = (
        "You evaluate ML system architectures for enterprise deployment readiness. "
        "Return ONLY JSON with keys: readiness_score, deployment_risks, recommended_metrics, verdict. "
        "readiness_score is a string float 0-1. deployment_risks and recommended_metrics are string arrays. "
        "verdict is one short string enum-like token."
    )
    user = json.dumps({"architecture": architecture}, ensure_ascii=False)
    fb = _fallback_eval(architecture)
    return json_llm_complete_dict(system, user, EvaluationResult, fallback_builder=fb)
