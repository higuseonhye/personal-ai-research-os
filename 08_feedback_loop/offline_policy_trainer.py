"""
Offline routing-policy updates from `route_feedback.jsonl` + recent benchmark outcomes.

Composes `route_learning.nudge_thresholds_from_feedback` with small heuristic shifts when
assertion violations dominate the latest benchmark run (release-gate signal).
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]


def _load(rel: str, name: str):
    path = _ROOT / rel
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)
    return mod


def train_route_policy_from_signals(
    *,
    benchmark_db_path: Path | None = None,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    rl = _load("06_execution_agents/route_learning.py", "pa_route_learning_offline")
    assertions = _load("08_feedback_loop/benchmark_assertions.py", "pa_assert_offline")
    rl.nudge_thresholds_from_feedback()

    tid = (tenant_id if tenant_id is not None else os.environ.get("PA_TENANT_ID") or "default").strip()
    store = _load("08_feedback_loop/benchmark_backend.py", "pa_bb_offline").load_benchmark_store()
    dbp = benchmark_db_path if benchmark_db_path is not None else store.default_benchmark_db_path()

    policy = rl.load_route_policy()
    th = dict(policy.get("thresholds") or {})

    run = store.get_latest_finished_run(dbp, tenant_id=tid)
    if run:
        rows = store.fetch_results(int(run["run_id"]), db_path=dbp, tenant_id=tid)
        n = len(rows)
        if n:
            av = sum(1 for r in rows if str(r.get("failure_category") or "") == assertions.FAILURE_ASSERTION)
            ratio = av / n
            if ratio > 0.25:
                th["decomposition_min"] = float(min(0.88, float(th.get("decomposition_min", 0.6)) + 0.03))
                th["retrieval_min"] = float(min(0.85, float(th.get("retrieval_min", 0.5)) + 0.02))
            elif ratio == 0 and int(run.get("fail_count") or 0) == 0:
                th["decomposition_min"] = float(max(0.52, float(th.get("decomposition_min", 0.6)) - 0.01))

    policy["thresholds"] = th
    rl.save_route_policy(policy)
    return policy
