from __future__ import annotations

from typing import Any, Literal

from .llm_judge import extract_candidate_text, llm_judge_scores

Outcome = Literal["A", "B", "tie"]


def pairwise_decision(
    output_a: dict[str, Any] | None,
    output_b: dict[str, Any] | None,
    query: str | None = None,
    reference: str | None = None,
) -> dict[str, Any]:
    """
    Forced-choice ranking using aggregated judge dimensions (local, system-agnostic).
    """
    ta = extract_candidate_text(output_a)
    tb = extract_candidate_text(output_b)
    ja = llm_judge_scores(ta, query=query, reference=reference)
    jb = llm_judge_scores(tb, query=query, reference=reference)

    def agg(j: dict[str, float]) -> float:
        return (
            j["relevance"] + j["correctness"] + j["usefulness"] - j["hallucination_risk"]
        ) / 3.0

    sa, sb = agg(ja), agg(jb)
    margin = 0.02
    if abs(sa - sb) < margin:
        winner: Outcome = "tie"
    elif sa > sb:
        winner = "A"
    else:
        winner = "B"

    return {
        "winner": winner,
        "scores": {"A": ja, "B": jb, "aggregate_A": sa, "aggregate_B": sb},
    }
