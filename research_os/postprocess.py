"""Map free-form research text into the product's fixed JSON shape (LLM)."""

from __future__ import annotations

import json
import re
from typing import Any

from openai import OpenAI

from research_os.settings import get_openai_client, get_model


def _fallback_structure(raw_text: str) -> dict[str, Any]:
    """If JSON parsing fails, return a minimal usable structure."""
    snippet = (raw_text or "").strip()[:2000]
    return {
        "problem": "Structured parse failed; showing raw digest excerpt below in UI.",
        "papers": [],
        "insights": [snippet[:800] + ("…" if len(snippet) > 800 else "")],
        "ideas": ["Re-run with a shorter query or check OPENAI_API_KEY permissions."],
        "experiments": [],
    }


def structure_output(raw_text: str) -> dict[str, Any]:
    """
    Return EXACT keys: problem, papers, insights, ideas, experiments.
    Lists must contain non-empty strings where possible.
    """
    raw_text = (raw_text or "").strip()
    if not raw_text:
        return {
            "problem": "No research output was produced.",
            "papers": [],
            "insights": [],
            "ideas": [],
            "experiments": [],
        }

    client: OpenAI = get_openai_client()
    model = get_model()

    system = (
        "You extract structured research summaries. Output ONLY valid JSON, no markdown fences, "
        'with keys exactly: "problem" (string), "papers" (array of strings — titles or "Title — URL"), '
        '"insights" (array of strings), "ideas" (array of strings, novel angles), '
        '"experiments" (array of strings, concrete steps). '
        "Use at least 3 papers entries if the source text mentions any sources; otherwise infer well-known "
        "paper titles/topics from the domain. At least 2 ideas and 2 experiments when the text allows."
    )

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": raw_text[:24000]},
        ],
        temperature=0.3,
        max_tokens=1800,
        response_format={"type": "json_object"},
    )

    text = (resp.choices[0].message.content or "").strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            try:
                data = json.loads(m.group(0))
            except json.JSONDecodeError:
                return _fallback_structure(raw_text)
        else:
            return _fallback_structure(raw_text)

    def _list_str(key: str, min_n: int = 0) -> list[str]:
        v = data.get(key)
        if not isinstance(v, list):
            return []
        out = [str(x).strip() for x in v if str(x).strip()]
        return out

    out = {
        "problem": str(data.get("problem", "")).strip() or "Problem not stated.",
        "papers": _list_str("papers"),
        "insights": _list_str("insights"),
        "ideas": _list_str("ideas"),
        "experiments": _list_str("experiments"),
    }

    # Light validation: ensure lists look useful
    if len(out["ideas"]) < 2 and out["insights"]:
        out["ideas"].append("Combine the strongest insight with a small offline human eval of retrieval cases.")
    if len(out["experiments"]) < 2 and out["insights"]:
        out["experiments"].append("A/B retriever configuration on a fixed 200-query set with labeled relevance.")

    return out
