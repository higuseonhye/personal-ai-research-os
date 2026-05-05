#!/usr/bin/env python3
"""Nudge `04_sota_engine/sota_ranker.py` weights from the latest benchmark run (pass/fail by domain)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _domain_to_tag(domain: str) -> str:
    d = (domain or "").lower()
    if any(k in d for k in ("search", "rag", "retrieval", "wiki", "lexical", "hybrid")):
        return "retrieval"
    if "agent" in d or "automation" in d or "workflow" in d:
        return "agent"
    if "forecast" in d or "churn" in d or "recommend" in d:
        return "forecast"
    if "rank" in d:
        return "rank"
    if "llm" in d or "gen" in d:
        return "llm"
    return "other"


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply benchmark feedback to SOTA ranker tag weights")
    parser.add_argument("--db", type=Path, default=None)
    parser.add_argument("--tenant-id", default="", help="Also reads PA_TENANT_ID")
    args = parser.parse_args()

    if args.tenant_id.strip():
        os.environ["PA_TENANT_ID"] = args.tenant_id.strip()

    from importlib.util import module_from_spec, spec_from_file_location

    be_name = "pa_bb_ranker_fb"
    be = spec_from_file_location(be_name, ROOT / "08_feedback_loop" / "benchmark_backend.py")
    mbe = module_from_spec(be)
    sys.modules[be_name] = mbe
    assert be.loader
    be.loader.exec_module(mbe)
    store = mbe.load_benchmark_store()

    dbp = args.db
    if dbp is None and os.environ.get("PA_BENCHMARK_DB"):
        dbp = Path(os.environ["PA_BENCHMARK_DB"])
    dbp = dbp or store.default_benchmark_db_path()

    tid = (args.tenant_id.strip() or os.environ.get("PA_TENANT_ID") or "default").strip()
    run = store.get_latest_finished_run(dbp, tenant_id=tid)
    if not run:
        raise SystemExit("No finished benchmark runs for tenant/backend.")

    rows = store.fetch_results(int(run["run_id"]), db_path=dbp, tenant_id=tid)

    rk_name = "pa_sota_ranker_feedback"
    rk = spec_from_file_location(rk_name, ROOT / "04_sota_engine" / "sota_ranker.py")
    mrk = module_from_spec(rk)
    sys.modules[rk_name] = mrk
    assert rk.loader
    rk.loader.exec_module(mrk)

    updates = 0
    for r in rows:
        domain = str(r.get("domain") or "")
        tag = _domain_to_tag(domain)
        summ = r.get("summary")
        if isinstance(summ, str):
            try:
                summ = json.loads(summ)
            except json.JSONDecodeError:
                summ = {}
        elif not isinstance(summ, dict):
            summ = {}
        rid = str(r.get("datapoint_id") or summ.get("input_meta", {}).get("id") or domain or tag)
        ok = bool(r.get("ok"))
        ap = r.get("assertions_passed")
        passed_assert = True if ap is None else bool(ap)
        reward = 0.72 if ok and passed_assert else 0.28
        mrk.record_feedback(rid, tag, reward)
        updates += 1

    print(json.dumps({"updated_rows": updates, "run_id": run.get("run_id"), "tenant_id": tid}, indent=2))


if __name__ == "__main__":
    main()
