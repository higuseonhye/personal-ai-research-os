from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SystemOutput:
    """Normalized container for any AISystem result."""

    system_id: str
    payload: dict[str, Any] = field(default_factory=dict)
    raw_text: str | None = None
    ranked_ids: list[str] | None = None
    scores: dict[str, float] | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "system_id": self.system_id,
            "payload": self.payload,
            "raw_text": self.raw_text,
            "ranked_ids": self.ranked_ids,
            "scores": self.scores,
            "extras": self.extras,
        }


class AISystem(ABC):
    """Universal interface: AISystem(input: dict) -> structured output."""

    system_id: str
    description: str = ""

    @abstractmethod
    def run(self, input: dict) -> SystemOutput:
        """Execute the system on a standardized input dict."""

    def validate_input(self, input: dict, required_keys: tuple[str, ...]) -> None:
        missing = [k for k in required_keys if k not in input]
        if missing:
            raise ValueError(f"{self.system_id} missing keys: {missing}")
