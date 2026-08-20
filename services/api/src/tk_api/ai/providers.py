"""Provider-neutral LLM abstraction supporting multiple backend models and hermetic stubs."""

from __future__ import annotations

import hashlib
import json
import math
import re
import time
from dataclasses import dataclass
from typing import Any, Protocol, TypeVar

import httpx
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@dataclass
class LLMResponse:
    text: str
    content_json: dict[str, Any] | None
    tokens_in: int
    tokens_out: int
    latency_ms: int
    model_id: str
    provider: str


class LLMProvider(Protocol):
    """Provider interface for text generation, structured outputs, and embeddings."""

    @property
    def provider_name(self) -> str: ...

    async def generate(
        self,
        *,
        prompt: str,
        system_prompt: str | None = None,
        model_id: str = "default",
        temperature: float = 0.2,
        max_tokens: int = 1000,
    ) -> LLMResponse: ...

    async def generate_structured(
        self,
        *,
        prompt: str,
        schema_class: type[T],
        system_prompt: str | None = None,
        model_id: str = "default",
    ) -> tuple[T, LLMResponse]: ...

    async def embed(
        self,
        *,
        texts: list[str],
        model_id: str = "text-embedding-3-small",
    ) -> list[list[float]]: ...


# -----------------------------------------------------------------------------
# 1. Deterministic Stub Provider (Hermetic for Tests, Dev, CI)
# -----------------------------------------------------------------------------


class StubLlmProvider:
    """Deterministic, hermetic provider requiring zero external network calls."""

    provider_name = "stub"

    def __init__(self, default_model: str = "stub-civic-v1") -> None:
        self.default_model = default_model

    async def generate(
        self,
        *,
        prompt: str,
        system_prompt: str | None = None,
        model_id: str = "default",
        temperature: float = 0.2,
        max_tokens: int = 1000,
    ) -> LLMResponse:
        start = time.perf_counter()
        m_id = self.default_model if model_id == "default" else model_id

        text_lower = prompt.lower()
        if "translate" in text_lower:
            match = re.search(r"<input_text>(.*?)</input_text>", prompt, re.DOTALL)
            orig_text = match.group(1).strip() if match else prompt
            ans = f"[Translated] {orig_text}"
        elif "patna" in text_lower or "school" in text_lower:
            ans = (
                "Based on recent civic data, 3 reports in Patna mention recurring drinking water "
                "interruptions, while official UDISE+ records show water as available."
            )
        elif "hospital" in text_lower:
            ans = (
                "District hospital records indicate emergency services are operational, "
                "with 2 community observation reports under verification."
            )
        else:
            ans = (
                "Civic intelligence analysis completed. Information is synthesized from "
                "registered official datasets and community reports."
            )

        latency = max(1, int((time.perf_counter() - start) * 1000))
        t_in = len(prompt.split()) + (len(system_prompt.split()) if system_prompt else 0)
        t_out = len(ans.split())

        return LLMResponse(
            text=ans,
            content_json={"answer": ans},
            tokens_in=t_in,
            tokens_out=t_out,
            latency_ms=latency,
            model_id=m_id,
            provider="stub",
        )

    async def generate_structured(
        self,
        *,
        prompt: str,
        schema_class: type[T],
        system_prompt: str | None = None,
        model_id: str = "default",
    ) -> tuple[T, LLMResponse]:
        start = time.perf_counter()
        m_id = self.default_model if model_id == "default" else model_id
        text_lower = prompt.lower()

        # Heuristic synthesis based on target schema
        schema_name = schema_class.__name__
        content: dict[str, Any] = {}

        if schema_name == "ReportClassificationOutput":
            # Extract content from report_content block if present
            match = re.search(r"<report_content>(.*?)</report_content>", prompt, re.DOTALL)
            report_text = match.group(1).lower() if match else text_lower

            category = "sanitation"
            if any(w in report_text for w in ("water", "pipe", "leak", "tap", "drain")):
                category = "water"
            elif any(w in report_text for w in ("road", "pothole", "street", "traffic")):
                category = "road"
            elif any(w in report_text for w in ("school", "teacher", "class", "student")):
                category = "school"
            elif any(
                w in report_text for w in ("hospital", "doctor", "medicine", "health", "clinic")
            ):
                category = "health"

            content = {
                "category_slug": category,
                "issue_type_slug": f"{category}_general",
                "severity": "high"
                if "urgent" in report_text or "danger" in report_text
                else "medium",
                "missing_information": ["exact_landmark"] if len(report_text) < 40 else [],
                "confidence": 0.85,
                "rationale": f"Rule-based classification matched keywords for '{category}'.",
            }
        elif schema_name == "DuplicateAnalysisOutput":
            is_dup = "similar" in text_lower or "duplicate" in text_lower or "pothole" in text_lower
            content = {
                "is_duplicate": is_dup,
                "similarity_score": 0.82 if is_dup else 0.20,
                "duplicate_candidate_id": "rep-test-duplicate" if is_dup else None,
                "duplicate_ticket_no": "TK-1002" if is_dup else None,
                "rationale": "High textual and geographic alignment detected."
                if is_dup
                else "No duplicate matches above threshold.",
            }
        elif schema_name == "TranslationOutput" or schema_name == "TranslationResponse":
            match = re.search(r"<input_text>(.*?)</input_text>", prompt, re.DOTALL)
            orig_text = match.group(1).strip() if match else prompt
            content = {
                "translated_text": f"[Translated] {orig_text}",
                "source_language": "auto",
                "target_language": "en",
                "model_id": m_id,
                "confidence": 0.95,
            }
        else:
            content = {"summary": "Structured output generated (stub).", "confidence": 0.8}

        instance = schema_class.model_validate(content)
        latency = max(1, int((time.perf_counter() - start) * 1000))
        t_in = len(prompt.split()) + (len(system_prompt.split()) if system_prompt else 0)
        t_out = len(json.dumps(content).split())

        llm_resp = LLMResponse(
            text=json.dumps(content),
            content_json=content,
            tokens_in=t_in,
            tokens_out=t_out,
            latency_ms=latency,
            model_id=m_id,
            provider="stub",
        )
        return instance, llm_resp

    async def embed(
        self,
        *,
        texts: list[str],
        model_id: str = "text-embedding-3-small",
    ) -> list[list[float]]:
        """Generate deterministic 64-dimensional mock embeddings using sha256 hash."""
        embeddings: list[list[float]] = []
        for t in texts:
            raw_hash = hashlib.sha256(t.encode("utf-8")).digest()
            vec = [((b / 255.0) * 2.0 - 1.0) for b in raw_hash[:64]]
            norm = math.sqrt(sum(x * x for x in vec)) or 1.0
            unit_vec = [round(x / norm, 4) for x in vec]
            embeddings.append(unit_vec)
        return embeddings


