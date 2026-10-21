"""X (Twitter) API publishing adapter for Civic Bot social amplification (PRD §8, §14).

Decouples social post dispatching into a clean provider interface:
- DisabledXPublisher: Explicitly disabled by policy/feature flag.
- SimulatedXPublisher: Sandbox mode (dev, tests, and pre-credential staging).
- LiveXPublisher: Twitter/X API v2 client with OAuth authentication, rate limit
  classification, timeouts, and sanitized error reporting.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import secrets
import time
import urllib.parse
import uuid
from typing import Any, Protocol

import httpx

from tk_api.core.config import Settings
from tk_api.core.logging import log_extra

logger = logging.getLogger("tk_api.social_publisher")


class PublishResult:
    """Outcome of an attempted social broadcast publication."""

    def __init__(
        self,
        *,
        ok: bool,
        external_post_id: str | None = None,
        published_url: str | None = None,
        error: str | None = None,
        retryable: bool = False,
        status_code: int | None = None,
        outcome_unknown: bool = False,
    ) -> None:
        self.ok = ok
        self.external_post_id = external_post_id
        self.published_url = published_url
        self.error = error
        self.retryable = retryable
        self.status_code = status_code
        self.outcome_unknown = outcome_unknown


class XPublisherProtocol(Protocol):
    """Protocol defining the social broadcast publishing contract."""

    async def publish(
        self,
        text: str,
        *,
        report_id: str,
        idempotency_key: str | None = None,
    ) -> PublishResult: ...


class DisabledXPublisher:
    """Rejects broadcasts when the social amplification feature is disabled."""

    async def publish(
        self,
        text: str,
        *,
        report_id: str,
        idempotency_key: str | None = None,
    ) -> PublishResult:
        logger.warning(
            "social broadcast rejected: feature is disabled by configuration",
            extra=log_extra(report_id=report_id),
        )
        return PublishResult(
            ok=False,
            retryable=False,
            outcome_unknown=False,
            error=(
                "Civic bot social broadcasting is currently disabled by administrator "
                "configuration."
            ),
        )


class SimulatedXPublisher:
    """Sandbox publisher for local development, testing, and staging validation.

    Generates a simulated external post ID without contacting live external endpoints.
    Does NOT fabricate a published URL to uphold production truthfulness.
    """

    async def publish(
        self,
        text: str,
        *,
        report_id: str,
        idempotency_key: str | None = None,
    ) -> PublishResult:
        simulated_id = f"sim-{uuid.uuid4().hex[:12]}"
        logger.info(
            "simulated social broadcast executed",
            extra=log_extra(
                report_id=report_id,
                simulated_post_id=simulated_id,
                text_len=len(text),
            ),
        )
        return PublishResult(
            ok=True,
            external_post_id=simulated_id,
            published_url=None,  # Truthful: None in simulation
        )


class LiveXPublisher:
    """Production adapter communicating with X (Twitter) API v2 (/2/tweets)."""

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._client = client

    def _build_oauth1_header(
        self,
        method: str,
        url: str,
        *,
        nonce: str | None = None,
        timestamp: str | None = None,
        extra_params: list[tuple[str, str]] | None = None,
        include_version: bool = True,
    ) -> str:
        """Constructs an RFC 5849 OAuth 1.0a HMAC-SHA1 Authorization header."""
        resolved_nonce = nonce or secrets.token_hex(16)
        resolved_timestamp = timestamp or str(int(time.time()))

        def _percent_encode(s: str) -> str:
            return urllib.parse.quote(str(s), safe="")

        # RFC 5849 §3.4.1.2: Base String URI normalization
        parsed_url = urllib.parse.urlsplit(url)
        scheme = parsed_url.scheme.lower()
        netloc = parsed_url.netloc.lower()
        if scheme == "http" and netloc.endswith(":80"):
            netloc = netloc[:-3]
        elif scheme == "https" and netloc.endswith(":443"):
            netloc = netloc[:-4]
        path = parsed_url.path or "/"
        normalized_uri = f"{scheme}://{netloc}{path}"

        oauth_params: dict[str, str] = {
            "oauth_consumer_key": self._settings.twitter_api_key or "",
            "oauth_nonce": resolved_nonce,
            "oauth_signature_method": "HMAC-SHA1",
            "oauth_timestamp": resolved_timestamp,
            "oauth_token": self._settings.twitter_access_token or "",
        }
        if include_version:
            oauth_params["oauth_version"] = "1.0"

        # RFC 5849 §3.4.1.3: Collect parameters from OAuth header, query string, and extra params
        param_pairs: list[tuple[str, str]] = [
            (_percent_encode(k), _percent_encode(v)) for k, v in oauth_params.items()
        ]
        if parsed_url.query:
            query_items = urllib.parse.parse_qsl(parsed_url.query, keep_blank_values=True)
            for k, v in query_items:
                param_pairs.append((_percent_encode(k), _percent_encode(v)))

        if extra_params:
            for k, v in extra_params:
                param_pairs.append((_percent_encode(k), _percent_encode(v)))

        # RFC 5849 §3.4.1.3.2: Sort parameters by encoded key, then by encoded value
        param_pairs.sort(key=lambda p: (p[0], p[1]))
        param_str = "&".join(f"{k}={v}" for k, v in param_pairs)

        # RFC 5849 §3.4.1.1: Signature Base String
        base_string = (
            f"{method.upper()}&{_percent_encode(normalized_uri)}&{_percent_encode(param_str)}"
        )

        # RFC 5849 §3.4.2: Signing Key
        signing_key = (
            f"{_percent_encode(self._settings.twitter_api_secret or '')}&"
            f"{_percent_encode(self._settings.twitter_access_token_secret or '')}"
        )

        signature_raw = hmac.new(
            signing_key.encode("utf-8"),
            base_string.encode("utf-8"),
            hashlib.sha1,
        ).digest()
        signature = base64.b64encode(signature_raw).decode("utf-8")

        oauth_params["oauth_signature"] = signature
        header_params = [
            f'{_percent_encode(k)}="{_percent_encode(v)}"' for k, v in sorted(oauth_params.items())
        ]
        return f"OAuth {', '.join(header_params)}"

    def _build_headers(self, url: str) -> dict[str, str]:
        # If OAuth 1.0a User Context credentials are fully configured, use RFC 5849 HMAC-SHA1
        if (
            self._settings.twitter_api_key
            and self._settings.twitter_api_secret
            and self._settings.twitter_access_token
            and self._settings.twitter_access_token_secret
        ):
            auth_header = self._build_oauth1_header("POST", url)
            return {
                "Authorization": auth_header,
                "Content-Type": "application/json",
                "User-Agent": "TheekKaroCivicBot/1.0",
            }

        # Check for invalid app-only bearer token configuration for POST /2/tweets
        if self._settings.twitter_bearer_token and not (
            self._settings.twitter_api_key
            and self._settings.twitter_api_secret
            and self._settings.twitter_access_token
            and self._settings.twitter_access_token_secret
        ):
            logger.error(
                "x api credentials invalid for /2/tweets: endpoint requires user context; "
                "app-only bearer token cannot create tweets"
            )
            return {}

        # Fallback to OAuth 2.0 User Context Access Token (if configured without secret)
        if self._settings.twitter_access_token:
            return {
                "Authorization": f"Bearer {self._settings.twitter_access_token}",
                "Content-Type": "application/json",
                "User-Agent": "TheekKaroCivicBot/1.0",
            }

        return {}

    async def publish(
        self,
        text: str,
        *,
        report_id: str,
        idempotency_key: str | None = None,
    ) -> PublishResult:
        url = f"{self._settings.twitter_api_base_url.rstrip('/')}/2/tweets"
        headers = self._build_headers(url)
        if not headers:
            logger.error(
                "live social broadcast failed: missing twitter user-context credentials",
                extra=log_extra(report_id=report_id),
            )
            return PublishResult(
                ok=False,
                retryable=False,
                outcome_unknown=False,
                error="X API user-context credentials are not configured in environment.",
            )

        payload: dict[str, Any] = {"text": text}

        async def _do_post(c: httpx.AsyncClient) -> PublishResult:
            try:
                resp = await c.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=self._settings.twitter_request_timeout_seconds,
                )
                if resp.status_code == 201:
                    data = resp.json()
                    tweet_id = str(data.get("data", {}).get("id") or "")
                    if tweet_id:
                        published_url = f"https://x.com/TheekKaro/status/{tweet_id}"
                        logger.info(
                            "x post published successfully",
                            extra=log_extra(report_id=report_id, tweet_id=tweet_id),
                        )
                        return PublishResult(
                            ok=True,
                            external_post_id=tweet_id,
                            published_url=published_url,
                            status_code=201,
                            outcome_unknown=False,
                        )
                    return PublishResult(
                        ok=False,
                        retryable=False,
                        outcome_unknown=False,
                        error="X API returned 201 but response payload missing tweet ID.",
                        status_code=201,
                    )

                if resp.status_code == 429:
                    logger.warning(
                        "x api rate limit exceeded",
                        extra=log_extra(report_id=report_id, status_code=429),
                    )
                    return PublishResult(
                        ok=False,
                        retryable=True,
                        outcome_unknown=False,
                        error="X API rate limit exceeded.",
                        status_code=429,
                    )

                if resp.status_code in (500, 502, 503, 504):
                    logger.warning(
                        "x api upstream server error",
                        extra=log_extra(report_id=report_id, status_code=resp.status_code),
                    )
                    return PublishResult(
                        ok=False,
                        retryable=True,
                        outcome_unknown=False,
                        error=f"X API server error ({resp.status_code}).",
                        status_code=resp.status_code,
                    )

                # Permanent client error (400, 401, 403, etc.)
                err_text = resp.text[:200]
                logger.error(
                    "x api client error",
                    extra=log_extra(
                        report_id=report_id,
                        status_code=resp.status_code,
                        error_snippet=err_text,
                    ),
                )
                return PublishResult(
                    ok=False,
                    retryable=False,
                    outcome_unknown=False,
                    error=f"X API rejected request ({resp.status_code}): {err_text}",
                    status_code=resp.status_code,
                )

            except httpx.ConnectTimeout as exc:
                # Connection timed out before request could be transmitted
                logger.warning(
                    "x api connect timeout (safe to retry)",
                    extra=log_extra(report_id=report_id, error=str(exc)),
                )
                return PublishResult(
                    ok=False,
                    retryable=True,
                    outcome_unknown=False,
                    error="Connection timed out connecting to X API.",
                )
            except httpx.ConnectError as exc:
                # Socket/TCP connection failed before transmission
                logger.warning(
                    "x api connect error (safe to retry)",
                    extra=log_extra(report_id=report_id, error=str(exc)),
                )
                return PublishResult(
                    ok=False,
                    retryable=True,
                    outcome_unknown=False,
                    error=f"Network connection error to X API: {type(exc).__name__}",
                )
            except (httpx.TimeoutException, httpx.ReadTimeout, httpx.WriteTimeout) as exc:
                # In-flight timeout after connection: outcome is AMBIGUOUS
                logger.warning(
                    "x api request timed out post-transmission (ambiguous outcome - do not retry)",
                    extra=log_extra(report_id=report_id, error=str(exc)),
                )
                return PublishResult(
                    ok=False,
                    retryable=False,
                    outcome_unknown=True,
                    error="X API request timed out after transmission; outcome is ambiguous.",
                )
            except httpx.RequestError as exc:
                # In-flight network error during or after transmission
                logger.warning(
                    "x api request error post-connect (ambiguous outcome - do not retry)",
                    extra=log_extra(report_id=report_id, error=str(exc)),
                )
                return PublishResult(
                    ok=False,
                    retryable=False,
                    outcome_unknown=True,
                    error=f"Network error during X API request: {type(exc).__name__}",
                )

        if self._client is not None:
            return await _do_post(self._client)
        else:
            async with httpx.AsyncClient() as client:
                return await _do_post(client)


def get_social_publisher(settings: Settings) -> XPublisherProtocol:
    """Returns the configured X publisher implementation based on runtime settings."""
    if settings.social_broadcast_mode == "disabled":
        return DisabledXPublisher()
    if settings.social_broadcast_mode == "live":
        return LiveXPublisher(settings)
    return SimulatedXPublisher()
