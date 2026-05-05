"""Synthetic enterprise evaluation datasets for regression / benchmarking decomposition quality."""

from __future__ import annotations

import hashlib
import random
import uuid
from typing import Any


_DOMAINS = {
    "cs_automation": [
        (
            "ticket_routing",
            "Reduce median routing latency while preserving SLA-aware escalation paths.",
            ["intent_classification", "queue_prioritization", "sla_constraints"],
            "intent_router_with_human_escalation_and_audit_logging",
        ),
        (
            "response_generation",
            "Increase first-contact resolution without increasing compliance risk.",
            ["grounded_generation", "policy_checks", "human_in_the_loop"],
            "rag_with_retrieval_rerank_and_policy_filtered_generation",
        ),
        (
            "escalation_prediction",
            "Predict escalations early to reduce churn and backlog spikes.",
            ["tabular_sequence_signals", "threshold_calibration", "fairness_review"],
            "gradient_boosted_escalation_model_plus_uncertainty_gating",
        ),
    ],
    "enterprise_search": [
        (
            "hybrid_retrieval",
            "Improve relevance across heterogeneous docs with conflicting schemas.",
            ["bm25_dense_fusion", "reranking", "latency_budget"],
            "hybrid_retriever_plus_cross_encoder_rerank_under_latency_budget",
        ),
        (
            "permission_aware_search",
            "Semantic search must enforce ACLs and lineage constraints.",
            ["acl_filters", "approx_nearest_neighbor", "audit_trails"],
            "acl_filtered_dense_retrieval_with_document_level_permissions",
        ),
    ],
    "workflow_agents": [
        (
            "multi_step_task_automation",
            "Automate multi-system workflows with approvals and rollback.",
            ["planning", "state_machine", "idempotent_tools"],
            "planner_executor_agent_with_checkpointed_tool_calls",
        ),
        (
            "tool_usage_planning",
            "Choose tools safely under ambiguous instructions.",
            ["tool_schema_validation", "sandboxing", "monitoring"],
            "tool_router_llm_with_schema_constraints_and_runtime_guardrails",
        ),
    ],
    "decision_systems": [
        (
            "ranking",
            "Rank suppliers/offers under incomplete labels and shifting objectives.",
            ["learning_to_rank", "cold_start", "exploration_vs_exploit"],
            "ltr_model_with_exploration_guardrails_and_shadow_metrics",
        ),
        (
            "recommendation",
            "Increase attach rate without harming diversity or fairness KPIs.",
            ["two_tower_retrieval", "constraints", "offline_online_gap"],
            "constrained_recommender_with_multi_objective_evaluation",
        ),
        (
            "forecasting",
            "Forecast demand with drift and sparse signals across regions.",
            ["time_series", "hierarchical_models", "probabilistic_forecasts"],
            "hierarchical_prob_forecast_with_drift_detection_and_override_hooks",
        ),
    ],
}


_ADVERSARIAL_SEEDS = [
    {
        "enterprise_problem": (
            "Ambiguous multi-intent enterprise support ticket: billing dispute tied to SSO outage "
            "and conflicting escalation policies across regions."
        ),
        "goal": "Force decomposition failure if the system misses contradictory constraints.",
        "constraints_hint": ["latency", "cost", "compliance", "multi_region_policy_conflict"],
        "gold_focus": ["intent_disambiguation", "policy_conflict_resolution", "human_escalation_design"],
        "gold_solution_pattern": "multi_intent_classifier_plus_policy_resolver_with_forced_human_review",
        "difficulty_level": "frontier",
    },
    {
        "enterprise_problem": (
            "Executive asks for full automation of regulated decisions while analysts insist "
            "on mandatory manual approvals — timeline is unrealistic."
        ),
        "goal": "Expose shallow architectures that skip governance.",
        "constraints_hint": ["regulated_environment", "manual_approval_nonnegotiable", "schedule_pressure"],
        "gold_focus": ["governance_layer", "risk_quantification", "phased_rollout"],
        "gold_solution_pattern": "human_in_the_loop_decision_stack_with_audit_and_phased_automation",
        "difficulty_level": "high",
    },
]


