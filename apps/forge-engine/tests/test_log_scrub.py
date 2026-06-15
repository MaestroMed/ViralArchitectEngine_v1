"""Tests for core/log_scrub — secret redaction in log output."""

import logging

from forge_engine.core.log_scrub import (
    REDACTED,
    SecretScrubFilter,
    install_secret_scrubbing,
    scrub,
)


def test_scrubs_access_token_query_param():
    line = "HTTP Request: GET https://graph.instagram.com/me?fields=id&access_token=ABC123XYZ"
    out = scrub(line)
    assert "ABC123XYZ" not in out
    assert "access_token=" + REDACTED in out
    # Non-secret params survive.
    assert "fields=id" in out


def test_scrubs_bearer_token():
    out = scrub("Authorization: Bearer ya29.SECRETtoken-value_123")
    assert "ya29.SECRETtoken-value_123" not in out
    assert REDACTED in out


def test_scrubs_authorization_header_dict_repr():
    out = scrub("headers={'Authorization': 'Bearer abc.def.ghi'}")
    assert "abc.def.ghi" not in out


def test_scrubs_x_api_key():
    out = scrub("X-API-Key: forge_abcdefghijklmnopqrstuvwxyz123456")
    assert "abcdefghijklmnopqrstuvwxyz123456" not in out
    assert REDACTED in out


def test_scrubs_bare_forge_key():
    out = scrub("client sent key forge_abcdefghijklmnopqrstuvwxyz0123456789")
    assert "forge_abcdefghijklmnopqrstuvwxyz0123456789" not in out


def test_scrubs_refresh_token_and_client_secret():
    out = scrub("refresh_token=RT-123&client_secret=CS-456")
    assert "RT-123" not in out
    assert "CS-456" not in out


def test_no_false_positive_on_clean_text():
    line = "Loaded 3 cached analytics entries"
    assert scrub(line) == line


def test_filter_redacts_record_message():
    f = SecretScrubFilter()
    record = logging.LogRecord(
        name="httpx",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="GET https://x/me?access_token=%s",
        args=("LEAKED_TOKEN",),
        exc_info=None,
    )
    assert f.filter(record) is True
    assert "LEAKED_TOKEN" not in record.getMessage()
    assert REDACTED in record.getMessage()


def test_install_is_idempotent():
    root = logging.getLogger()
    before = len([f for f in root.filters if isinstance(f, SecretScrubFilter)])
    install_secret_scrubbing()
    install_secret_scrubbing()
    after = len([f for f in root.filters if isinstance(f, SecretScrubFilter)])
    # At most one filter of our type on the root logger.
    assert after <= max(before, 1)
