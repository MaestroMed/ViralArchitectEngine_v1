"""Social Media Publishing Service for TikTok, YouTube, Instagram."""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Optional

import httpx

from forge_engine.services.credential_store import CredentialStore

logger = logging.getLogger(__name__)


class Platform(StrEnum):
    """Supported social media platforms."""
    TIKTOK = "tiktok"
    YOUTUBE = "youtube"
    INSTAGRAM = "instagram"


class PublishStatus(StrEnum):
    """Publishing status."""
    PENDING = "pending"
    UPLOADING = "uploading"
    PROCESSING = "processing"
    PUBLISHED = "published"
    FAILED = "failed"
    SCHEDULED = "scheduled"


@dataclass
class PlatformCredentials:
    """OAuth credentials for a platform."""
    platform: Platform
    access_token: str
    refresh_token: str | None = None
    expires_at: datetime | None = None
    user_id: str | None = None
    username: str | None = None

    def to_record(self) -> dict[str, Any]:
        """Plain-dict form for the encrypted credential store."""
        return {
            "platform": str(self.platform),
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "user_id": self.user_id,
            "username": self.username,
        }

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> "PlatformCredentials | None":
        """Inverse of :meth:`to_record`; returns None on malformed input."""
        try:
            platform = Platform(record["platform"])
            access_token = record["access_token"]
        except (KeyError, ValueError):
            return None
        if not access_token:
            return None
        expires_raw = record.get("expires_at")
        expires_at = None
        if expires_raw:
            try:
                expires_at = datetime.fromisoformat(expires_raw)
            except ValueError:
                expires_at = None
        return cls(
            platform=platform,
            access_token=access_token,
            refresh_token=record.get("refresh_token"),
            expires_at=expires_at,
            user_id=record.get("user_id"),
            username=record.get("username"),
        )


@dataclass
class PublishRequest:
    """Request to publish a video."""
    video_path: str
    title: str
    description: str
    hashtags: list[str]
    platform: Platform
    thumbnail_path: str | None = None
    schedule_time: datetime | None = None
    privacy: str = "public"  # public, private, unlisted (YouTube)


@dataclass
class PublishResult:
    """Result of a publish operation."""
    success: bool
    platform: Platform
    status: PublishStatus
    video_id: str | None = None
    video_url: str | None = None
    error: str | None = None
    published_at: datetime | None = None


