"""
LangGraph multi-agent orchestration: enterprise problem → execution-grade plan.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import StateGraph

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import networkx as nx  # noqa: E402

from shared.llm_client import json_llm_complete_dict  # noqa: E402
from shared.schemas import (  # noqa: E402
    ArchitectureAgentGraphOutput,
    EvalAgentGraphOutput,
    IterationAgentGraphOutput,
    PMGraphOutput,
    SOTAAgentGraphOutput,
)


class ResearchState(TypedDict, total=False):
    """LangGraph merges partial updates into this state (values are JSON-serializable blobs)."""

    problem: str
    pm_output: dict[str, object]
    decomposition: dict[str, object]
    sota: dict[str, object]
    architecture: dict[str, object]
    evaluation: dict[str, object]
    iteration: dict[str, object]


def _load(rel: str, name: str) -> Any:
    path = _ROOT / rel
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)
    return mod


_et = _load("03_problem_decomposer/enterprise_to_tech.py", "pa_et")
_sota_stub = _load("04_sota_engine/sota_retrieval.py", "pa_sota_stub")
_arch = _load("05_solution_engine/architecture_generator.py", "pa_arch_gen")
_eval = _load("00_core/evaluation_framework/evaluate_solution.py", "pa_eval_sol")
_iterate = _load("08_feedback_loop/iteration_engine.py", "pa_iter")
_emb_mod = _load("07_rag_system/embedding_store.py", "pa_emb")


def _task_graph(subproblems: list[str]) -> dict[str, Any]:
    G = nx.DiGraph()
    for sp in subproblems:
        G.add_node(sp)
    for u, v in zip(subproblems, subproblems[1:]):
        G.add_edge(u, v, rel="next")
    return nx.node_link_data(G)


def _pm_fallback(problem: str) -> dict[str, Any]:
    return {
        "problem_summary": problem.strip(),
        "kpi": ["cost_reduction", "quality_of_service", "time_to_resolution"],
        "constraints": ["privacy_and_compliance", "latency_slos", "budget_and_headcount"],
    }


def pm_agent(state: ResearchState) -> dict[str, Any]:
    problem = state.get("problem", "")
    system = (
        "You are an enterprise AI PM. Return ONLY JSON with keys: "
        "problem_summary, kpi, constraints — all concise; kpi/constraints are string arrays."
    )
    fb = _pm_fallback(problem)
    data = json_llm_complete_dict(system, problem, PMGraphOutput, fallback_builder=fb)
    return {"pm_output": data}


def decomposer_agent(state: ResearchState) -> dict[str, Any]:
    problem = state.get("problem", "")
    legacy = _et.decompose_enterprise_problem(problem)
    subs = list(legacy.get("technical_subproblems") or [])
    dec = {
        "subproblems": subs,
        "task_graph": _task_graph(subs),
        "assumptions": list(legacy.get("assumptions") or []),
        "technical_subproblems": subs,
        "interpreted_goal": legacy.get("interpreted_goal", ""),
        "constraints": list(legacy.get("constraints") or []),
        "success_metrics": list(legacy.get("success_metrics") or []),
        "raw_problem": legacy.get("raw_problem", problem),
    }
    pm = state.get("pm_output") or {}
    extra = pm.get("constraints") or []
    if extra:
        merged = list(dict.fromkeys([*dec.get("constraints", []), *[str(x) for x in extra]]))
        dec["constraints"] = merged
    return {"decomposition": dec}


def _sota_fallback(ctx: dict[str, Any]) -> dict[str, Any]:
    papers = ctx.get("papers") or []
    rel: list[dict[str, Any]] = []
    methods: list[str] = []
    for p in papers:
        rel.append(
            {
                "title": p.get("title", ""),
                "relevance": p.get("relevance", ""),
                "venue": p.get("venue", ""),
                "year": p.get("year", ""),
                "methods": p.get("methods", []),
            }
        )
        methods.extend([str(m) for m in (p.get("methods") or [])])
    methods = list(dict.fromkeys(methods))
    return {
        "relevant_papers": rel,
        "methods": methods,
        "baseline_models": ["bm25_lexical_retriever", "prompt_only_llm_baseline"],
        "sota_models": ["hybrid_dense_sparse_retriever", "late_interaction_reranker", "tool_using_llm_agent"],
    }


def sota_agent(state: ResearchState) -> dict[str, Any]:
    decomposition = state.get("decomposition") or {}
    stub_in = {
        "technical_subproblems": decomposition.get("technical_subproblems")
        or decomposition.get("subproblems")
        or [],
    }
    ctx = _sota_stub.retrieve_relevant_sota(stub_in)

    retrieved: list[dict[str, Any]] = []
    try:
        store = _emb_mod.get_default_embedding_store()
        q = state.get("problem", "")
        hits = store.search(q, k=5)
        for h in hits:
            retrieved.append(
                {
                    "title": str(h.get("title", "")),
                    "source": "embedding_index",
                    "problem": str(h.get("problem", ""))[:400],
                    "method": str(h.get("method", ""))[:400],
                }
            )
    except Exception:  # noqa: BLE001
        retrieved = []

    fb = _sota_fallback(ctx)
    if retrieved:
        fb["relevant_papers"] = [*retrieved, *fb.get("relevant_papers", [])]

    system = (
        "You are a research operator. Rank and normalize SOTA pointers for an enterprise build. "
        "Return ONLY JSON with keys: relevant_papers (array of objects with title,relevance,methods[] optional), "
        "methods (strings), baseline_models (strings), sota_models (strings)."
    )
    user = json.dumps({"stub_context": ctx, "problem": state.get("problem", "")}, ensure_ascii=False)
    data = json_llm_complete_dict(system, user, SOTAAgentGraphOutput, fallback_builder=fb)
    data["retrieval_mode"] = ctx.get("retrieval_mode", "stub_static")
    return {"sota": data}


def architecture_agent(state: ResearchState) -> dict[str, Any]:
    decomposition = state.get("decomposition") or {}
    sota_ctx = state.get("sota") or {}
    legacy_dec = {
        "technical_subproblems": decomposition.get("technical_subproblems")
        or decomposition.get("subproblems")
        or [],
        "interpreted_goal": decomposition.get("interpreted_goal", ""),
        "constraints": decomposition.get("constraints", []),
        "success_metrics": decomposition.get("success_metrics", []),
        "assumptions": decomposition.get("assumptions", []),
        "raw_problem": decomposition.get("raw_problem", state.get("problem", "")),
    }
    stub_arch_input = {
        "papers": sota_ctx.get("relevant_papers") or [],
        "mapped_subproblems": legacy_dec["technical_subproblems"],
        "retrieval_mode": sota_ctx.get("retrieval_mode", ""),
        "methods": sota_ctx.get("methods", []),
    }
    legacy_arch = _arch.generate_architecture(legacy_dec, stub_arch_input)
    graph_arch = {
        "architecture": legacy_arch.get("system_design", ""),
        "components": list(legacy_arch.get("components") or []),
        "data_flow": list(legacy_arch.get("data_flow") or []),
        "model_choices": (
            [legacy_arch["model_choice"]] if legacy_arch.get("model_choice") else []
        ),
        "_legacy": legacy_arch,
    }
    system = (
        "Rewrite deployment architecture as JSON ONLY with keys: architecture (string narrative), "
        "components (strings), data_flow (strings), model_choices (strings). "
        "Must stay grounded in the provided legacy_architecture JSON."
    )
    user = json.dumps({"legacy_architecture": legacy_arch, "sota": sota_ctx}, ensure_ascii=False)
    fb = {
        "architecture": graph_arch["architecture"],
        "components": graph_arch["components"],
        "data_flow": graph_arch["data_flow"],
        "model_choices": graph_arch["model_choices"],
    }
    data = json_llm_complete_dict(system, user, ArchitectureAgentGraphOutput, fallback_builder=fb)
    return {"architecture": {**data, "_legacy": legacy_arch}}


def _legacy_architecture_blob(architecture: dict[str, Any]) -> dict[str, Any]:
    legacy = architecture.get("_legacy")
    if isinstance(legacy, dict) and legacy:
        return legacy
    choices = architecture.get("model_choices") or []
    mc = choices[0] if choices else ""
    return {
        "system_design": architecture.get("architecture", ""),
        "components": architecture.get("components", []),
        "data_flow": architecture.get("data_flow", []),
        "model_choice": mc,
        "tradeoffs": [],
        "baseline_vs_sota": "",
    }


def eval_agent(state: ResearchState) -> dict[str, Any]:
    architecture = state.get("architecture") or {}
    legacy_arch = _legacy_architecture_blob(architecture)
    ev = _eval.evaluate_solution(legacy_arch)
    fb = {
        "metrics": list(ev.get("recommended_metrics") or []),
        "expected_failure_modes": list(ev.get("deployment_risks") or []),
        "eval_strategy": f"{ev.get('verdict', '')}: readiness={ev.get('readiness_score', '')}",
    }
    system = (
        "Return ONLY JSON with keys metrics (strings), expected_failure_modes (strings), eval_strategy (string) "
        "using the supplied evaluation snapshot."
    )
    user = json.dumps({"evaluation": ev, "architecture": architecture}, ensure_ascii=False)
    data = json_llm_complete_dict(system, user, EvalAgentGraphOutput, fallback_builder=fb)
    return {"evaluation": {**data, "_legacy": ev}}


def iteration_agent(state: ResearchState) -> dict[str, Any]:
    architecture = state.get("architecture") or {}
    evaluation = state.get("evaluation") or {}
    legacy_arch = _legacy_architecture_blob(architecture)
    legacy_ev = evaluation.get("_legacy") or {
        "deployment_risks": evaluation.get("expected_failure_modes", []),
        "recommended_metrics": evaluation.get("metrics", []),
        "readiness_score": "",
        "verdict": "",
    }
    it = _iterate.evaluate_and_iterate(legacy_arch, legacy_ev)
    improvements = [
        *[str(x) for x in it.get("improvement_iterations") or []],
        *[str(x) for x in it.get("architecture_updates") or []],
    ]
    plan_parts = [
        *[str(x) for x in it.get("failure_points") or []],
        *[str(x) for x in it.get("improvement_iterations") or []],
    ]
    fb = {
        "improvements": improvements,
        "next_iteration_plan": "; ".join(plan_parts)[:4000],
    }
    system = (
        "Return ONLY JSON improvements (string array) and next_iteration_plan (single string). "
        "Ground updates in evaluation weaknesses."
    )
    user = json.dumps({"iteration_hint": it, "evaluation": evaluation}, ensure_ascii=False)
    data = json_llm_complete_dict(system, user, IterationAgentGraphOutput, fallback_builder=fb)
    data["_legacy_iteration"] = it
    return {"iteration": data}


def build_graph() -> Any:
    graph = StateGraph(ResearchState)
    graph.add_node("pm_agent", pm_agent)
    graph.add_node("decomposer", decomposer_agent)
    graph.add_node("sota", sota_agent)
    graph.add_node("architecture", architecture_agent)
    graph.add_node("evaluation", eval_agent)
    graph.add_node("iteration", iteration_agent)

    graph.set_entry_point("pm_agent")
    graph.add_edge("pm_agent", "decomposer")
    graph.add_edge("decomposer", "sota")
    graph.add_edge("sota", "architecture")
    graph.add_edge("architecture", "evaluation")
    graph.add_edge("evaluation", "iteration")
    graph.set_finish_point("iteration")
    return graph.compile()


_compiled_app = None


def get_app():
    global _compiled_app  # noqa: PLW0603
    if _compiled_app is None:
        _compiled_app = build_graph()
    return _compiled_app


def run_system(problem: str) -> dict[str, Any]:
    return get_app().invoke({"problem": problem})
