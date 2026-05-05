#!/usr/bin/env python3
"""
Long-running arXiv sync worker (hourly by default). Safe for systemd / Task Scheduler.

Usage:
  python scripts/arxiv_hourly_worker.py --interval-sec 3600 --max-results 25
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> None:
    parser = argparse.ArgumentParser(description="Hourly-style arXiv → embeddings → radar snapshots")
    parser.add_argument("--interval-sec", type=int, default=3600)
    parser.add_argument("--max-results", type=int, default=25)
    parser.add_argument(
        "--query",
        default="retrieval augmented generation OR agent OR llm OR ranking OR forecasting",
    )
    parser.add_argument("--once", action="store_true", help="Run a single cycle then exit")
    args = parser.parse_args()

    from importlib.util import module_from_spec, spec_from_file_location

    path = ROOT / "09_apps" / "radar_pipeline.py"
    spec = spec_from_file_location("radar_pipeline_worker", path)
    mod = module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)

    while True:
        try:
            out = mod.run_radar_single_cycle(query=args.query, max_results=args.max_results)
            print(time.strftime("%Y-%m-%dT%H:%M:%SZ"), "indexed", out.get("indexed"), flush=True)
        except Exception as e:  # noqa: BLE001
            print("cycle_error", e, flush=True)
        if args.once:
            break
        time.sleep(max(30, int(args.interval_sec)))


if __name__ == "__main__":
    main()
