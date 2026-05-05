"""
End-to-end enterprise problem → decomposition → SOTA → architecture → eval → iteration.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load(rel_path: str) -> ModuleType:
    path = ROOT / rel_path
    name = path.stem
    spec = importlib.util.spec_from_file_location(f"pa_{name}", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)
    return mod


_enterprise_to_tech = _load("03_problem_decomposer/enterprise_to_tech.py")
_sota_retrieval = _load("04_sota_engine/sota_retrieval.py")
_architecture_generator = _load("05_solution_engine/architecture_generator.py")
_evaluate_solution = _load("00_core/evaluation_framework/evaluate_solution.py")
_iteration_engine = _load("08_feedback_loop/iteration_engine.py")

decompose_enterprise_problem = _enterprise_to_tech.decompose_enterprise_problem
retrieve_relevant_sota = _sota_retrieval.retrieve_relevant_sota
generate_architecture = _architecture_generator.generate_architecture
evaluate_solution = _evaluate_solution.evaluate_solution
evaluate_and_iterate = _iteration_engine.evaluate_and_iterate

_langgraph_orch: ModuleType | None = None
_production_dag: ModuleType | None = None


def _get_langgraph_orchestrator() -> ModuleType:
    """Load only when running the LangGraph path (optional dependency)."""
    global _langgraph_orch  # noqa: PLW0603
    if _langgraph_orch is None:
        _langgraph_orch = _load("06_execution_agents/langgraph_orchestrator.py")
    return _langgraph_orch


def run_system(problem: str) -> dict[str, Any]:
    return _get_langgraph_orchestrator().run_system(problem)


def _get_production_dag() -> ModuleType:
    global _production_dag  # noqa: PLW0603
    if _production_dag is None:
        _production_dag = _load("06_execution_agents/production_langgraph_dag.py")
    return _production_dag


def run_production_system(problem: str) -> dict[str, Any]:
    return _get_production_dag().run_production_system(problem)


def run_full_pipeline(problem: str) -> dict[str, Any]:
    decomposition = decompose_enterprise_problem(problem)
    papers = retrieve_relevant_sota(decomposition)
    architecture = generate_architecture(decomposition, papers)
    evaluation = evaluate_solution(architecture)
    iteration = evaluate_and_iterate(architecture, evaluation)
    return {
        "decomposition": decomposition,
        "architecture": architecture,
        "evaluation": evaluation,
        "iteration": iteration,
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Enterprise AI Research OS — full MVP pipeline")
    parser.add_argument(
        "problem",
        nargs="?",
        default="Reduce customer support cost in SaaS product",
    )
    parser.add_argument(
        "--langgraph",
        action="store_true",
        help="Run LangGraph multi-agent orchestrator (enterprise OS loop).",
    )
    parser.add_argument(
        "--production-dag",
        action="store_true",
        help="Run production conditional LangGraph DAG (routing + retries).",
    )
    parser.add_argument(
        "--case-id",
        default="",
        help="Use a company simulation case from 00_core/company_simulation/cases.json (overrides problem text).",
    )
    args = parser.parse_args()
    problem_text = args.problem
    if args.case_id.strip():
        import importlib.util

        sim_path = ROOT / "00_core" / "company_simulation" / "simulation.py"
        sspec = importlib.util.spec_from_file_location("company_simulation_cli", sim_path)
        smod = importlib.util.module_from_spec(sspec)
        assert sspec.loader
        sspec.loader.exec_module(smod)
        envelope = smod.build_problem_envelope(args.case_id.strip())
        problem_text = envelope["problem"]
    if args.langgraph and args.production_dag:
        raise SystemExit("Choose only one of --langgraph or --production-dag.")
    if args.production_dag:
        try:
            out = run_production_system(problem_text)
        except ImportError as e:
            raise SystemExit(
                "Production DAG requires LangGraph stack. Install:\n"
                "  pip install langgraph langchain networkx\n"
                f"Original error: {e}"
            ) from e
    elif args.langgraph:
        try:
            out = run_system(problem_text)
        except ImportError as e:
            raise SystemExit(
                "LangGraph path requires optional deps. In the same Python env you use for this command, run:\n"
                "  pip install langgraph langchain\n"
                f"Original error: {e}"
            ) from e
    else:
        out = run_full_pipeline(problem_text)
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
