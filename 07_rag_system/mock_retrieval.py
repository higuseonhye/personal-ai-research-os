"""Mock corpus retrieval for papers (JSON records, no network)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_pipeline_path = _ROOT / "04_sota_engine" / "sota_retrieval.py"
_spec = importlib.util.spec_from_file_location("pa_sota_retrieval", _pipeline_path)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader
_spec.loader.exec_module(_mod)


def mock_retrieve_papers(query: str, *, top_k: int = 5) -> dict[str, Any]:
    decoy = {"technical_subproblems": [query], "raw_problem": query}
    ctx = _mod.retrieve_relevant_sota(decoy)
    papers = (ctx.get("papers") or [])[:top_k]
    return {"query": query, "top_k": str(top_k), "papers": papers, "source": "mock_static"}
