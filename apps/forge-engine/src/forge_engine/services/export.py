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

logger = logging.getLogger(__name__)


class ExportService:
    """Service for exporting clips and generating export packs."""
    
    def __init__(self):
        self.render = RenderService()
        self.captions = CaptionEngine()
    
    async def run_export(
        self,
        job: Job,
        project_id: str,
        segment_id: str,
        variant: str = "A",
        template_id: Optional[str] = None,
        platform: str = "tiktok",
        include_captions: bool = True,
        include_cover: bool = True,
        include_metadata: bool = True,
        include_post: bool = True,
        use_nvenc: bool = True
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
                transcript_segments = [
                    seg for seg in transcript_data.get("segments", [])
                    if segment.start_time <= seg.get("start", 0) <= segment.end_time
                ]
            
            job_manager.update_progress(job, 5, "setup", "Preparing export...")
            
            # Build layout config
            layout_config = {
                "facecam_rect": segment.facecam_rect,
                "content_rect": segment.content_rect,
                "facecam_ratio": 0.4,
                "background_blur": True,
            }
            
            if template and template.layout:
                layout_config.update(template.layout)
            
            # Build caption config
            caption_config = {
                "style": "forge_minimal",
                "word_level": True,
                "max_words_per_line": 6,
                "max_lines": 2,
            }
            
            if template and template.caption_style:
                caption_config.update(template.caption_style)
            
            # Render video
            job_manager.update_progress(job, 10, "render", "Rendering video...")
            
            video_path = exports_dir / f"{base_name}.mp4"
            
            render_result = await self.render.render_clip(
                source_path=project.source_path,
                output_path=str(video_path),
                start_time=segment.start_time,
                duration=segment.duration,
                layout_config=layout_config,
                caption_config=caption_config if include_captions else None,
                transcript_segments=transcript_segments if include_captions else None,
                use_nvenc=use_nvenc,
                progress_callback=lambda p: job_manager.update_progress(
                    job, 10 + p * 0.6, "render", f"Rendering: {p:.0f}%"
                )
            )
            
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
            
            # Generate standalone captions
            if include_captions and transcript_segments:
                job_manager.update_progress(job, 80, "captions", "Generating captions...")
                
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









