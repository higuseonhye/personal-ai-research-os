from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from typing import Any

_TOKEN = re.compile(r"\w+", re.UNICODE)


def _tok(s: str) -> set[str]:
    return set(t.lower() for t in _TOKEN.findall(s or ""))


@dataclass
class LLMJudgeConfig:
    """Local-first judge; no network calls."""

    reference: str | None = None
    seed: str = "local"


def _bounded(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def llm_judge_scores(
    candidate_text: str,
    query: str | None = None,
    reference: str | None = None,
    config: LLMJudgeConfig | None = None,
) -> dict[str, float]:
    """
    System-agnostic local 'LLM judge' proxy using lexical signals + stability noise.
    Returns scores in [0,1] for relevance, correctness, usefulness, hallucination_risk.
    """
    cfg = config or LLMJudgeConfig()
    ref = reference if reference is not None else cfg.reference
    q = query or ""

    ct = candidate_text or ""
    qt = _tok(q)
    rt = _tok(ref) if ref else set()
    ct_t = _tok(ct)

    relevance = _bounded(math.log1p(len(qt & ct_t)) / math.log1p(max(len(qt), 1)))
    if qt:
        relevance = _bounded(relevance * (0.5 + 0.5 * (len(qt & ct_t) / len(qt))))

    if ref:
        overlap = len(rt & ct_t)
        correctness = _bounded(overlap / max(len(rt), 1))
    else:
        correctness = 0.45

    usefulness = _bounded(0.35 * relevance + 0.35 * correctness + 0.3 * _bounded(len(ct) / 1200.0))

    if ref:
        unsupported = max(len(ct_t - qt - rt), 0)
        hallucination_risk = _bounded(unsupported / max(len(ct_t), 1))
    else:
        # Without a reference, long concatenated retrieval contexts are not "hallucinations".
        if len(ct) > 400:
            unsupported = max(len(ct_t - qt), 0)
            hallucination_risk = _bounded(0.2 * (unsupported / max(len(ct_t), 1)))
        else:
            unsupported = max(len(ct_t - qt), 0)
            hallucination_risk = _bounded(unsupported / max(len(ct_t), 1))

    h = hashlib.sha256(f"{cfg.seed}:{ct[:200]}".encode()).digest()
    jitter = (h[0] / 255.0 - 0.5) * 0.04
    out = {
        "relevance": _bounded(relevance + jitter),
        "correctness": _bounded(correctness + jitter),
        "usefulness": _bounded(usefulness + jitter),
        "hallucination_risk": _bounded(hallucination_risk - jitter),
    }
    return out


def extract_candidate_text(output_dict: dict[str, Any] | None) -> str:
    if not output_dict:
        return ""
    if output_dict.get("raw_text"):
        return str(output_dict["raw_text"])
    payload = output_dict.get("payload") or {}
    if isinstance(payload.get("answer"), str):
        return str(payload["answer"])
    if isinstance(payload.get("plan"), list):
        return str(payload.get("plan"))
    hits = payload.get("hits") or payload.get("ranked") or []
    if isinstance(hits, list) and hits:
        parts = []
        for h in hits[:8]:
            parts.append(str(h.get("text", h)))
        return "\n".join(parts)
    return str(payload)[:4000]
