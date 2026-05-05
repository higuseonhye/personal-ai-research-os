"""Select SQLite vs Postgres benchmark persistence via BENCHMARK_BACKEND."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from types import ModuleType

_ROOT = Path(__file__).resolve().parents[1]


def load_benchmark_store() -> ModuleType:
    backend = os.environ.get("BENCHMARK_BACKEND", "sqlite").lower().strip()
    if backend == "postgres":
        path = _ROOT / "08_feedback_loop" / "benchmark_store_postgres.py"
        name = "pa_benchmark_store_pg"
    else:
        path = _ROOT / "08_feedback_loop" / "benchmark_store.py"
        name = "pa_benchmark_store_sqlite"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)
    return mod
