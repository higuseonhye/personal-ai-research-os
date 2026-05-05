"""Fetch recent arXiv papers for SOTA ingestion."""

from __future__ import annotations

try:
    import arxiv  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - optional env
    arxiv = None  # type: ignore[assignment]

_ARXIV_AVAILABLE = arxiv is not None


def client_available() -> bool:
    """True when the PyPI `arxiv` package is installed."""
    return _ARXIV_AVAILABLE


def fetch_recent_papers(query: str, max_results: int = 20) -> list[dict[str, str]]:
    """Returns [] if the `arxiv` PyPI package is not installed (`pip install arxiv`)."""
    if not _ARXIV_AVAILABLE:
        return []

    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate,
    )
    client = arxiv.Client()
    papers: list[dict[str, str]] = []
    for result in client.results(search):
        papers.append(
            {
                "title": result.title.replace("\n", " ").strip(),
                "summary": result.summary.replace("\n", " ").strip(),
                "pdf_url": str(result.pdf_url),
            }
        )
    return papers
