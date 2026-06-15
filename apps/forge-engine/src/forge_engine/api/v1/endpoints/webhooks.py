"""Inbound webhooks (Twitch EventSub).

POST /v1/webhooks/twitch handles the EventSub handshake + stream.offline
notifications. On a verified stream.offline for the watched channel, it kicks
the auto-pipeline immediately instead of waiting for the poll loop.

Note: this route is intentionally NOT behind the X-API-Key dependency — Twitch
can't send a custom header. It authenticates via the HMAC signature instead.
The router mounts it so that the global /v1 auth dependency does not apply (see
main.py wiring).
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Request, Response

from forge_engine.core import twitch_webhook as tw

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/twitch")
async def twitch_eventsub(request: Request) -> Response:
    secret = tw.webhook_secret()
    if not secret:
        # Integration disabled — don't pretend to accept events.
        return Response(status_code=503, content="Twitch webhook not configured")

    body = await request.body()
    if not tw.verify_signature(
        secret,
        request.headers.get(tw.MESSAGE_ID_HEADER),
        request.headers.get(tw.TIMESTAMP_HEADER),
        body,
        request.headers.get(tw.SIGNATURE_HEADER),
    ):
        logger.warning("Twitch webhook signature verification failed")
        return Response(status_code=403, content="invalid signature")

    msg_type = request.headers.get(tw.MESSAGE_TYPE_HEADER)
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return Response(status_code=400, content="invalid json")

    # 1. Handshake: echo the challenge as plain text.
    if msg_type == tw.TYPE_VERIFICATION:
        challenge = payload.get("challenge", "")
        return Response(status_code=200, content=challenge, media_type="text/plain")

    # 2. Revocation: just acknowledge.
    if msg_type == tw.TYPE_REVOCATION:
        logger.info("Twitch EventSub subscription revoked: %s", payload.get("subscription", {}).get("status"))
        return Response(status_code=204)

    # 3. Notification.
    if msg_type == tw.TYPE_NOTIFICATION:
        if tw.is_stream_offline(payload):
            login = tw.extract_broadcaster_login(payload)
            logger.info("stream.offline for %s — triggering auto-pipeline", login)
            await _trigger_pipeline()
        return Response(status_code=204)

    return Response(status_code=204)


async def _trigger_pipeline() -> None:
    """Nudge the auto-pipeline to check now. Best-effort: never raise back to
    Twitch (which would retry and could storm us)."""
    try:
        from forge_engine.services.auto_pipeline import AutoPipelineService

        pipeline = AutoPipelineService.get_instance()
        # check_now() runs one immediate pass without disturbing the loop.
        await pipeline.check_now()
    except Exception as exc:  # noqa: BLE001 — must not propagate to Twitch
        logger.error("Failed to trigger pipeline from webhook: %s", exc)
