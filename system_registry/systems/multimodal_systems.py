from __future__ import annotations

import hashlib
import math
from typing import Any

from system_registry.base import AISystem, SystemOutput

from .ir_systems import _stable_shuffle_ids


class CLIPRetrieval(AISystem):
    system_id = "CLIPRetrieval"
    description = "Mock CLIP-style cross-modal retrieval (image/text → ranked ids)."

    def run(self, input: dict) -> SystemOutput:
        self.validate_input(input, ("query", "items"))
        query = str(input["query"])
        items: list[dict[str, Any]] = list(input["items"])
        k = int(input.get("top_k", 10))
        modality = str(input.get("modality", "image_text"))
        ids = [str(it.get("id", str(i))) for i, it in enumerate(items)]
        seed = f"clip_mock::{query}::{modality}"
        ranked = _stable_shuffle_ids(ids, seed)[:k]
        scores = {doc_id: float(math.exp(-0.07 * (i + 1))) for i, doc_id in enumerate(ranked)}
        id_meta = {str(it.get("id", str(j))): it for j, it in enumerate(items)}
        hits = [{"id": i, "score": scores[i], "meta": id_meta.get(i, {})} for i in ranked]
        return SystemOutput(
            self.system_id,
            payload={"hits": hits, "mock": True, "modality": modality},
            ranked_ids=ranked,
            scores=scores,
            extras={"note": "Replace with real CLIP embeddings for production research."},
        )


class VideoRetrievalSystem(AISystem):
    system_id = "VideoRetrievalSystem"
    description = "TwelveLabs-like abstraction: segment-level mock retrieval over video corpus."

    def run(self, input: dict) -> SystemOutput:
        self.validate_input(input, ("query", "videos"))
        query = str(input["query"])
        videos: list[dict[str, Any]] = list(input["videos"])
        k = int(input.get("top_k", 5))
        ids = [str(v.get("id", str(i))) for i, v in enumerate(videos)]
        seed = f"video_tl::{query}"
        ranked = _stable_shuffle_ids(ids, seed)[:k]
        scores = {vid: float(hashlib.md5(f"{query}:{vid}".encode()).hexdigest()[:6], 16) / 16**6 for vid in ranked}
        hits = []
        for vid in ranked:
            meta = next((v for v in videos if str(v.get("id")) == vid), {})
            hits.append(
                {
                    "id": vid,
                    "score": scores[vid],
                    "segments": meta.get("segments", [{"t0": 0, "t1": 5, "text": "mock segment"}]),
                }
            )
        return SystemOutput(
            self.system_id,
            payload={"hits": hits, "mock": True},
            ranked_ids=ranked,
            scores=scores,
            extras={"note": "Wire to real multimodal video index when available."},
        )
