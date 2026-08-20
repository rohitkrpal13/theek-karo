"""Model registry, capability descriptors, pricing, and task routing."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal

LatencyTier = Literal["fast", "balanced", "deep_reasoning"]


@dataclass
class ModelSpec:
    model_id: str
    provider: str
    capabilities: list[str]
    context_window: int = 8192
    cost_per_1k_in: float = 0.0005
    cost_per_1k_out: float = 0.0015
    latency_tier: LatencyTier = "balanced"
    supported_languages: list[str] = field(default_factory=lambda: ["en", "hi"])
    structured_output: bool = True
    vision: bool = False
    embedding: bool = False


# -----------------------------------------------------------------------------
# Approved Model Registry
# -----------------------------------------------------------------------------

MODEL_REGISTRY: dict[str, ModelSpec] = {
    # 1. Primary Reasoning & Chat Model
    "deepseek-chat": ModelSpec(
        model_id="deepseek-chat",
        provider="deepseek",
        capabilities=[
            "classification",
            "summarization",
            "comparison",
            "chat_assistant",
            "duplicate_detection",
        ],
        context_window=32768,
        cost_per_1k_in=0.00014,
        cost_per_1k_out=0.00028,
        latency_tier="balanced",
        supported_languages=[
            "en",
            "hi",
            "bn",
            "te",
            "mr",
            "ta",
            "gu",
            "kn",
            "ml",
            "or",
            "pa",
            "as",
            "ur",
            "mai",
        ],
        structured_output=True,
    ),
    # 2. Fast Low-Cost Classifier / Translation
    "gpt-4o-mini": ModelSpec(
        model_id="gpt-4o-mini",
        provider="openai",
        capabilities=["classification", "translation", "duplicate_detection"],
        context_window=16384,
        cost_per_1k_in=0.00015,
        cost_per_1k_out=0.00060,
        latency_tier="fast",
        supported_languages=[
            "en",
            "hi",
            "bn",
            "te",
            "mr",
            "ta",
            "gu",
            "kn",
            "ml",
            "or",
            "pa",
            "as",
            "ur",
            "mai",
        ],
        structured_output=True,
    ),
    # 3. Embedding Model
    "text-embedding-3-small": ModelSpec(
        model_id="text-embedding-3-small",
        provider="openai",
        capabilities=["embedding"],
        context_window=8191,
        cost_per_1k_in=0.00002,
        cost_per_1k_out=0.0,
        latency_tier="fast",
        embedding=True,
    ),
    # 4. Hermetic Test / Dev Stub
    "stub-civic-v1": ModelSpec(
        model_id="stub-civic-v1",
        provider="stub",
        capabilities=[
            "classification",
            "summarization",
            "comparison",
            "translation",
            "chat_assistant",
            "duplicate_detection",
            "embedding",
        ],
        context_window=8192,
        cost_per_1k_in=0.0,
        cost_per_1k_out=0.0,
        latency_tier="fast",
        supported_languages=[
            "en",
            "hi",
            "bn",
            "te",
            "mr",
            "ta",
            "gu",
            "kn",
            "ml",
            "or",
            "pa",
            "as",
            "ur",
            "mai",
        ],
        structured_output=True,
        embedding=True,
    ),
}


class ModelRouter:
    """Task-aware router selecting optimal models with fallback chains."""

    def __init__(self, registry: dict[str, ModelSpec] | None = None) -> None:
        self.registry = registry or MODEL_REGISTRY

    def select_model(
        self,
        task: str,
        *,
        language: str = "en",
        preferred_tier: LatencyTier | None = None,
        use_stub: bool = False,
    ) -> ModelSpec:
        if use_stub:
            return self.registry.get("stub-civic-v1", next(iter(self.registry.values())))

        candidates = [
            m
            for m in self.registry.values()
            if task in m.capabilities
            and (language in m.supported_languages or not m.supported_languages)
        ]

        if not candidates:
            # Fallback to any model capable of the task
            candidates = [m for m in self.registry.values() if task in m.capabilities]

        if not candidates:
            # Fallback to default
            return self.registry.get("stub-civic-v1", next(iter(self.registry.values())))

        if preferred_tier:
            matching_tier = [c for c in candidates if c.latency_tier == preferred_tier]
            if matching_tier:
                return matching_tier[0]

        return candidates[0]

    def calculate_cost(
        self,
        model_id: str,
        tokens_in: int,
        tokens_out: int,
    ) -> Decimal:
        """Calculate estimated cost in USD based on token consumption."""
        spec = self.registry.get(model_id)
        if not spec:
            return Decimal("0.000000")

        cost = (tokens_in / 1000.0 * spec.cost_per_1k_in) + (
            tokens_out / 1000.0 * spec.cost_per_1k_out
        )
        return Decimal(str(round(cost, 6)))
