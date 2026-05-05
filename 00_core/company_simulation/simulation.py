"""Company simulation mode — case-based reasoning envelopes for the enterprise OS."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
_CASES_PATH = Path(__file__).resolve().parent / "cases.json"


def load_cases() -> list[dict[str, Any]]:
    if not _CASES_PATH.exists():
        return []
    return json.loads(_CASES_PATH.read_text(encoding="utf-8"))


def get_case(case_id: str) -> dict[str, Any] | None:
    for row in load_cases():
        if str(row.get("id")) == case_id:
            return row
    return None


def build_problem_envelope(case_id: str) -> dict[str, Any]:
    """
    Merge structured enterprise story into a single problem string + metadata for pipelines / DAG.
    """
    c = get_case(case_id)
    if not c:
        raise KeyError(f"Unknown case_id={case_id}")
    personas = ", ".join(str(p) for p in (c.get("personas") or []))
    hidden = "; ".join(str(x) for x in (c.get("hidden_constraints") or []))
    profile = str(c.get("company_profile", ""))
    prob = str(c.get("case_problem", ""))
    merged_problem = (
        f"[CompanySimulation:{case_id}] {prob}\n\n"
        f"Company profile: {profile}\n"
        f"Stakeholders: {personas}\n"
        f"Hidden constraints (internal tension): {hidden}\n"
        f"Declared success criteria: {c.get('success_criteria')}\n"
    )
    return {
        "case_id": case_id,
        "problem": merged_problem.strip(),
        "difficulty": c.get("difficulty", "medium"),
        "metadata": {
            "personas": c.get("personas"),
            "hidden_constraints": c.get("hidden_constraints"),
            "success_criteria": c.get("success_criteria"),
        },
    }


def list_case_ids() -> list[str]:
    return [str(c.get("id")) for c in load_cases() if c.get("id")]
