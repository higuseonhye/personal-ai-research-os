"""SQLite persistence for scheduled enterprise benchmarks (upgrade path to Postgres via benchmark_backend)."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

_ROOT = Path(__file__).resolve().parents[1]


def default_benchmark_db_path() -> Path:
    return _ROOT / "data" / "benchmarks.sqlite3"


SCHEMA = """
CREATE TABLE IF NOT EXISTS benchmark_runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL DEFAULT 'default',
    started_at TEXT NOT NULL,
    finished_at TEXT,
    dataset_path TEXT NOT NULL,
    dataset_digest TEXT,
    dataset_version TEXT DEFAULT '',
    pipeline_mode TEXT NOT NULL,
    limit_n INTEGER,
    git_commit TEXT,
    ok_count INTEGER NOT NULL DEFAULT 0,
    fail_count INTEGER NOT NULL DEFAULT 0,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS benchmark_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    tenant_id TEXT NOT NULL DEFAULT 'default',
    datapoint_id TEXT,
    domain TEXT,
    ok INTEGER NOT NULL,
    failure_category TEXT DEFAULT '',
    assertions_passed INTEGER NOT NULL DEFAULT 1,
    error TEXT,
    summary_json TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES benchmark_runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_benchmark_results_run_id ON benchmark_results(run_id);
"""


def digest_file(path: Path) -> str:
    if not path.exists():
        return ""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:24]


def _migrate(conn: sqlite3.Connection) -> None:
    def cols(table: str) -> set[str]:
        return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}

    rcols = cols("benchmark_runs")
    if "dataset_version" not in rcols:
        conn.execute("ALTER TABLE benchmark_runs ADD COLUMN dataset_version TEXT DEFAULT ''")
    if "tenant_id" not in rcols:
        conn.execute("ALTER TABLE benchmark_runs ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'default'")

    xcols = cols("benchmark_results")
    if "tenant_id" not in xcols:
        conn.execute("ALTER TABLE benchmark_results ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'default'")
    if "failure_category" not in xcols:
        conn.execute("ALTER TABLE benchmark_results ADD COLUMN failure_category TEXT DEFAULT ''")
    if "assertions_passed" not in xcols:
        conn.execute("ALTER TABLE benchmark_results ADD COLUMN assertions_passed INTEGER NOT NULL DEFAULT 1")

    conn.execute("UPDATE benchmark_runs SET tenant_id = 'default' WHERE tenant_id IS NULL OR tenant_id = ''")
    conn.execute("UPDATE benchmark_results SET tenant_id = 'default' WHERE tenant_id IS NULL OR tenant_id = ''")
    conn.commit()


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()
    _migrate(conn)


@contextmanager
def connect(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    p = db_path or default_benchmark_db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p))
    conn.row_factory = sqlite3.Row
    try:
        init_schema(conn)
        yield conn
    finally:
        conn.close()


def create_run(
    *,
    dataset_path: Path,
    pipeline_mode: str,
    limit_n: int | None,
    git_commit: str | None,
    notes: str | None,
    dataset_version: str | None = None,
    tenant_id: str | None = None,
    db_path: Path | None = None,
) -> int:
    started = datetime.now(timezone.utc).isoformat()
    digest = digest_file(dataset_path)
    tid = (tenant_id or os.environ.get("PA_TENANT_ID", "default") or "default").strip()
    with connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO benchmark_runs (
              tenant_id, started_at, finished_at, dataset_path, dataset_digest,
              pipeline_mode, limit_n, git_commit, ok_count, fail_count, notes,
              dataset_version
            ) VALUES (?, ?, NULL, ?, ?, ?, ?, ?, 0, 0, ?, ?)
            """,
            (
                tid,
                started,
                str(dataset_path.resolve()),
                digest,
                pipeline_mode,
                limit_n,
                git_commit or "",
                notes or "",
                dataset_version or "",
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def finalize_run(
    run_id: int,
    *,
    ok_count: int,
    fail_count: int,
    db_path: Path | None = None,
) -> None:
    finished = datetime.now(timezone.utc).isoformat()
    with connect(db_path) as conn:
        conn.execute(
            """
            UPDATE benchmark_runs
            SET finished_at = ?, ok_count = ?, fail_count = ?
            WHERE run_id = ?
            """,
            (finished, ok_count, fail_count, run_id),
        )
        conn.commit()


def insert_result(
    run_id: int,
    *,
    datapoint_id: str | None,
    domain: str | None,
    ok: bool,
    error: str | None,
    summary: dict[str, Any],
    failure_category: str | None = None,
    assertions_passed: bool | None = None,
    tenant_id: str | None = None,
    db_path: Path | None = None,
) -> None:
    tid = (tenant_id or os.environ.get("PA_TENANT_ID", "default") or "default").strip()
    fc = failure_category or ""
    ap = 1 if (assertions_passed if assertions_passed is not None else True) else 0
    payload = json.dumps(summary, ensure_ascii=False)
    if len(payload) > 120_000:
        payload = json.dumps({"truncated": True, "preview": payload[:80_000]}, ensure_ascii=False)
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO benchmark_results (
              run_id, tenant_id, datapoint_id, domain, ok, failure_category, assertions_passed, error, summary_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                tid,
                datapoint_id or "",
                domain or "",
                1 if ok else 0,
                fc,
                ap,
                error or "",
                payload,
            ),
        )
        conn.commit()


