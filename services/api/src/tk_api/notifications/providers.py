"""Notification providers (API.md §9).

Console sandbox is the default channel for SMS/email (dev + tests): it logs the
rendered message through the standard logger so compose delivers are inspectable
in ``docker compose logs worker``. The DLT-registered India SMS provider and a
transactional email provider plug in behind the same protocol (ROADMAP §6 open
question; SECURITY.md monitors this surface). In-app delivery writes the
``notifications`` history row directly.
"""

from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage
from typing import Any, Protocol

from tk_api.core.config import Settings
from tk_api.core.logging import log_extra

logger = logging.getLogger("tk_api.notifications")


class DeliveryResult:
    def __init__(self, provider_message_id: str | None = None, error: str | None = None) -> None:
        self.provider_message_id = provider_message_id
        self.error = error

    @property
    def ok(self) -> bool:
        return self.error is None


class SmsProvider(Protocol):
    def send(self, *, to_contact: str, body: str, message_id: str) -> DeliveryResult: ...


class EmailProvider(Protocol):
    def send(
        self, *, to_contact: str, subject: str, body: str, message_id: str
    ) -> DeliveryResult: ...


class ConsoleSmsProvider:
    """Sandbox: never leaves the process; the message is structured-logged."""

    def send(self, *, to_contact: str, body: str, message_id: str) -> DeliveryResult:
        logger.info(
            "sms sandbox delivery",
            extra=log_extra(to=to_contact, message_id=message_id, body=body[:200]),
        )
        return DeliveryResult(provider_message_id=message_id)


class ConsoleEmailProvider:
    """Sandbox: never leaves the process; the message is structured-logged."""

    def send(self, *, to_contact: str, subject: str, body: str, message_id: str) -> DeliveryResult:
        logger.info(
            "email sandbox delivery",
            extra=log_extra(to=to_contact, subject=subject, message_id=message_id),
        )
        return DeliveryResult(provider_message_id=message_id)


class SmtpEmailProvider:
    """Transaction email delivery via SMTP (standard library, STARTTLS).

    Used for auth-critical mail (verification links) and application
    notifications. Requires a configured relay: ``TK_SMTP_HOST`` and
    ``TK_SMTP_FROM`` (plus ``TK_SMTP_USER``/``TK_SMTP_PASSWORD`` for
    authenticated relays).
    """

    def __init__(
        self,
        *,
        host: str,
        port: int,
        from_addr: str,
        user: str | None = None,
        password: str | None = None,
        starttls: bool = True,
    ) -> None:
        self.host = host
        self.port = port
        self.from_addr = from_addr
        self.user = user
        self.password = password
        self.starttls = starttls

    def send(self, *, to_contact: str, subject: str, body: str, message_id: str) -> DeliveryResult:
        try:
            self._send_sync(to_contact, subject, body)
            return DeliveryResult(provider_message_id=message_id)
        except (smtplib.SMTPException, OSError) as exc:
            logger.error(
                "email delivery failed",
                extra=log_extra(to=to_contact, subject=subject, error=str(exc)),
            )
            return DeliveryResult(error=str(exc))

    def _send_sync(self, to_contact: str, subject: str, body: str) -> None:
        message = EmailMessage()
        message["From"] = self.from_addr
        message["To"] = to_contact
        message["Subject"] = subject
        message.set_content(body)
        context = ssl.create_default_context()
        with smtplib.SMTP(self.host, self.port, timeout=15) as client:
            if self.starttls:
                client.starttls(context=context)
            if self.user:
                client.login(self.user, self.password or "")
            client.send_message(message)


def build_providers(settings: Settings) -> dict[str, Any]:
    providers: dict[str, Any] = {}
    if settings.sms_provider == "console":
        providers["sms"] = ConsoleSmsProvider()
    if settings.email_provider == "console":
        providers["email"] = ConsoleEmailProvider()
    elif settings.email_provider == "smtp":
        if not (settings.smtp_host and settings.smtp_from):
            raise ValueError("TK_EMAIL_PROVIDER=smtp requires TK_SMTP_HOST and TK_SMTP_FROM.")
        providers["email"] = SmtpEmailProvider(
            host=settings.smtp_host,
            port=settings.smtp_port,
            from_addr=settings.smtp_from,
            user=settings.smtp_user,
            password=settings.smtp_password,
            starttls=settings.smtp_starttls,
        )
    if settings.is_production and isinstance(providers.get("email"), ConsoleEmailProvider):
        raise ValueError(
            "In production/staging, TK_EMAIL_PROVIDER must be configured "
            "(console is not allowed); notifications SMS stays an open ROADMAP item."
        )
    return providers