def _metrics_for(domain_bucket: str, _facet: str) -> list[str]:
    common = ["offline_regression_suite", "latency_p95", "cost_per_event"]
    if domain_bucket == "cs_automation":
        return [*common, "deflection_rate", "csat_delta", "policy_violation_rate"]
    if domain_bucket == "enterprise_search":
        return [*common, "precision_at_k", "permission_leak_tests", "freshness_gap"]
    if domain_bucket == "workflow_agents":
        return [*common, "task_success_rate", "tool_failure_rate", "recovery_rate"]
    return [*common, "business_kpi_alignment", "calibration_error", "fairness_audit_pass_rate"]


def _vary(seed_text: str, idx: int) -> dict[str, Any]:
    h = hashlib.sha256(f"{seed_text}:{idx}".encode()).hexdigest()
    ambiguity = (
        "Stakeholders disagree on objective weights; dataset intentionally underspecified key KPIs."
        if int(h[:2], 16) % 3 == 0
        else "Partial telemetry gaps force reliance on proxies."
    )
    tradeoffs = []
    if int(h[2:4], 16) % 2 == 0:
        tradeoffs.append("Lower latency vs higher retrieval precision")
    if int(h[4:6], 16) % 2 == 0:
        tradeoffs.append("Automation coverage vs compliance conservatism")
    return {"ambiguity": ambiguity, "tradeoffs": tradeoffs}


def generate_dataset(domain: str, n: int = 50) -> list[dict[str, Any]]:
    """
    Generate `n` datapoints with realistic ambiguity/constraints/tradeoffs for the requested domain bucket.
    Domains: cs_automation | enterprise_search | workflow_agents | decision_systems
    """
    bucket = domain.strip().lower()
    templates = _DOMAINS.get(bucket)
    if not templates:
        raise ValueError(f"Unknown domain '{domain}'. Expected one of {list(_DOMAINS)}.")

    rng = random.Random(42)
    out: list[dict[str, Any]] = []
    adversarial_quota = min(n, max(1, int(round(n * 0.12))))

    for i in range(n):
        facet_id, headline, tech_hints, gold_pattern = templates[i % len(templates)]
        variation = _vary(headline, i)
        constraints = [
            "latency_budget_ms_interactive_paths",
            "cost_ceiling_gpu_hours_per_month",
            "privacy_retention_and_redaction_rules",
            *variation["tradeoffs"],
        ]
        ctx_parts = [
            f"Facet={facet_id}",
            variation["ambiguity"],
            f"Operational footprint includes legacy tooling with uneven telemetry fidelity (sample #{i}).",
        ]

        difficulty_roll = rng.random()
        if difficulty_roll < 0.25:
            difficulty = "low"
        elif difficulty_roll < 0.65:
            difficulty = "medium"
        elif difficulty_roll < 0.9:
            difficulty = "high"
        else:
            difficulty = "frontier"

        expected_decomp = [
            f"{bucket}:{hint}" for hint in tech_hints
        ]
        dp = {
            "id": str(uuid.uuid4()),
            "enterprise_problem": f"[{bucket.upper()}::{facet_id}] {headline}",
            "domain": bucket,
            "context": " ".join(ctx_parts),
            "constraints": constraints,
            "expected_technical_decomposition": expected_decomp,
            "gold_solution_pattern": gold_pattern,
            "evaluation_metrics": _metrics_for(bucket, facet_id),
            "difficulty_level": difficulty,
        }
        out.append(dp)

    # Hard/adversarial evaluation injectors (overwrite tail)
    for j in range(adversarial_quota):
        seed = rng.choice(_ADVERSARIAL_SEEDS)
        dp_adv = {
            "id": str(uuid.uuid4()),
            "enterprise_problem": seed["enterprise_problem"],
            "domain": bucket,
            "context": (
                f"Adversarial benchmark #{j}: {seed['goal']} "
                f"(constraints_hint={seed['constraints_hint']})"
            ),
            "constraints": [
                *seed["constraints_hint"],
                "ambiguous stakeholder objectives",
                "non_stationary seasonal demand",
            ],
            "expected_technical_decomposition": [*seed["gold_focus"], "risk_controls"],
            "gold_solution_pattern": seed["gold_solution_pattern"],
            "evaluation_metrics": [
                "decomposition_consistency_score",
                "constraint_coverage_score",
                "hallucinated_capability_detection_rate",
                *_metrics_for(bucket, "adversarial"),
            ],
            "difficulty_level": seed["difficulty_level"],
        }
        out[-(j + 1)] = dp_adv

    return out
