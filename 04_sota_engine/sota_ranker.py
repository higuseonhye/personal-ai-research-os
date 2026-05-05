"""
Adaptive SOTA relevance ranking (bandit-style; ready for policy-gradient / RL swap-in).

Combines cheap lexical features with learnable per-tag weights persisted on disk.
"""

from __future__ import annotations

import json
import math
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_STATE = _ROOT / "data" / "sota_ranker_state.json"


@dataclass
class RankerState:
    version: int = 1
    tag_weights: dict[str, float] = field(
        default_factory=lambda: {
            "retrieval": 1.0,
            "rag": 1.0,
            "agent": 1.0,
            "llm": 1.0,
            "rank": 1.0,
            "forecast": 1.0,
            "other": 1.0,
        }
    )
    global_step: int = 0
    learning_rate: float = 0.12


def _lexical_features(text: str) -> dict[str, float]:
    t = text.lower()
    tags = ("retrieval", "rag", "agent", "llm", "rank", "forecast", "tool", "reason")
    hits = {tag: 1.0 if tag in t else 0.0 for tag in tags}
    hits["length_norm"] = math.tanh(len(t) / 2000.0)
    return hits


def _primary_tag(text: str) -> str:
    t = text.lower()
    for tag in ("retrieval", "rag", "agent", "llm", "rank", "forecast"):
        if tag in t:
            return tag
    return "other"


def _load_state(path: Path | None = None) -> RankerState:
    p = path or _DEFAULT_STATE
    if not p.exists():
        return RankerState()
    raw = json.loads(p.read_text(encoding="utf-8"))
    return RankerState(
        version=int(raw.get("version", 1)),
        tag_weights=dict(raw.get("tag_weights", RankerState().tag_weights)),
        global_step=int(raw.get("global_step", 0)),
        learning_rate=float(raw.get("learning_rate", 0.12)),
    )


def _save_state(state: RankerState, path: Path | None = None) -> None:
    p = path or _DEFAULT_STATE
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(
            {
                "version": state.version,
                "tag_weights": state.tag_weights,
                "global_step": state.global_step,
                "learning_rate": state.learning_rate,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def score_paper_relevance(
    query: str,
    paper: dict[str, Any],
    *,
    structured: dict[str, Any] | None = None,
    state: RankerState | None = None,
) -> float:
    """
    Return [0,1] relevance score. Incorporates title/summary and optional structured fields.
    """
    st = state or _load_state()
    title = str(paper.get("title", "") or "")
    summary = str(paper.get("summary", "") or "")
    blob = f"{query}\n{title}\n{summary}"
    if structured:
        blob += "\n" + json.dumps(structured, ensure_ascii=False)[:2000]
    tag = _primary_tag(blob)
    w = float(st.tag_weights.get(tag, st.tag_weights.get("other", 1.0)))
    feats = _lexical_features(blob)
    base = 0.25 * feats["length_norm"]
    for k, v in feats.items():
        if k == "length_norm":
            continue
        base += 0.1 * v * w
    # light query-term overlap
    qtok = set(re.findall(r"\w+", query.lower())) - {"the", "a", "an", "or", "and", "of", "to", "in"}
    ttok = set(re.findall(r"\w+", title.lower()))
    if qtok:
        base += 0.35 * min(1.0, len(qtok & ttok) / max(1, len(qtok)))
    return float(max(0.0, min(1.0, base)))


def rank_papers(
    query: str,
    papers: list[dict[str, Any]],
    structured_list: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Return papers sorted by descending relevance, each with `_relevance_score` and `_paper_id`."""
    st = _load_state()
    out: list[dict[str, Any]] = []
    for i, p in enumerate(papers):
        sid = str(p.get("id") or p.get("paper_id") or uuid.uuid4())
        struct = None
        if structured_list and i < len(structured_list):
            struct = structured_list[i]
        s = score_paper_relevance(query, p, structured=struct, state=st)
        row = dict(p)
        row["_relevance_score"] = s
        row["_paper_id"] = sid
        out.append(row)
    out.sort(key=lambda r: float(r.get("_relevance_score", 0.0)), reverse=True)
    return out


def record_feedback(
    paper_id: str,
    tag: str,
    reward: float,
    *,
    state_path: Path | None = None,
) -> RankerState:
    """
    Bandit-style nudge: reward in [0,1] updates tag weight toward better actions.
    Swap this policy for an RL policy without changing the IO contract.
    """
    st = _load_state(state_path)
    st.global_step += 1
    tag = tag if tag in st.tag_weights else "other"
    r = max(0.0, min(1.0, float(reward)))
    w = st.tag_weights.get(tag, 1.0)
    w = w + st.learning_rate * (r - 0.5)
    st.tag_weights[tag] = float(max(0.1, min(3.0, w)))
    _save_state(st, state_path)
    return st
