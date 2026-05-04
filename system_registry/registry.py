from __future__ import annotations

from typing import Iterable

from .base import AISystem
from .systems import (
    BM25Retriever,
    CLIPRetrieval,
    ColBERTRetriever,
    DenseRetriever,
    GPTStyleQA,
    HybridRetriever,
    LangGraphStylePlanner,
    LLMReranker,
    PredictionModel,
    RAGSystem,
    RankingModel,
    RecommendationModel,
    RuleBasedAgent,
    VideoRetrievalSystem,
)


class SystemRegistry:
    """Register and resolve AISystem implementations by id."""

    def __init__(self) -> None:
        self._systems: dict[str, AISystem] = {}

    def register(self, system: AISystem) -> None:
        self._systems[system.system_id] = system

    def register_many(self, systems: Iterable[AISystem]) -> None:
        for s in systems:
            self.register(s)

    def get(self, system_id: str) -> AISystem:
        if system_id not in self._systems:
            raise KeyError(f"Unknown system_id: {system_id}. Known: {sorted(self._systems)}")
        return self._systems[system_id]

    def list_ids(self) -> list[str]:
        return sorted(self._systems.keys())

    def all_systems(self) -> dict[str, AISystem]:
        return dict(self._systems)


def get_default_registry() -> SystemRegistry:
    reg = SystemRegistry()
    reg.register_many(
        [
            BM25Retriever(),
            DenseRetriever(),
            HybridRetriever(),
            ColBERTRetriever(),
            LLMReranker(),
            GPTStyleQA(),
            RAGSystem(),
            CLIPRetrieval(),
            VideoRetrievalSystem(),
            RuleBasedAgent(),
            LangGraphStylePlanner(),
            RankingModel(),
            RecommendationModel(),
            PredictionModel(),
        ]
    )
    return reg
