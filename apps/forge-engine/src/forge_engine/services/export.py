"""Export service for generating complete export packs."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from forge_engine.core.config import settings
from forge_engine.core.database import async_session_maker
from forge_engine.core.jobs import Job, JobManager
from forge_engine.models import Project, Segment, Artifact, Template
from forge_engine.services.render import RenderService
from forge_engine.services.captions import CaptionEngine
from forge_engine.services.intro import IntroEngine

logger = logging.getLogger(__name__)


class ExportService:
    """Service for exporting clips and generating export packs."""
    
    def __init__(self):
        self.render = RenderService()
        self.captions = CaptionEngine()
        self.intro = IntroEngine()
    
    async def run_export(
        self,
        job: Job,
        project_id: str,
        segment_id: str,
        variant: str = "A",
        template_id: Optional[str] = None,
        platform: str = "tiktok",
        include_captions: bool = True,
        burn_subtitles: bool = True,
        include_cover: bool = True,
        include_metadata: bool = True,
        include_post: bool = True,
        use_nvenc: bool = True,
        caption_style: Optional[Dict[str, Any]] = None,
        layout_config: Optional[Dict[str, Any]] = None,
        intro_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Run the export pipeline."""
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
                with open(transcript_path, "r", encoding="utf-8") as f:
                    transcript_data = json.load(f)
                
                # Filter to segment time range
                all_segments = transcript_data.get("segments", [])
                transcript_segments = [
                    seg for seg in all_segments
                    if segment.start_time <= seg.get("start", 0) <= segment.end_time
                ]
                logger.info(f"Loaded {len(all_segments)} total transcript segments, filtered to {len(transcript_segments)} for clip range {segment.start_time}-{segment.end_time}")
            
            job_manager.update_progress(job, 5, "setup", "Preparing export...")
            
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
            logger.info(f"[EXPORT] caption_style received: {caption_style}")
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
            
            # Render video
            job_manager.update_progress(job, 10, "render", "Rendering video...")
            
            video_path = exports_dir / f"{base_name}.mp4"
            
            # If intro is enabled, render to temp file first
            if intro_config and intro_config.get("enabled"):
                temp_clip_path = exports_dir / f"{base_name}_clip_temp.mp4"
                actual_video_path = temp_clip_path
            else:
                actual_video_path = video_path
            
            render_result = await self.render.render_clip(
                source_path=project.source_path,
                output_path=str(actual_video_path),
                start_time=segment.start_time,
                duration=segment.duration,
                layout_config=render_layout_config,
                caption_config=caption_config if include_captions else None,
                transcript_segments=transcript_segments if include_captions else None,
                use_nvenc=use_nvenc,
                progress_callback=lambda p: job_manager.update_progress(
                    job, 10 + p * 0.5, "render", f"Rendering: {p:.0f}%"
                )
            )
            
            # If intro is enabled, render intro and concatenate
            if intro_config and intro_config.get("enabled"):
                try:
                    job_manager.update_progress(job, 60, "intro", "Generating intro...")
                    
                    intro_path = exports_dir / f"{base_name}_intro_temp.mp4"
                    
                    # Set title from segment if not provided
                    if not intro_config.get("title"):
                        intro_config["title"] = segment.topic_label or "Untitled"
                    
                    await self.intro.render_intro(
                        source_path=project.source_path,
                        output_path=str(intro_path),
                        start_time=segment.start_time,
                        duration=intro_config.get("duration", 2.0),
                        config=intro_config,
                        progress_callback=lambda p: job_manager.update_progress(
                            job, 60 + p * 0.1, "intro", f"Intro: {p:.0f}%"
                        )
                    )
                    
                    job_manager.update_progress(job, 70, "concat", "Concatenating intro + clip...")
                    
                    await self.intro.concat_intro_with_clip(
                        intro_path=str(intro_path),
                        clip_path=str(temp_clip_path),
                        output_path=str(video_path),
                    )
                    
                    # Cleanup temp files
                    try:
                        intro_path.unlink()
                        temp_clip_path.unlink()
                    except Exception as e:
                        logger.warning(f"Could not delete temp files: {e}")
                        
                except Exception as intro_error:
                    # Intro rendering failed - fallback to clip without intro
                    logger.warning(f"Intro rendering failed, exporting without intro: {intro_error}")
                    job_manager.update_progress(job, 70, "fallback", "Intro échouée, export sans intro...")
                    
                    # Move temp clip to final path
                    import shutil
                    if temp_clip_path.exists():
                        shutil.move(str(temp_clip_path), str(video_path))
                    
                    # Try to cleanup intro temp file if it exists
                    try:
                        if intro_path.exists():
                            intro_path.unlink()
                    except:
                        pass
            
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
            
            await db.commit()
            
            job_manager.update_progress(job, 100, "complete", "Export complete!")
            
            return {
                "project_id": project_id,
                "segment_id": segment_id,
                "variant": variant,
                "export_dir": str(exports_dir),
                "artifacts": [a.to_dict() for a in artifacts],
            }
    
    async def generate_variants(
        self,
        job: Job,
        project_id: str,
        segment_id: str,
        variants: List[Dict[str, Any]],
        render_proxy: bool = True
    ) -> Dict[str, Any]:
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









