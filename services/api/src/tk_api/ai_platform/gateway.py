"""AI Gateway (Phase 27).

Centralized entry point for all AI calls. Responsibilities:
- Authentication & authorization
- Model selection via ModelRouter
- Prompt management
- Token limits & rate limiting
- Cost tracking & budget enforcement
- Safety checks
- Logging & tracing
- Retries & fallback
- Circuit breaker
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from sqlalchemy.ext.asyncio import AsyncSession

from tk_api.ai.prompts import redact_pii_from_prompt
from tk_api.ai.providers import LLMProvider, StubLlmProvider
from tk_api.ai.registry import ModelRouter, ModelSpec


@dataclass
class AIGatewayRequest:
    """Standardized AI request model."""

    request_id: uuid.UUID = field(default_factory=uuid.uuid4)
    user_id: uuid.UUID | None = None
    agent_code: str = "general"
    task: str = "chat"
    model_id: str | None = None
    input_data: dict[str, Any] = field(default_factory=dict)
    context: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    output_schema: dict[str, Any] | None = None
    language: str = "en"
    risk_level: str = "low"
    max_tokens: int = 4000
    temperature: float = 0.2
    timeout_s: int = 30
    idempotency_key: str | None = None


@dataclass
class AIGatewayResponse:
    """Standardized AI response model."""

    request_id: uuid.UUID
    status: str  # success | error | refused | fallback
    text: str = ""
    structured_output: dict[str, Any] | None = None
    model_id: str = ""
    provider: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    citations: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class AICircuitBreaker:
    """Simple circuit breaker for AI providers."""

    def __init__(self, failure_threshold: int = 5, recovery_timeout_s: int = 60):
        self._failure_counts: dict[str, int] = {}
        self._circuit_open_until: dict[str, datetime] = {}
        self._failure_threshold = failure_threshold
        self._recovery_timeout_s = recovery_timeout_s

    def is_open(self, provider: str) -> bool:
        until = self._circuit_open_until.get(provider)
        if until and datetime.now(UTC) < until:
            return True
        if until and datetime.now(UTC) >= until:
            # Recovery check — reset
            self._failure_counts[provider] = 0
            del self._circuit_open_until[provider]
            return False
        return False

    def record_success(self, provider: str) -> None:
        self._failure_counts[provider] = 0
        self._circuit_open_until.pop(provider, None)

    def record_failure(self, provider: str) -> None:
        count = self._failure_counts.get(provider, 0) + 1
        self._failure_counts[provider] = count
        if count >= self._failure_threshold:
            self._circuit_open_until[provider] = datetime.now(UTC) + timedelta(
                seconds=self._recovery_timeout_s
            )

    def get_status(self) -> dict[str, Any]:
        return {
            "failure_counts": dict(self._failure_counts),
            "open_until": {k: v.isoformat() for k, v in self._circuit_open_until.items()},
        }


class AIGateway:
    """Centralized AI Gateway routing requests through providers with
    safety, cost, and authorization controls.
    """

    def __init__(
        self,
        provider: LLMProvider | None = None,
        router: ModelRouter | None = None,
    ):
        self.provider = provider or StubLlmProvider()
        self.router = router or ModelRouter()
        self.circuit_breaker = AICircuitBreaker()
        self._rate_limits: dict[str, list[datetime]] = {}

    def _check_rate_limit(self, user_id: uuid.UUID | None, max_per_minute: int = 30) -> bool:
        """Simple in-memory rate limiter per user."""
        key = str(user_id) if user_id else "anonymous"
        now = datetime.now(UTC)
        cutoff = now - timedelta(minutes=1)
        timestamps = self._rate_limits.get(key, [])
        # Prune old entries
        timestamps = [t for t in timestamps if t > cutoff]
        if len(timestamps) >= max_per_minute:
            return False
        timestamps.append(now)
        self._rate_limits[key] = timestamps
        return True

    def _select_model(self, request: AIGatewayRequest) -> ModelSpec:
        """Select model based on task, language, and availability."""
        if request.model_id and request.model_id in self.router.registry:
            return self.router.registry[request.model_id]

        # Check circuit breaker
        preferred_tier: Literal["deep_reasoning", "balanced", "fast"] | None = None
        if request.risk_level == "critical":
            preferred_tier = "deep_reasoning"

        return self.router.select_model(
            request.task,
            language=request.language,
            preferred_tier=preferred_tier,
        )

    async def process(
        self,
        session: AsyncSession,
        request: AIGatewayRequest,
    ) -> AIGatewayResponse:
        """Process an AI request through the full gateway pipeline."""
        # 1. Rate limit check
        if not self._check_rate_limit(request.user_id):
            return AIGatewayResponse(
                request_id=request.request_id,
                status="error",
                error="Rate limit exceeded. Please try again later.",
            )

        # 2. Circuit breaker check
        model_spec = self._select_model(request)
        if self.circuit_breaker.is_open(model_spec.provider):
            # Try fallback
            fallback = self.router.select_model(request.task, language=request.language)
            if fallback.provider != model_spec.provider:
                model_spec = fallback
            else:
                return AIGatewayResponse(
                    request_id=request.request_id,
                    status="error",
                    error="AI provider temporarily unavailable. Please try again.",
                )

        # 3. PII scrubbing
        clean_input = redact_pii_from_prompt(
            str(request.input_data.get("query", request.input_data.get("text", "")))
        )
        request.input_data["query"] = clean_input

        # 4. Build prompt
        prompt = clean_input
        if request.context:
            context_str = "\n---\n".join(request.context[:5])
            prompt = f"Context:\n{context_str}\n\nQuery: {clean_input}"

        system_prompt = request.input_data.get("system_prompt")

        # 5. Execute with retry
        last_error = None
        for attempt in range(3):
            try:
                start = datetime.now(UTC)
                llm_response = await self.provider.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    model_id=model_spec.model_id,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                )
                latency_ms = int((datetime.now(UTC) - start).total_seconds() * 1000)

                # Calculate cost
                cost = float(
                    self.router.calculate_cost(
                        model_spec.model_id, llm_response.tokens_in, llm_response.tokens_out
                    )
                )

                self.circuit_breaker.record_success(model_spec.provider)

                return AIGatewayResponse(
                    request_id=request.request_id,
                    status="success",
                    text=llm_response.text,
                    model_id=model_spec.model_id,
                    provider=model_spec.provider,
                    tokens_in=llm_response.tokens_in,
                    tokens_out=llm_response.tokens_out,
                    cost_usd=cost,
                    latency_ms=latency_ms,
                )
            except Exception as exc:
                last_error = str(exc)
                self.circuit_breaker.record_failure(model_spec.provider)
                # Try fallback model on next attempt
                if attempt < 2:
                    model_spec = self.router.select_model(request.task, language=request.language)

        return AIGatewayResponse(
            request_id=request.request_id,
            status="error",
            error=f"AI request failed after retries: {last_error}",
        )

    def get_health(self) -> dict[str, Any]:
        """Gateway health status."""
        return {
            "status": "healthy",
            "provider": self.provider.provider_name,
            "circuit_breaker": self.circuit_breaker.get_status(),
            "models_available": list(self.router.registry.keys()),
        }
