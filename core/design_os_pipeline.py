"""Shared backend for CLI and Streamlit: full design-OS pipeline run."""

from __future__ import annotations

from typing import Any

from core.composition.composer import compose_strategy
from core.evaluation.evaluator import evaluation_targets
from core.memory.store import SolutionMemory
from core.planning.planner import build_architecture, build_execution_plan
from core.requirement.parser import parse_requirement
from core.research.retriever import research_snapshot
from core.structuring.structurer import structure_requirement


def run_design_os(raw_input: str, *, persist_memory: bool = True) -> dict[str, Any]:
    """
    Requirement → structuring → research snapshot → composition → plan → evaluation.
    Optionally appends one record to SolutionMemory.
    """
    text = (raw_input or "").strip()
    requirement = parse_requirement(text)
    structured = structure_requirement(requirement)
    research = research_snapshot(structured["use_case"])
    composition = compose_strategy(structured, requirement)
    architecture = build_architecture(structured["use_case"], composition["strategy"])
    plan = build_execution_plan(structured["use_case"], composition["strategy"])
    targets = evaluation_targets(structured, requirement)

    memory_id = ""
    if persist_memory:
        mem = SolutionMemory()
        saved = mem.save(problem={"raw_input": text, **requirement}, strategy=composition["strategy"], plan=plan)
        memory_id = str(saved.get("id", ""))

    return {
        "raw_input": text,
        "requirement": requirement,
        "structured": structured,
        "research": research,
        "composition": composition,
        "architecture": architecture,
        "plan": plan,
        "targets": targets,
        "memory_id": memory_id,
    }
