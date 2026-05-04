from __future__ import annotations

import hashlib
import re
from typing import Any

from research_os.system_registry.base import AISystem, SystemOutput
from research_os.system_registry.systems.ir_systems import DenseRetriever

_TOKEN = re.compile(r"\w+", re.UNICODE)


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN.findall(text)]


class GPTStyleQA(AISystem):
    system_id = "GPTStyleQA"
    description = "Local template QA (no external API) — simulates grounded-style answer."

    def run(self, input: dict) -> SystemOutput:
        self.validate_input(input, ("question",))
        q = str(input["question"])
        context = str(input.get("context", ""))
        seed = hashlib.sha256(q.encode()).hexdigest()[:8]
        if context.strip():
            snippet = context.strip()[:800]
            answer = (
                f"[local-gpt-style:{seed}] Based on the provided context, the key points are: "
                f"{snippet[:240]}{'…' if len(snippet) > 240 else ''}"
            )
        else:
            answer = (
                f"[local-gpt-style:{seed}] No context supplied — provide `context` or `corpus` "
                f"for grounded answers. Question understood as: {q[:200]}"
            )
        return SystemOutput(
            self.system_id,
            payload={"answer": answer, "model": "local_template"},
            raw_text=answer,
        )


class RAGSystem(AISystem):
    system_id = "RAGSystem"
    description = "Retrieve-then-answer pipeline using DenseRetriever + template answer."

    def __init__(self) -> None:
        self._retriever = DenseRetriever()

    def run(self, input: dict) -> SystemOutput:
        self.validate_input(input, ("question", "corpus"))
        question = str(input["question"])
        corpus = list(input["corpus"])
        k = int(input.get("top_k", 3))
        retr_input = {"query": question, "corpus": corpus, "top_k": k}
        r = self._retriever.run(retr_input)
        ctx_parts: list[str] = []
        for h in r.payload.get("hits", [])[:k]:
            ctx_parts.append(str(h.get("text", "")))
        context = "\n".join(ctx_parts)
        qa = GPTStyleQA()
        ans = qa.run({"question": question, "context": context})
        return SystemOutput(
            self.system_id,
            payload={
                "answer": ans.payload.get("answer"),
                "retrieval_hits": r.payload.get("hits", []),
                "pipeline": "dense_retrieve_then_qa",
            },
            raw_text=str(ans.payload.get("answer")),
            ranked_ids=r.ranked_ids,
            scores=r.scores,
            extras={"retriever": r.system_id},
        )
