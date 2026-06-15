"""Redact secrets from log records before they are emitted.

Why (P0 audit fix): httpx logs every request line at INFO, e.g.
``HTTP Request: GET https://graph.instagram.com/me?...&access_token=XXXX``.
Instagram/TikTok pass the OAuth token as a *query parameter*, so the raw token
leaked into logs. We also defensively scrub ``Authorization: Bearer …`` and our
own ``X-API-Key`` in case any handler is configured to log headers.

The scrubbing is implemented as a ``logging.Filter`` so it works regardless of
which logger emits the line. :func:`install_secret_scrubbing` attaches it to the
root logger (covering all child loggers, incl. ``httpx``/``httpcore``/``uvicorn``).
"""

from __future__ import annotations

import logging
import re

REDACTED = "***REDACTED***"

# Sensitive query-string / form keys → redact their value up to the next
# delimiter (& , space, quote, brace).
_QUERY_KEYS = (
    "access_token",
    "refresh_token",
    "client_secret",
    "id_token",
    "code",
    "password",
    "secret",
    "api_key",
    "apikey",
    "token",
    "key",
)

_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # key=value in URLs / query strings / form bodies
    (
        re.compile(
            r"(?i)\b(" + "|".join(_QUERY_KEYS) + r")=([^&\s'\"}]+)",
        ),
        r"\1=" + REDACTED,
    ),
    # Authorization: Bearer <token>  /  "Authorization": "Bearer <token>"
    (re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/\-]+=*"), r"\1" + REDACTED),
    # Generic "Authorization": "<value>" or Authorization=<value>
    (
        re.compile(r"(?i)(authorization[\"']?\s*[:=]\s*[\"']?)([^\"'\s,}]+)"),
        r"\1" + REDACTED,
    ),
    # Our own LAN API key header, however it is rendered.
    (
        re.compile(r"(?i)(x-api-key[\"']?\s*[:=]\s*[\"']?)([^\"'\s,}]+)"),
        r"\1" + REDACTED,
    ),
    # Bare forge_ API keys appearing anywhere in a message.
    (re.compile(r"\bforge_[A-Za-z0-9_\-]{20,}"), REDACTED),
)


def scrub(text: str) -> str:
    """Return *text* with known secret shapes replaced by a redaction marker."""
    for pattern, repl in _PATTERNS:
        text = pattern.sub(repl, text)
    return text


class SecretScrubFilter(logging.Filter):
    """Logging filter that rewrites each record's rendered message in place."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:
            # If formatting fails, leave the record untouched for the handler.
            return True
        scrubbed = scrub(message)
        if scrubbed != message:
            record.msg = scrubbed
            record.args = ()
        return True


_FILTER = SecretScrubFilter()


def install_secret_scrubbing() -> None:
    """Attach the scrubbing filter to the root logger (idempotent).

    Filters on a logger only apply to records *emitted through that logger*, so
    we also attach to the root's handlers to catch records that propagate up.
    """
    root = logging.getLogger()
    if not any(isinstance(f, SecretScrubFilter) for f in root.filters):
        root.addFilter(_FILTER)
    for handler in root.handlers:
        if not any(isinstance(f, SecretScrubFilter) for f in handler.filters):
            handler.addFilter(_FILTER)
