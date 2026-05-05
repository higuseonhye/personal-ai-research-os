"""Pydantic models for JSON-first pipeline outputs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ProblemDecomposition(BaseModel):
    model_config = ConfigDict(extra="ignore")

    raw_problem: str = ""
    interpreted_goal: str = ""
    technical_subproblems: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    success_metrics: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class PaperSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")

    problem: str = ""
    method: str = ""
    architecture: str = ""
    dataset: str = ""
    metrics: str = ""
    key_innovation: str = ""
    limitations: str = ""


class BenchmarkEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")

    task: str = ""
    model: str = ""
    metric: str = ""
    score: str = ""
    date: str = ""


class ArchitectureOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    system_design: str = ""
    components: list[str] = Field(default_factory=list)
    data_flow: list[str] = Field(default_factory=list)
    model_choice: str = ""
    tradeoffs: list[str] = Field(default_factory=list)
    baseline_vs_sota: str = ""


class PMAgentOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    interpreted_problem: str = ""
    kpis: list[str] = Field(default_factory=list)
    product_requirements: list[str] = Field(default_factory=list)


class FDEAgentOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    deployment_plan: list[str] = Field(default_factory=list)
    infrastructure: list[str] = Field(default_factory=list)
    tooling: list[str] = Field(default_factory=list)
    bottlenecks: list[str] = Field(default_factory=list)


class IterationOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    failure_points: list[str] = Field(default_factory=list)
    improvement_iterations: list[str] = Field(default_factory=list)
    architecture_updates: list[str] = Field(default_factory=list)


class EvaluationResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    readiness_score: str = ""
    deployment_risks: list[str] = Field(default_factory=list)
    recommended_metrics: list[str] = Field(default_factory=list)
    verdict: str = ""


# --- LangGraph agent outputs (enterprise OS loop)


class PMGraphOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    problem_summary: str = ""
    kpi: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)


class DecomposerGraphOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    subproblems: list[str] = Field(default_factory=list)
    task_graph: dict[str, Any] = Field(default_factory=dict)
    assumptions: list[str] = Field(default_factory=list)


class SOTAAgentGraphOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    relevant_papers: list[dict[str, Any]] = Field(default_factory=list)
    methods: list[str] = Field(default_factory=list)
    baseline_models: list[str] = Field(default_factory=list)
    sota_models: list[str] = Field(default_factory=list)


class ArchitectureAgentGraphOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    architecture: str = ""
    components: list[str] = Field(default_factory=list)
    data_flow: list[str] = Field(default_factory=list)
    model_choices: list[str] = Field(default_factory=list)


class EvalAgentGraphOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    metrics: list[str] = Field(default_factory=list)
    expected_failure_modes: list[str] = Field(default_factory=list)
    eval_strategy: str = ""


class IterationAgentGraphOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    improvements: list[str] = Field(default_factory=list)
    next_iteration_plan: str = ""
