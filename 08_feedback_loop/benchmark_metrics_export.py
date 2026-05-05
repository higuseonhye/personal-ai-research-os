"""
Export benchmark SQLite metrics for Grafana (Prometheus textfile) and Datadog (series API).

Grafana Agent / node_exporter textfile collector:
  python scripts/export_benchmark_metrics.py --prometheus-file data/benchmark_metrics.prom

Datadog (optional live push):
  export DD_API_KEY=...  # and optionally DD_SITE=datadoghq.eu
  python scripts/export_benchmark_metrics.py --push-datadog
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]


def _sanitize_label(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def _finished_unix_ts(finished_at: str | None) -> int:
    if not finished_at:
        return int(datetime.now(timezone.utc).timestamp())
    s = str(finished_at).replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    except ValueError:
        return int(datetime.now(timezone.utc).timestamp())


def _avg_readiness(results: list[dict[str, Any]]) -> float | None:
    vals: list[float] = []
    for r in results:
        if not r.get("ok"):
            continue
        summary = r.get("summary") or {}
        summ = summary.get("summarize") or {}
        rs = summ.get("readiness_score")
        if rs is None:
            continue
        try:
            vals.append(float(str(rs).strip().replace("%", "")))
        except ValueError:
            continue
    if not vals:
        return None
    return sum(vals) / len(vals)


def build_prometheus_text(run: dict[str, Any], results: list[dict[str, Any]]) -> str:
    rid = str(run.get("run_id", ""))
    mode = _sanitize_label(str(run.get("pipeline_mode", "")))
    git = _sanitize_label(str(run.get("git_commit", "")))
    digest = _sanitize_label(str(run.get("dataset_digest", "")))
    dver = _sanitize_label(str(run.get("dataset_version", "")))
    dpath = _sanitize_label(str(run.get("dataset_path", "")))
    ts = _finished_unix_ts(run.get("finished_at"))

    ok = int(run.get("ok_count") or 0)
    fail = int(run.get("fail_count") or 0)
    total = ok + fail
    ratio = (ok / total) if total else 0.0

    readiness = _avg_readiness(results)

    lines = [
        "# HELP enterprise_benchmark_last_finished_unixtime Unix time (UTC) of last finished benchmark run.",
        "# TYPE enterprise_benchmark_last_finished_unixtime gauge",
        f'enterprise_benchmark_last_finished_unixtime{{run_id="{rid}",pipeline_mode="{mode}",git_commit="{git}",dataset_digest="{digest}",dataset_version="{dver}",dataset_path="{dpath}"}} {ts}',
        "# HELP enterprise_benchmark_run_ok_datapoints Datapoints succeeded in last finished run.",
        "# TYPE enterprise_benchmark_run_ok_datapoints gauge",
        f'enterprise_benchmark_run_ok_datapoints{{run_id="{rid}",pipeline_mode="{mode}",git_commit="{git}",dataset_digest="{digest}",dataset_version="{dver}"}} {ok}',
        "# HELP enterprise_benchmark_run_fail_datapoints Datapoints failed in last finished run.",
        "# TYPE enterprise_benchmark_run_fail_datapoints gauge",
        f'enterprise_benchmark_run_fail_datapoints{{run_id="{rid}",pipeline_mode="{mode}",git_commit="{git}",dataset_digest="{digest}",dataset_version="{dver}"}} {fail}',
        "# HELP enterprise_benchmark_run_success_ratio ok / (ok+fail) for last finished run.",
        "# TYPE enterprise_benchmark_run_success_ratio gauge",
        f'enterprise_benchmark_run_success_ratio{{run_id="{rid}",pipeline_mode="{mode}",git_commit="{git}",dataset_digest="{digest}",dataset_version="{dver}"}} {ratio:.6f}',
    ]
    if readiness is not None:
        lines.extend(
            [
                "# HELP enterprise_benchmark_avg_readiness_score Mean readiness_score across successful datapoints (when present).",
                "# TYPE enterprise_benchmark_avg_readiness_score gauge",
                f'enterprise_benchmark_avg_readiness_score{{run_id="{rid}",pipeline_mode="{mode}",git_commit="{git}",dataset_digest="{digest}",dataset_version="{dver}"}} {readiness:.6f}',
            ]
        )

    cat_counts = Counter(str(r.get("failure_category") or "unknown") for r in results)
    lines.append("# HELP enterprise_benchmark_last_run_failures_by_category Failures in last run by taxonomy bucket.")
    lines.append("# TYPE enterprise_benchmark_last_run_failures_by_category gauge")
    for cat, cnt in sorted(cat_counts.items()):
        cat_l = _sanitize_label(cat)
        lines.append(
            f'enterprise_benchmark_last_run_failures_by_category{{run_id="{rid}",pipeline_mode="{mode}",category="{cat_l}"}} {int(cnt)}'
        )

    return "\n".join(lines) + "\n"


def build_datadog_series(run: dict[str, Any], results: list[dict[str, Any]]) -> dict[str, Any]:
    """Datadog metrics API v1 `series` payload (`POST /api/v1/series`)."""
    ts = _finished_unix_ts(run.get("finished_at"))
    tags = [
        f"run_id:{run.get('run_id')}",
        f"pipeline_mode:{run.get('pipeline_mode')}",
        f"git_commit:{run.get('git_commit')}",
        f"dataset_digest:{run.get('dataset_digest')}",
        f"dataset_version:{run.get('dataset_version')}",
    ]

    def entry(metric: str, val: float) -> dict[str, Any]:
        return {"metric": metric, "points": [[ts, val]], "tags": tags}

    ok = float(run.get("ok_count") or 0)
    fail = float(run.get("fail_count") or 0)
    total = ok + fail
    ratio = (ok / total) if total else 0.0
    series = [
        entry("enterprise_benchmark.ok_count", ok),
        entry("enterprise_benchmark.fail_count", fail),
        entry("enterprise_benchmark.success_ratio", ratio),
    ]
    readiness = _avg_readiness(results)
    if readiness is not None:
        series.append(entry("enterprise_benchmark.avg_readiness_score", float(readiness)))

    cat_counts = Counter(str(r.get("failure_category") or "unknown") for r in results)
    for cat, cnt in cat_counts.items():
        tags_cat = tags + [f"failure_category:{cat}"]
        series.append(
            {
                "metric": "enterprise_benchmark.failures_by_category",
                "points": [[ts, float(cnt)]],
                "tags": tags_cat,
            }
        )
    return {"series": series}


def _load_store():
    import importlib.util

    p = _ROOT / "08_feedback_loop" / "benchmark_backend.py"
    spec = importlib.util.spec_from_file_location("benchmark_backend_exporter", p)
    be = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(be)
    return be.load_benchmark_store()


def export_latest_prometheus(db_path: Path | None = None, tenant_id: str | None = None) -> str:
    store = _load_store()
    run = store.get_latest_finished_run(db_path, tenant_id=tenant_id)
    if not run:
        return "# enterprise_benchmark: no finished runs yet.\n"
    rid = int(run["run_id"])
    results = store.fetch_results(rid, db_path=db_path, tenant_id=tenant_id)
    return build_prometheus_text(run, results)


def export_run_prometheus(run_id: int, db_path: Path | None = None, tenant_id: str | None = None) -> str:
    store = _load_store()
    run = store.get_run_by_id(run_id, db_path, tenant_id=tenant_id)
    if not run:
        return f"# enterprise_benchmark: unknown run_id={run_id}\n"
    if not run.get("finished_at"):
        return f"# enterprise_benchmark: run_id={run_id} not finished yet.\n"
    results = store.fetch_results(run_id, db_path=db_path, tenant_id=tenant_id)
    return build_prometheus_text(run, results)


def write_textfile(content: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def push_datadog_series(payload: dict[str, Any]) -> tuple[bool, str]:
    api_key = os.environ.get("DD_API_KEY", "").strip()
    if not api_key:
        return False, "DD_API_KEY not set"
    site = os.environ.get("DD_SITE", "datadoghq.com").strip()
    url = f"https://api.{site}/api/v1/series"
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "DD-API-KEY": api_key,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            code = getattr(resp, "status", None) or resp.getcode()
            resp.read()
        return True, f"posted:{code}"
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:2000]
        return False, f"http_error:{e.code}:{detail}"
    except urllib.error.URLError as e:
        return False, f"url_error:{e}"


def export_latest_datadog_json(db_path: Path | None = None, tenant_id: str | None = None) -> dict[str, Any]:
    store = _load_store()
    run = store.get_latest_finished_run(db_path, tenant_id=tenant_id)
    if not run:
        return {"series": []}
    rid = int(run["run_id"])
    results = store.fetch_results(rid, db_path=db_path, tenant_id=tenant_id)
    return build_datadog_series(run, results)
