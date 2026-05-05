"""In-memory + JSON leaderboard for model/task benchmarks."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from shared.schemas import BenchmarkEntry


def _parse_score(score: str) -> float:
    try:
        return float(str(score).strip().replace("%", ""))
    except (TypeError, ValueError):
        return float("-inf")


class BenchmarkTracker:
    def __init__(self, json_path: Path | None = None) -> None:
        self._entries: list[dict[str, Any]] = []
        self._json_path = json_path or (_ROOT / "data" / "benchmark_leaderboard.json")
        self._load()

    def _load(self) -> None:
        if not self._json_path.exists():
            return
        raw = json.loads(self._json_path.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            for row in raw:
                if isinstance(row, dict):
                    self._entries.append(BenchmarkEntry.model_validate(row).model_dump())

    def _persist(self) -> None:
        self._json_path.parent.mkdir(parents=True, exist_ok=True)
        self._json_path.write_text(
            json.dumps(self._entries, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def add_entry(
        self,
        *,
        task: str,
        model: str,
        metric: str,
        score: str,
        date_value: str | None = None,
    ) -> dict[str, Any]:
        row = BenchmarkEntry(
            task=task,
            model=model,
            metric=metric,
            score=score,
            date=date_value or date.today().isoformat(),
        ).model_dump()
        self._entries.append(row)
        self._persist()
        return row

    def get_best_model(self, task: str) -> dict[str, Any]:
        """Best row by numeric score for matching task (metric with highest score wins per metric group)."""
        subset = [e for e in self._entries if e.get("task") == task]
        if not subset:
            return {
                "task": task,
                "model": "",
                "metric": "",
                "score": "",
                "date": "",
                "note": "no_entries",
            }
        best = max(subset, key=lambda e: _parse_score(str(e.get("score", ""))))
        return dict(best)

    def compare_models(self, task: str) -> dict[str, Any]:
        subset = [e for e in self._entries if e.get("task") == task]
        by_model: dict[str, list[dict[str, Any]]] = {}
        for e in subset:
            by_model.setdefault(str(e.get("model", "")), []).append(dict(e))
        ranking = sorted(
            by_model.items(),
            key=lambda kv: max((_parse_score(str(x.get("score", ""))) for x in kv[1]), default=float("-inf")),
            reverse=True,
        )
        return {"task": task, "models": [{"model": m, "entries": es} for m, es in ranking]}


_default_tracker: BenchmarkTracker | None = None


def get_default_tracker() -> BenchmarkTracker:
    global _default_tracker  # noqa: PLW0603
    if _default_tracker is None:
        _default_tracker = BenchmarkTracker()
    return _default_tracker


def add_entry(
    *,
    task: str,
    model: str,
    metric: str,
    score: str,
    date: str | None = None,
) -> dict[str, Any]:
    return get_default_tracker().add_entry(task=task, model=model, metric=metric, score=score, date_value=date)


def get_best_model(task: str) -> dict[str, Any]:
    return get_default_tracker().get_best_model(task)


def compare_models(task: str) -> dict[str, Any]:
    return get_default_tracker().compare_models(task)
