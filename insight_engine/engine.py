from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from evaluation_engine.engine import EvaluationBundle, PerSystemEval
from experiment_engine.engine import ExperimentRecord
from problem_compiler.compiler import StructuredResearchTask


@dataclass
class InsightReport:
    best_system: str | None
    ranking: list[tuple[str, float]]
    reasoning: list[str]
    failure_cases: list[dict[str, Any]]
    hypothesis_status: list[dict[str, Any]]
    next_steps: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "best_system": self.best_system,
            "ranking": [{"system_id": s, "score": v} for s, v in self.ranking],
            "reasoning": self.reasoning,
            "failure_cases": self.failure_cases,
            "hypothesis_status": self.hypothesis_status,
            "next_steps": self.next_steps,
            "metadata": self.metadata,
        }


class InsightEngine:
    """Research-style reasoning over experiment + evaluation artifacts (not mere summarization)."""

    def generate(
        self,
        task: StructuredResearchTask,
        record: ExperimentRecord,
        eval_bundle: EvaluationBundle,
        input_snapshot: dict | None = None,
    ) -> InsightReport:
        scored: list[tuple[str, float, PerSystemEval]] = []
        failures: list[dict[str, Any]] = []
        snap = input_snapshot if input_snapshot is not None else record.input_snapshot
        has_ref = bool(snap.get("reference_answer"))

        for p in eval_bundle.per_system:
            if not p.success:
                failures.append(
                    {
                        "type": "execution_failure",
                        "system_id": p.system_id,
                        "notes": p.notes,
                    }
                )
                continue

            ir = sum(p.metrics.get(k, 0.0) for k in ("recall@k", "mrr") if k in p.metrics)
            ir += sum(v for kk, v in p.metrics.items() if kk.startswith("ndcg@"))
            j = p.judge
            judge_agg = (
                j.get("relevance", 0.0)
                + j.get("correctness", 0.0)
                + j.get("usefulness", 0.0)
                - j.get("hallucination_risk", 0.0)
            ) / 3.0
            acc = p.metrics.get("accuracy_proxy", 0.0)
            composite = 0.55 * judge_agg + 0.35 * (ir / 3.0 if ir > 0 else judge_agg) + 0.1 * acc
            scored.append((p.system_id, composite, p))

            low_recall = "recall@k" in p.metrics and p.metrics["recall@k"] < 0.25
            hall = j.get("hallucination_risk", 0.0) > 0.75 and has_ref
            if judge_agg < 0.35 or low_recall or hall:
                failures.append(
                    {
                        "type": "quality_failure",
                        "system_id": p.system_id,
                        "judge": j,
                        "metrics": p.metrics,
                    }
                )

        scored.sort(key=lambda x: (-x[1], x[0]))
        ranking = [(s, v) for s, v, _ in scored]
        best = ranking[0][0] if ranking else None

        reasoning: list[str] = []
        if best:
            reasoning.append(
                f"Under the composite research score mixing judge signals and IR metrics when present, "
                f"`{best}` leads the cohort, indicating the strongest tradeoff of relevance, correctness, "
                f"and groundedness for this input."
            )
        if len(ranking) > 1:
            reasoning.append(
                f"The margin between `{ranking[0][0]}` and `{ranking[1][0]}` quantifies how much headroom "
                f"remains for retrieval, reranking, or generative fixes in the `{task.domain}` domain."
            )
        if task.hypothesis:
            reasoning.append(
                "Hypotheses from the problem compiler frame what this experiment can falsify: "
                + "; ".join(task.hypothesis[:2])
            )

        hyp_status: list[dict[str, Any]] = []
        for h in task.hypothesis:
            supported = bool(best and ("hybrid" in h.lower() and "Hybrid" in (best or "")))
            hyp_status.append(
                {
                    "hypothesis": h,
                    "status": "supported" if supported else "inconclusive",
                    "evidence": f"best_system={best}" if best else "no successful runs",
                }
            )

        next_steps: list[str] = [
            "Promote the leading system to a higher-fidelity dataset slice and rerun with held-out queries.",
            "Mine failure cases into memory and attach counterfactual inputs for the next iteration.",
            "If IR metrics were skipped, annotate `relevant_ids` to enable recall/MRR/nDCG.",
        ]

        return InsightReport(
            best_system=best,
            ranking=ranking,
            reasoning=reasoning,
            failure_cases=failures,
            hypothesis_status=hyp_status,
            next_steps=next_steps,
            metadata={"task_type": task.task_type, "domain": task.domain, "experiment_id": record.experiment_id},
        )
