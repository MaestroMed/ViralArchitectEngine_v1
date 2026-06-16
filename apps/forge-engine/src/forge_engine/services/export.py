"""Export service for generating complete export packs.

Pipeline order (Phase 0 corrected):
  1. Analyze jump cuts on SOURCE audio (VAD needs original audio)
  2. Detect cold open hooks from transcript
  3. Render clip (source -> 9:16 + captions) -> temp.mp4
  4. Apply jump cuts on RENDERED clip (not source!) with segment_start=0
  5. Apply cold open reorder on rendered clip
  6. Apply intro overlay on rendered clip
  7. Mix music if configured
  8. Validate output with ffprobe
  9. Record artifacts
"""

import asyncio
import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import select

from forge_engine.core.config import settings
from forge_engine.core.database import async_session_maker
from forge_engine.core.jobs import Job, JobManager
from forge_engine.models import Artifact, Project, Segment, Template
from forge_engine.services.captions import CaptionEngine
from forge_engine.services.cold_open import ColdOpenEngine
from forge_engine.services.intro import IntroEngine
from forge_engine.services.jump_cuts import JumpCutConfig, JumpCutEngine
from forge_engine.services.pipeline_builder import PipelineConfig, PipelineSinglePass
from forge_engine.services.qc import QCService
from forge_engine.services.render import RenderService

logger = logging.getLogger(__name__)


