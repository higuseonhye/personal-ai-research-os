"""Dense embeddings + FAISS index for paper abstracts / structured metadata."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import Any

import numpy as np

try:
    import faiss  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - optional on some Windows/conda envs
    faiss = None  # type: ignore[assignment]

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_DEFAULT_DIM = 384
_MODEL_NAME = "all-MiniLM-L6-v2"
_HAS_FAISS = faiss is not None


def _hash_embedding(text: str, dim: int) -> np.ndarray:
    """Deterministic pseudo-embedding when sentence-transformers is not installed."""
    raw = text.encode("utf-8", errors="replace")
    vals: list[float] = []
    counter = 0
    seed = hashlib.sha256(raw).digest()
    while len(vals) < dim:
        chunk = hashlib.sha256(seed + counter.to_bytes(4, "little")).digest()
        vals.extend(float(b) / 255.0 for b in chunk)
        counter += 1
    v = np.asarray(vals[:dim], dtype=np.float32)
    n = float(np.linalg.norm(v))
    if n > 1e-8:
        v = v / n
    return v


class EmbeddingStore:
    def __init__(self, dim: int = _DEFAULT_DIM) -> None:
        self.dim = dim
        self._use_faiss = _HAS_FAISS
        self.index = faiss.IndexFlatL2(dim) if self._use_faiss else None
        self._vectors: list[np.ndarray] = []
        self.meta: list[dict[str, Any]] = []
        self._st_model: Any = None
        self._st_attempted = False

    def _maybe_load_sentence_transformers(self) -> None:
        if self._st_attempted:
            return
        self._st_attempted = True
        try:
            from sentence_transformers import SentenceTransformer

            self._st_model = SentenceTransformer(_MODEL_NAME)
        except ImportError:
            self._st_model = None

    def _embed(self, texts: list[str]) -> np.ndarray:
        self._maybe_load_sentence_transformers()
        if self._st_model is not None:
            out = self._st_model.encode(texts, normalize_embeddings=True)
            return np.asarray(out, dtype=np.float32)
        return np.stack([_hash_embedding(t, self.dim) for t in texts], axis=0)

    def _ntotal(self) -> int:
        if self._use_faiss and self.index is not None:
            return int(self.index.ntotal)
        return len(self._vectors)

    def add(self, text: str, metadata: dict[str, Any]) -> None:
        emb = self._embed([text])
        vec = np.asarray(emb, dtype=np.float32).reshape(1, -1)
        if vec.shape[1] != self.dim:
            raise ValueError(f"Embedding dim {vec.shape[1]} != index dim {self.dim}")
        if self._use_faiss and self.index is not None:
            self.index.add(vec)
        else:
            self._vectors.append(vec.reshape(-1))
        self.meta.append(metadata)

    def all_metadata(self) -> list[dict[str, Any]]:
        return list(self.meta)

    def search(self, query: str, k: int = 5) -> list[dict[str, Any]]:
        if self._ntotal() == 0:
            return []
        q = self._embed([query])
        kk = min(k, self._ntotal())
        if self._use_faiss and self.index is not None:
            _distances, indices = self.index.search(q, kk)
            out: list[dict[str, Any]] = []
            for idx in indices[0]:
                ii = int(idx)
                if 0 <= ii < len(self.meta):
                    out.append(self.meta[ii])
            return out

        mat = np.stack(self._vectors, axis=0)
        qv = q.reshape(-1)
        dist = np.linalg.norm(mat - qv, axis=1)
        top = np.argsort(dist)[:kk]
        return [self.meta[int(i)] for i in top if 0 <= int(i) < len(self.meta)]


_default_store: EmbeddingStore | None = None


def get_default_embedding_store() -> EmbeddingStore:
    global _default_store  # noqa: PLW0603
    if _default_store is None:
        _default_store = EmbeddingStore()
    return _default_store
