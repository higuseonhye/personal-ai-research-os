"""Batch benchmark runner with assertions, failure taxonomy, and pluggable persistence (SQLite/Postgres)."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _load(rel: str, name: str):
    path = _ROOT / rel
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)
    return mod


def _load_benchmark_store():
    mod = _load("08_feedback_loop/benchmark_backend.py", "pa_benchmark_backend")
    return mod.load_benchmark_store()


def _load_assertions():
    return _load("08_feedback_loop/benchmark_assertions.py", "pa_benchmark_assert")


def _runner_for_mode(mode: str) -> Callable[[str], dict[str, Any]]:
    pipe = _load("pipeline.py", "pa_pipeline_auto")
    if mode == "full":
        return pipe.run_full_pipeline
    if mode == "langgraph":
        return pipe.run_system
    if mode == "production":
        return pipe.run_production_system
    raise ValueError(f"Unknown pipeline_mode={mode}")


def _summarize_ok(result: dict[str, Any]) -> dict[str, Any]:
    dec = result.get("decomposition") or {}
    subs = dec.get("technical_subproblems") or dec.get("subproblems")
    arch = result.get("architecture") or {}
    ev = result.get("evaluation") or {}
    readiness = ev.get("readiness_score")
    if readiness is None and isinstance(ev.get("_legacy"), dict):
        readiness = ev["_legacy"].get("readiness_score")
    iteration = result.get("iteration") or {}
    return {
        "pipeline_keys": list(result.keys()),
        "subproblem_count": len(subs or []) if isinstance(subs, list) else None,
        "architecture_components": len(arch.get("components") or []) if isinstance(arch, dict) else None,
        "readiness_score": readiness,
        "iteration_keys": list(iteration.keys()) if isinstance(iteration, dict) else [],
    }


def run_auto_benchmark(
    dataset_path: Path,
    *,
    limit: int | None = None,
    runner: Callable[[str], dict[str, Any]] | None = None,
    output_path: Path | None = None,
    pipeline_mode: str = "full",
    persist_db: bool = True,
    db_path: Path | None = None,
    git_commit: str | None = None,
    dataset_version: str | None = None,
    notes: str | None = None,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    inj = _load("08_feedback_loop/dataset_injection.py", "pa_dataset_inj")
    ba = _load_assertions()
    bench_store = _load_benchmark_store()

    rows_in = inj.load_dataset(dataset_path)
    run_fn = runner or _runner_for_mode(pipeline_mode)
    dset_version = (dataset_version if dataset_version is not None else os.environ.get("PA_DATASET_VERSION", "") or "").strip()
    tid = (tenant_id if tenant_id is not None else os.environ.get("PA_TENANT_ID", "default") or "default").strip()

    effective_db: Path | None = None
    run_id: int | None = None
    if persist_db:
        effective_db = db_path or bench_store.default_benchmark_db_path()
        run_id = bench_store.create_run(
            dataset_path=dataset_path,
            pipeline_mode=pipeline_mode,
            limit_n=limit,
            git_commit=git_commit,
            dataset_version=dset_version or None,
            notes=notes,
            tenant_id=tid,
            db_path=effective_db,
        )

    out_rows: list[dict[str, Any]] = []
    ok_count = 0
    fail_count = 0

    try:
        for i, row in enumerate(rows_in):
            if limit is not None and i >= limit:
                break
            prob = str(row.get("enterprise_problem", "")).strip()
            if not prob:
                fail_count += 1
                wrapped = {
                    "input_meta": {"id": row.get("id"), "domain": row.get("domain")},
                    "ok": False,
                    "failure_category": ba.FAILURE_MISSING_FIELD,
                    "pipeline_ok": False,
                    "assertions_passed": False,
                    "error": "missing enterprise_problem",
                }
                out_rows.append(wrapped)
                if run_id is not None and effective_db is not None:
                    bench_store.insert_result(
                        run_id,
                        datapoint_id=str(row.get("id") or ""),
                        domain=str(row.get("domain") or ""),
                        ok=False,
                        error="missing enterprise_problem",
                        summary=wrapped,
                        failure_category=ba.FAILURE_MISSING_FIELD,
                        assertions_passed=False,
                        tenant_id=tid,
                        db_path=effective_db,
                    )
                continue

            datapoint_id = str(row.get("id", "") or "")
            domain = str(row.get("domain", "") or "")
            pipeline_ok = False
            assertions_passed = True
            failure_category = ba.FAILURE_NONE
            err: str | None = None
            result: dict[str, Any] | None = None

            try:
                result = run_fn(prob)
                pipeline_ok = True
            except Exception as e:  # noqa: BLE001
                err = str(e)
                failure_category = ba.classify_exception(e)

            assertion_report: dict[str, Any] | None = None
            if pipeline_ok and result is not None:
                assertion_report = ba.run_assertions(row, result)
                assertions_passed = bool(assertion_report.get("passed"))
                if not assertions_passed:
                    failure_category = ba.FAILURE_ASSERTION

            overall_pass = pipeline_ok and assertions_passed
            if overall_pass:
                ok_count += 1
            else:
                fail_count += 1

            summary: dict[str, Any]
            if pipeline_ok and result is not None:
                summary = {
                    "id": row.get("id"),
                    "pipeline_ok": True,
                    "assertions_passed": assertions_passed,
                    "assertion_report": assertion_report,
                    "summarize": _summarize_ok(result),
                }
            else:
                summary = {
                    "id": row.get("id"),
                    "pipeline_ok": False,
                    "assertions_passed": False,
                    "error": err,
                }

            wrapped = {
                "input_meta": {"id": row.get("id"), "domain": row.get("domain")},
                "ok": overall_pass,
                "failure_category": failure_category,
                **summary,
            }
            out_rows.append(wrapped)

            if run_id is not None and effective_db is not None:
                bench_store.insert_result(
                    run_id,
                    datapoint_id=datapoint_id or None,
                    domain=domain or None,
                    ok=overall_pass,
                    error=err,
                    summary=wrapped,
                    failure_category=failure_category,
                    assertions_passed=assertions_passed,
                    tenant_id=tid,
                    db_path=effective_db,
                )

        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with output_path.open("w", encoding="utf-8") as f:
                for r in out_rows:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
    finally:
        if run_id is not None and effective_db is not None:
            bench_store.finalize_run(run_id, ok_count=ok_count, fail_count=fail_count, db_path=effective_db)

    return {
        "run_id": run_id,
        "ok_count": ok_count,
        "fail_count": fail_count,
        "rows": out_rows,
        "db_path": str(effective_db) if effective_db else "",
        "tenant_id": tid,
    }


def _git_commit_short() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(_ROOT),
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return (out.stdout or "").strip()
    except OSError:
        return ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Auto-benchmark enterprise dataset against pipeline")
    parser.add_argument("dataset", type=Path, help="Path to JSONL/CSV dataset")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--mode", choices=("full", "langgraph", "production"), default="full")
    parser.add_argument("--db", type=Path, default=None, help="SQLite path (defaults to data/benchmarks.sqlite3)")
    parser.add_argument("--no-db", action="store_true", help="Skip DB persistence")
    parser.add_argument("--notes", default="cli")
    parser.add_argument(
        "--dataset-version",
        default="",
        help="Logical dataset version tag (also reads PA_DATASET_VERSION).",
    )
    parser.add_argument("--tenant-id", default="", help="Tenant id (also reads PA_TENANT_ID).")
    args = parser.parse_args()

    if args.tenant_id.strip():
        os.environ["PA_TENANT_ID"] = args.tenant_id.strip()

    outp = args.dataset.parent / f"{args.dataset.stem}_benchmark_results.jsonl"
    if args.out is not None:
        outp = args.out
    meta = run_auto_benchmark(
        args.dataset,
        limit=args.limit,
        output_path=outp,
        pipeline_mode=args.mode,
        persist_db=not args.no_db,
        db_path=args.db,
        git_commit=_git_commit_short() or None,
        dataset_version=(args.dataset_version or os.environ.get("PA_DATASET_VERSION", "") or None),
        notes=args.notes,
        tenant_id=args.tenant_id.strip() or None,
    )
    print(
        json.dumps(
            {
                "written": len(meta.get("rows") or []),
                "output": str(outp),
                "run_id": meta.get("run_id"),
                "db_path": meta.get("db_path"),
                "tenant_id": meta.get("tenant_id"),
                "ok": meta.get("ok_count"),
                "fail": meta.get("fail_count"),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
