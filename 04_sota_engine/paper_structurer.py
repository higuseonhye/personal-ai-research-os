"""Structured extraction from paper abstracts / PDF-extracted text."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def extract_structure(paper_text: str) -> dict[str, str]:
    """Same schema as summarize_paper / PaperSummary (strings only)."""
    path = _ROOT / "04_sota_engine" / "paper_summarizer.py"
    spec = importlib.util.spec_from_file_location("pa_paper_summarizer", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)
    return mod.summarize_paper(paper_text)