def list_recent_runs(limit: int = 50, db_path: Path | None = None, tenant_id: str | None = None) -> list[dict[str, Any]]:
    tid = (tenant_id or os.environ.get("PA_TENANT_ID", "default") or "default").strip()
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT run_id, tenant_id, started_at, finished_at, dataset_path, dataset_digest,
                   pipeline_mode, limit_n, git_commit, ok_count, fail_count, notes,
                   dataset_version
            FROM benchmark_runs
            WHERE COALESCE(NULLIF(TRIM(tenant_id), ''), 'default') = ?
            ORDER BY run_id DESC
            LIMIT ?
            """,
            (tid, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def get_latest_finished_run(db_path: Path | None = None, tenant_id: str | None = None) -> dict[str, Any] | None:
    tid = (tenant_id or os.environ.get("PA_TENANT_ID", "default") or "default").strip()
    with connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT *
            FROM benchmark_runs
            WHERE finished_at IS NOT NULL
              AND COALESCE(NULLIF(TRIM(tenant_id), ''), 'default') = ?
            ORDER BY run_id DESC
            LIMIT 1
            """,
            (tid,),
        ).fetchone()
        return dict(row) if row else None


def get_run_by_id(run_id: int, db_path: Path | None = None, tenant_id: str | None = None) -> dict[str, Any] | None:
    tid = (tenant_id or os.environ.get("PA_TENANT_ID", "default") or "default").strip()
    with connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT * FROM benchmark_runs
            WHERE run_id = ? AND COALESCE(NULLIF(TRIM(tenant_id), ''), 'default') = ?
            """,
            (run_id, tid),
        ).fetchone()
        return dict(row) if row else None


def fetch_results(run_id: int, db_path: Path | None = None, tenant_id: str | None = None) -> list[dict[str, Any]]:
    tid = (tenant_id or os.environ.get("PA_TENANT_ID", "default") or "default").strip()
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, datapoint_id, domain, ok, failure_category, assertions_passed, error, summary_json
            FROM benchmark_results
            WHERE run_id = ? AND COALESCE(NULLIF(TRIM(tenant_id), ''), 'default') = ?
            ORDER BY id ASC
            """,
            (run_id, tid),
        ).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            d = dict(r)
            try:
                d["summary"] = json.loads(d.pop("summary_json"))
            except json.JSONDecodeError:
                d["summary"] = {}
            out.append(d)
        return out