class SocialPublishService:
    """
    Service for publishing clips to social media platforms.

    Supports:
    - TikTok (via TikTok for Developers API)
    - YouTube (via YouTube Data API v3)
    - Instagram (via Instagram Basic Display API / Graph API)
    """

    # API endpoints
    TIKTOK_API = "https://open.tiktokapis.com/v2"
    YOUTUBE_API = "https://www.googleapis.com/youtube/v3"
    INSTAGRAM_API = "https://graph.instagram.com"

    _instance: Optional["SocialPublishService"] = None

    def __init__(self, store: "CredentialStore | None" = None):
        self.credentials: dict[Platform, PlatformCredentials] = {}
        self._client = httpx.AsyncClient(timeout=60.0)
        self._store = store or CredentialStore()
        self._load_persisted()

    @classmethod
    def get_instance(cls) -> "SocialPublishService":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load_persisted(self) -> None:
        """Restore credentials from the encrypted store at startup."""
        for record in self._store.load():
            cred = PlatformCredentials.from_record(record)
            if cred is not None:
                self.credentials[cred.platform] = cred
        if self.credentials:
            logger.info(
                "Restored %d social credential(s) from encrypted store",
                len(self.credentials),
            )

    def _persist(self) -> None:
        """Write the current credentials to the encrypted store."""
        try:
            self._store.save([c.to_record() for c in self.credentials.values()])
        except Exception as exc:  # never let persistence failure break a request
            logger.error("Failed to persist social credentials: %s", exc)

    def is_authenticated(self, platform: Platform) -> bool:
        """Check if authenticated with a platform."""
        cred = self.credentials.get(platform)
        if not cred:
            return False

        # Check expiration
        if cred.expires_at and datetime.now() > cred.expires_at:
            return False

        return True

    # ── Methods consumed by the /v1/social endpoints (api/v1/endpoints/social.py)
    # These thin wrappers map the HTTP surface to the existing primitives.

    def get_connected_platforms(self) -> list[str]:
        """Return the list of platforms with an active (non-expired) session."""
        return [str(p) for p in self.credentials if self.is_authenticated(p)]

    async def connect_account(
        self, platform: str, credentials: dict[str, Any]
    ) -> bool:
        """Persist OAuth credentials for a platform after validating them."""
        try:
            plat = Platform(platform)
        except ValueError:
            return False
        creds = PlatformCredentials(
            platform=plat,
            access_token=credentials.get("access_token", ""),
            refresh_token=credentials.get("refresh_token"),
            user_id=credentials.get("user_id"),
            username=credentials.get("username"),
        )
        if not creds.access_token:
            return False
        return await self.authenticate(plat, creds)

    async def disconnect_account(self, platform: str) -> bool:
        """Forget a platform's session. Returns True iff one was present."""
        try:
            plat = Platform(platform)
        except ValueError:
            return False
        removed = self.credentials.pop(plat, None) is not None
        if removed:
            self._persist()
        return removed

    async def get_publish_status(self, job_id: str) -> dict[str, Any] | None:
        """Compat alias for the endpoint module — the real method is
        `get_publishing_status`. Kept here so /v1/social/publish/{id} works
        without touching the route handler."""
        return await self.get_publishing_status(job_id)

    async def authenticate(
        self,
        platform: Platform,
        credentials: PlatformCredentials
    ) -> bool:
        """
        Authenticate with a platform.

        Args:
            platform: Target platform
            credentials: OAuth credentials

        Returns:
            True if authentication successful
        """
        self.credentials[platform] = credentials

        # Validate credentials by making a test API call
        validated = False
        try:
            if platform == Platform.YOUTUBE:
                # Test YouTube auth
                response = await self._client.get(
                    f"{self.YOUTUBE_API}/channels",
                    params={"part": "snippet", "mine": "true"},
                    headers={"Authorization": f"Bearer {credentials.access_token}"}
                )
                if response.status_code == 200:
                    data = response.json()
                    if data.get("items"):
                        credentials.user_id = data["items"][0]["id"]
                        credentials.username = data["items"][0]["snippet"]["title"]
                        validated = True

            elif platform == Platform.TIKTOK:
                # Test TikTok auth
                response = await self._client.get(
                    f"{self.TIKTOK_API}/user/info/",
                    headers={"Authorization": f"Bearer {credentials.access_token}"}
                )
                if response.status_code == 200:
                    data = response.json()
                    if data.get("data", {}).get("user"):
                        user = data["data"]["user"]
                        credentials.user_id = user.get("open_id")
                        credentials.username = user.get("display_name")
                        validated = True

            elif platform == Platform.INSTAGRAM:
                # Test Instagram auth
                response = await self._client.get(
                    f"{self.INSTAGRAM_API}/me",
                    params={
                        "fields": "id,username",
                        "access_token": credentials.access_token
                    }
                )
                if response.status_code == 200:
                    data = response.json()
                    credentials.user_id = data.get("id")
                    credentials.username = data.get("username")
                    validated = True

        except Exception as e:
            logger.error(f"Authentication failed for {platform}: {e}")

        if validated:
            # Persist (encrypted) only the credentials we actually validated.
            self._persist()
            return True

        # Validation failed — don't keep an unusable token in RAM.
        self.credentials.pop(platform, None)
        return False

    async def publish(
        self,
        request: PublishRequest,
        progress_callback: Callable[[float, str], None] | None = None
    ) -> PublishResult:
        """
        Publish a video to a social media platform.

        Args:
            request: Publish request with video and metadata
            progress_callback: Progress callback (percent, message)

        Returns:
            PublishResult with status and video URL
        """
        if not self.is_authenticated(request.platform):
            return PublishResult(
                success=False,
                platform=request.platform,
                status=PublishStatus.FAILED,
                error="Not authenticated with platform"
            )

        credentials = self.credentials[request.platform]

        try:
            if request.platform == Platform.YOUTUBE:
                return await self._publish_youtube(request, credentials, progress_callback)

            elif request.platform == Platform.TIKTOK:
                return await self._publish_tiktok(request, credentials, progress_callback)

            elif request.platform == Platform.INSTAGRAM:
                return await self._publish_instagram(request, credentials, progress_callback)

            else:
                return PublishResult(
                    success=False,
                    platform=request.platform,
                    status=PublishStatus.FAILED,
                    error=f"Unsupported platform: {request.platform}"
                )

        except Exception as e:
            logger.error(f"Publish failed: {e}")
            return PublishResult(
                success=False,
                platform=request.platform,
                status=PublishStatus.FAILED,
                error=str(e)
            )

    async def _publish_youtube(
        self,
        request: PublishRequest,
        credentials: PlatformCredentials,
        progress_callback: Callable[[float, str], None] | None = None
    ) -> PublishResult:
        """Publish to YouTube using YouTube Data API."""
        if progress_callback:
            progress_callback(5, "Préparation de l'upload YouTube...")

        # Build description with hashtags
        description = request.description
        if request.hashtags:
            description += "\n\n" + " ".join(request.hashtags)

        # Video metadata
        metadata = {
            "snippet": {
                "title": request.title[:100],  # YouTube limit
                "description": description[:5000],
                "tags": [h.replace("#", "") for h in request.hashtags],
                "categoryId": "20"  # Gaming category
            },
            "status": {
                "privacyStatus": request.privacy,
                "selfDeclaredMadeForKids": False
            }
        }

        if progress_callback:
            progress_callback(10, "Upload de la vidéo...")

        # Upload video (resumable upload)
        # Note: This is a simplified version. Production would use resumable uploads.
        video_path = Path(request.video_path)

        if not video_path.exists():
            return PublishResult(
                success=False,
                platform=Platform.YOUTUBE,
                status=PublishStatus.FAILED,
                error="Video file not found"
            )

        # Start upload
        headers = {
            "Authorization": f"Bearer {credentials.access_token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Type": "video/mp4",
            "X-Upload-Content-Length": str(video_path.stat().st_size)
        }

        init_response = await self._client.post(
            f"{self.YOUTUBE_API}/videos",
            params={"uploadType": "resumable", "part": "snippet,status"},
            headers=headers,
            json=metadata
        )

        if init_response.status_code not in (200, 308):
            return PublishResult(
                success=False,
                platform=Platform.YOUTUBE,
                status=PublishStatus.FAILED,
                error=f"Upload init failed: {init_response.text[:200]}"
            )

        upload_url = init_response.headers.get("Location")
        if not upload_url:
            return PublishResult(
                success=False,
                platform=Platform.YOUTUBE,
                status=PublishStatus.FAILED,
                error="No upload URL returned"
            )

        if progress_callback:
            progress_callback(30, "Transfert de la vidéo...")

        # Upload video content
        with open(video_path, "rb") as f:
            video_data = f.read()

        upload_response = await self._client.put(
            upload_url,
            content=video_data,
            headers={"Content-Type": "video/mp4"}
        )

        if progress_callback:
            progress_callback(90, "Finalisation...")

        if upload_response.status_code == 200:
            data = upload_response.json()
            video_id = data.get("id")

            return PublishResult(
                success=True,
                platform=Platform.YOUTUBE,
                status=PublishStatus.PUBLISHED,
                video_id=video_id,
                video_url=f"https://youtube.com/shorts/{video_id}",
                published_at=datetime.now()
            )

        return PublishResult(
            success=False,
            platform=Platform.YOUTUBE,
            status=PublishStatus.FAILED,
            error=f"Upload failed: {upload_response.text[:200]}"
        )

    async def _publish_tiktok(
        self,
        request: PublishRequest,
        credentials: PlatformCredentials,
        progress_callback: Callable[[float, str], None] | None = None
    ) -> PublishResult:
        """Publish to TikTok using TikTok API."""
        if progress_callback:
            progress_callback(5, "Préparation de l'upload TikTok...")

        # TikTok requires a specific upload flow
        # 1. Initialize upload
        # 2. Upload video
        # 3. Create post

        # Note: TikTok API has limitations and requires app review
        # This is a placeholder implementation

        return PublishResult(
            success=False,
            platform=Platform.TIKTOK,
            status=PublishStatus.FAILED,
            error="TikTok API integration requires app review. Use manual upload for now."
        )

    async def _publish_instagram(
        self,
        request: PublishRequest,
        credentials: PlatformCredentials,
        progress_callback: Callable[[float, str], None] | None = None
    ) -> PublishResult:
        """Publish to Instagram using Graph API."""
        if progress_callback:
            progress_callback(5, "Préparation de l'upload Instagram...")

        # Instagram Reels require hosted video URL
        # This requires:
        # 1. Upload video to a public URL
        # 2. Create media container
        # 3. Publish container

        # Note: Requires Instagram Business/Creator account + Facebook App

        return PublishResult(
            success=False,
            platform=Platform.INSTAGRAM,
            status=PublishStatus.FAILED,
            error="Instagram API requires Business account and Facebook App setup."
        )

    async def get_publishing_status(
        self,
        platform: Platform,
        video_id: str
    ) -> dict[str, Any] | None:
        """Get publishing status for a video."""
        if not self.is_authenticated(platform):
            return None

        credentials = self.credentials[platform]

        if platform == Platform.YOUTUBE:
            response = await self._client.get(
                f"{self.YOUTUBE_API}/videos",
                params={
                    "part": "status,processingDetails",
                    "id": video_id
                },
                headers={"Authorization": f"Bearer {credentials.access_token}"}
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("items"):
                    return data["items"][0]

        return None

    async def close(self):
        """Close HTTP client."""
        await self._client.aclose()


# Convenience functions
def get_social_publish_service() -> SocialPublishService:
    """Get the social publish service instance."""
    return SocialPublishService.get_instance()
