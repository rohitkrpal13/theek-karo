"""Communication provider abstraction (Phase 26).

Provider architecture:
CommunicationProvider
 ├── InAppProvider
 ├── EmailProvider
 ├── PushProvider
 ├── SMSProvider
 ├── WhatsAppProvider
 └── FutureProvider

Providers are pluggable; business logic never couples to a specific provider.
Each provider implements send(), check_health(), and estimate_cost().
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class DeliveryResult:
    """Result of a provider send attempt."""

    ok: bool
    provider_message_id: str | None = None
    error: str | None = None
    cost: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class CommunicationProvider(ABC):
    """Abstract base for all communication providers."""

    @property
    @abstractmethod
    def channel(self) -> str:
        """Channel identifier (in_app, email, sms, push, whatsapp)."""

    @abstractmethod
    def send(
        self,
        *,
        to: str,
        subject: str | None = None,
        body: str,
        html: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DeliveryResult:
        """Send a message. Returns DeliveryResult."""

    def check_health(self) -> dict[str, Any]:
        """Check provider health. Override for real health checks."""
        return {"status": "healthy", "provider": self.channel}

    def estimate_cost(self, *, to: str, body: str) -> float | None:
        """Estimate delivery cost. Override for real cost estimation."""
        return None


class InAppProvider(CommunicationProvider):
    """In-app notifications are already written to the DB by the service layer.
    This provider is a no-op for the delivery pipeline — the notification
    record IS the delivery.
    """

    @property
    def channel(self) -> str:
        return "in_app"

    def send(
        self,
        *,
        to: str,
        subject: str | None = None,
        body: str,
        html: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DeliveryResult:
        logger.debug("InApp notification for user %s: %s", to, subject or body[:50])
        return DeliveryResult(ok=True)


class EmailProvider(CommunicationProvider):
    """Email provider using configurable backend. In production, integrates
    with SMTP, SendGrid, SES, or similar. In dev/test, logs to console.
    """

    def __init__(self, *, backend: str = "console", config: dict[str, Any] | None = None):
        self._backend = backend
        self._config = config or {}

    @property
    def channel(self) -> str:
        return "email"

    def send(
        self,
        *,
        to: str,
        subject: str | None = None,
        body: str,
        html: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DeliveryResult:
        if self._backend == "console":
            logger.info("EMAIL to=%s subject=%s body=%s", to, subject, body[:100])
            return DeliveryResult(ok=True, provider_message_id=f"console-{to}")
        # Production: integrate with actual email provider
        logger.warning(
            "Email provider '%s' not configured, message queued for retry", self._backend
        )
        return DeliveryResult(ok=False, error=f"provider '{self._backend}' not configured")

    def check_health(self) -> dict[str, Any]:
        return {
            "status": "healthy" if self._backend == "console" else "unknown",
            "provider": "email",
            "backend": self._backend,
        }


class SMSProvider(CommunicationProvider):
    """SMS provider. In dev/test, logs to console. Production integrates
    with DLT-registered SMS gateway.
    """

    def __init__(self, *, backend: str = "console", config: dict[str, Any] | None = None):
        self._backend = backend
        self._config = config or {}

    @property
    def channel(self) -> str:
        return "sms"

    def send(
        self,
        *,
        to: str,
        subject: str | None = None,
        body: str,
        html: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DeliveryResult:
        if self._backend == "console":
            logger.info("SMS to=%s body=%s", to, body[:100])
            return DeliveryResult(ok=True, provider_message_id=f"console-sms-{to}")
        logger.warning("SMS provider '%s' not configured", self._backend)
        return DeliveryResult(ok=False, error=f"provider '{self._backend}' not configured")

    def estimate_cost(self, *, to: str, body: str) -> float:
        return 0.05  # approximate per-SMS cost

    def check_health(self) -> dict[str, Any]:
        return {
            "status": "healthy" if self._backend == "console" else "unknown",
            "provider": "sms",
            "backend": self._backend,
        }


class PushProvider(CommunicationProvider):
    """Push notification provider (web/mobile). In dev/test, logs to console."""

    def __init__(self, *, backend: str = "console", config: dict[str, Any] | None = None):
        self._backend = backend
        self._config = config or {}

    @property
    def channel(self) -> str:
        return "push"

    def send(
        self,
        *,
        to: str,
        subject: str | None = None,
        body: str,
        html: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DeliveryResult:
        if self._backend == "console":
            logger.info("PUSH to=%s title=%s body=%s", to, subject, body[:100])
            return DeliveryResult(ok=True, provider_message_id=f"console-push-{to}")
        logger.warning("Push provider '%s' not configured", self._backend)
        return DeliveryResult(ok=False, error=f"provider '{self._backend}' not configured")

    def check_health(self) -> dict[str, Any]:
        return {
            "status": "healthy" if self._backend == "console" else "unknown",
            "provider": "push",
            "backend": self._backend,
        }


class WhatsAppProvider(CommunicationProvider):
    """WhatsApp Business API provider. Placeholder for future implementation.
    Never use unofficial WhatsApp automation.
    """

    def __init__(self, *, backend: str = "console", config: dict[str, Any] | None = None):
        self._backend = backend
        self._config = config or {}

    @property
    def channel(self) -> str:
        return "whatsapp"

    def send(
        self,
        *,
        to: str,
        subject: str | None = None,
        body: str,
        html: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DeliveryResult:
        if self._backend == "console":
            logger.info("WHATSAPP to=%s body=%s", to, body[:100])
            return DeliveryResult(ok=True, provider_message_id=f"console-wa-{to}")
        logger.warning("WhatsApp provider not configured — requires official Business API")
        return DeliveryResult(ok=False, error="WhatsApp provider not configured")

    def estimate_cost(self, *, to: str, body: str) -> float:
        return 0.10  # approximate per-message cost

    def check_health(self) -> dict[str, Any]:
        return {
            "status": "unknown",
            "provider": "whatsapp",
            "note": "requires official Business API integration",
        }


def build_providers(settings: Any | None = None) -> dict[str, CommunicationProvider]:
    """Build the default provider set. In production, read from settings."""
    return {
        "in_app": InAppProvider(),
        "email": EmailProvider(backend="console"),
        "sms": SMSProvider(backend="console"),
        "push": PushProvider(backend="console"),
        "whatsapp": WhatsAppProvider(backend="console"),
    }
