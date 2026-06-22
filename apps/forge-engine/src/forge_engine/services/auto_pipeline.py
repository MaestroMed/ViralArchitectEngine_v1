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
from forge_engine.core.timeutils import utcnow
from pathlib import Path
from typing import Any, Optional

from forge_engine.core.config import settings
from forge_engine.core.database import async_session_maker
from forge_engine.core.jobs import JobManager, JobType

logger = logging.getLogger(__name__)


# Default EtoStark configuration
ETOSTARK_CONFIG = {
    "channel_id": "etostark__",   # real Twitch handle (was "etostark")
    "channel_name": "EtoStark",
    "platform": "twitch",
    "check_interval": 1800,  # 30 minutes
    "auto_import": True,
    "auto_analyze": True,
    "auto_export": True,
    "export_config": {
        # Quality-first detection (2026-06-21): only bangers become clips. Raised
        # the floor (58→65) so the mediocre 58-64 band is dropped, and tightened
        # the ceiling (120→85s) — short + punch-centered retains far better on
        # TikTok (the scorer's own "Too long → completion drops" penalty agrees).
        "min_score": 65,
        "max_clips": 12,
        # Variable clip length: the best NON-OVERLAPPING scored windows are kept
        # at their natural duration (see _select_clips), capped at this ceiling
        # and centered on the punch.
        "max_clip_seconds": 85,
        "clip_lead_in_seconds": 8,
        # Two windows overlapping by more than this fraction of the shorter one
        # are treated as the same moment (only the higher-scoring kept).
        "clip_overlap_threshold": 0.3,
        # EtoStark's webcam sits in the bottom-right corner the whole VOD →
        # compose a vertical "reaction" layout: cam on top, content below.
        # Normalized 0-1 source crops, validated empirically on the real VOD
        # (frames sampled at 420s/1500s/2600s/3700s/5900s/6600s — cam is
        # consistently bottom-right; head centered ~(0.83, 0.82)). The facecam
        # crop frames Eto's head+shoulders; content is the left-center area
        # (avoids the Twitch chat column at x≈0.66–0.88 and the cam itself).
        "layout": {
            "facecam": {"sourceCrop": {"x": 0.70, "y": 0.71, "width": 0.255, "height": 0.29}},
            "content": {"sourceCrop": {"x": 0.04, "y": 0.0, "width": 0.63, "height": 1.0}},
            "facecamRatio": 0.42,
        },
        "platform": "tiktok",
        "include_captions": True,
        "burn_subtitles": True,
        "include_cover": True,
        # This Mac has no NVENC → software x264 (-crf). Forcing NVENC emits a
        # `-cq` flag x264 rejects ("Unrecognized option 'cq'", rc=8).
        "use_nvenc": False,
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


_HOOK_WORDS = (
    "non mais", "attends", "attend", "regarde", "wesh", "jure", "putain",
    "frère", "frere", "incroyable", "dingue", "ouf", "jamais", "toujours",
    "pourquoi", "comment", "genre", "carrément", "avoue", "assume", "imagine",
    "le pire", "le truc", "c'est quand", "tu sais",
)


def _best_hook_clause(transcript: str) -> str:
    """Pick the punchiest clause from a clip's transcript for a title.

    Taking the FIRST clause of a 1-2min clip usually grabs a weak mid-sentence
    opener. Instead, split into clauses and pick the most hook-like one
    (questions/exclamations/intensifiers, punchy length) — a much better
    clip-title than the opener.
    """
    import re

    clauses = re.split(r"(?<=[.!?])\s+|(?<=[,;:])\s+", transcript)
    best, best_score = "", -1.0
    for c in clauses:
        c = c.strip(" -–—,;:\"'")
        words = c.split()
        n = len(words)
        # Require enough substance: a bare "Dans quel sens ?" is a weak title.
        if not (4 <= n <= 13) or not (18 <= len(c) <= 68):
            continue
        cl = c.lower()
        score = 0.0
        if "?" in c:
            score += 3
        if "!" in c:
            score += 2
        if any(w in cl for w in _HOOK_WORDS):
            score += 2
        if 4 <= n <= 9:          # punchy length sweet spot
            score += 2
        # Mild preference for earlier clauses to break ties (the setup line).
        score += 0.01 * (len(clauses) - clauses.index(c) if c in clauses else 0)
        if score > best_score:
            best_score, best = score, c
    return best


def _heuristic_caption(segment, idx: int, channel_name: str) -> tuple[str, str, list[str]]:
    """FR title/description/hashtags without an LLM (Ollama not available).

    Builds a short, clean FR title from the punchiest clause of the spoken line,
    quoted for a clip-title feel. Real top-tier accroches need an LLM (Ollama) —
    this is the no-LLM fallback.
    """
    import re

    transcript = re.sub(r"\s+", " ", (getattr(segment, "transcript", None) or "")).strip()
    # Guard against any whisper boilerplate hallucination leaking into a title
    # (e.g. "Sous-titres réalisés par la communauté d'Amara.org").
    try:
        from forge_engine.services.transcription import _is_hallucinated_segment
        if transcript and _is_hallucinated_segment(transcript, None):
            transcript = ""
    except Exception:
        pass
    # Prefer the punchiest clause; fall back to the first clause / a head slice.
    raw = ""
    if transcript:
        raw = _best_hook_clause(transcript)
        if not raw:
            m = re.match(r"(.{12,55}?[.!?,;:])\s", transcript)
            raw = (m.group(1) if m else transcript[:55])
        raw = raw.strip(" -–—,;:\"'")
    if raw:
        raw = raw[0].upper() + raw[1:]
        if len(raw) >= 55 and not raw.endswith((".", "!", "?")):
            raw = raw.rstrip(",;: ") + "…"
        title = f'"{raw}"'
    else:
        title = getattr(segment, "topic_label", None) or f"Clip #{idx + 1}"

    handle = "#" + re.sub(r"[^a-z0-9]", "", (channel_name or "etostark").lower())
    tags = [handle, "#twitch", "#stream", "#viral", "#fyp", "#pourtoi"]
    for t in (getattr(segment, "score_tags", None) or [])[:3]:
        tag = "#" + re.sub(r"[^a-z0-9]", "", str(t).lower())
        if tag != "#" and tag not in tags:
            tags.append(tag)
    return title, "", tags


def _cluster_segments(
    segments: list,
    *,
    merge_gap: float,
    cap: float,
    pre: float = 8.0,
) -> list[dict]:
    """Merge overlapping/adjacent high-score windows into one clip per moment.

    The segmenter emits many overlapping multi-scale windows (30s, 90s, …) over
    the same content, so the top-N-by-score are often near-duplicates of the
    SAME moment (e.g. three 30s windows inside one 2-min exchange). Selecting
    them verbatim yields redundant clips that are all ~30s.

    This groups segments whose windows overlap or sit within `merge_gap` seconds
    of each other into a single clip spanning their union (clamped to `cap`
    seconds, centered on the best window's punch). The result is fewer,
    non-redundant clips of NATURALLY VARYING length (some 20-40s, some 1-2min).

    Returns clip specs ``{"start", "end", "duration", "score", "rep"}`` sorted by
    score descending. ``rep`` is the highest-scoring member (used for the punch,
    transcript and metadata).
    """
    if not segments:
        return []

    ordered = sorted(segments, key=lambda s: s.start_time)
    clusters: list[dict] = []
    for seg in ordered:
        st, en = seg.start_time, seg.end_time
        if clusters and st <= clusters[-1]["end"] + merge_gap:
            clusters[-1]["end"] = max(clusters[-1]["end"], en)
            clusters[-1]["members"].append(seg)
        else:
            clusters.append({"start": st, "end": en, "members": [seg]})

    specs: list[dict] = []
    for c in clusters:
        members = c["members"]
        best = max(members, key=lambda s: s.score_total or 0)
        start, end = c["start"], c["end"]
        if end - start > cap:
            # Too long → keep a `cap`-second window centered on the punch.
            punch = getattr(best, "cold_open_start_time", None)
            if punch and start <= punch <= end:
                start = max(start, punch - pre)
            start = min(start, end - cap)
            end = start + cap
        specs.append({
            "start": start,
            "end": end,
            "duration": end - start,
            "score": max(s.score_total or 0 for s in members),
            "rep": best,
        })

    specs.sort(key=lambda x: x["score"], reverse=True)
    return specs


def _select_clips(
    segments: list,
    *,
    cap: float,
    max_clips: int,
    overlap_thresh: float = 0.3,
    min_seconds: float = 12.0,
) -> list[dict]:
    """Pick the best NON-OVERLAPPING windows, keeping their natural durations.

    The segmenter emits overlapping multi-scale windows (≈30s up to several
    minutes) over the same content. Rather than MERGE them (which, on this kind
    of segmentation, collapses everything to the cap), we greedily take the
    highest-scoring windows and skip any that overlaps an already-picked clip by
    more than `overlap_thresh` of the shorter window. This:
      * de-duplicates near-identical windows of the same moment, and
      * preserves the segmenter's NATURAL duration spread — so the batch lands a
        mix of ~1min and ~2min clips instead of all-30s or all-capped.

    Windows longer than `cap` are trimmed to a `cap`-second window centered on
    the punch (`cold_open_start_time`). Returns clip specs
    ``{"start", "end", "duration", "score", "rep"}`` sorted by score desc.
    """
    chosen: list[dict] = []
    for seg in sorted(segments, key=lambda s: s.score_total or 0, reverse=True):
        if len(chosen) >= max_clips:
            break
        start = seg.start_time
        end = seg.end_time
        if end - start > cap:
            punch = getattr(seg, "cold_open_start_time", None)
            if punch and start <= punch <= end:
                start = max(start, punch - 8.0)
            start = min(start, end - cap)
            end = start + cap
        dur = end - start
        if dur < min_seconds:
            continue
        overlaps = False
        for c in chosen:
            inter = max(0.0, min(end, c["end"]) - max(start, c["start"]))
            if inter > overlap_thresh * min(dur, c["end"] - c["start"]):
                overlaps = True
                break
        if overlaps:
            continue
        chosen.append({
            "start": start,
            "end": end,
            "duration": dur,
            "score": seg.score_total or 0,
            "rep": seg,
        })
    return chosen


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

        self._last_check = utcnow()

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

            # Check for new VODs via yt-dlp (no headless-browser dependency).
            try:
                from forge_engine.services import vod_detector
                vods = await vod_detector.get_twitch_vods(channel.channel_id, limit=5)
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
            channel.last_check_at = utcnow()
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

        start = utcnow()
        poll_interval = 30  # Check every 30 seconds

        while (utcnow() - start).total_seconds() < timeout:
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

        cap = export_config.get("max_clip_seconds") or 120.0
        overlap_thresh = export_config.get("clip_overlap_threshold", 0.3)

        async with async_session_maker() as db:
            # Fetch ALL segments above the score floor. The segmenter emits many
            # overlapping multi-scale windows over the same content, so we pick
            # the best NON-OVERLAPPING ones (keeping their natural durations)
            # rather than the top-N verbatim — see _select_clips.
            result = await db.execute(
                select(Segment)
                .where(Segment.project_id == project_id)
                .where(Segment.score_total >= min_score)
            )
            candidates = result.scalars().all()

            if not candidates:
                logger.info(f"[AutoPipeline] No segments above {min_score} for project {project_id[:8]}")
                return

            # Greedy non-overlapping selection → a natural mix of ~1-2min clips,
            # de-duplicated. Windows are passed to the export as OVERRIDES (the
            # canonical Segment rows are never mutated → idempotent re-runs).
            specs = _select_clips(
                candidates, cap=cap, max_clips=max_clips, overlap_thresh=overlap_thresh,
            )

            _durs = sorted((round(s["duration"]) for s in specs), reverse=True)
            logger.info(
                f"[AutoPipeline] {len(candidates)} candidates (score≥{min_score}) → "
                f"{len(specs)} non-overlapping clips (cap {cap:g}s); durations={_durs}"
            )

            # Export each selected clip
            export_service = ExportService()
            content_service = ContentGenerationService.get_instance()

            for idx, spec in enumerate(specs):
                segment = spec["rep"]
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
                        layout_config=export_config.get("layout"),
                        jump_cut_config=export_config.get("jump_cut_config"),
                        cold_open_config=export_config.get("cold_open_config"),
                        clip_start_override=spec["start"],
                        clip_duration_override=spec["duration"],
                    )

                    # Generate title/description — LLM when available, else a
                    # hook-based FR heuristic (no raw transcript opener).
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
                    except Exception:
                        generated = None
                    h_title, h_desc, h_tags = _heuristic_caption(segment, idx, channel_name)
                    _llm_ok = (
                        settings.LLM_ENABLED and generated and generated.titles
                        and content_service.is_quality_title(
                            generated.titles[0], segment.transcript or ""
                        )
                    )
                    if _llm_ok:
                        # Real LLM accroche (passed the quality gate).
                        title = generated.titles[0]
                        description = generated.description or ""
                        hashtags = generated.hashtags or h_tags
                    else:
                        # No LLM: short hook-based FR title, but keep the
                        # content service's content-aware hashtags if present.
                        title = h_title
                        description = (generated.description if generated else "") or h_desc
                        hashtags = (generated.hashtags if generated and generated.hashtags else h_tags)

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
                        # The CLIP duration (cap-trimmed window), not the segment's
                        # full multi-scale window — segment.duration was up to 210s.
                        duration=spec["duration"],
                        viral_score=segment.score_total,
                        status="pending_review",
                        channel_name=channel_name,
                    )
                    db.add(queue_item)

                    logger.info(
                        f"[AutoPipeline] Exported & queued clip {idx+1}/{len(specs)}: "
                        f"'{title[:40]}...' (score={segment.score_total:.0f})"
                    )

                except Exception as e:
                    logger.error(f"[AutoPipeline] Failed to export segment {segment.id[:8]}: {e}")

            await db.commit()
            logger.info(f"[AutoPipeline] Finished: {len(specs)} clips exported and queued for review")

        # Wake any backgrounded phones: real APNs push "N clips prêts pour QC".
        # No-op (and never raises) until APNs is configured — see services/apns.py.
        try:
            from forge_engine.services.apns import notify_clips_ready
            await notify_clips_ready(project_id, len(specs))
        except Exception as exc:
            logger.warning(f"[AutoPipeline] clips-ready push failed (ignored): {exc}")

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