class ExportService:
    """Service for exporting clips and generating export packs."""

    def __init__(self):
        self.render = RenderService()
        self.captions = CaptionEngine()
        self.intro = IntroEngine()
        self.jump_cuts = JumpCutEngine.get_instance()
        self.cold_open = ColdOpenEngine()

    async def run_export(
        self,
        job: Job,
        project_id: str,
        segment_id: str,
        variant: str = "A",
        template_id: str | None = None,
        platform: str = "tiktok",
        include_captions: bool = True,
        burn_subtitles: bool = True,
        include_cover: bool = True,
        include_metadata: bool = True,
        include_post: bool = True,
        use_nvenc: bool = True,
        caption_style: dict[str, Any] | None = None,
        layout_config: dict[str, Any] | None = None,
        intro_config: dict[str, Any] | None = None,
        music_config: dict[str, Any] | None = None,
        jump_cut_config: dict[str, Any] | None = None,
        cold_open_config: dict[str, Any] | None = None,
        clip_start_override: float | None = None,
        clip_duration_override: float | None = None,
    ) -> dict[str, Any]:
        """Run the export pipeline.

        clip_start_override/clip_duration_override let a caller render a DIFFERENT
        window than the segment's stored one (e.g. the auto-pipeline's clip
        selection) WITHOUT mutating the canonical Segment row — the segment is
        detached from the session before any commit, so the override never
        persists. This keeps clip selection idempotent across re-runs.
        """
        logger.info(f"[EXPORT] Starting export for project={project_id}, segment={segment_id}")
        job_manager = JobManager.get_instance()

        async with async_session_maker() as db:
            # Get project and segment
            result = await db.execute(select(Project).where(Project.id == project_id))
            project = result.scalar_one_or_none()

            if not project:
                raise ValueError(f"Project not found: {project_id}")

            result = await db.execute(select(Segment).where(Segment.id == segment_id))
            segment = result.scalar_one_or_none()

            if not segment:
                raise ValueError(f"Segment not found: {segment_id}")

            # Apply a window override WITHOUT persisting it: mutate the loaded
            # row then expunge it from the session so a later commit can't flush
            # the change back to the DB. All downstream code (transcript filter,
            # single-pass export) reads segment.start_time/duration as usual.
            if clip_start_override is not None:
                segment.start_time = float(clip_start_override)
                if clip_duration_override is not None:
                    segment.duration = float(clip_duration_override)
                    segment.end_time = float(clip_start_override) + float(clip_duration_override)
                db.expunge(segment)

            # Get template if specified
            template = None
            if template_id:
                result = await db.execute(select(Template).where(Template.id == template_id))
                template = result.scalar_one_or_none()

            # Setup paths
            project_dir = settings.LIBRARY_PATH / "projects" / project_id
            exports_dir = project_dir / "exports" / f"{segment_id}_{variant}"
            exports_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_name = f"clip_{variant}_{timestamp}"

            artifacts = []

            # Load transcript for this segment
            transcript_segments = []
            analysis_dir = project_dir / "analysis"
            transcript_path = analysis_dir / "transcript.json"

            if transcript_path.exists():
                with open(transcript_path, encoding="utf-8") as f:
                    transcript_data = json.load(f)

                # Filter to segment time range
                all_segments = transcript_data.get("segments", [])
                transcript_segments = [
                    seg for seg in all_segments
                    if segment.start_time <= seg.get("start", 0) <= segment.end_time
                ]
                logger.info(f"Loaded {len(all_segments)} total transcript segments, filtered to {len(transcript_segments)} for clip range {segment.start_time}-{segment.end_time}")

            job_manager.update_progress(job, 5, "setup", "Preparing export...")

            # ── Single-pass fast path ─────────────────────────────────────
            # When EXPORT_SINGLE_PASS is True (default), we delegate ALL
            # transformations to the single-pass pipeline builder, which
            # collapses layout + jump cuts + cold open + subtitles +
            # intro overlay + music into one FFmpeg filter_complex call.
            #
            # Intro overlay is handled by pre-rendering a standalone intro
            # clip (blurred background + text) inside _run_single_pass_export,
            # then compositing it inline via PipelineConfig.intro_path.
            # Cold open hook timing is detected via ColdOpenEngine and passed
            # as PipelineConfig.cold_open_hook_start/end.
            #
            # Legacy multi-pass path is retained only as a safety net when
            # EXPORT_SINGLE_PASS is explicitly set to False.
            if settings.EXPORT_SINGLE_PASS:
                logger.info("[Export] Using single-pass FFmpeg pipeline")
                return await self._run_single_pass_export(
                    job=job,
                    job_manager=job_manager,
                    project=project,
                    segment=segment,
                    project_id=project_id,
                    segment_id=segment_id,
                    variant=variant,
                    exports_dir=exports_dir,
                    base_name=base_name,
                    platform=platform,
                    include_captions=include_captions,
                    burn_subtitles=burn_subtitles,
                    include_cover=include_cover,
                    include_metadata=include_metadata,
                    include_post=include_post,
                    use_nvenc=use_nvenc,
                    caption_style=caption_style,
                    layout_config=layout_config,
                    intro_config=intro_config,
                    music_config=music_config,
                    jump_cut_config=jump_cut_config,
                    cold_open_config=cold_open_config,
                    transcript_segments=transcript_segments,
                    template=template,
                    template_id=template_id,
                    db=db,
                )
            # ── End single-pass fast path ─────────────────────────────────

            # Get actual video dimensions from project metadata or probe
            video_width = project.width or 1920
            video_height = project.height or 1080
            logger.info(f"Source video dimensions: {video_width}x{video_height}")

            # Build layout config - use edited zones from frontend if provided
            if layout_config and layout_config.get("facecam") and layout_config.get("content"):
                # Use frontend-edited zones with sourceCrop
                fc = layout_config["facecam"]
                cc = layout_config["content"]

                # Convert sourceCrop (0-1 normalized) to pixel values based on ACTUAL video size
                facecam_source = fc.get("sourceCrop", {"x": 0, "y": 0, "width": 1, "height": 1})
                content_source = cc.get("sourceCrop", {"x": 0, "y": 0, "width": 1, "height": 1})

                # Ensure crop values are within bounds
                def clamp_crop(crop, max_w, max_h):
                    x = max(0, min(crop["x"], 0.99))
                    y = max(0, min(crop["y"], 0.99))
                    w = max(0.01, min(crop["width"], 1 - x))
                    h = max(0.01, min(crop["height"], 1 - y))
                    return {
                        "x": int(x * max_w),
                        "y": int(y * max_h),
                        "width": max(2, int(w * max_w)),  # FFmpeg requires even dimensions
                        "height": max(2, int(h * max_h)),
                    }

                render_layout_config = {
                    "facecam_rect": clamp_crop(facecam_source, video_width, video_height),
                    "content_rect": clamp_crop(content_source, video_width, video_height),
                    "facecam_ratio": layout_config.get("facecamRatio", 0.4),
                    "background_blur": True,
                }
                logger.info(f"Layout config: facecam={render_layout_config['facecam_rect']}, content={render_layout_config['content_rect']}")
            else:
                # Fallback to segment's detected zones
                render_layout_config = {
                    "facecam_rect": segment.facecam_rect,
                    "content_rect": segment.content_rect,
                    "facecam_ratio": 0.4,
                    "background_blur": True,
                }

            if template and template.layout:
                render_layout_config.update(template.layout)

            # Build caption config from custom style or template
            logger.info("=== EXPORT DEBUG ===")
            logger.info(f"[EXPORT] caption_style received: {caption_style}")
            if caption_style:
                logger.info(f"[EXPORT] fontFamily: {caption_style.get('fontFamily')}")
                logger.info(f"[EXPORT] color: {caption_style.get('color')}")
                logger.info(f"[EXPORT] highlightColor: {caption_style.get('highlightColor')}")
                logger.info(f"[EXPORT] animation: {caption_style.get('animation')}")
            logger.info("====================")
            logger.info(f"[EXPORT] layout_config received: {layout_config}")

            caption_config = {
                "style": "custom" if caption_style else "forge_minimal",
                "word_level": True,
                "max_words_per_line": caption_style.get("wordsPerLine", 6) if caption_style else 6,
                "max_lines": 2,
            }

            # If custom style provided, add it to caption config
            if caption_style:
                caption_config["custom_style"] = {
                    "font_family": caption_style.get("fontFamily", "Inter"),
                    "font_size": caption_style.get("fontSize", 48),
                    "font_weight": caption_style.get("fontWeight", 700),
                    "color": caption_style.get("color", "#FFFFFF"),
                    "background_color": caption_style.get("backgroundColor", "transparent"),
                    "outline_color": caption_style.get("outlineColor", "#000000"),
                    "outline_width": caption_style.get("outlineWidth", 2),
                    "position": caption_style.get("position", "bottom"),
                    "position_y": caption_style.get("positionY"),  # Custom Y position
                    "animation": caption_style.get("animation", "none"),
                    "highlight_color": caption_style.get("highlightColor", "#FFD700"),
                }
            elif template and template.caption_style:
                caption_config.update(template.caption_style)

            # Analyze jump cuts if enabled
            jump_cut_analysis = None
            needs_jump_cuts = jump_cut_config and jump_cut_config.get("enabled")

            if needs_jump_cuts:
                try:
                    job_manager.update_progress(job, 5, "jump_cuts", "Analyzing audio for jump cuts...")

                    jc_config = JumpCutConfig.from_dict(jump_cut_config)
                    jump_cut_analysis = await self.jump_cuts.analyze_segment(
                        audio_path=project.source_path,
                        start_time=segment.start_time,
                        duration=segment.duration,
                        config=jc_config,
                        progress_callback=lambda p: job_manager.update_progress(
                            job, 5 + p * 0.05, "jump_cuts", f"Analyzing: {p:.0f}%"
                        )
                    )

                    logger.info(
                        f"[Export] Jump cut analysis: {jump_cut_analysis.cuts_count} cuts, "
                        f"{jump_cut_analysis.time_saved:.1f}s saved ({jump_cut_analysis.time_saved_percent:.0f}%)"
                    )

                    # Store analysis in job metadata
                    job.metadata = job.metadata or {}
                    job.metadata["jump_cuts"] = jump_cut_analysis.to_dict()

                except Exception as e:
                    logger.warning(f"[Export] Jump cut analysis failed: {e}, continuing without")
                    needs_jump_cuts = False

            # ================================================================
            # RENDER PIPELINE (Phase 0 corrected order)
            # ================================================================

            video_path = exports_dir / f"{base_name}.mp4"
            # Legacy multi-pass path (only reached when EXPORT_SINGLE_PASS=False)
            needs_intro = intro_config and intro_config.get("enabled")
            needs_cold_open = cold_open_config and cold_open_config.get("enabled")
            needs_post_processing = needs_intro or needs_jump_cuts or needs_cold_open

            # --- STEP 1: Render 9:16 clip with captions ---
            job_manager.update_progress(job, 10, "render", "Rendering 9:16 clip...")

            if needs_post_processing:
                temp_clip_path = exports_dir / f"{base_name}_temp.mp4"
                render_output = temp_clip_path
            else:
                render_output = video_path

            try:
                await self.render.render_clip(
                    source_path=project.source_path,
                    output_path=str(render_output),
                    start_time=segment.start_time,
                    duration=segment.duration,
                    layout_config=render_layout_config,
                    caption_config=caption_config if include_captions else None,
                    transcript_segments=transcript_segments if include_captions else None,
                    use_nvenc=use_nvenc,
                    progress_callback=lambda p: job_manager.update_progress(
                        job, 10 + p * 0.4, "render", f"Rendering: {p:.0f}%"
                    )
                )
            except Exception as render_err:
                raise RuntimeError(f"Render failed: {render_err}") from render_err

            if not render_output.exists() or render_output.stat().st_size == 0:
                raise RuntimeError(f"Render produced no output at {render_output}")

            current_clip = render_output

            # --- STEP 2: Apply jump cuts on the RENDERED clip (not source!) ---
            # FIX: Previously applied on project.source_path which produced
            # raw 16:9 video without composition or subtitles.
            # Now applies on the rendered 9:16 clip with segment_start=0.
            if needs_jump_cuts and jump_cut_analysis and jump_cut_analysis.cuts_count > 0:
                try:
                    job_manager.update_progress(job, 50, "jump_cuts", "Applying jump cuts...")

                    jump_cut_output = exports_dir / f"{base_name}_jumpcut.mp4"
                    jc_config = JumpCutConfig.from_dict(jump_cut_config)

                    await self.jump_cuts.apply_jump_cuts(
                        source_path=str(current_clip),  # FIXED: use rendered clip
                        output_path=str(jump_cut_output),
                        segment_start=0,  # FIXED: rendered clip starts at 0
                        keep_ranges=jump_cut_analysis.keep_ranges,
                        config=jc_config,
                        progress_callback=lambda p: job_manager.update_progress(
                            job, 50 + p * 0.05, "jump_cuts", f"Jump cuts: {p:.0f}%"
                        )
                    )

                    self._cleanup_temp(current_clip, video_path)
                    current_clip = jump_cut_output

                    logger.info(f"[Export] Applied {jump_cut_analysis.cuts_count} jump cuts on rendered clip")

                except Exception as jc_error:
                    logger.warning(f"[Export] Jump cuts failed: {jc_error}, using original")
                    self._add_warning(job, "jump_cuts_failed",
                        f"Les jump cuts n'ont pas pu être appliqués: {str(jc_error)[:100]}")

            # --- STEP 3: Apply cold open (reorder timeline) ---
            if needs_cold_open:
                try:
                    job_manager.update_progress(job, 56, "cold_open", "Applying cold open...")

                    cold_open_output = exports_dir / f"{base_name}_coldopen.mp4"

                    await self._apply_cold_open(
                        clip_path=str(current_clip),
                        output_path=str(cold_open_output),
                        segment=segment,
                        transcript_segments=transcript_segments,
                        config=cold_open_config,
                        progress_callback=lambda p: job_manager.update_progress(
                            job, 56 + p * 0.04, "cold_open", f"Cold open: {p:.0f}%"
                        )
                    )

                    self._cleanup_temp(current_clip, video_path)
                    current_clip = cold_open_output

                    logger.info("[Export] Applied cold open reorder")

                except Exception as co_error:
                    import traceback
                    logger.error(f"[Export] Cold open failed: {co_error}")
                    logger.error(traceback.format_exc())
                    self._add_warning(job, "cold_open_failed",
                        f"Le cold open n'a pas pu être appliqué: {str(co_error)[:100]}")

            # --- STEP 4: Apply intro overlay ---
            if needs_intro:
                try:
                    job_manager.update_progress(job, 60, "intro", "Applying intro overlay...")

                    if not intro_config.get("title"):
                        intro_config["title"] = segment.topic_label or "Untitled"

                    intro_output = exports_dir / f"{base_name}_intro.mp4"

                    await self.intro.apply_intro_overlay(
                        clip_path=str(current_clip),
                        output_path=str(intro_output),
                        config=intro_config,
                        progress_callback=lambda p: job_manager.update_progress(
                            job, 60 + p * 0.1, "intro", f"Intro: {p:.0f}%"
                        )
                    )

                    self._cleanup_temp(current_clip, video_path)
                    current_clip = intro_output

                except Exception as intro_error:
                    import traceback
                    error_details = str(intro_error)
                    logger.error(f"Intro overlay failed: {error_details}")
                    logger.error(f"Intro config was: {intro_config}")
                    logger.error(traceback.format_exc())

                    job_manager.update_progress(
                        job, 70, "warning",
                        f"Intro échouée ({error_details[:50]}...), export sans intro"
                    )
                    self._add_warning(job, "intro_failed",
                        f"L'intro n'a pas pu être appliquée: {error_details[:100]}")

            # --- STEP 5: Move final clip to destination ---
            if current_clip != video_path and current_clip.exists():
                if video_path.exists():
                    video_path.unlink()
                shutil.move(str(current_clip), str(video_path))

            # Mix music if configured
            if music_config and music_config.get("path"):
                try:
                    job_manager.update_progress(job, 72, "music", "Mixing music...")
                    music_path = music_config.get("path")
                    music_volume = music_config.get("volume", 0.5)
                    music_offset = music_config.get("startOffset", 0)

                    if Path(music_path).exists():
                        video_with_music_path = exports_dir / f"{base_name}_with_music.mp4"

                        await self._mix_audio_track(
                            video_path=str(video_path),
                            audio_path=music_path,
                            output_path=str(video_with_music_path),
                            audio_volume=music_volume,
                            audio_offset=music_offset,
                        )

                        # Replace original with music version
                        if video_with_music_path.exists():
                            video_path.unlink()
                            video_with_music_path.rename(video_path)
                            logger.info(f"Mixed music into video: {music_path}")
                    else:
                        logger.warning(f"Music file not found: {music_path}")
                except Exception as music_error:
                    logger.warning(f"Music mixing failed, continuing without: {music_error}")

            # Record video artifact
            video_artifact = Artifact(
                project_id=project_id,
                segment_id=segment_id,
                variant=variant,
                type="video",
                path=str(video_path),
                filename=video_path.name,
                size=video_path.stat().st_size if video_path.exists() else 0,
                title=segment.topic_label,
            )
            db.add(video_artifact)
            artifacts.append(video_artifact)

            # Render cover
            if include_cover:
                job_manager.update_progress(job, 75, "cover", "Generating cover...")

                cover_path = exports_dir / f"{base_name}_cover.jpg"
                cover_time = segment.start_time + segment.duration * 0.3  # 30% into clip

                await self.render.render_cover(
                    source_path=project.source_path,
                    output_path=str(cover_path),
                    time=cover_time,
                    title_text=segment.topic_label
                )

                if cover_path.exists():
                    cover_artifact = Artifact(
                        project_id=project_id,
                        segment_id=segment_id,
                        variant=variant,
                        type="cover",
                        path=str(cover_path),
                        filename=cover_path.name,
                        size=cover_path.stat().st_size,
                    )
                    db.add(cover_artifact)
                    artifacts.append(cover_artifact)

            # Generate standalone caption files only if NOT burning subtitles
            # (when burning, subtitles are embedded in video - no need for separate files)
            if include_captions and transcript_segments and not burn_subtitles:
                job_manager.update_progress(job, 80, "captions", "Generating caption files...")

                # Adjust times to be relative to clip start
                adjusted_segments = [
                    {
                        **seg,
                        "start": seg["start"] - segment.start_time,
                        "end": seg["end"] - segment.start_time,
                    }
                    for seg in transcript_segments
                ]

                caption_paths = self.captions.save_captions(
                    adjusted_segments,
                    exports_dir,
                    base_name
                )

                for fmt, path in caption_paths.items():
                    artifact = Artifact(
                        project_id=project_id,
                        segment_id=segment_id,
                        variant=variant,
                        type=f"captions_{fmt}",
                        path=path,
                        filename=Path(path).name,
                        size=Path(path).stat().st_size if Path(path).exists() else 0,
                    )
                    db.add(artifact)
                    artifacts.append(artifact)

            # Generate post text
            if include_post:
                job_manager.update_progress(job, 85, "post", "Generating post text...")

                post_content = self._generate_post(segment, platform)
                post_path = exports_dir / f"{base_name}_post.txt"

                with open(post_path, "w", encoding="utf-8") as f:
                    f.write(post_content)

                post_artifact = Artifact(
                    project_id=project_id,
                    segment_id=segment_id,
                    variant=variant,
                    type="post",
                    path=str(post_path),
                    filename=post_path.name,
                    size=post_path.stat().st_size,
                    description=post_content[:500],
                )
                db.add(post_artifact)
                artifacts.append(post_artifact)

            # Generate metadata
            if include_metadata:
                job_manager.update_progress(job, 90, "metadata", "Generating metadata...")

                metadata = {
                    "project_id": project_id,
                    "segment_id": segment_id,
                    "variant": variant,
                    "platform": platform,
                    "source_file": project.source_filename,
                    "start_time": segment.start_time,
                    "end_time": segment.end_time,
                    "duration": segment.duration,
                    "score": {
                        "total": segment.score_total,
                        "hook_strength": segment.score_hook,
                        "payoff": segment.score_payoff,
                        "humour_reaction": segment.score_humour,
                        "tension_surprise": segment.score_tension,
                        "clarity_autonomy": segment.score_clarity,
                        "rhythm": segment.score_rhythm,
                        "reasons": segment.score_reasons,
                        "tags": segment.score_tags,
                    },
                    "topic_label": segment.topic_label,
                    "hook_text": segment.hook_text,
                    "layout_type": segment.layout_type,
                    "template_id": template_id,
                    "render_settings": {
                        "width": settings.OUTPUT_WIDTH,
                        "height": settings.OUTPUT_HEIGHT,
                        "fps": settings.OUTPUT_FPS,
                        "use_nvenc": use_nvenc,
                    },
                    "exported_at": datetime.utcnow().isoformat(),
                    "artifacts": [
                        {"type": a.type, "filename": a.filename}
                        for a in artifacts
                    ],
                }

                metadata_path = exports_dir / f"{base_name}_metadata.json"
                with open(metadata_path, "w", encoding="utf-8") as f:
                    json.dump(metadata, f, indent=2, ensure_ascii=False)

                metadata_artifact = Artifact(
                    project_id=project_id,
                    segment_id=segment_id,
                    variant=variant,
                    type="metadata",
                    path=str(metadata_path),
                    filename=metadata_path.name,
                    size=metadata_path.stat().st_size,
                )
                db.add(metadata_artifact)
                artifacts.append(metadata_artifact)

            # --- STEP 6: Validate output with ffprobe ---
            job_manager.update_progress(job, 95, "validate", "Validating export...")

            validation = await self._validate_export(str(video_path))
            if not validation["valid"]:
                logger.error(f"[Export] Validation failed: {validation['errors']}")
                self._add_warning(job, "validation_failed",
                    f"Validation: {', '.join(validation['errors'])}")
            else:
                logger.info(
                    f"[Export] Validation passed: {validation['duration']:.1f}s, "
                    f"{validation['width']}x{validation['height']}, "
                    f"audio={'yes' if validation['has_audio'] else 'NO'}"
                )

            # --- STEP 7: QC check ---
            qc_result = None
            if video_path.exists():
                try:
                    qc_service = QCService()
                    qc_report = await qc_service.run(
                        file_path=video_path,
                        expected_duration=segment.duration,
                        has_audio=True,
                        ffprobe_path=settings.FFPROBE_PATH,
                    )
                    qc_result = qc_report.to_dict()
                    logger.info(
                        f"[Export] QC result: {qc_report.overall.value} "
                        f"({sum(1 for c in qc_report.checks if c.passed)}/{len(qc_report.checks)} checks passed)"
                    )
                    # Store QC result in video artifact metadata
                    if video_artifact.description is None:
                        video_artifact.description = ""
                    # Store as JSON string in description field since Artifact has no metadata column
                    import json as _json
                    video_artifact.description = _json.dumps({"qc": qc_result})
                except Exception as qc_error:
                    logger.warning(f"[Export] QC check failed (non-blocking): {qc_error}")

            await db.commit()

            job_manager.update_progress(job, 100, "complete", "Export complete!")

            return {
                "project_id": project_id,
                "segment_id": segment_id,
                "variant": variant,
                "export_dir": str(exports_dir),
                "artifacts": [a.to_dict() for a in artifacts],
                "validation": validation,
                "qc": qc_result,
            }

    async def _run_single_pass_export(
        self,
        job: "Job",
        job_manager: "JobManager",
        project: "Project",
        segment: "Segment",
        project_id: str,
        segment_id: str,
        variant: str,
        exports_dir: Path,
        base_name: str,
        platform: str,
        include_captions: bool,
        burn_subtitles: bool,
        include_cover: bool,
        include_metadata: bool,
        include_post: bool,
        use_nvenc: bool,
        caption_style: dict[str, Any] | None,
        layout_config: dict[str, Any] | None,
        intro_config: dict[str, Any] | None,
        music_config: dict[str, Any] | None,
        jump_cut_config: dict[str, Any] | None,
        cold_open_config: dict[str, Any] | None,
        transcript_segments: list[dict[str, Any]],
        template: Optional["Template"],
        template_id: str | None,
        db,
    ) -> dict[str, Any]:
        """
        Single-pass export: assembles ALL transformations into one FFmpeg call.

        Covers: layout composition, jump cuts, cold open reorder, subtitle burn,
        intro overlay (pre-rendered then composited inline), and music mix.
        """
        logger.info("[SinglePass] Building single-pass FFmpeg pipeline")
        artifacts = []
        datetime.now().strftime("%Y%m%d_%H%M%S")
        video_path = exports_dir / f"{base_name}.mp4"

        # ── Apply platform preset constraints ────────────────────────────
        preset = settings.PLATFORM_PRESETS.get(platform, {})
        preset_max_duration = preset.get("max_duration")
        actual_duration = segment.duration
        if preset_max_duration and actual_duration > preset_max_duration:
            logger.warning(
                f"[SinglePass] Segment duration {actual_duration:.1f}s exceeds "
                f"{platform} max of {preset_max_duration}s — clip will be trimmed"
            )
            actual_duration = preset_max_duration

        # Platform codec: YouTube Shorts prefers H.265 when nvenc not in use
        _use_nvenc = use_nvenc
        if platform == "youtube_shorts" and not use_nvenc:
            # H.265 (libx265) is preferred for YouTube Shorts quality/size ratio
            # but NVENC h264 is acceptable and much faster
            logger.info("[SinglePass] YouTube Shorts: using libx265 for CPU encode")

        # ── Build layout config ───────────────────────────────────────────

        facecam_rect_norm = None
        content_rect_norm = None
        # Fraction of output height for the facecam zone (two-zone vstack).
        # Honors `facecamRatio` from the layout config when present.
        facecam_ratio_val = 0.4
        if layout_config and layout_config.get("facecamRatio"):
            try:
                facecam_ratio_val = float(layout_config["facecamRatio"])
            except (TypeError, ValueError):
                facecam_ratio_val = 0.4

        if layout_config and layout_config.get("facecam") and layout_config.get("content"):
            fc = layout_config["facecam"]
            cc = layout_config["content"]
            facecam_source = fc.get("sourceCrop", {"x": 0, "y": 0, "width": 1, "height": 1})
            content_source = cc.get("sourceCrop", {"x": 0, "y": 0, "width": 1, "height": 1})
            # Store as normalized {x, y, w, h} as expected by PipelineConfig
            facecam_rect_norm = {
                "x": max(0.0, min(facecam_source["x"], 0.99)),
                "y": max(0.0, min(facecam_source["y"], 0.99)),
                "w": max(0.01, min(facecam_source["width"], 1.0)),
                "h": max(0.01, min(facecam_source["height"], 1.0)),
            }
            content_rect_norm = {
                "x": max(0.0, min(content_source["x"], 0.99)),
                "y": max(0.0, min(content_source["y"], 0.99)),
                "w": max(0.01, min(content_source["width"], 1.0)),
                "h": max(0.01, min(content_source["height"], 1.0)),
            }
        elif (
            getattr(segment, "layout_type", None) == "stream_facecam"
            and segment.facecam_rect
            and segment.content_rect
        ):
            # No frontend layout passed (auto-pipeline path) — fall back to the
            # facecam/content zones detected during analysis, normalized to 0-1.
            # Gated to stream_facecam: produced/full-screen segments
            # (podcast_irl, talk_fullscreen) keep the safe center-crop rather
            # than a bogus two-zone built from a low-confidence facecam box.
            _vw = float(project.width or 1920)
            _vh = float(project.height or 1080)
            _fr, _cr = segment.facecam_rect, segment.content_rect
            facecam_rect_norm = {
                "x": _fr["x"] / _vw, "y": _fr["y"] / _vh,
                "w": _fr["width"] / _vw, "h": _fr["height"] / _vh,
            }
            content_rect_norm = {
                "x": _cr["x"] / _vw, "y": _cr["y"] / _vh,
                "w": _cr["width"] / _vw, "h": _cr["height"] / _vh,
            }

        # ── Face tracking — animated SmartCrop ──────────────────────────
        # NOTE: the single-pass pipeline builder composes a STATIC crop and does
        # not consume keyframes, so tracking is wasted there. Skip it for the
        # single-pass path and whenever the layout comes from an explicit
        # layout_config (a deliberately fixed zone, e.g. a corner webcam).
        facecam_keyframes: list = []
        _track_faces = (
            facecam_rect_norm
            and not layout_config
            and not getattr(settings, "EXPORT_SINGLE_PASS", True)
        )
        if _track_faces:
            # Only run tracking when there's a dedicated facecam zone
            try:
                from forge_engine.services.facecam_tracking import FacecamTracker
                _face_tracker = FacecamTracker()
                if _face_tracker.is_available():
                    job_manager.update_progress(
                        job, 5, "tracking", "Analyse des positions du visage..."
                    )
                    _detections = await _face_tracker.track_faces(
                        video_path=project.source_path,
                        start_time=segment.start_time,
                        end_time=segment.start_time + segment.duration,
                        sample_interval=0.5,
                    )
                    facecam_keyframes = _face_tracker.generate_keyframes(_detections)
                    logger.info(
                        f"[SinglePass] Face tracking: {len(facecam_keyframes)} keyframes "
                        f"over {segment.duration:.0f}s"
                    )
                    if len(facecam_keyframes) <= 1:
                        # Not enough movement to animate — use static crop
                        facecam_keyframes = []
            except Exception as _e:
                logger.info(f"[SinglePass] Face tracking unavailable ({_e}), using static crop")

        # ── Build ASS subtitle file ───────────────────────────────────────
        ass_path = None
        if include_captions and burn_subtitles and transcript_segments:
            try:
                caption_config = {
                    "style": "custom" if caption_style else "forge_minimal",
                    "word_level": True,
                    "max_words_per_line": caption_style.get("wordsPerLine", 4) if caption_style else 4,
                    "max_lines": 2,
                    # Layout-aware caption placement (safe band in the content zone).
                    "facecam_ratio": facecam_ratio_val,
                }
                if caption_style:
                    caption_config["custom_style"] = {
                        "facecam_ratio": facecam_ratio_val,
                        "font_family": caption_style.get("fontFamily", "Inter"),
                        "font_size": caption_style.get("fontSize", 48),
                        "font_weight": caption_style.get("fontWeight", 700),
                        "color": caption_style.get("color", "#FFFFFF"),
                        "background_color": caption_style.get("backgroundColor", "transparent"),
                        "outline_color": caption_style.get("outlineColor", "#000000"),
                        "outline_width": caption_style.get("outlineWidth", 2),
                        "position": caption_style.get("position", "bottom"),
                        "position_y": caption_style.get("positionY"),
                        "animation": caption_style.get("animation", "none"),
                        "highlight_color": caption_style.get("highlightColor", "#FFD700"),
                    }
                elif template and template.caption_style:
                    caption_config.update(template.caption_style)

                # Adjust timestamps to clip-relative (0-based). Must shift the
                # per-WORD timestamps too: karaoke uses segment["words"][].start/
                # end, and shifting only the segment start/end left every caption
                # timed at its absolute VOD position (e.g. 0:53:03) — so none
                # rendered within the trimmed clip.
                _off = segment.start_time
                adjusted = []
                for seg in transcript_segments:
                    new_seg = {
                        **seg,
                        "start": seg["start"] - _off,
                        "end": seg["end"] - _off,
                    }
                    if seg.get("words"):
                        new_seg["words"] = [
                            {
                                **w,
                                "start": w.get("start", 0.0) - _off,
                                "end": w.get("end", 0.0) - _off,
                            }
                            for w in seg["words"]
                        ]
                    adjusted.append(new_seg)
                ass_file = exports_dir / f"{base_name}.ass"
                # generate_ass returns the ASS document as a string and takes
                # `transcript_segments` + `custom_style` (it does NOT write a file
                # nor accept segments=/output_path=/config= — that was a stale call
                # that silently dropped subtitles on every export).
                ass_content = self.captions.generate_ass(
                    transcript_segments=adjusted,
                    custom_style=caption_config,
                )
                ass_file.write_text(ass_content, encoding="utf-8")
                if ass_file.exists():
                    ass_path = ass_file
                    logger.info(f"[SinglePass] Generated ASS subtitles: {ass_file}")
            except Exception as e:
                logger.warning(f"[SinglePass] ASS subtitle generation failed: {e}, continuing without")

        # ── Analyze jump cuts if enabled ─────────────────────────────────
        keep_ranges = []
        needs_jump_cuts = jump_cut_config and jump_cut_config.get("enabled")
        if needs_jump_cuts:
            try:
                job_manager.update_progress(job, 8, "jump_cuts", "Analyzing audio for jump cuts...")
                jc_config = JumpCutConfig.from_dict(jump_cut_config)
                jump_cut_analysis = await self.jump_cuts.analyze_segment(
                    audio_path=project.source_path,
                    start_time=segment.start_time,
                    duration=segment.duration,
                    config=jc_config,
                )
                if jump_cut_analysis.cuts_count > 0:
                    keep_ranges = [
                        (r.start, r.end) for r in jump_cut_analysis.keep_ranges
                    ]
                    logger.info(
                        f"[SinglePass] Jump cuts: {jump_cut_analysis.cuts_count} cuts, "
                        f"{jump_cut_analysis.time_saved:.1f}s saved"
                    )
                    job.metadata = job.metadata or {}
                    job.metadata["jump_cuts"] = jump_cut_analysis.to_dict()
            except Exception as e:
                logger.warning(f"[SinglePass] Jump cut analysis failed: {e}, continuing without")

        # ── Music path ───────────────────────────────────────────────────
        music_path_obj = None
        music_volume = 0.15
        if music_config and music_config.get("path"):
            mp = Path(music_config["path"])
            if mp.exists():
                music_path_obj = mp
                music_volume = music_config.get("volume", 0.15)

        # ── Cold open hook detection ─────────────────────────────────────
        cold_open_hook_start: float | None = None
        cold_open_hook_end: float | None = None
        if cold_open_config and cold_open_config.get("enabled"):
            try:
                # Timestamps must be relative to clip start (0-based) AND within
                # the *effective* clip window (actual_duration may be trimmed to
                # the platform max). Using segment.duration here let a hook past
                # the trimmed window through → concat referenced frames beyond the
                # input and FFmpeg crashed (rc=234, "Error reinitializing filters").
                clip_end_abs = segment.start_time + actual_duration
                adjusted_transcript = [
                    {
                        **seg,
                        "start": seg["start"] - segment.start_time,
                        "end": seg["end"] - segment.start_time,
                    }
                    for seg in transcript_segments
                    if segment.start_time <= seg.get("start", 0) <= clip_end_abs
                ]
                segment_dict = {"start_time": 0.0, "end_time": actual_duration}
                language = cold_open_config.get("language", "fr")
                variations = await self.cold_open.generate_cold_opens(
                    segment=segment_dict,
                    transcript_segments=adjusted_transcript,
                    language=language,
                    max_variations=1,
                )
                real_variations = [v for v in variations if v.id != "control"]
                if real_variations:
                    best = real_variations[0]
                    hs, he = best.hook.start_time, best.hook.end_time
                    if hs >= 1.0 and he <= actual_duration - 1.0:
                        cold_open_hook_start = hs
                        cold_open_hook_end = he
                        logger.info(
                            f"[SinglePass] Cold open hook detected: "
                            f"{hs:.1f}s–{he:.1f}s (score={best.hook.score})"
                        )
                    else:
                        logger.info("[SinglePass] Cold open hook too close to edges, skipping")
                else:
                    logger.info("[SinglePass] No cold open hook found")
            except Exception as e:
                logger.warning(f"[SinglePass] Cold open detection failed: {e}, continuing without")

        # ── Intro pre-render ─────────────────────────────────────────────
        intro_clip_path: Path | None = None
        intro_duration_val: float = 0.0
        if intro_config and intro_config.get("enabled"):
            try:
                if not intro_config.get("title"):
                    intro_config = {**intro_config, "title": segment.topic_label or "Untitled"}
                intro_duration_val = float(intro_config.get("duration", 2.5))
                _intro_out = exports_dir / f"{base_name}_intro_clip.mp4"
                job_manager.update_progress(job, 8, "intro", "Pre-rendering intro clip...")
                await self.intro.render_intro(
                    source_path=project.source_path,
                    output_path=str(_intro_out),
                    start_time=segment.start_time,
                    duration=intro_duration_val,
                    config=intro_config,
                )
                if _intro_out.exists() and _intro_out.stat().st_size > 0:
                    intro_clip_path = _intro_out
                    logger.info(
                        f"[SinglePass] Intro pre-rendered: {_intro_out.name} "
                        f"({intro_duration_val:.1f}s)"
                    )
                else:
                    logger.warning("[SinglePass] Intro render produced no output, skipping")
            except Exception as e:
                logger.warning(f"[SinglePass] Intro pre-render failed: {e}, continuing without")
                intro_clip_path = None
                intro_duration_val = 0.0

        # ── Build PipelineConfig ─────────────────────────────────────────
        pipeline_cfg = PipelineConfig(
            source_path=Path(project.source_path),
            segment_start=segment.start_time,
            segment_duration=actual_duration,  # Possibly trimmed to platform max
            output_width=settings.OUTPUT_WIDTH,
            output_height=settings.OUTPUT_HEIGHT,
            source_width=project.width or 1920,
            source_height=project.height or 1080,
            facecam_rect=facecam_rect_norm,
            content_rect=content_rect_norm,
            facecam_ratio=facecam_ratio_val,
            facecam_keyframes=facecam_keyframes,
            ass_path=ass_path,
            fonts_dir=getattr(settings, "FONTS_DIR", None),
            keep_ranges=keep_ranges,
            cold_open_hook_start=cold_open_hook_start,
            cold_open_hook_end=cold_open_hook_end,
            intro_path=intro_clip_path,
            intro_duration=intro_duration_val,
            music_path=music_path_obj,
            music_volume=music_volume,
            output_path=video_path,
            fps=settings.OUTPUT_FPS,
            crf=settings.OUTPUT_CRF,
            use_nvenc=use_nvenc,
            platform=platform,
        )

        pipeline = PipelineSinglePass(pipeline_cfg)
        cmd = pipeline.build_command()

        logger.info(f"[SinglePass] FFmpeg command ({len(cmd)} args): {' '.join(cmd[:12])} ...")

        job_manager.update_progress(job, 10, "render", "Running single-pass render...")

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            err = stderr.decode(errors="replace")[-1000:]
            logger.error(f"[SinglePass] FFmpeg failed (rc={proc.returncode}): {err}")
            raise RuntimeError(f"Single-pass render failed: {err}")

        logger.info(f"[SinglePass] Render complete: {video_path}")
        job_manager.update_progress(job, 70, "render", "Single-pass render complete")

        # ── Record video artifact ────────────────────────────────────────
        video_artifact = Artifact(
            project_id=project_id,
            segment_id=segment_id,
            variant=variant,
            type="video",
            path=str(video_path),
            filename=video_path.name,
            size=video_path.stat().st_size if video_path.exists() else 0,
            title=segment.topic_label,
        )
        db.add(video_artifact)
        artifacts.append(video_artifact)

        # ── Cover ────────────────────────────────────────────────────────
        if include_cover:
            job_manager.update_progress(job, 75, "cover", "Generating cover...")
            cover_path = exports_dir / f"{base_name}_cover.jpg"
            cover_time = segment.start_time + segment.duration * 0.3
            await self.render.render_cover(
                source_path=project.source_path,
                output_path=str(cover_path),
                time=cover_time,
                title_text=segment.topic_label,
            )
            if cover_path.exists():
                cover_artifact = Artifact(
                    project_id=project_id,
                    segment_id=segment_id,
                    variant=variant,
                    type="cover",
                    path=str(cover_path),
                    filename=cover_path.name,
                    size=cover_path.stat().st_size,
                )
                db.add(cover_artifact)
                artifacts.append(cover_artifact)

        # ── Post text ────────────────────────────────────────────────────
        if include_post:
            job_manager.update_progress(job, 85, "post", "Generating post text...")
            post_content = self._generate_post(segment, platform)
            post_path = exports_dir / f"{base_name}_post.txt"
            with open(post_path, "w", encoding="utf-8") as f:
                f.write(post_content)
            post_artifact = Artifact(
                project_id=project_id,
                segment_id=segment_id,
                variant=variant,
                type="post",
                path=str(post_path),
                filename=post_path.name,
                size=post_path.stat().st_size,
                description=post_content[:500],
            )
            db.add(post_artifact)
            artifacts.append(post_artifact)

        # ── Metadata ─────────────────────────────────────────────────────
        if include_metadata:
            job_manager.update_progress(job, 90, "metadata", "Generating metadata...")
            metadata = {
                "project_id": project_id,
                "segment_id": segment_id,
                "variant": variant,
                "platform": platform,
                "source_file": project.source_filename,
                "start_time": segment.start_time,
                "end_time": segment.end_time,
                "duration": segment.duration,
                "pipeline": "single_pass",
                "exported_at": datetime.utcnow().isoformat(),
                "artifacts": [{"type": a.type, "filename": a.filename} for a in artifacts],
            }
            metadata_path = exports_dir / f"{base_name}_metadata.json"
            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            metadata_artifact = Artifact(
                project_id=project_id,
                segment_id=segment_id,
                variant=variant,
                type="metadata",
                path=str(metadata_path),
                filename=metadata_path.name,
                size=metadata_path.stat().st_size,
            )
            db.add(metadata_artifact)
            artifacts.append(metadata_artifact)

        # ── Validate ─────────────────────────────────────────────────────
        job_manager.update_progress(job, 95, "validate", "Validating export...")
        validation = await self._validate_export(str(video_path))
        if not validation["valid"]:
            logger.error(f"[SinglePass] Validation failed: {validation['errors']}")
            self._add_warning(job, "validation_failed",
                f"Validation: {', '.join(validation['errors'])}")
        else:
            logger.info(
                f"[SinglePass] Validation passed: {validation['duration']:.1f}s, "
                f"{validation['width']}x{validation['height']}"
            )

        # ── QC check ─────────────────────────────────────────────────────
        qc_result = None
        if video_path.exists():
            try:
                qc_service = QCService()
                qc_report = await qc_service.run(
                    file_path=video_path,
                    expected_duration=segment.duration,
                    has_audio=True,
                    ffprobe_path=settings.FFPROBE_PATH,
                )
                qc_result = qc_report.to_dict()
                logger.info(
                    f"[SinglePass] QC: {qc_report.overall.value} "
                    f"({sum(1 for c in qc_report.checks if c.passed)}/{len(qc_report.checks)} checks passed)"
                )
                if video_artifact.description is None:
                    video_artifact.description = ""
                video_artifact.description = json.dumps({"qc": qc_result})
            except Exception as qc_error:
                logger.warning(f"[SinglePass] QC check failed (non-blocking): {qc_error}")

        await db.commit()
        job_manager.update_progress(job, 100, "complete", "Export complete (single-pass)!")

        return {
            "project_id": project_id,
            "segment_id": segment_id,
            "variant": variant,
            "export_dir": str(exports_dir),
            "artifacts": [a.to_dict() for a in artifacts],
            "validation": validation,
            "qc": qc_result,
            "pipeline": "single_pass",
        }

    async def generate_variants(
        self,
        job: Job,
        project_id: str,
        segment_id: str,
        variants: list[dict[str, Any]],
        render_proxy: bool = True
    ) -> dict[str, Any]:
        """Generate multiple variants for a segment."""
        job_manager = JobManager.get_instance()

        async with async_session_maker() as db:
            result = await db.execute(select(Segment).where(Segment.id == segment_id))
            segment = result.scalar_one_or_none()

            if not segment:
                raise ValueError(f"Segment not found: {segment_id}")

            result = await db.execute(select(Project).where(Project.id == project_id))
            project = result.scalar_one_or_none()

            if not project:
                raise ValueError(f"Project not found: {project_id}")

            project_dir = settings.LIBRARY_PATH / "projects" / project_id
            renders_dir = project_dir / "renders" / segment_id
            renders_dir.mkdir(parents=True, exist_ok=True)

            generated_variants = []

            for i, variant_config in enumerate(variants):
                label = variant_config.get("label", chr(65 + i))  # A, B, C

                job_manager.update_progress(
                    job,
                    (i / len(variants)) * 100,
                    f"variant_{label}",
                    f"Generating variant {label}..."
                )

                if render_proxy:
                    proxy_path = renders_dir / f"variant_{label}_proxy.mp4"

                    layout_config = {
                        "facecam_rect": segment.facecam_rect,
                        "content_rect": segment.content_rect,
                        **(variant_config.get("layout_overrides", {}))
                    }

                    success = await self.render.render_proxy(
                        source_path=project.source_path,
                        output_path=str(proxy_path),
                        start_time=segment.start_time,
                        duration=segment.duration,
                        layout_config=layout_config
                    )

                    generated_variants.append({
                        "label": label,
                        "config": variant_config,
                        "proxy_path": str(proxy_path) if success else None,
                    })
                else:
                    generated_variants.append({
                        "label": label,
                        "config": variant_config,
                        "proxy_path": None,
                    })

            # Update segment with variants
            segment.variants = generated_variants
            await db.commit()

            job_manager.update_progress(job, 100, "complete", f"Generated {len(variants)} variants")

            return {
                "segment_id": segment_id,
                "variants": generated_variants,
            }

    # ================================================================
    # Utility methods
    # ================================================================

    def _cleanup_temp(self, temp_path: Path, final_path: Path):
        """Clean up a temporary file if it's not the final output."""
        if temp_path != final_path and temp_path.exists():
            try:
                temp_path.unlink()
            except Exception as e:
                logger.warning(f"Could not delete temp clip {temp_path}: {e}")

    def _add_warning(self, job: Job, warning_type: str, message: str):
        """Add a warning to job metadata."""
        job.metadata = job.metadata or {}
        job.metadata["warnings"] = job.metadata.get("warnings", [])
        job.metadata["warnings"].append({
            "type": warning_type,
            "message": message
        })

    async def _validate_export(self, video_path: str) -> dict[str, Any]:
        """Validate exported video using ffprobe.

        Checks:
        - File exists and is not empty
        - Has video stream with correct dimensions (1080x1920)
        - Has audio stream
        - Duration is reasonable (> 3s, < 300s)

        Returns dict with validation results.
        """
        from forge_engine.services.ffmpeg import FFmpegService

        result = {
            "valid": True,
            "errors": [],
            "width": 0,
            "height": 0,
            "duration": 0,
            "has_audio": False,
            "has_video": False,
            "file_size_mb": 0,
        }

        path = Path(video_path)
        if not path.exists():
            result["valid"] = False
            result["errors"].append("Output file does not exist")
            return result

        file_size = path.stat().st_size
        result["file_size_mb"] = round(file_size / (1024 * 1024), 2)

        if file_size < 10000:  # < 10KB is definitely corrupted
            result["valid"] = False
            result["errors"].append(f"File too small ({result['file_size_mb']} MB)")
            return result

        try:
            ffmpeg = FFmpegService.get_instance()
            probe_data = await ffmpeg.probe(video_path)

            streams = probe_data.get("streams", [])
            format_info = probe_data.get("format", {})

            # Check duration
            duration = float(format_info.get("duration", 0))
            result["duration"] = duration

            if duration < 1.0:
                result["valid"] = False
                result["errors"].append(f"Duration too short ({duration:.1f}s)")
            elif duration > 600:
                result["errors"].append(f"Duration unusually long ({duration:.1f}s)")

            # Check streams
            for stream in streams:
                codec_type = stream.get("codec_type")
                if codec_type == "video":
                    result["has_video"] = True
                    result["width"] = stream.get("width", 0)
                    result["height"] = stream.get("height", 0)
                elif codec_type == "audio":
                    result["has_audio"] = True

            if not result["has_video"]:
                result["valid"] = False
                result["errors"].append("No video stream found")

            if not result["has_audio"]:
                result["errors"].append("No audio stream (may be intentional)")

            # Check dimensions (should be 1080x1920 for 9:16)
            if result["has_video"]:
                w, h = result["width"], result["height"]
                if w > 0 and h > 0:
                    aspect = h / w if w > 0 else 0
                    if aspect < 1.5:  # Not vertical
                        result["errors"].append(
                            f"Unexpected aspect ratio: {w}x{h} (expected vertical 9:16)"
                        )

        except Exception as e:
            result["errors"].append(f"ffprobe failed: {str(e)[:100]}")

        return result

    async def _apply_cold_open(
        self,
        clip_path: str,
        output_path: str,
        segment: "Segment",
        transcript_segments: list[dict[str, Any]],
        config: dict[str, Any],
        progress_callback=None,
    ):
        """Apply cold open effect: move the best hook to the beginning.

        Takes the rendered clip and reorders it:
        1. Hook section (from middle/end of clip) plays first
        2. Optional transition
        3. Rest of clip plays from the beginning

        This creates the "start with the best moment" effect.
        """
        from forge_engine.services.ffmpeg import FFmpegService

        ffmpeg = FFmpegService.get_instance()

        # Adjust transcript timestamps to be relative to clip start (0-based)
        adjusted_transcript = []
        for seg in transcript_segments:
            if segment.start_time <= seg.get("start", 0) <= segment.end_time:
                adjusted_transcript.append({
                    **seg,
                    "start": seg["start"] - segment.start_time,
                    "end": seg["end"] - segment.start_time,
                    "words": [
                        {**w, "start": w["start"] - segment.start_time, "end": w["end"] - segment.start_time}
                        for w in seg.get("words", [])
                    ] if seg.get("words") else None
                })

        # Build segment dict for cold_open engine
        segment_dict = {
            "start_time": 0,
            "end_time": segment.duration,
        }

        # Generate cold open variations
        language = config.get("language", "fr")
        variations = await self.cold_open.generate_cold_opens(
            segment=segment_dict,
            transcript_segments=adjusted_transcript,
            language=language,
            max_variations=1,
        )

        # Filter out control variation, take best
        real_variations = [v for v in variations if v.id != "control"]
        if not real_variations:
            logger.info("[Export] No suitable cold open hook found, skipping")
            # Just copy the file
            shutil.copy2(clip_path, output_path)
            return

        best = real_variations[0]
        logger.info(
            f"[Export] Cold open: hook '{best.hook.text[:40]}...' "
            f"at {best.hook.start_time:.1f}s-{best.hook.end_time:.1f}s "
            f"(score={best.hook.score}, style={best.style.value})"
        )

        # Build FFmpeg command to reorder the clip:
        # [hook_section] + [beginning_to_hook] + [after_hook_to_end]
        hook_start = best.hook.start_time
        hook_end = best.hook.end_time
        clip_duration = segment.duration

        # Ensure valid ranges
        if hook_start < 1.0 or hook_end > clip_duration - 1.0:
            logger.info("[Export] Hook too close to edges, skipping cold open")
            shutil.copy2(clip_path, output_path)
            return

        filter_parts = []
        concat_parts = []
        idx = 0

        # Part 1: The hook (from middle/end)
        filter_parts.append(
            f"[0:v]trim=start={hook_start}:end={hook_end},setpts=PTS-STARTPTS[v{idx}]"
        )
        filter_parts.append(
            f"[0:a]atrim=start={hook_start}:end={hook_end},asetpts=PTS-STARTPTS[a{idx}]"
        )
        concat_parts.append(f"[v{idx}][a{idx}]")
        idx += 1

        # Part 2: Beginning up to hook start
        if hook_start > 0.1:
            filter_parts.append(
                f"[0:v]trim=start=0:end={hook_start},setpts=PTS-STARTPTS[v{idx}]"
            )
            filter_parts.append(
                f"[0:a]atrim=start=0:end={hook_start},asetpts=PTS-STARTPTS[a{idx}]"
            )
            concat_parts.append(f"[v{idx}][a{idx}]")
            idx += 1

        # Part 3: After hook to end
        if hook_end < clip_duration - 0.1:
            filter_parts.append(
                f"[0:v]trim=start={hook_end}:end={clip_duration},setpts=PTS-STARTPTS[v{idx}]"
            )
            filter_parts.append(
                f"[0:a]atrim=start={hook_end}:end={clip_duration},asetpts=PTS-STARTPTS[a{idx}]"
            )
            concat_parts.append(f"[v{idx}][a{idx}]")
            idx += 1

        # Concat all parts
        n = len(concat_parts)
        filter_parts.append(
            f"{''.join(concat_parts)}concat=n={n}:v=1:a=1[outv][outa]"
        )

        filter_complex = ";".join(filter_parts)

        cmd = [
            ffmpeg.ffmpeg_path,
            "-y",
            "-i", clip_path,
            "-filter_complex", filter_complex,
            "-map", "[outv]",
            "-map", "[outa]",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "18",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
            output_path
        ]

        logger.info(f"[Export] Cold open FFmpeg: {n} parts, hook={hook_start:.1f}-{hook_end:.1f}s")

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            error_msg = stderr.decode(errors='replace')[:500]
            logger.error(f"[Export] Cold open FFmpeg failed: {error_msg}")
            raise RuntimeError(f"Cold open render failed: {error_msg}")

        if progress_callback:
            progress_callback(100)

    def _generate_post(self, segment: "Segment", platform: str) -> str:
        """Generate post text with title, description, and hashtags."""
        title = segment.topic_label or "Check this out!"

        # Generate description
        description = segment.hook_text or ""
        if segment.score_reasons:
            description += "\n\n" + " • ".join(segment.score_reasons[:3])

        # Generate hashtags based on tags
        base_hashtags = ["viral", "clip", "highlights"]

        tag_to_hashtag = {
            "humour": ["funny", "comedy", "lol"],
            "surprise": ["unexpected", "shocking", "wow"],
            "rage": ["angry", "rage", "rant"],
            "clutch": ["clutch", "gaming", "win"],
            "debate": ["debate", "discussion", "hot"],
            "fail": ["fail", "fails", "rip"],
        }

        hashtags = base_hashtags.copy()
        for tag in (segment.score_tags or []):
            if tag in tag_to_hashtag:
                hashtags.extend(tag_to_hashtag[tag])

        # Platform-specific hashtags
        platform_hashtags = {
            "tiktok": ["fyp", "foryou", "tiktok"],
            "shorts": ["shorts", "youtube", "ytshorts"],
            "reels": ["reels", "instagram", "igreels"],
        }

        hashtags.extend(platform_hashtags.get(platform, []))

        # Deduplicate and limit
        hashtags = list(dict.fromkeys(hashtags))[:15]
        hashtag_text = " ".join(f"#{tag}" for tag in hashtags)

        return f"""📌 {title}

{description}

{hashtag_text}
"""

    async def _mix_audio_track(
        self,
        video_path: str,
        audio_path: str,
        output_path: str,
        audio_volume: float = 0.5,
        audio_offset: float = 0.0,
    ) -> None:
        """Mix an additional audio track (music) with the video's audio.

        Args:
            video_path: Path to video file
            audio_path: Path to audio file (MP3, WAV, etc.)
            output_path: Path for output video
            audio_volume: Volume of added audio (0.0-1.0)
            audio_offset: Seconds to skip at start of audio track
        """
        import asyncio

        # FFmpeg command to mix audio
        # - adelay to sync if needed
        # - amix to blend the two audio tracks
        # - Keep video stream, add mixed audio
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-ss", str(audio_offset),
            "-i", audio_path,
            "-filter_complex", f"[0:a]volume=1.0[a0];[1:a]volume={audio_volume}[a1];[a0][a1]amix=inputs=2:duration=first:dropout_transition=2[aout]",
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "copy",  # Copy video stream without re-encoding
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            output_path,
        ]

        logger.info(f"Mixing audio: {' '.join(cmd)}")

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise RuntimeError(f"Audio mixing failed: {stderr.decode(errors='replace')[:500]}")

    async def generate_all_variants(
        self,
        job: Job,
        project_id: str,
        segment_id: str,
        styles: list[str] | None = None,
        platform: str = "tiktok",
        include_captions: bool = True,
        burn_subtitles: bool = True,
        use_nvenc: bool = True,
        layout_config: dict[str, Any] | None = None,
        intro_config: dict[str, Any] | None = None,
        music_config: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Generate all 3 style variants in one operation.

        This exports the same segment with VIRAL, CLEAN, and IMPACT styles,
        allowing the user to quickly compare and choose the best one.
        """
        from forge_engine.services.auto_params import get_auto_params_service

        job_manager = JobManager.get_instance()

        # Default to all 3 TikTok-optimized styles
        if styles is None:
            styles = ["viral", "clean", "impact"]

        results = {
            "success": True,
            "variants": [],
            "errors": []
        }

        total_styles = len(styles)

        for idx, style_name in enumerate(styles):
            variant_letter = chr(65 + idx)  # A, B, C

            try:
                # Update progress
                base_progress = int((idx / total_styles) * 100)
                await job_manager._update_db_progress(
                    job.id,
                    progress=base_progress,
                    message=f"Generating {style_name.upper()} variant ({idx+1}/{total_styles})",
                    stage="multi_export"
                )

                # Get auto-computed parameters
                auto_params = get_auto_params_service()
                optimal = await auto_params.compute_optimal_params(
                    layout_info=layout_config
                )

                # Create caption style for this variant
                caption_style = {
                    "style_name": style_name,
                    "position": optimal.get("subtitle_position", "bottom"),
                    "positionY": optimal.get("subtitle_position_y"),
                }

                # Run export for this variant
                variant_result = await self.run_export(
                    job=job,
                    project_id=project_id,
                    segment_id=segment_id,
                    variant=f"{variant_letter}_{style_name}",
                    platform=platform,
                    include_captions=include_captions,
                    burn_subtitles=burn_subtitles,
                    use_nvenc=use_nvenc,
                    caption_style=caption_style,
                    layout_config=layout_config,
                    intro_config=intro_config,
                    music_config=music_config
                )

                results["variants"].append({
                    "style": style_name,
                    "variant": variant_letter,
                    "output_path": variant_result.get("video_path"),
                    "artifacts": variant_result.get("artifacts", [])
                })

                logger.info(f"[MultiExport] Generated {style_name} variant successfully")

            except Exception as e:
                logger.error(f"[MultiExport] Failed to generate {style_name} variant: {e}")
                results["errors"].append({
                    "style": style_name,
                    "error": str(e)
                })

        # Final progress
        await job_manager._update_db_progress(
            job.id,
            progress=100,
            message=f"Generated {len(results['variants'])} variants",
            stage="complete"
        )

        results["success"] = len(results["errors"]) == 0

        return results

    async def batch_export_all(
        self,
        job: Job,
        project_id: str,
        min_score: float = 70.0,
        max_clips: int = 500,
        style: str = "viral_pro",
        platform: str = "tiktok",
        include_captions: bool = True,
        burn_subtitles: bool = True,
        include_cover: bool = True,
        include_metadata: bool = True,
        use_nvenc: bool = True,
    ) -> dict[str, Any]:
        """
        WORLD CLASS BATCH EXPORT - Export all high-scoring segments in one click.

        This is the simplified workflow:
        1. Get all segments with score >= min_score
        2. Take top max_clips segments
        3. Apply viral_pro style by default
        4. Export all clips automatically with covers

        Args:
            project_id: Project ID
            min_score: Minimum score threshold (default: 70)
            max_clips: Maximum number of clips to export (default: 20)
            style: Caption style to use (default: viral_pro)
            platform: Target platform (default: tiktok)
        """
        job_manager = JobManager.get_instance()

        async with async_session_maker() as db:
            # Get project
            result = await db.execute(select(Project).where(Project.id == project_id))
            project = result.scalar_one_or_none()

            if not project:
                raise ValueError(f"Project not found: {project_id}")

            # Get all segments above threshold, sorted by score
            result = await db.execute(
                select(Segment)
                .where(Segment.project_id == project_id)
                .where(Segment.score_total >= min_score)
                .order_by(Segment.score_total.desc())
                .limit(max_clips)
            )
            segments = result.scalars().all()

            if not segments:
                job_manager.update_progress(job, 100, "complete", "Aucun segment au-dessus du seuil")
                return {
                    "success": True,
                    "project_id": project_id,
                    "exported_count": 0,
                    "clips": [],
                    "message": f"Aucun segment avec score >= {min_score}"
                }

            logger.info(f"[BatchExport] Found {len(segments)} segments to export (score >= {min_score})")

            exported_clips = []
            errors = []
            total_segments = len(segments)

            from forge_engine.services.captions import DEFAULT_STYLE
            caption_style_config = DEFAULT_STYLE

            # Convert backend style to frontend format for run_export
            caption_style = {
                "fontFamily": caption_style_config.get("font_family", "Montserrat"),
                "fontSize": caption_style_config.get("font_size", 96),
                "fontWeight": 900 if caption_style_config.get("bold") else 700,
                "color": self._ass_color_to_hex(caption_style_config.get("primary_color", "&H00FFFFFF")),
                "backgroundColor": "transparent",
                "outlineColor": self._ass_color_to_hex(caption_style_config.get("outline_color", "&H00000000")),
                "outlineWidth": caption_style_config.get("outline_width", 5),
                "position": "center" if caption_style_config.get("alignment") == 5 else "bottom",
                "positionY": caption_style_config.get("margin_v", 960),
                "animation": caption_style_config.get("animation", "pop"),
                "highlightColor": self._ass_color_to_hex(caption_style_config.get("highlight_color", "&H0000D7FF")),
                "wordsPerLine": caption_style_config.get("max_words_per_line", 3),
            }

            for idx, segment in enumerate(segments):
                try:
                    # Calculate progress
                    base_progress = int((idx / total_segments) * 100)
                    job_manager.update_progress(
                        job,
                        base_progress,
                        f"export_{idx+1}",
                        f"Exporting clip {idx+1}/{total_segments}: {segment.topic_label or 'Untitled'}"
                    )

                    # Create a sub-job for this export (or use same job with progress offset)
                    variant = f"batch_{idx+1:02d}"

                    # Let run_export use the segment's detected layout via its
                    # own fallback (lines that read segment.facecam_rect directly).
                    # Don't build a sourceCrop wrapper here -- that format expects
                    # 0-1 normalized values which we don't have from segment rects.
                    layout_config = None

                    # Run export
                    export_result = await self.run_export(
                        job=job,
                        project_id=project_id,
                        segment_id=segment.id,
                        variant=variant,
                        platform=platform,
                        include_captions=include_captions,
                        burn_subtitles=burn_subtitles,
                        include_cover=include_cover,
                        include_metadata=include_metadata,
                        include_post=True,
                        use_nvenc=use_nvenc,
                        caption_style=caption_style,
                        layout_config=layout_config,
                    )

                    exported_clips.append({
                        "segment_id": segment.id,
                        "topic": segment.topic_label,
                        "score": segment.score_total,
                        "duration": segment.duration,
                        "variant": variant,
                        "export_dir": export_result.get("export_dir"),
                        "artifacts": export_result.get("artifacts", []),
                    })

                    logger.info(f"[BatchExport] Exported clip {idx+1}/{total_segments}: {segment.topic_label}")

                except Exception as e:
                    logger.error(f"[BatchExport] Failed to export segment {segment.id}: {e}")
                    errors.append({
                        "segment_id": segment.id,
                        "topic": segment.topic_label,
                        "error": str(e)
                    })

            job_manager.update_progress(job, 100, "complete", f"Batch export terminé: {len(exported_clips)} clips")

            return {
                "success": len(errors) == 0,
                "project_id": project_id,
                "exported_count": len(exported_clips),
                "total_available": total_segments,
                "clips": exported_clips,
                "errors": errors,
                "style_used": style,
            }

    def _ass_color_to_hex(self, ass_color: str) -> str:
        """Convert ASS color (&HAABBGGRR) to hex (#RRGGBB)."""
        if not ass_color or not ass_color.startswith("&H"):
            return "#FFFFFF"

        # ASS format: &HAABBGGRR where AA=alpha, BB=blue, GG=green, RR=red
        color = ass_color[2:]  # Remove &H
        if len(color) >= 6:
            # Extract BGR and convert to RGB
            bb = color[-6:-4] if len(color) >= 6 else "FF"
            gg = color[-4:-2] if len(color) >= 4 else "FF"
            rr = color[-2:] if len(color) >= 2 else "FF"
            return f"#{rr}{gg}{bb}"

        return "#FFFFFF"









