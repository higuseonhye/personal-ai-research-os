"""Periodic arXiv → structure → embeddings → leaderboard hooks."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _load(mod_rel: str, name: str):
    path = _ROOT / mod_rel
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)
    return mod


_arxiv_mod = _load("04_sota_engine/arxiv_ingestor.py", "pa_arxiv_ingestor")
_struct_mod = _load("04_sota_engine/paper_structurer.py", "pa_paper_structurer")
_emb_mod = _load("07_rag_system/embedding_store.py", "pa_embedding_store")
_lb_mod = _load("04_sota_engine/leaderboard.py", "pa_leaderboard")

fetch_recent_papers = _arxiv_mod.fetch_recent_papers
extract_structure = _struct_mod.extract_structure


def run_sota_update_cycle(
    query: str = "retrieval augmented generation OR agent OR llm",
    *,
    max_results: int = 20,
) -> dict[str, int | str]:
    papers = fetch_recent_papers(query, max_results=max_results)
    embedding_store = _emb_mod.get_default_embedding_store()
    leaderboard = _lb_mod.get_default_leaderboard()
    indexed = 0
    for paper in papers:
        structured = extract_structure(paper["summary"])
        embedding_store.add(
            text=paper["summary"],
            metadata={
                "title": paper["title"],
                "pdf_url": paper["pdf_url"],
                **structured,
            },
        )
        task_key = str(structured.get("problem", ""))[:512] or paper["title"][:256]
        model_key = str(structured.get("method", ""))[:256] or "unknown_method"
        leaderboard.update(task=task_key, model=model_key, score=0.0)
        indexed += 1
    return {"indexed": indexed, "query": query}
