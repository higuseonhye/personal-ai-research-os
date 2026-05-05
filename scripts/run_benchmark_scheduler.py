#!/usr/bin/env python3
"""
Schedule enterprise benchmark runs (dataset injection → pipeline → SQLite metrics).

Typical ops:
  # nightly
  python scripts/run_benchmark_scheduler.py --dataset data/enterprise_eval.jsonl --interval-sec 86400

  # once (cron/Task Scheduler friendly)
  python scripts/run_benchmark_scheduler.py --dataset %PA_BENCHMARK_DATASET% --once

Environment:
  PA_BENCHMARK_DATASET   fallback dataset path if --dataset omitted
  PA_BENCHMARK_DB        optional sqlite path (default data/benchmarks.sqlite3)
  PA_TENANT_ID           tenant scope for benchmark rows (SQLite / Postgres)
  BENCHMARK_BACKEND      sqlite | postgres (Postgres needs DATABASE_URL)
  DATABASE_URL           SQL connection string when backend=postgres
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _git_commit_short() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return (out.stdout or "").strip()
    except OSError:
        return ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Scheduled auto-benchmark runner")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=None,
        help="JSONL/CSV/JSON dataset path (defaults to PA_BENCHMARK_DATASET)",
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--mode",
        choices=("full", "langgraph", "production"),
        default="full",
        help="Which pipeline entrypoint to benchmark",
    )
    parser.add_argument("--interval-sec", type=int, default=86400)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--db", type=Path, default=None, help="SQLite DB path override")
    parser.add_argument("--notes", default="scheduler")
    args = parser.parse_args()

    ds = args.dataset or Path(os.environ.get("PA_BENCHMARK_DATASET", "") or "")
    if not str(ds):
        raise SystemExit("Provide --dataset or set PA_BENCHMARK_DATASET.")
    if not ds.exists():
        raise SystemExit(f"Dataset not found: {ds}")

    from importlib.util import module_from_spec, spec_from_file_location

    path = ROOT / "08_feedback_loop" / "auto_benchmark.py"
    spec = spec_from_file_location("auto_benchmark_scheduler", path)
    mod = module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)

    db_path = args.db
    if db_path is None and os.environ.get("PA_BENCHMARK_DB"):
        db_path = Path(os.environ["PA_BENCHMARK_DB"])

    while True:
        commit = _git_commit_short()
        tenant_raw = os.environ.get("PA_TENANT_ID", "").strip()
        meta = mod.run_auto_benchmark(
            ds,
            limit=args.limit,
            pipeline_mode=args.mode,
            persist_db=True,
            db_path=db_path,
            notes=f"{args.notes}; git={commit}",
            git_commit=commit or None,
            dataset_version=os.environ.get("PA_DATASET_VERSION"),
            tenant_id=tenant_raw or None,
        )
        print(
            time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "benchmark_run_id",
            meta.get("run_id"),
            "ok",
            meta.get("ok_count"),
            "fail",
            meta.get("fail_count"),
            flush=True,
        )
        if args.once:
            break
        time.sleep(max(60, int(args.interval_sec)))


if __name__ == "__main__":
    main()
