from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from experiment_engine.engine import ExperimentRecord

from .llm_judge import LLMJudgeConfig, extract_candidate_text, llm_judge_scores
from .metrics import accuracy_score, mean_reciprocal_rank, ndcg_at_k, recall_at_k
from .pairwise import pairwise_decision


@dataclass
class PerSystemEval:
    system_id: str
    success: bool
    metrics: dict[str, float] = field(default_factory=dict)
    judge: dict[str, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


@dataclass
class EvaluationBundle:
    per_system: list[PerSystemEval]
    pairwise: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "per_system": [
                {
                    "system_id": p.system_id,
                    "success": p.success,
                    "metrics": p.metrics,
                    "judge": p.judge,
                    "notes": p.notes,
                }
                for p in self.per_system
            ],
            "pairwise": self.pairwise,
        }


def _get_ranked_ids(output_dict: dict[str, Any] | None) -> list[str] | None:
    if not output_dict:
        return None
    rid = output_dict.get("ranked_ids")
    if isinstance(rid, list):
        return [str(x) for x in rid]
    payload = output_dict.get("payload") or {}
    hits = payload.get("hits")
    if isinstance(hits, list):
        return [str(h.get("id")) for h in hits if h.get("id") is not None]
    ranked = payload.get("ranked")
    if isinstance(ranked, list):
        return [str(h.get("id")) for h in ranked if h.get("id") is not None]
    return None


def evaluate_record(
    record: ExperimentRecord,
    input_dict: dict[str, Any],
    k: int = 10,
    judge_config: LLMJudgeConfig | None = None,
) -> EvaluationBundle:
    """Evaluate all successful systems in an experiment record (domain-agnostic)."""
    rel = input_dict.get("relevant_ids")
    relevant: set[str] = set(str(x) for x in rel) if rel else set()
    query = str(input_dict.get("query") or input_dict.get("question") or "")
    reference = input_dict.get("reference_answer")
    reference = str(reference) if reference is not None else None

    per_system: list[PerSystemEval] = []
    outputs_by_id: dict[str, dict[str, Any] | None] = {}

    for r in record.results:
        if not r.success or not r.output:
            per_system.append(
                PerSystemEval(
                    system_id=r.system_id,
                    success=False,
                    notes=["run_failed"],
                )
            )
            outputs_by_id[r.system_id] = None
            continue

        out = r.output
        outputs_by_id[r.system_id] = out
        notes: list[str] = []
        metrics: dict[str, float] = {}

        ranked = _get_ranked_ids(out)
        if relevant and ranked:
            metrics["recall@k"] = recall_at_k(ranked, relevant, k)
            metrics["mrr"] = mean_reciprocal_rank(ranked, relevant)
            metrics[f"ndcg@{k}"] = ndcg_at_k(ranked, relevant, k)
        elif ranked and not relevant:
            notes.append("ranked_output_without_relevant_ids_skipped_ir_metrics")

        cand_text = extract_candidate_text(out)
        judge = llm_judge_scores(cand_text, query=query, reference=reference, config=judge_config)

        if reference and (out.get("raw_text") or (out.get("payload") or {}).get("answer") is not None):
            ans = str((out.get("payload") or {}).get("answer") or out.get("raw_text") or "")
            metrics["accuracy_proxy"] = accuracy_score(ans, reference)

        per_system.append(
            PerSystemEval(
                system_id=r.system_id,
                success=True,
                metrics=metrics,
                judge=judge,
                notes=notes,
            )
        )

    pairwise: list[dict[str, Any]] = []
    ids = [r.system_id for r in record.results if r.success and r.output]
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = ids[i], ids[j]
            pairwise.append(
                {
                    "A": a,
                    "B": b,
                    **pairwise_decision(outputs_by_id[a], outputs_by_id[b], query=query, reference=reference),
                }
            )

    return EvaluationBundle(per_system=per_system, pairwise=pairwise)
