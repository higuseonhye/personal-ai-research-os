from __future__ import annotations

import hashlib
import math
import re
from typing import Any

import numpy as np

from research_os.system_registry.base import AISystem, SystemOutput

_TOKEN = re.compile(r"\w+", re.UNICODE)


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN.findall(text)]


def _stable_shuffle_ids(ids: list[str], seed: str) -> list[str]:
    h = hashlib.sha256(seed.encode("utf-8")).digest()
    key = int.from_bytes(h[:8], "big")
    pairs = sorted(((hash((key, i)) % (2**32)), i) for i in ids)
    return [p[1] for p in pairs]


class BM25Retriever(AISystem):
    system_id = "BM25Retriever"
    description = "Lexical BM25 retrieval over a text corpus."

    def run(self, input: dict) -> SystemOutput:
        self.validate_input(input, ("query", "corpus"))
        query = str(input["query"])
        corpus: list[dict[str, Any]] = list(input["corpus"])
        k = int(input.get("top_k", 10))

        try:
            from rank_bm25 import BM25Okapi
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("Install rank-bm25: pip install rank-bm25") from e

        docs = [_tokenize(str(c.get("text", ""))) for c in corpus]
        if not docs:
            return SystemOutput(self.system_id, payload={"hits": []}, ranked_ids=[], scores={})

        bm25 = BM25Okapi(docs)
        q = _tokenize(query)
        scores = bm25.get_scores(q)
        order = np.argsort(-scores)[:k]
        hits: list[dict[str, Any]] = []
        ranked_ids: list[str] = []
        score_map: dict[str, float] = {}
        for idx in order:
            cid = str(corpus[int(idx)].get("id", str(int(idx))))
            s = float(scores[int(idx)])
            hits.append({"id": cid, "score": s, "text": corpus[int(idx)].get("text", "")})
            ranked_ids.append(cid)
            score_map[cid] = s

        return SystemOutput(
            self.system_id,
            payload={"hits": hits},
            ranked_ids=ranked_ids,
            scores=score_map,
        )


class DenseRetriever(AISystem):
    system_id = "DenseRetriever"
    description = "Dense embedding retrieval (sentence-transformers when available)."

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self._model_name = model_name
        self._model = None

    def _embed(self, texts: list[str]) -> np.ndarray:
        try:
            from sentence_transformers import SentenceTransformer

            if self._model is None:
                self._model = SentenceTransformer(self._model_name)
            emb = self._model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
            return np.asarray(emb, dtype=np.float32)
        except Exception:
            # Lightweight deterministic fallback (no torch)
            vecs = []
            for t in texts:
                v = np.zeros(256, dtype=np.float32)
                for tok in _tokenize(t)[:200]:
                    h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
                    v[h % 256] += 1.0
                n = float(np.linalg.norm(v) + 1e-9)
                vecs.append(v / n)
            return np.stack(vecs, axis=0)

    def run(self, input: dict) -> SystemOutput:
        self.validate_input(input, ("query", "corpus"))
        query = str(input["query"])
        corpus: list[dict[str, Any]] = list(input["corpus"])
        k = int(input.get("top_k", 10))

        texts = [str(c.get("text", "")) for c in corpus]
        if not texts:
            return SystemOutput(self.system_id, payload={"hits": []}, ranked_ids=[], scores={})

        qv = self._embed([query])[0]
        dv = self._embed(texts)
        sims = dv @ qv
        order = np.argsort(-sims)[:k]
        hits: list[dict[str, Any]] = []
        ranked_ids: list[str] = []
        score_map: dict[str, float] = {}
        for idx in order:
            cid = str(corpus[int(idx)].get("id", str(int(idx))))
            s = float(sims[int(idx)])
            hits.append({"id": cid, "score": s, "text": corpus[int(idx)].get("text", "")})
            ranked_ids.append(cid)
            score_map[cid] = s

        return SystemOutput(
            self.system_id,
            payload={"hits": hits},
            ranked_ids=ranked_ids,
            scores=score_map,
        )


