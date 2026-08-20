"""AI gateway (AI-ARCHITECTURE.md §2, ADR-017).

OpenAI-compatible client targeting a DeepSeek-compatible endpoint with a
fallback provider chain; without an API key the deterministic
:class:`StubGateway` is used (dev, unit tests, and the eval harness). Every
result carries the pieces the T4 envelope needs (content JSON, confidence,
model id, provider, latency) and the caller records them in ``ai_runs``
(ADR-019: PII-insulated payloads).
"""

from __future__ import annotations

import json
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from tk_api.core.config import Settings

SYSTEM_PROMPT = (
    "You are Theek Karo's civic analysis engine. Analyse the citizen report and "
    'respond with STRICT JSON only: {"summary": string, "entities": '
    '[{name, type}], "suggested_category": slug, "confidence": number 0..1, '
    '"cross_references": [label]} . Never invent official facts; when unsure, '
    "lower confidence. Hindi and English input are both fine."
)


@dataclass
class GatewayResult:
    content: dict[str, Any]
    confidence: float
    model_id: str
    provider: str
    latency_ms: int | None


class AiGateway(Protocol):
    async def analyze(self, *, prompt: str) -> GatewayResult: ...

    @property
    def provider(self) -> str: ...

    @property
    def model_id(self) -> str: ...


# ---------------------------------------------------------------------------
# Stub (the fallback that makes dev/tests/eval hermetic)
# ---------------------------------------------------------------------------

_KEYWORDS: dict[str, list[str]] = {
    "school": ["classroom", "school", "teacher", "window", "washroom", "playground"],
    "road": ["pothole", "road", "street", "signage", "streetlight", "traffic"],
    "water": ["water", "pipe", "leak", "tap", "supply"],
    "sanitation": ["garbage", "waste", "drain", "sewage", "sanitation"],
}


class StubGateway:
    """Deterministic keyword classifier; never reaches the network."""

    def __init__(self, model_id: str) -> None:
        self._model_id = model_id

    @property
    def provider(self) -> str:
        return "stub"

    @property
    def model_id(self) -> str:
        return self._model_id

    async def analyze(self, *, prompt: str) -> GatewayResult:
        start = time.perf_counter()
        text = prompt.lower()
        best: tuple[float, str] = (0.0, "other")
        for slug, words in _KEYWORDS.items():
            hits = sum(1 for w in words if w in text)
            score = hits / max(1, len(words) * 2) + (0.15 if slug in text else 0.0)
            if score > best[0]:
                best = (score, slug)
        score, slug = best
        latency = int((time.perf_counter() - start) * 1000)
        return GatewayResult(
            content={
                "summary": f"Keyword analysis suggests a {slug}-related issue (stub).",
                "entities": [],
                "suggested_category": slug,
                "cross_references": [],
            },
            confidence=0.5 + min(0.45, score),
            model_id=self._model_id,
            provider=self.provider,
            latency_ms=latency,
        )


# ---------------------------------------------------------------------------
# OpenAI-compatible remote gateway with fallback chain (ADR-017)
# ---------------------------------------------------------------------------


class OpenAiGateway:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self._urls: Sequence[str] = settings.ai_gateway_urls
        self._api_key = settings.ai_api_key
        self._model_id = settings.ai_model
        self._timeout = settings.ai_timeout_seconds
        self._client = client or httpx.AsyncClient(timeout=self._timeout)

    @property
    def provider(self) -> str:
        main = self._urls[0] if self._urls else ""
        return main.replace("https://", "").replace("http://", "").split("/")[0] or "openai"

    @property
    def model_id(self) -> str:
        return self._model_id

    async def analyze(self, *, prompt: str) -> GatewayResult:
        last_error: Exception | None = None
        for url in self._urls:
            try:
                return await self._call(url, prompt)
            except (httpx.HTTPError, ValueError, json.JSONDecodeError) as exc:
                last_error = exc
        raise RuntimeError(f"all AI providers failed: {last_error}")

    async def _call(self, base_url: str, prompt: str) -> GatewayResult:
        start = time.perf_counter()
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        response = await self._client.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers=headers,
            json={
                "model": self._model_id,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.2,
            },
        )
        response.raise_for_status()
        data = response.json()
        raw_content = data["choices"][0]["message"]["content"]
        parsed: dict[str, Any] = json.loads(raw_content)
        latency = int((time.perf_counter() - start) * 1000)
        return GatewayResult(
            content=parsed,
            confidence=float(parsed.get("confidence", 0.5)),
            model_id=self._model_id,
            provider=self.provider,
            latency_ms=latency,
        )


def build_gateway(settings: Settings) -> AiGateway:
    if not settings.ai_api_key:
        return StubGateway(model_id=settings.ai_model)
    return OpenAiGateway(settings)
