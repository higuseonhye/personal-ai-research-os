"""Simple in-memory task leaderboard keyed by extracted problem description."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class Leaderboard:
    def __init__(self, history_path: Path | None = None) -> None:
        self.db: dict[str, list[dict[str, Any]]] = {}
        self.history_path = history_path

    def update(self, task: str, model: str, score: float) -> None:
        if task not in self.db:
            self.db[task] = []
        row = {"model": model, "score": float(score)}
        self.db[task].append(row)
        self._append_history(task, row)

    def _append_history(self, task: str, row: dict[str, Any]) -> None:
        if self.history_path is None:
            return
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        line = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "task": task[:512],
            "model": row.get("model", ""),
            "score": row.get("score", 0.0),
        }
        with self.history_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")

    def get_best(self, task: str) -> dict[str, Any]:
        rows = self.db.get(task, [])
        if not rows:
            return {"model": "", "score": float("-inf")}
        return max(rows, key=lambda x: float(x["score"]))

    def all_tasks(self) -> dict[str, list[dict[str, Any]]]:
        return dict(self.db)

    def table_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for task, entries in self.db.items():
            best = self.get_best(task)
            rows.append(
                {
                    "task": task[:120],
                    "best_model": best.get("model", ""),
                    "best_score": best.get("score", float("-inf")),
                    "entries": len(entries),
                }
            )
        return sorted(rows, key=lambda r: float(r.get("best_score", float("-inf"))), reverse=True)


_default_lb: Leaderboard | None = None


def default_leaderboard_history_path() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "leaderboard_history.jsonl"


def get_default_leaderboard() -> Leaderboard:
    global _default_lb  # noqa: PLW0603
    if _default_lb is None:
        _default_lb = Leaderboard(history_path=default_leaderboard_history_path())
    return _default_lb
