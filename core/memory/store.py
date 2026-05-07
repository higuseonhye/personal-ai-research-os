"""Append-only JSON memory: problem snapshot, composed strategy, plan."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SolutionMemory:
    """Persists enough context to replay or extend a design session."""

    def __init__(self, path: str | Path | None = None) -> None:
        root = Path(__file__).resolve().parents[2]
        self.path = Path(path) if path else root / "data" / "solution_design_memory.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("[]", encoding="utf-8")

    def save(
        self,
        problem: dict[str, Any],
        strategy: list[str],
        plan: list[str],
    ) -> dict[str, Any]:
        record = {
            "id": str(uuid.uuid4()),
            "saved_at": _utc_now(),
            "problem": problem,
            "selected_strategy": strategy,
            "execution_plan": plan,
        }
        existing = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(existing, list):
            existing = []
        existing.append(record)
        self.path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
        return record
