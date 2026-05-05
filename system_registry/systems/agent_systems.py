from __future__ import annotations

import json
from typing import Any

from system_registry.base import AISystem, SystemOutput


class RuleBasedAgent(AISystem):
    system_id = "RuleBasedAgent"
    description = "Deterministic rule-based planner over a simple task spec."

    def run(self, input: dict) -> SystemOutput:
        self.validate_input(input, ("task",))
        task = str(input["task"]).lower()
        tools = list(input.get("tools", ["search", "summarize", "verify"]))
        plan: list[dict[str, Any]] = []
        if "search" in task or "find" in task:
            plan.append({"step": 1, "action": "search", "tool": "search", "reason": "task requests discovery"})
        if "summarize" in task or "report" in task:
            plan.append({"step": len(plan) + 1, "action": "summarize", "tool": "summarize", "reason": "output shaping"})
        if not plan:
            plan.append({"step": 1, "action": "clarify", "tool": "ask_user", "reason": "ambiguous task"})
        plan.append({"step": len(plan) + 1, "action": "verify", "tool": "verify", "reason": "reduce hallucination risk"})
        out = {"plan": plan, "available_tools": tools}
        return SystemOutput(
            self.system_id,
            payload=out,
            raw_text=json.dumps(out, indent=2),
        )


class LangGraphStylePlanner(AISystem):
    system_id = "LangGraphStylePlanner"
    description = "Mock LangGraph-style state machine planner (deterministic stub)."

    def run(self, input: dict) -> SystemOutput:
        self.validate_input(input, ("task",))
        task = str(input["task"])
        graph = {
            "nodes": ["ingest", "plan", "execute", "reflect"],
            "edges": [("ingest", "plan"), ("plan", "execute"), ("execute", "reflect")],
            "state": {"task": task, "attempt": 1},
            "mock": True,
        }
        return SystemOutput(
            self.system_id,
            payload=graph,
            raw_text=json.dumps(graph),
            extras={"note": "Replace with real LangGraph workflow for deep agent research."},
        )
