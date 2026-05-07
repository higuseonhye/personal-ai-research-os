"""Deep research wrapper + end-to-end orchestration."""

from __future__ import annotations

import os
import re
from typing import Any

import requests
from openai import OpenAI

from research_os.planner import create_research_plan
from research_os.postprocess import structure_output
from research_os.settings import get_openai_client, get_model

# Optional: pip install tavily-python — we use raw HTTP if key present
REQUEST_TIMEOUT = 12


def _try_auto_deep_research(_plan: str) -> str | None:
    """Placeholder hook for future `auto-deep-research` style packages."""
    try:
        import importlib.util

        spec = importlib.util.find_spec("auto_deep_research")
        if spec is None:
            return None
        # If a known API appears later, wire it here without breaking imports.
    except Exception:
        return None
    return None


def _tavily_search(query: str, max_results: int = 5) -> str:
    key = os.environ.get("TAVILY_API_KEY", "").strip()
    if not key:
        return ""
    try:
        r = requests.post(
            "https://api.tavily.com/search",
            json={"api_key": key, "query": query, "max_results": max_results},
            timeout=REQUEST_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        lines: list[str] = ["### Tavily web results"]
        for item in (data.get("results") or [])[:max_results]:
            title = item.get("title", "")
            url = item.get("url", "")
            content = (item.get("content") or "")[:500]
            lines.append(f"- {title} | {url}\n  {content}")
        return "\n".join(lines)
    except Exception as exc:  # noqa: BLE001
        return f"(Tavily error: {exc})"


def _semantic_scholar_search(query: str, limit: int = 6) -> str:
    q = query[:280]
    lines: list[str] = ["### Semantic Scholar (paper search)"]
    try:
        r = requests.get(
            "https://api.semanticscholar.org/graph/v1/paper/search",
            params={"query": q, "limit": limit, "fields": "title,authors,year,url,abstract"},
            headers={"User-Agent": "PersonalAIResearchOS/1.0 (research demo)"},
            timeout=REQUEST_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        for p in (data.get("data") or [])[:limit]:
            title = p.get("title", "")
            year = p.get("year", "")
            url = p.get("url") or f"https://www.semanticscholar.org/paper/{p.get('paperId', '')}"
            abs_ = (p.get("abstract") or "")[:400]
            auth = p.get("authors") or []
            an = ", ".join(a.get("name", "") for a in auth[:3])
            lines.append(f"- {title} ({year}) — {an}\n  {url}\n  Abstract: {abs_}")
        if len(lines) == 1:
            lines.append("(no papers returned)")
    except Exception as exc:  # noqa: BLE001
        lines.append(f"(Semantic Scholar error: {exc})")
    return "\n".join(lines)


def _duckduckgo_instant_answer(query: str) -> str:
    lines: list[str] = ["### DuckDuckGo instant answer"]
    try:
        r = requests.get(
            "https://api.duckduckgo.com/",
            params={"q": query[:200], "format": "json", "no_html": 1, "skip_disambig": 1},
            timeout=REQUEST_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        if data.get("AbstractText"):
            lines.append(data["AbstractText"])
        for t in (data.get("RelatedTopics") or [])[:5]:
            if isinstance(t, dict) and t.get("Text"):
                lines.append(f"- {t['Text']}")
    except Exception as exc:  # noqa: BLE001
        lines.append(f"(DuckDuckGo error: {exc})")
    return "\n".join(lines)


def _synthesis_prompt(plan: str, evidence: str) -> str:
    return (
        "You are writing the research digest for engineers.\n"
        "Use the PLAN and EVIDENCE below. Synthesize: key themes, tensions, and actionable threads.\n"
        "Cite paper titles and URLs from evidence when present; do not invent URLs.\n"
        "If evidence is thin, say so and lean on established RAG/IR best practices.\n\n"
        f"--- PLAN ---\n{plan}\n\n--- EVIDENCE ---\n{evidence}\n"
    )


def run_deep_research(plan: str) -> str:
    """
    Search → summarize → combine. Tries optional packages; then Tavily; always uses
    Semantic Scholar + DuckDuckGo fallback; final pass is an LLM synthesis.
    """
    plan = (plan or "").strip()
    if not plan:
        return ""

    auto = _try_auto_deep_research(plan)
    if auto:
        return auto

    # Short query string for APIs: first sentence or first line of plan
    m = re.split(r"[\n\.]", plan, maxsplit=1)
    seed = (m[0] if m else plan)[:220]

    chunks: list[str] = []
    tav = _tavily_search(seed)
    if tav:
        chunks.append(tav)
    chunks.append(_semantic_scholar_search(seed))
    chunks.append(_duckduckgo_instant_answer(seed))
    evidence = "\n\n".join(chunks)

    client: OpenAI = get_openai_client()
    model = get_model()
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "Produce a dense research memo (plain text). No JSON. Max ~1200 words.",
            },
            {"role": "user", "content": _synthesis_prompt(plan, evidence)},
        ],
        temperature=0.35,
        max_tokens=2000,
    )
    memo = (resp.choices[0].message.content or "").strip()
    header = "=== Source bundle (for traceability) ===\n" + evidence[:8000] + "\n=== End sources ===\n\n"
    return header + memo


def run_research_pipeline(query: str) -> tuple[dict[str, Any], str]:
    """Returns (structured result, research plan text) for UI expanders."""
    plan = create_research_plan(query)
    raw = run_deep_research(plan)
    result = structure_output(raw)
    return result, plan


def research_os(query: str) -> dict[str, Any]:
    """Planner → deep research → structured sections (product contract)."""
    result, _plan = run_research_pipeline(query)
    return result
