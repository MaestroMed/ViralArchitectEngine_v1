"""APNs (Apple Push Notification service) sender.

================================================================================
WHAT MEHDI MUST PROVIDE BEFORE ANY PUSH ACTUALLY FIRES
================================================================================
Nothing in this module sends a real notification until the following are set.
Until then every send is a logged NO-OP (the engine never raises because of it).

1. An **APNs Auth Key (.p8)** from the Apple Developer portal:
       Apple Developer  →  Certificates, Identifiers & Profiles  →  Keys  →  +
       Enable the "Apple Push Notifications service (APNs)" capability, create
       the key, and DOWNLOAD the .p8 file (you can only download it ONCE).
   Note its **Key ID** (10 chars, shown next to the key) and keep the .p8 safe.

2. Set these environment variables for the engine process (e.g. in
   apps/forge-engine/.env — they are read with the FORGE_ prefix):

       FORGE_APNS_KEY_PATH   = /absolute/path/to/AuthKey_XXXXXXXXXX.p8
       FORGE_APNS_KEY_ID     = XXXXXXXXXX          # the 10-char Key ID
       FORGE_APNS_TEAM_ID    = ST2RNU2ZX9          # Apple Team ID (fixed)
       FORGE_APNS_BUNDLE_ID  = com.maestromed.forgelab   # app bundle id == apns-topic
       FORGE_APNS_ENV        = sandbox             # or "production"

   - Use FORGE_APNS_ENV=sandbox while running a Debug build from Xcode (tokens
     from a development provisioning profile only work against the sandbox host).
   - Use FORGE_APNS_ENV=production for TestFlight / App Store builds.

If ANY of KEY_PATH / KEY_ID / TEAM_ID / BUNDLE_ID is missing (or the .p8 file
does not exist), the sender logs the reason ONCE and returns without sending —
exactly like the auth layer's "auth off" gating. It NEVER raises into the
pipeline, so wiring the notify call is safe even before the key exists.

================================================================================
HOW THE SEND WORKS (no heavy deps)
================================================================================
APNs is HTTP/2 + a provider JWT (ES256) signed with the .p8 key. We:
  - build/sign the JWT ourselves with `cryptography` (already a dep), cached
    for ~50 min (Apple requires a fresh token at least hourly),
  - POST the alert over HTTP/2 with httpx.

HTTP/2 requires the `h2` package. If it is not installed, http2 is unavailable
and the sender no-ops with a clear log (install with the "apns" extra:
`pip install "httpx[http2]"`). cryptography + httpx are core deps already.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import threading
import time
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

# Apple's APNs HTTP/2 endpoints.
_HOST_SANDBOX = "https://api.sandbox.push.apple.com"
_HOST_PRODUCTION = "https://api.push.apple.com"

# Apple wants the provider JWT refreshed at least hourly; we refresh at 50 min.
_JWT_TTL_SECONDS = 50 * 60

# One-shot guards so we explain *why* we're not sending exactly once, not on
# every clip-ready event (mirrors the auth layer's single-warning style).
_warned_unconfigured = False
_warned_no_http2 = False
_warn_lock = threading.Lock()


@dataclass(frozen=True)
class ApnsConfig:
    key_path: str
    key_id: str
    team_id: str
    bundle_id: str
    use_sandbox: bool

    @property
    def host(self) -> str:
        return _HOST_SANDBOX if self.use_sandbox else _HOST_PRODUCTION


def load_config() -> ApnsConfig | None:
    """Read APNs config from the environment, or None if not fully configured.

    Returns None (and logs once) when any required value is missing or the .p8
    file does not exist — the caller treats None as "no-op".
    """
    key_path = os.environ.get("FORGE_APNS_KEY_PATH", "").strip()
    key_id = os.environ.get("FORGE_APNS_KEY_ID", "").strip()
    team_id = os.environ.get("FORGE_APNS_TEAM_ID", "").strip()
    bundle_id = os.environ.get("FORGE_APNS_BUNDLE_ID", "").strip()
    env = os.environ.get("FORGE_APNS_ENV", "sandbox").strip().lower()

    missing = [
        name
        for name, val in (
            ("FORGE_APNS_KEY_PATH", key_path),
            ("FORGE_APNS_KEY_ID", key_id),
            ("FORGE_APNS_TEAM_ID", team_id),
            ("FORGE_APNS_BUNDLE_ID", bundle_id),
        )
        if not val
    ]
    if missing:
        _warn_once_unconfigured(f"APNs not configured (missing: {', '.join(missing)})")
        return None
    if not os.path.exists(key_path):
        _warn_once_unconfigured(f"APNs key file not found at {key_path}")
        return None

    return ApnsConfig(
        key_path=key_path,
        key_id=key_id,
        team_id=team_id,
        bundle_id=bundle_id,
        use_sandbox=(env != "production"),
    )


def _warn_once_unconfigured(msg: str) -> None:
    global _warned_unconfigured
    with _warn_lock:
        if not _warned_unconfigured:
            logger.info("[APNs] %s — push is a no-op until set.", msg)
            _warned_unconfigured = True


def _warn_once_no_http2(msg: str) -> None:
    global _warned_no_http2
    with _warn_lock:
        if not _warned_no_http2:
            logger.warning("[APNs] %s", msg)
            _warned_no_http2 = True


# --- JWT (ES256) -------------------------------------------------------------

def _b64url(data: bytes) -> str:
    """Base64url without padding (JWT compact form)."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


# Cache: (key_id, team_id, key_path) -> (jwt, issued_at)
_jwt_cache: dict[tuple[str, str, str], tuple[str, float]] = {}
_jwt_lock = threading.Lock()