# -----------------------------------------------------------------------------
# 2. OpenAI / DeepSeek / External Compatible Provider
# -----------------------------------------------------------------------------


class OpenAiCompatibleProvider:
    """Production provider targeting OpenAI, DeepSeek, or Groq compatible endpoints."""

    provider_name = "openai_compatible"

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com/v1",
        default_model: str = "deepseek-chat",
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model

    async def generate(
        self,
        *,
        prompt: str,
        system_prompt: str | None = None,
        model_id: str = "default",
        temperature: float = 0.2,
        max_tokens: int = 1000,
    ) -> LLMResponse:
        start = time.perf_counter()
        m_id = self.default_model if model_id == "default" else model_id

        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": m_id,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            resp.raise_for_status()
            data = resp.json()

        choice = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        latency = int((time.perf_counter() - start) * 1000)

        return LLMResponse(
            text=choice,
            content_json=None,
            tokens_in=usage.get("prompt_tokens", len(prompt.split())),
            tokens_out=usage.get("completion_tokens", len(choice.split())),
            latency_ms=latency,
            model_id=m_id,
            provider="openai_compatible",
        )

    async def generate_structured(
        self,
        *,
        prompt: str,
        schema_class: type[T],
        system_prompt: str | None = None,
        model_id: str = "default",
    ) -> tuple[T, LLMResponse]:
        schema_json = json.dumps(schema_class.model_json_schema())
        prefix = f"{system_prompt}\n\n" if system_prompt else ""
        augmented_system = (
            f"{prefix}Respond with STRICT JSON ONLY matching this schema:\n{schema_json}"
        )
        resp = await self.generate(
            prompt=prompt,
            system_prompt=augmented_system,
            model_id=model_id,
            temperature=0.1,
        )

        raw = resp.text.strip()
        if raw.startswith("```json"):
            raw = raw[7:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

        parsed = json.loads(raw)
        instance = schema_class.model_validate(parsed)
        resp.content_json = parsed
        return instance, resp

    async def embed(
        self,
        *,
        texts: list[str],
        model_id: str = "text-embedding-3-small",
    ) -> list[list[float]]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.base_url}/embeddings",
                json={"input": texts, "model": model_id},
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            resp.raise_for_status()
            data = resp.json()
        return [item["embedding"] for item in data["data"]]