class HybridRetriever(AISystem):
    system_id = "HybridRetriever"
    description = "Hybrid dense + BM25 fusion (RRF-style)."

    def __init__(self) -> None:
        self._dense = DenseRetriever()
        self._bm25 = BM25Retriever()

    def run(self, input: dict) -> SystemOutput:
        self.validate_input(input, ("query", "corpus"))
        k = int(input.get("top_k", 10))
        d_out = self._dense.run(input)
        b_out = self._bm25.run(input)

        rrf: dict[str, float] = {}
        rrf_k = 60.0

        def add_rank_list(ranked: list[str] | None, weight: float) -> None:
            if not ranked:
                return
            for rank, doc_id in enumerate(ranked, start=1):
                rrf[doc_id] = rrf.get(doc_id, 0.0) + weight / (rrf_k + rank)

        add_rank_list(d_out.ranked_ids, 1.0)
        add_rank_list(b_out.ranked_ids, 1.0)

        corpus: list[dict[str, Any]] = list(input["corpus"])
        id_to_text = {str(c.get("id", str(i))): c.get("text", "") for i, c in enumerate(corpus)}

        ranked = sorted(rrf.keys(), key=lambda x: rrf[x], reverse=True)[:k]
        hits = [{"id": i, "score": rrf[i], "text": id_to_text.get(i, "")} for i in ranked]

        return SystemOutput(
            self.system_id,
            payload={"hits": hits, "fusion": "rrf_bm25_dense"},
            ranked_ids=ranked,
            scores={i: float(rrf[i]) for i in ranked},
        )


class ColBERTRetriever(AISystem):
    system_id = "ColBERTRetriever"
    description = "Mock ColBERT-style late interaction retriever (placeholder)."

    def run(self, input: dict) -> SystemOutput:
        self.validate_input(input, ("query", "corpus"))
        corpus: list[dict[str, Any]] = list(input["corpus"])
        k = int(input.get("top_k", 10))
        query = str(input["query"])
        ids = [str(c.get("id", str(i))) for i, c in enumerate(corpus)]
        seed = f"colbert_mock::{query}"
        ranked = _stable_shuffle_ids(ids, seed)[:k]
        scores = {doc_id: float(math.exp(-0.1 * (i + 1))) for i, doc_id in enumerate(ranked)}
        id_to_text = {str(c.get("id", str(i))): str(c.get("text", "")) for i, c in enumerate(corpus)}
        hits = [{"id": doc_id, "score": scores[doc_id], "text": id_to_text.get(doc_id, "")} for doc_id in ranked]
        return SystemOutput(
            self.system_id,
            payload={"hits": hits, "mock": True},
            ranked_ids=ranked,
            scores=scores,
            extras={"note": "ColBERT mock — swap for real late-interaction model."},
        )


class LLMReranker(AISystem):
    system_id = "LLMReranker"
    description = "Rerank candidate documents using lexical overlap proxy (local, no API)."

    def run(self, input: dict) -> SystemOutput:
        self.validate_input(input, ("query", "candidates"))
        query = str(input["query"])
        candidates: list[dict[str, Any]] = list(input["candidates"])
        k = int(input.get("top_k", len(candidates)))
        qt = set(_tokenize(query))

        def score_text(text: str) -> float:
            dt = set(_tokenize(text))
            if not qt:
                return 0.0
            inter = len(qt & dt)
            return inter / (math.sqrt(len(qt)) * math.sqrt(max(len(dt), 1)))

        scored: list[tuple[float, dict[str, Any]]] = []
        for c in candidates:
            s = score_text(str(c.get("text", "")))
            scored.append((s, c))
        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:k]
        hits = []
        ranked_ids = []
        scores: dict[str, float] = {}
        for rank, (s, c) in enumerate(top):
            cid = str(c.get("id", f"cand_{rank}"))
            hits.append({"id": cid, "score": s, "text": c.get("text", "")})
            ranked_ids.append(cid)
            scores[cid] = float(s)

        return SystemOutput(
            self.system_id,
            payload={"hits": hits},
            ranked_ids=ranked_ids,
            scores=scores,
            extras={"reranker": "lexical_overlap_proxy"},
        )