def build_provider_jwt(config: ApnsConfig, *, now: float | None = None) -> str:
    """Build (and cache ~50 min) the ES256 provider JWT Apple expects.

    Header: {"alg":"ES256","kid":<Key ID>}
    Claims: {"iss":<Team ID>,"iat":<unix seconds>}
    Signed with the .p8 ECDSA P-256 private key, encoded as raw r||s (JOSE),
    NOT DER — Apple rejects DER signatures.

    `cryptography` is a core dependency, so this works in the protected venv
    without PyJWT. `now` is injectable for deterministic tests.
    """
    issued_at = int(now if now is not None else time.time())
    cache_key = (config.key_id, config.team_id, config.key_path)

    with _jwt_lock:
        cached = _jwt_cache.get(cache_key)
        if cached is not None:
            token, ts = cached
            if issued_at - ts < _JWT_TTL_SECONDS:
                return token

    # Lazy import so the module imports even if cryptography were ever absent.
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

    with open(config.key_path, "rb") as fh:
        private_key = serialization.load_pem_private_key(fh.read(), password=None)
    if not isinstance(private_key, ec.EllipticCurvePrivateKey):
        raise ValueError("APNs .p8 key is not an EC private key")

    header = {"alg": "ES256", "kid": config.key_id}
    claims = {"iss": config.team_id, "iat": issued_at}
    signing_input = (
        _b64url(json.dumps(header, separators=(",", ":")).encode())
        + "."
        + _b64url(json.dumps(claims, separators=(",", ":")).encode())
    ).encode("ascii")

    der_sig = private_key.sign(signing_input, ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der_sig)
    # P-256 → 32-byte big-endian r and s, concatenated (JOSE raw form).
    raw_sig = r.to_bytes(32, "big") + s.to_bytes(32, "big")

    token = signing_input.decode("ascii") + "." + _b64url(raw_sig)
    with _jwt_lock:
        _jwt_cache[cache_key] = (token, float(issued_at))
    return token


# --- Sending -----------------------------------------------------------------

def _http2_available() -> bool:
    try:
        import h2  # noqa: F401
        return True
    except Exception:
        return False


def send_alert(
    token: str,
    *,
    title: str,
    body: str,
    config: ApnsConfig | None = None,
    extra: dict | None = None,
    timeout: float = 10.0,
) -> bool:
    """Send one APNs alert to one device token. Returns True on a 200 from Apple.

    No-op (returns False) when APNs is unconfigured or HTTP/2 is unavailable —
    never raises. A non-200 from Apple is logged and returns False; the caller
    can ignore the result (best-effort wake).
    """
    config = config or load_config()
    if config is None:
        return False
    if not _http2_available():
        _warn_once_no_http2(
            'HTTP/2 (h2) unavailable — APNs send skipped. Install with: '
            'pip install "httpx[http2]"'
        )
        return False

    payload: dict = {
        "aps": {
            "alert": {"title": title, "body": body},
            "sound": "default",
        }
    }
    if extra:
        payload.update(extra)

    url = f"{config.host}/3/device/{token}"
    headers = {
        "authorization": f"bearer {build_provider_jwt(config)}",
        "apns-topic": config.bundle_id,
        "apns-push-type": "alert",
        "apns-priority": "10",
    }

    try:
        with httpx.Client(http2=True, timeout=timeout) as client:
            resp = client.post(url, headers=headers, content=json.dumps(payload).encode())
    except Exception as exc:  # network/TLS/etc — best effort, never raise.
        logger.warning("[APNs] send failed for token=…%s: %s", token[-6:], exc)
        return False

    if resp.status_code == 200:
        logger.info("[APNs] delivered to …%s", token[-6:])
        return True

    # 410 = token no longer valid; 400 = bad request (topic/payload). Log detail.
    detail = ""
    try:
        detail = resp.json().get("reason", "")
    except Exception:
        detail = resp.text[:200]
    logger.warning(
        "[APNs] non-200 (%d, %s) for token=…%s", resp.status_code, detail, token[-6:]
    )
    return False


async def notify_clips_ready(project_id: str, count: int) -> int:
    """Fan an APNs "N clips prêts pour QC" alert out to every registered device.

    Loads all DeviceToken rows and sends best-effort. Returns the number of
    devices Apple accepted (0 when APNs is unconfigured — a clean no-op, so it
    is safe to call from inside the running pipeline). Never raises.
    """
    config = load_config()
    if config is None:
        return 0

    # Local imports keep this module import-light and avoid a cycle with models.
    from sqlalchemy import select

    from forge_engine.core.database import async_session_maker
    from forge_engine.models.device_token import DeviceToken

    try:
        async with async_session_maker() as db:
            result = await db.execute(select(DeviceToken))
            devices = result.scalars().all()
    except Exception as exc:
        logger.warning("[APNs] could not load device tokens: %s", exc)
        return 0

    if not devices:
        logger.info("[APNs] no registered devices — skipping clips-ready push.")
        return 0

    title = "Clips prêts ✨"
    body = (
        f"{count} clip prêt pour QC" if count == 1 else f"{count} clips prêts pour QC"
    )
    # Carry the deep-link target so a tap lands in the review queue (matches the
    # local-notification userInfo["url"] contract on the iOS side).
    extra = {"url": "forge-lab://clips", "projectId": project_id}

    sent = 0
    for device in devices:
        if send_alert(device.token, title=title, body=body, config=config, extra=extra):
            sent += 1
    logger.info("[APNs] clips-ready push: %d/%d devices accepted", sent, len(devices))
    return sent
