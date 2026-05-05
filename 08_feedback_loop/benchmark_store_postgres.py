"""
Postgres persistence for benchmarks (optional). Set DATABASE_URL and BENCHMARK_BACKEND=postgres.

pip install "psycopg[binary]>=3.1"
"""

from __future__ import annotations

import hashlib
import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

_ROOT = Path(__file__).resolve().parents[1]


def default_benchmark_db_path() -> Path:
    return _ROOT / "data" / "benchmarks.sqlite3"


def digest_file(path: Path) -> str:
    if not path.exists():
        return ""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:24]


DDL_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS benchmark_runs (
        run_id BIGSERIAL PRIMARY KEY,
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
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS benchmark_results (
        id BIGSERIAL PRIMARY KEY,
        run_id BIGINT NOT NULL REFERENCES benchmark_runs(run_id) ON DELETE CASCADE,
        tenant_id TEXT NOT NULL DEFAULT 'default',
        datapoint_id TEXT,
        domain TEXT,
        ok INTEGER NOT NULL,
        failure_category TEXT DEFAULT '',
        assertions_passed INTEGER NOT NULL DEFAULT 1,
        error TEXT,
        summary_json TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_benchmark_results_run ON benchmark_results(run_id)",
]


def _require_psycopg():
    try:
        import psycopg  # noqa: F401
    except ImportError as e:  # pragma: no cover
        raise RuntimeError('Install Postgres driver: pip install "psycopg[binary]>=3.1"') from e


def _dsn() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL must be set when BENCHMARK_BACKEND=postgres")
    return url


@contextmanager
def connect(db_path: Path | None = None) -> Iterator[Any]:
    _require_psycopg()
    import psycopg
    import psycopg.rows

    conn = psycopg.connect(_dsn(), row_factory=psycopg.rows.dict_row)
    try:
        with conn.cursor() as cur:
            for stmt in DDL_STATEMENTS:
                cur.execute(stmt)
        conn.commit()
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
    _require_psycopg()
    started = datetime.now(timezone.utc).isoformat()
    digest = digest_file(dataset_path)
    tid = (tenant_id or os.environ.get("PA_TENANT_ID", "default") or "default").strip()
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO benchmark_runs (
                  tenant_id, started_at, finished_at, dataset_path, dataset_digest, dataset_version,
                  pipeline_mode, limit_n, git_commit, ok_count, fail_count, notes
                ) VALUES (%s, %s, NULL, %s, %s, %s, %s, %s, %s, 0, 0, %s)
                RETURNING run_id
                """,
                (
                    tid,
                    started,
                    str(dataset_path.resolve()),
                    digest,
                    dataset_version or "",
                    pipeline_mode,
                    limit_n,
                    git_commit or "",
                    notes or "",
                ),
            )
            rid = int(cur.fetchone()["run_id"])
        conn.commit()
        return rid


def finalize_run(
    run_id: int,
    *,
    ok_count: int,
    fail_count: int,
    db_path: Path | None = None,
) -> None:
    finished = datetime.now(timezone.utc).isoformat()
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE benchmark_runs
                SET finished_at = %s, ok_count = %s, fail_count = %s
                WHERE run_id = %s
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
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO benchmark_results (
                  run_id, tenant_id, datapoint_id, domain, ok, failure_category, assertions_passed, error, summary_json
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
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
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT run_id, tenant_id, started_at, finished_at, dataset_path, dataset_digest,
                       pipeline_mode, limit_n, git_commit, ok_count, fail_count, notes, dataset_version
                FROM benchmark_runs
                WHERE tenant_id = %s
                ORDER BY run_id DESC
                LIMIT %s
                """,
                (tid, limit),
            )
            return list(cur.fetchall())


def get_latest_finished_run(db_path: Path | None = None, tenant_id: str | None = None) -> dict[str, Any] | None:
    tid = (tenant_id or os.environ.get("PA_TENANT_ID", "default") or "default").strip()
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM benchmark_runs
                WHERE finished_at IS NOT NULL AND tenant_id = %s
                ORDER BY run_id DESC
                LIMIT 1
                """,
                (tid,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def get_run_by_id(run_id: int, db_path: Path | None = None, tenant_id: str | None = None) -> dict[str, Any] | None:
    tid = (tenant_id or os.environ.get("PA_TENANT_ID", "default") or "default").strip()
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM benchmark_runs WHERE run_id = %s AND tenant_id = %s",
                (run_id, tid),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def fetch_results(run_id: int, db_path: Path | None = None, tenant_id: str | None = None) -> list[dict[str, Any]]:
    tid = (tenant_id or os.environ.get("PA_TENANT_ID", "default") or "default").strip()
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, datapoint_id, domain, ok, failure_category, assertions_passed, error, summary_json
                FROM benchmark_results
                WHERE run_id = %s AND tenant_id = %s
                ORDER BY id ASC
                """,
                (run_id, tid),
            )
            rows = cur.fetchall()
            out: list[dict[str, Any]] = []
            for r in rows:
                d = dict(r)
                try:
                    d["summary"] = json.loads(d.pop("summary_json"))
                except json.JSONDecodeError:
                    d["summary"] = {}
                out.append(d)
            return out
