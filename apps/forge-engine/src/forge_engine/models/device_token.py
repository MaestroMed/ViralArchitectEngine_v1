"""Device token model — APNs (and future FCM) push registration.

When the iOS app launches it calls ``registerForRemoteNotifications()``; Apple
hands back an opaque device token which the app POSTs to
``/v1/devices/register``. We persist one row per token so the engine can wake a
backgrounded phone with an APNs alert ("N clips prêts pour QC") the moment the
auto-pipeline finishes queueing clips.

Nothing here sends a push — that lives in ``services/apns.py``. This is purely
the registry of *who* to notify.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from forge_engine.core.database import Base


class DeviceToken(Base):
    """A push-notification target for one app install.

    ``token`` is the hex device token from APNs (unique — re-registering the
    same device upserts the row and bumps ``last_seen_at`` rather than
    duplicating). ``platform`` is "ios" today; ``bundle_id`` lets one engine
    serve multiple app builds (e.g. dev vs prod bundle ids) and is needed to
    pick the right ``apns-topic`` when sending.
    """

    __tablename__ = "device_tokens"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    # The APNs device token (hex). Unique so re-registration upserts.
    token: Mapped[str] = mapped_column(String(200), nullable=False, unique=True, index=True)
    # "ios" today; reserved for "android"/FCM later.
    platform: Mapped[str] = mapped_column(String(20), nullable=False, default="ios")
    # App bundle id, e.g. com.maestromed.forgelab — becomes the apns-topic.
    bundle_id: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "platform": self.platform,
            "bundleId": self.bundle_id,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "lastSeenAt": self.last_seen_at.isoformat() if self.last_seen_at else None,
        }
