"""
Persisted routing thresholds + outcome logging for DAG decisions (RL-ready).

Replace static thresholds in `route_decision` with blended values from `data/route_policy.json`.
Append outcomes to `data/route_feedback.jsonl` for offline policy improvement.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = _ROOT / "data" / "route_policy.json"
FEEDBACK_PATH = _ROOT / "data" / "route_feedback.jsonl"

DEFAULT_POLICY = {
    "version": 1,
    "thresholds": {
        "decomposition_min": 0.6,
        "retrieval_min": 0.5,
        "eval_min": 0.7,
        "max_iterations": 3,
    },
    "blend": 1.0,
}


def load_route_policy() -> dict[str, Any]:
    if not POLICY_PATH.exists():
        return dict(DEFAULT_POLICY)
    raw = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    merged = dict(DEFAULT_POLICY)
    merged.update(raw)
    if "thresholds" in raw:
        merged["thresholds"] = {**DEFAULT_POLICY["thresholds"], **raw["thresholds"]}
    return merged


def save_route_policy(policy: dict[str, Any]) -> None:
    POLICY_PATH.parent.mkdir(parents=True, exist_ok=True)
    POLICY_PATH.write_text(json.dumps(policy, indent=2), encoding="utf-8")


def log_route_outcome(entry: dict[str, Any]) -> None:
    FEEDBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": datetime.now(timezone.utc).isoformat(), **entry}
    with FEEDBACK_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def nudge_thresholds_from_feedback(
    *,
    learning_rate: float = 0.02,
    success_bonus: float = 0.01,
) -> dict[str, Any]:
    """
    Tiny heuristic nudge: if recent outcomes show frequent finalize with low eval_score,
    loosen eval threshold slightly — placeholder for proper RL / contextual bandits.
    """
    policy = load_route_policy()
    th = dict(policy.get("thresholds", DEFAULT_POLICY["thresholds"]))
    if FEEDBACK_PATH.exists():
        lines = FEEDBACK_PATH.read_text(encoding="utf-8").splitlines()[-200:]
        lows = 0
        finals = 0
        for line in lines:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("route") == "finalize":
                finals += 1
                try:
                    es = float(obj.get("eval_score", 1.0))
                    if es < th.get("eval_min", 0.7):
                        lows += 1
                except (TypeError, ValueError):
                    pass
        if finals >= 8 and lows / max(1, finals) > 0.6:
            th["eval_min"] = float(max(0.55, th.get("eval_min", 0.7) - learning_rate))
            policy["thresholds"] = th
            save_route_policy(policy)
    return policy
