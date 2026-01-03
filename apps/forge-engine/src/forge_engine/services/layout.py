"""Layout detection and composition engine."""

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

# Optional numpy import
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

logger = logging.getLogger(__name__)


class LayoutEngine:
    """Service for detecting facecam regions and composing vertical layouts."""
    
    # Common facecam positions (normalized)
    FACECAM_POSITIONS = [
        {"name": "top_right", "x": 0.7, "y": 0.0, "w": 0.3, "h": 0.25},
        {"name": "top_left", "x": 0.0, "y": 0.0, "w": 0.3, "h": 0.25},
        {"name": "bottom_right", "x": 0.7, "y": 0.75, "w": 0.3, "h": 0.25},
        {"name": "bottom_left", "x": 0.0, "y": 0.75, "w": 0.3, "h": 0.25},
        {"name": "full_screen", "x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0},
    ]
    
    def __init__(self):
        self.face_cascade = None
        self.sample_interval = 1.0  # Sample every second for tracking
    
    async def detect_layout(
        self,
        video_path: str,
        duration: float,
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> Dict[str, Any]:
        """Detect layout type and facecam region."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self._detect_sync(video_path, duration, progress_callback)
        )
    
    def _detect_sync(
        self,
        video_path: str,
        duration: float,
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> Dict[str, Any]:
        """Synchronous layout detection."""
        try:
            import cv2
        except ImportError:
            logger.warning("OpenCV not available, returning default layout")
            return self._default_layout()
        
        # Load face cascade
        if self.face_cascade is None:
            cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            self.face_cascade = cv2.CascadeClassifier(cascade_path)
        
        # Open video
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.error("Failed to open video: %s", video_path)
            return self._default_layout()
        
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        if progress_callback:
            progress_callback(10)
        
        # Sample frames and detect faces
        face_detections = []
        sample_count = int(duration / self.sample_interval)
        # sample_count = min(sample_count, 50)  # Removed limit for full tracking
        
        for i in range(sample_count):
            target_time = i * self.sample_interval
            target_frame = int(target_time * fps)
            
            cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
            ret, frame = cap.read()
            
            if not ret:
                continue
            
            # Detect faces
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self.face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(50, 50)
            )
            
            for (x, y, w, h) in faces:
                face_detections.append({
                    "time": target_time,
                    "rect": {
                        "x": int(x),
                        "y": int(y),
                        "width": int(w),
                        "height": int(h)
                    },
                    "normalized": {
                        "x": x / width,
                        "y": y / height,
                        "width": w / width,
                        "height": h / height
                    }
                })
            
            if progress_callback:
                progress_callback(10 + (i + 1) / sample_count * 70)
        
        cap.release()
        
        if progress_callback:
            progress_callback(85)
        
        # Analyze face detections
        if not face_detections:
            # No faces detected - likely montage or no facecam
            return {
                "layout_type": "montage",
                "facecam_rect": None,
                "content_rect": {"x": 0, "y": 0, "width": width, "height": height},
                "confidence": 0.5,
                "face_detections": []
            }
        
        # Find stable facecam region
        facecam_region = self._find_stable_region(face_detections, width, height)
        
        if progress_callback:
            progress_callback(95)
        
        # Determine layout type
        layout_type = self._classify_layout(facecam_region, width, height)
        
        # Calculate content region (everything except facecam)
        content_rect = self._calculate_content_region(facecam_region, width, height)
        
        if progress_callback:
            progress_callback(100)
        
        # Apply smooth tracking to face detections
        smoothed_detections = self._smooth_face_tracking(face_detections, width, height)
        
        return {
            "layout_type": layout_type,
            "facecam_rect": facecam_region,
            "content_rect": content_rect,
            "confidence": 0.8 if facecam_region else 0.5,
            "face_detections": smoothed_detections,  # Smoothed for tracking
            "video_size": {"width": width, "height": height}
        }
    
    def _find_stable_region(
        self,
        detections: List[Dict],
        width: int,
        height: int
    ) -> Optional[Dict[str, int]]:
        """Find the most stable face region across detections."""
        if not detections:
            return None
        
        # Cluster detections by position
        position_clusters = {}
        
        for det in detections:
            norm = det["normalized"]
            # Round to create clusters
            cluster_key = (round(norm["x"], 1), round(norm["y"], 1))
            
            if cluster_key not in position_clusters:
                position_clusters[cluster_key] = []
            position_clusters[cluster_key].append(det["rect"])
        
        # Find largest cluster
        if not position_clusters:
            return None
        
        best_cluster = max(position_clusters.values(), key=len)
        
        if len(best_cluster) < 3:  # Not stable enough
            return None
        
        # Average the rectangles in the best cluster
        def mean(values):
            return sum(values) / len(values) if values else 0
        
        avg_x = int(mean([r["x"] for r in best_cluster]))
        avg_y = int(mean([r["y"] for r in best_cluster]))
        avg_w = int(mean([r["width"] for r in best_cluster]))
        avg_h = int(mean([r["height"] for r in best_cluster]))
        
        # Expand region slightly to ensure we capture full facecam
        padding = int(avg_w * 0.3)
        
        return {
            "x": max(0, avg_x - padding),
            "y": max(0, avg_y - padding),
            "width": min(width - avg_x + padding, avg_w + 2 * padding),
            "height": min(height - avg_y + padding, avg_h + 2 * padding)
        }
    
    def _classify_layout(
        self,
        facecam_rect: Optional[Dict],
        width: int,
        height: int
    ) -> str:
        """Classify the layout type based on facecam position."""
        if not facecam_rect:
            return "montage"
        
        # Calculate facecam size relative to video
        facecam_area = facecam_rect["width"] * facecam_rect["height"]
        video_area = width * height
        facecam_ratio = facecam_area / video_area
        
        if facecam_ratio > 0.5:
            return "talk_fullscreen"
        elif facecam_ratio > 0.1:
            return "stream_facecam"
        else:
            return "podcast_irl"
    
    def _calculate_content_region(
        self,
        facecam_rect: Optional[Dict],
        width: int,
        height: int
    ) -> Dict[str, int]:
        """Calculate the content region excluding facecam."""
        if not facecam_rect:
            return {"x": 0, "y": 0, "width": width, "height": height}
        
        fc = facecam_rect
        
        # Determine which part of the screen is content
        # If facecam is in a corner, content is the rest
        fc_center_x = fc["x"] + fc["width"] / 2
        fc_center_y = fc["y"] + fc["height"] / 2
        
        # Check if facecam is in top half
        if fc_center_y < height / 2:
            # Facecam is top, content is bottom
            content_y = fc["y"] + fc["height"]
            return {
                "x": 0,
                "y": content_y,
                "width": width,
                "height": height - content_y
            }
        else:
            # Facecam is bottom, content is top
            return {
                "x": 0,
                "y": 0,
                "width": width,
                "height": fc["y"]
            }
    
    def _smooth_face_tracking(
        self,
        detections: List[Dict],
        width: int,
        height: int,
        smoothing_window: int = 5
    ) -> List[Dict]:
        """Apply moving average smoothing to face detections for stable tracking."""
        if not detections or not HAS_NUMPY:
            return detections
        
        # Sort by time
        sorted_dets = sorted(detections, key=lambda d: d["time"])
        
        # Extract positions for smoothing
        times = [d["time"] for d in sorted_dets]
        xs = [d["normalized"]["x"] for d in sorted_dets]
        ys = [d["normalized"]["y"] for d in sorted_dets]
        ws = [d["normalized"]["width"] for d in sorted_dets]
        hs = [d["normalized"]["height"] for d in sorted_dets]
        
        # Apply moving average with numpy
        def moving_average(data: List[float], window: int) -> List[float]:
            arr = np.array(data)
            if len(arr) < window:
                return data
            kernel = np.ones(window) / window
            smoothed = np.convolve(arr, kernel, mode='same')
            # Fix edges
            half = window // 2
            for i in range(half):
                smoothed[i] = np.mean(arr[:i+half+1])
                smoothed[-(i+1)] = np.mean(arr[-(i+half+1):])
            return smoothed.tolist()
        
        smooth_xs = moving_average(xs, smoothing_window)
        smooth_ys = moving_average(ys, smoothing_window)
        smooth_ws = moving_average(ws, smoothing_window)
        smooth_hs = moving_average(hs, smoothing_window)
        
        # Create smoothed detections with zoom calculation
        smoothed = []
        for i, det in enumerate(sorted_dets):
            # Calculate center of face
            face_center_x = smooth_xs[i] + smooth_ws[i] / 2
            face_center_y = smooth_ys[i] + smooth_hs[i] / 2
            
            # Calculate optimal zoom to fill ~60% of facecam zone with face
            # Assuming facecam zone is ~35% of output height
            target_face_ratio = 0.6
            current_face_ratio = smooth_hs[i] / 0.35  # face height vs facecam zone
            zoom_factor = max(1.0, min(2.5, target_face_ratio / current_face_ratio)) if current_face_ratio > 0 else 1.5
            
            # Calculate crop region with zoom (centered on face)
            zoomed_width = 1.0 / zoom_factor
            zoomed_height = 1.0 / zoom_factor
            crop_x = max(0, min(1 - zoomed_width, face_center_x - zoomed_width / 2))
            crop_y = max(0, min(1 - zoomed_height, face_center_y - zoomed_height / 2))
            
            smoothed.append({
                **det,
                "smoothed_rect": {
                    "x": smooth_xs[i],
                    "y": smooth_ys[i],
                    "width": smooth_ws[i],
                    "height": smooth_hs[i]
                },
                "center": {
                    "x": face_center_x,
                    "y": face_center_y
                },
                "zoom_factor": round(zoom_factor, 2),
                "crop_region": {
                    "x": crop_x,
                    "y": crop_y,
                    "width": zoomed_width,
                    "height": zoomed_height
                }
            })
        
        return smoothed
    
    def _default_layout(self) -> Dict[str, Any]:
        """Return default layout when detection fails."""
        return {
            "layout_type": "montage",
            "facecam_rect": None,
            "content_rect": None,
            "confidence": 0.0,
            "error": "Layout detection failed"
        }
    
    def generate_layout_candidates(
        self,
        facecam_rect: Optional[Dict],
        content_rect: Optional[Dict],
        output_width: int = 1080,
        output_height: int = 1920
    ) -> List[Dict[str, Any]]:
        """Generate multiple layout candidates for A/B testing."""
        candidates = []
        
        if facecam_rect and content_rect:
            # Standard layout: facecam top, content bottom
            candidates.append({
                "name": "standard",
                "facecam_position": "top",
                "facecam_ratio": 0.4,
                "content_fit": "cover"
            })
            
            # Compact layout: smaller facecam
            candidates.append({
                "name": "compact",
                "facecam_position": "top",
                "facecam_ratio": 0.3,
                "content_fit": "cover"
            })
            
            # Large facecam layout
            candidates.append({
                "name": "speaker_focus",
                "facecam_position": "top",
                "facecam_ratio": 0.5,
                "content_fit": "contain"
            })
        else:
            # No facecam - full content layouts
            candidates.append({
                "name": "full_cover",
                "facecam_position": "none",
                "content_fit": "cover",
                "background_blur": True
            })
            
            candidates.append({
                "name": "full_contain",
                "facecam_position": "none",
                "content_fit": "contain",
                "background_blur": True
            })
        
        return candidates

