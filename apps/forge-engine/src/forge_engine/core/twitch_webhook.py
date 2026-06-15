"""Twitch EventSub webhook verification.

Lets the engine react the instant EtoStark's stream ends (stream.offline)
instead of waiting up to 30 min for the poll loop. Twitch signs every
request; we verify the HMAC before trusting anything.

Reference: https://dev.twitch.tv/docs/eventsub/handling-webhook-events/
- HMAC message = Twitch-Eventsub-Message-Id + Twitch-Eventsub-Message-Timestamp + raw body
- key = FORGE_TWITCH_WEBHOOK_SECRET
- signature header = "sha256=<hex>"

The pure functions here are unit-tested; the FastAPI route in
endpoints/webhooks.py is a thin wrapper.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os

logger = logging.getLogger(__name__)

MESSAGE_ID_HEADER = "Twitch-Eventsub-Message-Id"
TIMESTAMP_HEADER = "Twitch-Eventsub-Message-Timestamp"
SIGNATURE_HEADER = "Twitch-Eventsub-Message-Signature"
MESSAGE_TYPE_HEADER = "Twitch-Eventsub-Message-Type"

# Message types Twitch sends.
TYPE_VERIFICATION = "webhook_callback_verification"
TYPE_NOTIFICATION = "notification"
TYPE_REVOCATION = "revocation"


def webhook_secret() -> str | None:
    """The shared secret, or None if the integration isn't configured."""
    return os.environ.get("FORGE_TWITCH_WEBHOOK_SECRET") or None


def compute_signature(secret: str, message_id: str, timestamp: str, body: bytes) -> str:
    """Return the expected 'sha256=<hex>' signature for a request."""
    mac = hmac.new(
        secret.encode("utf-8"),
        msg=message_id.encode("utf-8") + timestamp.encode("utf-8") + body,
        digestmod=hashlib.sha256,
    )
    return "sha256=" + mac.hexdigest()


def verify_signature(
    secret: str,
    message_id: str | None,
    timestamp: str | None,
    body: bytes,
    provided_signature: str | None,
) -> bool:
    """Constant-time verify the Twitch signature. False on any missing piece."""
    if not (message_id and timestamp and provided_signature):
        return False
    expected = compute_signature(secret, message_id, timestamp, body)
    # compare_digest guards against timing attacks.
    return hmac.compare_digest(expected, provided_signature)


def is_stream_offline(payload: dict) -> bool:
    """True if a verified notification payload is a stream.offline event."""
    sub = payload.get("subscription") or {}
    return sub.get("type") == "stream.offline"


def extract_broadcaster_login(payload: dict) -> str | None:
    """Pull the broadcaster's login name from a notification, if present."""
    event = payload.get("event") or {}
    return event.get("broadcaster_user_login") or event.get("broadcaster_user_name")
