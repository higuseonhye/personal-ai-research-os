from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evaluation_engine.engine import EvaluationBundle
from experiment_engine.engine import ExperimentRecord
from insight_engine.engine import InsightReport
from problem_compiler.compiler import StructuredResearchTask


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ResearchMemory:
    """Long-term SQLite-backed memory: failures, experiments, hypotheses, domain insights."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        base = Path(__file__).resolve().parents[1] / "data" / "memory.db"
        self.db_path = Path(db_path) if db_path else base
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as c:
            c.executescript(
                """
                CREATE TABLE IF NOT EXISTS experiments (
                    id TEXT PRIMARY KEY,
                    created_at TEXT,
                    domain TEXT,
                    task_type TEXT,
                    payload TEXT
                );
                CREATE TABLE IF NOT EXISTS evaluations (
                    experiment_id TEXT PRIMARY KEY,
                    created_at TEXT,
                    payload TEXT,
                    FOREIGN KEY(experiment_id) REFERENCES experiments(id)
                );
                CREATE TABLE IF NOT EXISTS insights (
                    experiment_id TEXT PRIMARY KEY,
                    created_at TEXT,
                    payload TEXT,
                    FOREIGN KEY(experiment_id) REFERENCES experiments(id)
                );
                CREATE TABLE IF NOT EXISTS failure_cases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT,
                    experiment_id TEXT,
                    system_id TEXT,
                    failure_type TEXT,
                    payload TEXT
                );
                CREATE TABLE IF NOT EXISTS system_performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT,
                    system_id TEXT,
                    score REAL,
                    experiment_id TEXT,
                    domain TEXT
                );
                CREATE TABLE IF NOT EXISTS hypothesis_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT,
                    hypothesis TEXT,
                    status TEXT,
                    evidence TEXT,
                    experiment_id TEXT
                );
                CREATE TABLE IF NOT EXISTS domain_insights (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT,
                    domain TEXT,
                    insight TEXT,
                    experiment_id TEXT
                );
                """
            )

    def persist_run(
        self,
        task: StructuredResearchTask,
        record: ExperimentRecord,
        eval_bundle: EvaluationBundle,
        insight: InsightReport,
    ) -> None:
        now = _utc_now()
        with self._connect() as c:
            c.execute(
                "INSERT OR REPLACE INTO experiments (id, created_at, domain, task_type, payload) VALUES (?,?,?,?,?)",
                (
                    record.experiment_id,
                    now,
                    task.domain,
                    task.task_type,
                    json.dumps(record.to_dict(), ensure_ascii=False),
                ),
            )
            c.execute(
                "INSERT OR REPLACE INTO evaluations (experiment_id, created_at, payload) VALUES (?,?,?)",
                (record.experiment_id, now, json.dumps(eval_bundle.to_dict(), ensure_ascii=False)),
            )
            c.execute(
                "INSERT OR REPLACE INTO insights (experiment_id, created_at, payload) VALUES (?,?,?)",
                (record.experiment_id, now, json.dumps(insight.to_dict(), ensure_ascii=False)),
            )

            for fc in insight.failure_cases:
                c.execute(
                    """
                    INSERT INTO failure_cases (created_at, experiment_id, system_id, failure_type, payload)
                    VALUES (?,?,?,?,?)
                    """,
                    (
                        now,
                        record.experiment_id,
                        str(fc.get("system_id", "")),
                        str(fc.get("type", "unknown")),
                        json.dumps(fc, ensure_ascii=False),
                    ),
                )

            for sys_id, score in insight.ranking:
                c.execute(
                    """
                    INSERT INTO system_performance (created_at, system_id, score, experiment_id, domain)
                    VALUES (?,?,?,?,?)
                    """,
                    (now, sys_id, float(score), record.experiment_id, task.domain),
                )

            for h in insight.hypothesis_status:
                c.execute(
                    """
                    INSERT INTO hypothesis_results (created_at, hypothesis, status, evidence, experiment_id)
                    VALUES (?,?,?,?,?)
                    """,
                    (
                        now,
                        str(h.get("hypothesis", "")),
                        str(h.get("status", "")),
                        str(h.get("evidence", "")),
                        record.experiment_id,
                    ),
                )

            for line in insight.reasoning[:5]:
                c.execute(
                    """
                    INSERT INTO domain_insights (created_at, domain, insight, experiment_id)
                    VALUES (?,?,?,?)
                    """,
                    (now, task.domain, line, record.experiment_id),
                )

    def recent_failure_cases(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as c:
            rows = c.execute(
                "SELECT * FROM failure_cases ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def system_history(self, system_id: str, limit: int = 30) -> list[dict[str, Any]]:
        with self._connect() as c:
            rows = c.execute(
                "SELECT * FROM system_performance WHERE system_id = ? ORDER BY id DESC LIMIT ?",
                (system_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]
