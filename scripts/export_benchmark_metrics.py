#!/usr/bin/env python3
"""Emit Prometheus textfile metrics + optional Datadog push via `benchmark_metrics_export`.

Uses `BENCHMARK_BACKEND` (sqlite default, postgres optional) and `benchmark_backend.load_benchmark_store`.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> None:
    parser = argparse.ArgumentParser(description="Export benchmark metrics for Grafana/Datadog")
    parser.add_argument("--db", type=Path, default=None)
    parser.add_argument("--tenant-id", default="", help="PA_TENANT_ID scope for store reads")
    parser.add_argument("--prometheus-file", type=Path, default=ROOT / "data" / "benchmark_metrics.prom")
    parser.add_argument("--stdout", action="store_true", help="Print Prometheus text to stdout")
    parser.add_argument("--datadog-json", type=Path, default=None, help="Write Datadog series JSON payload")
    parser.add_argument("--push-datadog", action="store_true", help="POST series to Datadog (needs DD_API_KEY)")
    args = parser.parse_args()

    if args.tenant_id.strip():
        os.environ["PA_TENANT_ID"] = args.tenant_id.strip()

    from importlib.util import module_from_spec, spec_from_file_location

    exp_path = ROOT / "08_feedback_loop" / "benchmark_metrics_export.py"
    spec = spec_from_file_location("benchmark_metrics_export_cli", exp_path)
    mod = module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)

    db = args.db
    if db is None and os.environ.get("PA_BENCHMARK_DB"):
        db = Path(os.environ["PA_BENCHMARK_DB"])

    tid = args.tenant_id.strip() or None
    text = mod.export_latest_prometheus(db, tenant_id=tid)
    if args.stdout:
        print(text, end="")
    if args.prometheus_file:
        mod.write_textfile(text, args.prometheus_file)

    dd_payload = mod.export_latest_datadog_json(db, tenant_id=tid)
    if args.datadog_json:
        args.datadog_json.parent.mkdir(parents=True, exist_ok=True)
        args.datadog_json.write_text(json.dumps(dd_payload, indent=2), encoding="utf-8")

    if args.push_datadog:
        ok, msg = mod.push_datadog_series(dd_payload)
        print(json.dumps({"datadog_push_ok": ok, "detail": msg}, indent=2))


if __name__ == "__main__":
    main()
