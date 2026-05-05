#!/usr/bin/env python3
"""Refresh `data/route_policy.json` using route_feedback.jsonl + latest benchmark assertion rates."""

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
    parser = argparse.ArgumentParser(description="Offline route_policy trainer")
    parser.add_argument("--db", type=Path, default=None, help="SQLite benchmark DB (SQLite backend only)")
    parser.add_argument("--tenant-id", default="", help="Tenant scope (also PA_TENANT_ID)")
    args = parser.parse_args()

    if args.tenant_id.strip():
        os.environ["PA_TENANT_ID"] = args.tenant_id.strip()

    from importlib.util import module_from_spec, spec_from_file_location

    spec = spec_from_file_location(
        "offline_policy_trainer_cli",
        ROOT / "08_feedback_loop" / "offline_policy_trainer.py",
    )
    mod = module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)

    policy = mod.train_route_policy_from_signals(benchmark_db_path=args.db, tenant_id=args.tenant_id.strip() or None)
    print(json.dumps({"saved": True, "thresholds": policy.get("thresholds")}, indent=2))


if __name__ == "__main__":
    main()
