"""ACL-aware retrieval helpers over `EmbeddingStore` metadata."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_DIR = Path(__file__).resolve().parent
if str(_DIR) not in sys.path:
    sys.path.insert(0, str(_DIR))

from embedding_store import EmbeddingStore  # noqa: E402


def principal_allowed(meta: dict[str, Any], principal: str) -> bool:
    """
    Chunk metadata may include `acl_principals` or legacy `acl_allow`.
    Missing ACL implies public (`*`).
    """
    allowed = meta.get("acl_principals")
    if allowed is None:
        allowed = meta.get("acl_allow")
    if allowed is None:
        return True
    if isinstance(allowed, str):
        allowed = [allowed]
    if not isinstance(allowed, list):
        return False
    norm = [str(x).strip() for x in allowed if str(x).strip()]
    if not norm or "*" in norm:
        return True
    return principal.strip() in norm


def search_with_acl(
    store: EmbeddingStore,
    query: str,
    principal: str,
    *,
    k: int = 5,
    overfetch_factor: int = 8,
) -> list[dict[str, Any]]:
    """Over-fetch dense neighbors, then filter by principal visibility."""
    if store.index.ntotal == 0:
        return []
    want = max(k * max(overfetch_factor, 2), k)
    want = min(want, int(store.index.ntotal))
    hits = store.search(query, k=want)
    out: list[dict[str, Any]] = []
    for h in hits:
        if principal_allowed(h, principal):
            out.append(h)
        if len(out) >= k:
            break
    return out
