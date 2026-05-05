"""Dense embeddings + FAISS index for paper abstracts / structured metadata."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import faiss  # type: ignore[import-untyped]
import numpy as np
from sentence_transformers import SentenceTransformer

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


_DEFAULT_DIM = 384
_MODEL_NAME = "all-MiniLM-L6-v2"


class EmbeddingStore:
    def __init__(self, dim: int = _DEFAULT_DIM) -> None:
        self.dim = dim
        self.index = faiss.IndexFlatL2(dim)
        self.meta: list[dict[str, Any]] = []
        self._model: SentenceTransformer | None = None

    def _encoder(self) -> SentenceTransformer:
        if self._model is None:
            self._model = SentenceTransformer(_MODEL_NAME)
        return self._model

    def add(self, text: str, metadata: dict[str, Any]) -> None:
        enc = self._encoder()
        emb = enc.encode([text], normalize_embeddings=True)[0]
        vec = np.asarray([emb], dtype=np.float32)
        if vec.shape[1] != self.dim:
            raise ValueError(f"Embedding dim {vec.shape[1]} != index dim {self.dim}")
        self.index.add(vec)
        self.meta.append(metadata)

    def all_metadata(self) -> list[dict[str, Any]]:
        return list(self.meta)

    def search(self, query: str, k: int = 5) -> list[dict[str, Any]]:
        if self.index.ntotal == 0:
            return []
        enc = self._encoder()
        q = enc.encode([query], normalize_embeddings=True)
        q = np.asarray(q, dtype=np.float32)
        kk = min(k, int(self.index.ntotal))
        _distances, indices = self.index.search(q, kk)
        out: list[dict[str, Any]] = []
        for idx in indices[0]:
            ii = int(idx)
            if 0 <= ii < len(self.meta):
                out.append(self.meta[ii])
        return out


_default_store: EmbeddingStore | None = None


def get_default_embedding_store() -> EmbeddingStore:
    global _default_store  # noqa: PLW0603
    if _default_store is None:
        _default_store = EmbeddingStore()
    return _default_store
