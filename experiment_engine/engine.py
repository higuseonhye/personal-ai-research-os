from __future__ import annotations

import hashlib
import json
import random
import time
import traceback
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from system_registry.base import AISystem, SystemOutput
from system_registry.registry import SystemRegistry


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


@dataclass
class ExperimentResult:
    system_id: str
    success: bool
    output: dict[str, Any] | None
    error: str | None = None
    latency_ms: float = 0.0


@dataclass
class ExperimentRecord:
    experiment_id: str
    created_at: str
    seed: int
    config_hash: str
    system_ids: list[str]
    input_snapshot: dict[str, Any]
    results: list[ExperimentResult]
    batch_index: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "created_at": self.created_at,
            "seed": self.seed,
            "config_hash": self.config_hash,
            "system_ids": self.system_ids,
            "input_snapshot": self.input_snapshot,
            "batch_index": self.batch_index,
            "results": [
                {
                    "system_id": r.system_id,
                    "success": r.success,
                    "output": r.output,
                    "error": r.error,
                    "latency_ms": r.latency_ms,
                }
                for r in self.results
            ],
        }


class ExperimentEngine:
    """Run controlled experiments across multiple AISystems with deterministic logging."""

    def __init__(self, registry: SystemRegistry, log_dir: str | Path | None = None) -> None:
        self.registry = registry
        base = Path(__file__).resolve().parents[1] / "data" / "logs"
        self.log_dir = Path(log_dir) if log_dir else base
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def _append_log(self, record: ExperimentRecord) -> Path:
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        path = self.log_dir / f"experiments_{day}.jsonl"
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
        return path

    def run_single(
        self,
        system_ids: list[str],
        input_dict: dict[str, Any],
        seed: int = 42,
        experiment_id: str | None = None,
        batch_index: int | None = None,
    ) -> ExperimentRecord:
        rng = random.Random(seed)
        rng.randint(0, 10**9)  # touch RNG so seed affects any future stochastic systems

        eid = experiment_id or str(uuid.uuid4())
        created = datetime.now(timezone.utc).isoformat()
        config_payload = {"system_ids": system_ids, "seed": seed, "input": input_dict}
        config_hash = _sha256(_canonical_json(config_payload))

        results: list[ExperimentResult] = []
        for sid in system_ids:
            sys: AISystem = self.registry.get(sid)
            t0 = time.perf_counter()
            try:
                out: SystemOutput = sys.run(input_dict)
                dt = (time.perf_counter() - t0) * 1000.0
                results.append(
                    ExperimentResult(
                        system_id=sid,
                        success=True,
                        output=out.to_dict(),
                        error=None,
                        latency_ms=dt,
                    )
                )
            except Exception as e:  # noqa: BLE001 — capture all for experiment log
                dt = (time.perf_counter() - t0) * 1000.0
                results.append(
                    ExperimentResult(
                        system_id=sid,
                        success=False,
                        output=None,
                        error=f"{e}\n{traceback.format_exc()}",
                        latency_ms=dt,
                    )
                )

        record = ExperimentRecord(
            experiment_id=eid,
            created_at=created,
            seed=seed,
            config_hash=config_hash,
            system_ids=list(system_ids),
            input_snapshot=input_dict,
            results=results,
            batch_index=batch_index,
        )
        self._append_log(record)
        return record

    def run_batch(
        self,
        system_ids: list[str],
        inputs: list[dict[str, Any]],
        base_seed: int = 42,
        experiment_group_id: str | None = None,
    ) -> list[ExperimentRecord]:
        gid = experiment_group_id or str(uuid.uuid4())
        records: list[ExperimentRecord] = []
        for i, inp in enumerate(inputs):
            seed = base_seed + i * 9973
            rec = self.run_single(system_ids, inp, seed=seed, experiment_id=f"{gid}:{i}", batch_index=i)
            records.append(rec)
        return records
