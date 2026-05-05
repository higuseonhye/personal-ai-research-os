"""Structured paper summarization (arXiv PDF text or plain research text)."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from shared.llm_client import json_llm_complete_dict
from shared.schemas import PaperSummary


def _fallback_from_text(paper_text: str) -> dict[str, Any]:
    t = paper_text.strip()
    title = ""
    m = re.search(r"(?im)^title:\s*(.+)$", t)
    if m:
        title = m.group(1).strip()
    abstract = ""
    m = re.search(r"(?is)abstract[.\s]*(.{0,1200}?)(?:\n\n|introduction|1\.?\s+introduction)", t)
    if m:
        abstract = m.group(1).strip().replace("\n", " ")
    snippet = (abstract or t)[:800]
    return {
        "problem": snippet[:400] if snippet else "Not stated in excerpt.",
        "method": "Identify core algorithmic approach from methodology section.",
        "architecture": "Map model blocks, training objectives, and inference pipeline from the text.",
        "dataset": "Extract dataset names, splits, and preprocessing from experiments.",
        "metrics": "List primary metrics reported in results tables.",
        "key_innovation": title or "No explicit title line found; infer novelty from abstract.",
        "limitations": "Collect limitations / failure cases if stated; otherwise note evaluation gaps.",
    }


def summarize_paper(paper_text: str) -> dict[str, Any]:
    """
    Produce exactly the PaperSummary schema fields (strings only; no extra keys).
    """
    system = (
        "You extract structured research metadata. Return ONLY a JSON object with keys: "
        "problem, method, architecture, dataset, metrics, key_innovation, limitations. "
        "Every value must be a single string (use semicolons to combine multiple items). "
        "No markdown, no prose outside JSON."
    )
    user = f"Paper text:\n{paper_text[:120_000]}"
    fb = _fallback_from_text(paper_text)
    return json_llm_complete_dict(system, user, PaperSummary, fallback_builder=fb)
