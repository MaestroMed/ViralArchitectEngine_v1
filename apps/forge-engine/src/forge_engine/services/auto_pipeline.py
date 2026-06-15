"""Auto Pipeline Service - Full automation from VOD detection to clip queue.

This is the robot that works while you sleep:
1. Monitors EtoStark's Twitch channel for new VODs
2. Downloads the VOD automatically
3. Runs the full ingest + analyze pipeline
4. Auto-exports the top N clips with best viral scores
5. Adds them to the ClipQueue for morning review

The user's workflow becomes:
  Morning -> Open phone -> Scroll clips -> Approve/Reject -> Publish
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from forge_engine.core.database import async_session_maker
from forge_engine.core.jobs import JobManager, JobType

logger = logging.getLogger(__name__)


# Default EtoStark configuration
ETOSTARK_CONFIG = {
    "channel_id": "etostark",
    "channel_name": "EtoStark",
    "platform": "twitch",
    "check_interval": 1800,  # 30 minutes
    "auto_import": True,
    "auto_analyze": True,
    "auto_export": True,
    "export_config": {
        "min_score": 65,
        "max_clips": 15,
        "max_clip_seconds": 30,       # tight clips centered on the punch
        "clip_lead_in_seconds": 5,    # seconds before the hook
        "platform": "tiktok",
        "include_captions": True,
        "burn_subtitles": True,
        "include_cover": True,
        "use_nvenc": True,
        "jump_cut_config": {
            "enabled": True,
            "sensitivity": "normal",
            "transition": "zoom",
        },
        "cold_open_config": {
            "enabled": True,
            "language": "fr",
        },
    },
}


class AutoPipelineService:
    """Full automation pipeline: VOD -> Clips -> Queue.

    Integrates with MonitorService for periodic checks and
    ExportService for batch clip generation.
    """

    _instance: Optional["AutoPipelineService"] = None

    def __init__(self):
        self._running = False
        self._task: asyncio.Task | None = None
        self._check_interval = ETOSTARK_CONFIG["check_interval"]
        self._last_check: datetime | None = None
        self._processing_vods: set = set()  # Track VODs being processed

    @classmethod
    def get_instance(cls) -> "AutoPipelineService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def start(self):
        """Start the auto pipeline background loop."""
        if self._running:
            logger.info("[AutoPipeline] Already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._pipeline_loop())
        logger.info("[AutoPipeline] Started - monitoring EtoStark")

    async def stop(self):
        """Stop the auto pipeline."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("[AutoPipeline] Stopped")

    async def _pipeline_loop(self):
        """Background loop that checks for new VODs and processes them."""
        # Wait a bit before first check to let services initialize
        await asyncio.sleep(30)

        while self._running:
            try:
                await self._check_and_process()
            except Exception as e:
                logger.error(f"[AutoPipeline] Loop error: {e}")

            await asyncio.sleep(self._check_interval)

    async def check_now(self):
        """Run one immediate VOD check, outside the poll cadence.

        Called by the Twitch stream.offline webhook so clips start processing
        the moment a stream ends instead of waiting up to check_interval. Safe
        to call even if the loop isn't running.
        """
        try:
            await self._check_and_process()
        except Exception as e:
            logger.error(f"[AutoPipeline] check_now error: {e}")

    async def _check_and_process(self):
        """Check for new VODs and start processing pipeline."""
        from sqlalchemy import select

        from forge_engine.models import DetectedVOD, WatchedChannel

        self._last_check = datetime.utcnow()

        async with async_session_maker() as db:
            # Ensure EtoStark channel is registered
            result = await db.execute(
                select(WatchedChannel).where(
                    WatchedChannel.channel_id == ETOSTARK_CONFIG["channel_id"],
                    WatchedChannel.platform == ETOSTARK_CONFIG["platform"]
                )
            )
            channel = result.scalar_one_or_none()

            if not channel:
                # Auto-register EtoStark
                channel = WatchedChannel(
                    channel_id=ETOSTARK_CONFIG["channel_id"],
                    channel_name=ETOSTARK_CONFIG["channel_name"],
                    platform=ETOSTARK_CONFIG["platform"],
                    check_interval=ETOSTARK_CONFIG["check_interval"],
                    auto_import=True,
                    enabled=True,
                )
                db.add(channel)
                await db.commit()
                await db.refresh(channel)
                logger.info("[AutoPipeline] Auto-registered EtoStark channel")

            if not channel.enabled:
                return

            # Check for new VODs using scraper
            try:
                from forge_engine.services.playwright_scraper import PlaywrightScraper
                scraper = PlaywrightScraper.get_instance()

                vods = await scraper.get_twitch_vods(channel.channel_id, limit=5)
            except Exception as e:
                logger.warning(f"[AutoPipeline] VOD check failed: {e}")
                return

            # Find new VODs
            known_ids = set(channel.last_vod_ids or [])
            new_vods = []

            for vod in vods:
                if vod.id not in known_ids and vod.id not in self._processing_vods:
                    # Register as detected
                    detected = DetectedVOD(
                        external_id=vod.id,
                        title=vod.title,
                        channel_id=channel.channel_id,
                        channel_name=channel.channel_name,
                        platform=channel.platform,
                        url=vod.url,
                        thumbnail_url=vod.thumbnail_url,
                        duration=vod.duration,
                        published_at=vod.published_at,
                        view_count=vod.view_count,
                        status="new",
                    )
                    db.add(detected)
                    new_vods.append(detected)

            # Update channel state
            channel.last_check_at = datetime.utcnow()
            channel.last_vod_ids = [v.id for v in vods]
            await db.commit()

            if new_vods:
                logger.info(f"[AutoPipeline] Found {len(new_vods)} new VOD(s) for {channel.channel_name}")

                for vod in new_vods:
                    self._processing_vods.add(vod.external_id)
                    # Process each VOD asynchronously
                    asyncio.create_task(
                        self._process_vod(vod.id, vod.url, vod.title, channel.channel_name)
                    )

    async def _process_vod(
        self,
        vod_id: str,
        vod_url: str,
        vod_title: str,
        channel_name: str
    ):
        """Full pipeline for a single VOD: download -> ingest -> analyze -> export -> queue."""
        from forge_engine.models import Project

        logger.info(f"[AutoPipeline] Processing VOD: {vod_title}")

        try:
            async with async_session_maker() as db:
                # Create project
                project = Project(
                    name=f"[Auto] {vod_title}",
                    source_path="",
                    source_filename=f"{vod_title}.mp4",
                    status="downloading",
                    project_meta={
                        "importUrl": vod_url,
                        "platform": "twitch",
                        "channel": channel_name,
                        "autoPipeline": True,
                        "detectedVodId": vod_id,
                    }
                )
                db.add(project)
                await db.commit()
                await db.refresh(project)

                project_id = project.id
                logger.info(f"[AutoPipeline] Created project {project_id[:8]} for '{vod_title}'")

            # Create download job (which auto-chains to ingest -> analyze)
            job_manager = JobManager.get_instance()
            await job_manager.create_job(
                job_type=JobType.DOWNLOAD,
                project_id=project_id,
                url=vod_url,
                auto_ingest=True,
                auto_analyze=True,
            )

            # Wait for analysis to complete (poll project status)
            analyzed = await self._wait_for_analysis(project_id, timeout=7200)  # 2h max

            if not analyzed:
                logger.warning(f"[AutoPipeline] Analysis did not complete for project {project_id[:8]}")
                return

            # Auto-export top clips
            export_config = ETOSTARK_CONFIG["export_config"]
            await self._auto_export_top_clips(project_id, channel_name, export_config)

        except Exception as e:
            logger.error(f"[AutoPipeline] Failed to process VOD {vod_title}: {e}")
            import traceback
            logger.error(traceback.format_exc())
        finally:
            # Remove from processing set
            # Find the external_id from vod_id (internal id)
            self._processing_vods.discard(vod_id)

    async def _wait_for_analysis(self, project_id: str, timeout: int = 7200) -> bool:
        """Wait for a project to reach 'analyzed' status."""
        from sqlalchemy import select

        from forge_engine.models import Project

        start = datetime.utcnow()
        poll_interval = 30  # Check every 30 seconds

        while (datetime.utcnow() - start).total_seconds() < timeout:
            async with async_session_maker() as db:
                result = await db.execute(
                    select(Project).where(Project.id == project_id)
                )
                project = result.scalar_one_or_none()

                if not project:
                    return False

                if project.status == "analyzed":
                    return True
                elif project.status in ("error", "failed"):
                    logger.warning(f"[AutoPipeline] Project {project_id[:8]} failed: {project.status}")
                    return False

            await asyncio.sleep(poll_interval)

        logger.warning(f"[AutoPipeline] Timeout waiting for analysis of {project_id[:8]}")
        return False

    async def _auto_export_top_clips(
        self,
        project_id: str,
        channel_name: str,
        export_config: dict[str, Any]
    ):
        """Export top clips and add them to the review queue."""
        from sqlalchemy import select

        from forge_engine.core.scheduling import (
            export_window,
            seconds_until_window,
            should_export_now,
        )
        from forge_engine.models import Segment
        from forge_engine.models.review import ClipQueue
        from forge_engine.services.content_generation import ContentGenerationService
        from forge_engine.services.export import ExportService

        # Optional "clips ready by morning" gate: if FORGE_EXPORT_WINDOW is set
        # (e.g. 05:00-07:00), hold the GPU-heavy export until that window so the
        # queue is fresh at wake-up rather than rendered late at night. No
        # window configured → export immediately (unchanged behaviour).
        if not should_export_now():
            window = export_window()
            wait_s = seconds_until_window(window) if window else 0
            logger.info(
                "[AutoPipeline] Outside export window %s — deferring export of "
                "project %s by %dm",
                window, project_id[:8], wait_s // 60,
            )
            # Re-check periodically; cap the sleep so a stop() is responsive.
            while self._running and not should_export_now():
                await asyncio.sleep(min(300, max(30, wait_s)))
                wait_s = 0
            if not self._running:
                return

        min_score = export_config.get("min_score", 65)
        max_clips = export_config.get("max_clips", 15)

        async with async_session_maker() as db:
            # Get top segments
            result = await db.execute(
                select(Segment)
                .where(Segment.project_id == project_id)
                .where(Segment.score_total >= min_score)
                .order_by(Segment.score_total.desc())
                .limit(max_clips)
            )
            segments = result.scalars().all()

            if not segments:
                logger.info(f"[AutoPipeline] No segments above {min_score} for project {project_id[:8]}")
                return

            # Tighten each clip to a short window centered on its punch
            # (cold_open_start_time = absolute hook timestamp) instead of
            # exporting the first 60s of a long analyzed segment. Off when
            # max_clip_seconds is unset/0.
            tight = export_config.get("max_clip_seconds")
            if tight:
                pre = export_config.get("clip_lead_in_seconds", 5.0)
                for s in segments:
                    orig_start = s.start_time
                    orig_end = s.start_time + (s.duration or 0.0)
                    punch = s.cold_open_start_time
                    new_start = max(orig_start, punch - pre) if (punch and orig_start <= punch <= orig_end) else orig_start
                    new_dur = min(float(tight), orig_end - new_start)
                    if new_dur < 12:  # window too short → take `tight`s from the start
                        new_start = orig_start
                        new_dur = min(float(tight), orig_end - orig_start)
                    s.start_time = new_start
                    s.duration = new_dur
                    s.end_time = new_start + new_dur
                await db.commit()
                logger.info(f"[AutoPipeline] Tightened {len(segments)} clips to ~{tight:g}s around the punch")

            logger.info(f"[AutoPipeline] Found {len(segments)} clips to export (score >= {min_score})")

            # Export each segment
            export_service = ExportService()
            content_service = ContentGenerationService.get_instance()

            for idx, segment in enumerate(segments):
                try:
                    # Create a lightweight job for export
                    from forge_engine.core.jobs import Job
                    job = Job(
                        id=f"auto_export_{project_id[:8]}_{idx}",
                        type="export",
                        project_id=project_id,
                    )
                    job.metadata = {}

                    # Run export
                    result = await export_service.run_export(
                        job=job,
                        project_id=project_id,
                        segment_id=segment.id,
                        variant=f"auto_{idx+1:02d}",
                        platform=export_config.get("platform", "tiktok"),
                        include_captions=export_config.get("include_captions", True),
                        burn_subtitles=export_config.get("burn_subtitles", True),
                        include_cover=export_config.get("include_cover", True),
                        use_nvenc=export_config.get("use_nvenc", True),
                        jump_cut_config=export_config.get("jump_cut_config"),
                        cold_open_config=export_config.get("cold_open_config"),
                    )

                    # Generate title/description
                    try:
                        generated = await content_service.generate_for_segment(
                            segment={
                                "transcript": segment.transcript or "",
                                "score": {
                                    "tags": segment.score_tags or [],
                                },
                            },
                            platform=export_config.get("platform", "tiktok"),
                            channel_name=channel_name,
                        )
                        title = generated.titles[0] if generated.titles else segment.topic_label
                        description = generated.description
                        hashtags = generated.hashtags
                    except Exception:
                        title = segment.topic_label or f"Clip #{idx+1}"
                        description = ""
                        hashtags = ["#etostark", "#gaming", "#viral", "#fyp"]

                    # Find video artifact path
                    video_path = ""
                    cover_path = ""
                    for artifact_data in result.get("artifacts", []):
                        if isinstance(artifact_data, dict):
                            if artifact_data.get("type") == "video":
                                video_path = artifact_data.get("path", "")
                            elif artifact_data.get("type") == "cover":
                                cover_path = artifact_data.get("path", "")
                        elif hasattr(artifact_data, "type"):
                            if artifact_data.type == "video":
                                video_path = artifact_data.path
                            elif artifact_data.type == "cover":
                                cover_path = artifact_data.path

                    if not video_path:
                        # Try to construct from export dir
                        export_dir = result.get("export_dir", "")
                        if export_dir:
                            video_files = list(Path(export_dir).glob("*.mp4"))
                            if video_files:
                                video_path = str(video_files[0])

                    # Add to clip queue
                    queue_item = ClipQueue(
                        project_id=project_id,
                        segment_id=segment.id,
                        title=title,
                        description=description,
                        hashtags=hashtags,
                        video_path=video_path,
                        cover_path=cover_path,
                        duration=segment.duration,
                        viral_score=segment.score_total,
                        status="pending_review",
                        channel_name=channel_name,
                    )
                    db.add(queue_item)

                    logger.info(
                        f"[AutoPipeline] Exported & queued clip {idx+1}/{len(segments)}: "
                        f"'{title[:40]}...' (score={segment.score_total:.0f})"
                    )

                except Exception as e:
                    logger.error(f"[AutoPipeline] Failed to export segment {segment.id[:8]}: {e}")

            await db.commit()
            logger.info(f"[AutoPipeline] Finished: {len(segments)} clips exported and queued for review")

    def get_status(self) -> dict[str, Any]:
        """Get auto pipeline status."""
        return {
            "running": self._running,
            "lastCheck": self._last_check.isoformat() if self._last_check else None,
            "checkInterval": self._check_interval,
            "processingVods": len(self._processing_vods),
            "config": {
                "channel": ETOSTARK_CONFIG["channel_name"],
                "platform": ETOSTARK_CONFIG["platform"],
                "minScore": ETOSTARK_CONFIG["export_config"]["min_score"],
                "maxClips": ETOSTARK_CONFIG["export_config"]["max_clips"],
            }
        }
