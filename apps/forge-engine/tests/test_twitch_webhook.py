"""Twitch EventSub signature verification + payload helpers."""

from __future__ import annotations

from forge_engine.core import twitch_webhook as tw

SECRET = "s3cr3t-shared-key"


def test_compute_and_verify_roundtrip():
    msg_id = "abc-123"
    ts = "2026-06-15T01:00:00Z"
    body = b'{"hello":"world"}'
    sig = tw.compute_signature(SECRET, msg_id, ts, body)
    assert sig.startswith("sha256=")
    assert tw.verify_signature(SECRET, msg_id, ts, body, sig) is True


def test_verify_rejects_tampered_body():
    msg_id, ts = "id", "ts"
    good = tw.compute_signature(SECRET, msg_id, ts, b"original")
    assert tw.verify_signature(SECRET, msg_id, ts, b"tampered", good) is False


def test_verify_rejects_wrong_secret():
    msg_id, ts, body = "id", "ts", b"x"
    sig = tw.compute_signature("other-secret", msg_id, ts, body)
    assert tw.verify_signature(SECRET, msg_id, ts, body, sig) is False


def test_verify_rejects_missing_pieces():
    body = b"x"
    sig = tw.compute_signature(SECRET, "id", "ts", body)
    assert tw.verify_signature(SECRET, None, "ts", body, sig) is False
    assert tw.verify_signature(SECRET, "id", None, body, sig) is False
    assert tw.verify_signature(SECRET, "id", "ts", body, None) is False


def test_is_stream_offline():
    assert tw.is_stream_offline({"subscription": {"type": "stream.offline"}}) is True
    assert tw.is_stream_offline({"subscription": {"type": "stream.online"}}) is False
    assert tw.is_stream_offline({}) is False


def test_extract_broadcaster_login():
    payload = {"event": {"broadcaster_user_login": "etostark", "broadcaster_user_name": "EtoStark"}}
    assert tw.extract_broadcaster_login(payload) == "etostark"
    # Falls back to display name.
    assert tw.extract_broadcaster_login({"event": {"broadcaster_user_name": "EtoStark"}}) == "EtoStark"
    assert tw.extract_broadcaster_login({}) is None


def test_webhook_secret_env(monkeypatch):
    monkeypatch.delenv("FORGE_TWITCH_WEBHOOK_SECRET", raising=False)
    assert tw.webhook_secret() is None
    monkeypatch.setenv("FORGE_TWITCH_WEBHOOK_SECRET", "k")
    assert tw.webhook_secret() == "k"
