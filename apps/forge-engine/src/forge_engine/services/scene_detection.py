"""Scene detection service."""

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class SceneDetector:
    """Service for detecting scene changes in video."""
    
    def __init__(self):
        self.threshold = 30.0  # ContentDetector threshold (higher = fewer scenes)
        self.min_scene_len = 30  # Minimum frames between scenes
    
    async def detect_scenes(
        self,
        video_path: str,
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> Dict[str, Any]:
        """Detect scene changes in video."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self._detect_sync(video_path, progress_callback)
        )
    
    def _detect_sync(
        self,
        video_path: str,
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> Dict[str, Any]:
        """Synchronous scene detection with progress tracking."""
        try:
            from scenedetect import open_video, SceneManager, ContentDetector
        except ImportError:
            logger.warning("scenedetect not available, returning empty scene list")
            return {"scenes": [], "error": "scenedetect not installed"}
        
        if progress_callback:
            progress_callback(5)
        
        try:
            # Open video for frame count
            video = open_video(video_path)
            total_frames = video.duration.get_frames()
            fps = video.frame_rate
            logger.info("Scene detection: %d frames at %.1f fps", total_frames, fps)
            
            if progress_callback:
                progress_callback(10)
            
            # Create scene manager
            scene_manager = SceneManager()
            scene_manager.add_detector(
                ContentDetector(threshold=self.threshold, min_scene_len=self.min_scene_len)
            )
            
            # Process with progress - sample every Nth frame for speed
            # For long videos, we skip frames to speed up detection
            skip_frames = 2 if total_frames > 50000 else 1  # Skip frames for videos > ~30min
            
            processed = 0
            last_progress = 10
            
            while True:
                # Process a batch of frames
                frames_read = scene_manager.detect_scenes(video, frame_skip=skip_frames)
                if frames_read == 0:
                    break
                    
                processed += frames_read
                
                # Update progress (10% to 85%)
                if total_frames > 0:
                    pct = 10 + (processed / total_frames) * 75
                    if progress_callback and int(pct) > last_progress:
                        progress_callback(pct)
                        last_progress = int(pct)
                        if int(pct) % 10 == 0:
                            logger.info("Scene detection: %.0f%% (%d/%d frames)", pct, processed, total_frames)
            
            if progress_callback:
                progress_callback(85)
            
            # Get scene list
            scene_list = scene_manager.get_scene_list()
            
            # Convert to our format
            scenes = []
            for i, (start, end) in enumerate(scene_list):
                scenes.append({
                    "id": i,
                    "time": start.get_seconds(),
                    "end_time": end.get_seconds(),
                    "duration": (end - start).get_seconds(),
                    "confidence": 0.8,
                    "type": "cut"
                })
            
            if progress_callback:
                progress_callback(100)
            
            logger.info("Scene detection complete: %d scenes found", len(scenes))
            
            return {
                "scenes": scenes,
                "total_scenes": len(scenes),
            }
            
        except Exception as e:
            logger.exception("Scene detection failed: %s", e)
            return {"scenes": [], "error": str(e)}


