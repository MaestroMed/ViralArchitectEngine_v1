"""Continuous Facecam Tracking Service.

Provides frame-by-frame face tracking for auto-reframe in 9:16 vertical videos.

Features:
- Continuous face detection using MediaPipe/OpenCV
- Smooth interpolation between frames
- Auto-reframe with intelligent padding
- Multi-face support with priority detection
- GPU acceleration when available

Usage:
    from forge_engine.services.facecam_tracking import FacecamTracker

    tracker = FacecamTracker()
    detections = await tracker.track_faces(video_path, start_time, end_time)
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class FaceRect:
    """Normalized face rectangle (0-1 coordinates)."""
    x: float  # Left edge (0-1)
    y: float  # Top edge (0-1)
    width: float  # Width (0-1)
    height: float  # Height (0-1)
    confidence: float = 0.0

    @property
    def center_x(self) -> float:
        return self.x + self.width / 2

    @property
    def center_y(self) -> float:
        return self.y + self.height / 2

    @property
    def area(self) -> float:
        return self.width * self.height

    def to_dict(self) -> dict[str, float]:
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "center": {"x": self.center_x, "y": self.center_y},
            "confidence": self.confidence,
        }


@dataclass
class FaceDetection:
    """A face detection at a specific time."""
    time: float
    faces: list[FaceRect] = field(default_factory=list)
    primary_face: FaceRect | None = None

    # Computed crop region for 9:16 frame
    crop_region: dict[str, float] | None = None
    zoom_factor: float = 1.0

    # Smoothed values (after temporal filtering)
    smoothed_rect: dict[str, float] | None = None


class FacecamTracker:
    """Service for continuous face tracking with auto-reframe."""

    def __init__(self):
        self._detector = None
        self._detection_method = "mediapipe"  # or "opencv", "dlib"

        # Tracking settings
        self.sample_interval = 0.5  # Sample every 0.5 seconds by default
        self.smoothing_window = 5  # Number of frames for temporal smoothing
        self.min_face_size = 0.05  # Minimum face size (5% of frame)
        self.padding_factor = 0.3  # Add 30% padding around face

        # 9:16 output settings
        self.output_aspect = 9 / 16
        self.min_zoom = 1.5  # Minimum zoom for facecam
        self.max_zoom = 3.0  # Maximum zoom

        # Face priority (larger faces are usually the main subject)
        self.prioritize_center = True
        self.prioritize_size = True

    def is_available(self) -> bool:
        """Check if face detection is available."""
        try:
            import cv2
            return True
        except ImportError:
            return False

    def _init_detector(self):
        """Initialize face detector."""
        if self._detector is not None:
            return

        try:
            # Try MediaPipe first (best quality)
            import mediapipe as mp
            self._detector = mp.solutions.face_detection.FaceDetection(
                model_selection=1,  # 0 for close, 1 for far
                min_detection_confidence=0.5
            )
            self._detection_method = "mediapipe"
            logger.info("Using MediaPipe face detection")
        except ImportError:
            # Fall back to OpenCV
            try:
                import cv2
                cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
                self._detector = cv2.CascadeClassifier(cascade_path)
                self._detection_method = "opencv"
                logger.info("Using OpenCV Haar cascade face detection")
            except Exception as e:
                logger.error("No face detection available: %s", e)
                raise RuntimeError("Face detection not available")

    async def track_faces(
        self,
        video_path: str,
        start_time: float = 0,
        end_time: float | None = None,
        sample_interval: float | None = None,
        progress_callback: Callable[..., Any] | None = None,
    ) -> list[FaceDetection]:
        """Track faces throughout a video segment.

        Args:
            video_path: Path to video file
            start_time: Start time in seconds
            end_time: End time in seconds (None = entire video)
            sample_interval: Time between samples (None = use default)
            progress_callback: Progress callback function

        Returns:
            List of FaceDetection objects with timestamps
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self._track_faces_sync(
                video_path, start_time, end_time,
                sample_interval, progress_callback
            )
        )

    def _track_faces_sync(
        self,
        video_path: str,
        start_time: float,
        end_time: float | None,
        sample_interval: float | None,
        progress_callback: Callable[..., Any] | None,
    ) -> list[FaceDetection]:
        """Synchronous face tracking."""
        import cv2

        self._init_detector()

        if progress_callback:
            progress_callback(5)

        interval = sample_interval or self.sample_interval

        # Open video
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open video: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if fps > 0 else 0

        if end_time is None:
            end_time = duration

        frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        if progress_callback:
            progress_callback(10)

        logger.info(
            "Tracking faces in %s: %.1fs to %.1fs (%.1ffps, %dx%d)",
            video_path, start_time, end_time, fps, frame_width, frame_height
        )

        detections = []
        current_time = start_time
        total_duration = end_time - start_time

        while current_time < end_time:
            # Seek to time
            frame_number = int(current_time * fps)
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)

            ret, frame = cap.read()
            if not ret:
                current_time += interval
                continue

            # Detect faces
            faces = self._detect_faces(frame, frame_width, frame_height)

            # Determine primary face
            primary = self._select_primary_face(faces)

            # Calculate crop region for 9:16
            crop_region, zoom = self._calculate_crop_region(
                primary, frame_width, frame_height
            )

            detection = FaceDetection(
                time=current_time,
                faces=faces,
                primary_face=primary,
                crop_region=crop_region,
                zoom_factor=zoom,
            )
            detections.append(detection)

            # Progress
            if progress_callback:
                pct = 10 + ((current_time - start_time) / total_duration) * 80
                progress_callback(min(90, pct))

            current_time += interval

        cap.release()

        # Apply temporal smoothing
        detections = self._smooth_detections(detections)

        if progress_callback:
            progress_callback(100)

        logger.info("Face tracking complete: %d detections", len(detections))

        return detections

    def _detect_faces(
        self,
        frame: np.ndarray,
        frame_width: int,
        frame_height: int,
    ) -> list[FaceRect]:
        """Detect faces in a single frame."""
        faces = []

        if self._detection_method == "mediapipe":

            # Convert BGR to RGB
            rgb_frame = frame[:, :, ::-1]

            results = self._detector.process(rgb_frame)

            if results.detections:
                for detection in results.detections:
                    bbox = detection.location_data.relative_bounding_box

                    face = FaceRect(
                        x=max(0, bbox.xmin),
                        y=max(0, bbox.ymin),
                        width=min(1 - bbox.xmin, bbox.width),
                        height=min(1 - bbox.ymin, bbox.height),
                        confidence=detection.score[0] if detection.score else 0,
                    )

                    if face.area >= self.min_face_size:
                        faces.append(face)

        elif self._detection_method == "opencv":
            import cv2

            # Convert to grayscale
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # Detect faces
            detected = self._detector.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(int(frame_width * 0.05), int(frame_height * 0.05)),
            )

            for (x, y, w, h) in detected:
                face = FaceRect(
                    x=x / frame_width,
                    y=y / frame_height,
                    width=w / frame_width,
                    height=h / frame_height,
                    confidence=0.8,  # OpenCV doesn't provide confidence
                )

                if face.area >= self.min_face_size:
                    faces.append(face)

        return faces

    def _select_primary_face(self, faces: list[FaceRect]) -> FaceRect | None:
        """Select the primary face to track."""
        if not faces:
            return None

        if len(faces) == 1:
            return faces[0]

        # Score each face
        scored = []
        for face in faces:
            score = 0

            # Size priority (larger faces are more important)
            if self.prioritize_size:
                score += face.area * 100

            # Center priority (faces near center are more likely the subject)
            if self.prioritize_center:
                center_dist = abs(face.center_x - 0.5) + abs(face.center_y - 0.5)
                score += (1 - center_dist) * 50

            # Confidence boost
            score += face.confidence * 20

            scored.append((score, face))

        # Return highest scored face
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1]

    def _calculate_crop_region(
        self,
        face: FaceRect | None,
        frame_width: int,
        frame_height: int,
    ) -> tuple[dict[str, float] | None, float]:
        """Calculate the crop region for 9:16 output.

        Returns:
            Tuple of (crop_region dict, zoom_factor)
        """
        if face is None:
            # No face detected - use center crop
            source_aspect = frame_width / frame_height
            target_aspect = self.output_aspect

            if source_aspect > target_aspect:
                # Wider source - crop sides
                crop_width = target_aspect / source_aspect
                return {
                    "x": (1 - crop_width) / 2,
                    "y": 0,
                    "width": crop_width,
                    "height": 1,
                }, 1.0
            else:
                # Taller source - crop top/bottom
                crop_height = source_aspect / target_aspect
                return {
                    "x": 0,
                    "y": (1 - crop_height) / 2,
                    "width": 1,
                    "height": crop_height,
                }, 1.0

        # Calculate crop around face with padding
        padding = self.padding_factor

        # Expand face rect with padding
        face.width * (1 + padding * 2)
        face.height * (1 + padding * 2)
        face.x - face.width * padding
        face.y - face.height * padding

        # Calculate zoom to fit face in 9:16 frame
        # We want the face to be a reasonable size in the output
        target_face_height = 0.3  # Face should be ~30% of output height
        zoom = min(
            self.max_zoom,
            max(self.min_zoom, target_face_height / face.height)
        )

        # Calculate crop region (what portion of source to use)
        crop_height = 1 / zoom
        crop_width = crop_height * self.output_aspect

        # Center crop on face
        crop_x = face.center_x - crop_width / 2
        crop_y = face.center_y - crop_height / 2

        # Clamp to valid range
        crop_x = max(0, min(1 - crop_width, crop_x))
        crop_y = max(0, min(1 - crop_height, crop_y))

        return {
            "x": crop_x,
            "y": crop_y,
            "width": crop_width,
            "height": crop_height,
        }, zoom

    def _smooth_detections(
        self,
        detections: list[FaceDetection],
    ) -> list[FaceDetection]:
        """Apply temporal smoothing to detection results."""
        if len(detections) < 2:
            return detections

        window = min(self.smoothing_window, len(detections))

        for i, detection in enumerate(detections):
            if detection.crop_region is None:
                continue

            # Get neighboring detections for averaging
            start_idx = max(0, i - window // 2)
            end_idx = min(len(detections), i + window // 2 + 1)

            neighbors = [
                d for d in detections[start_idx:end_idx]
                if d.crop_region is not None
            ]

            if not neighbors:
                detection.smoothed_rect = detection.crop_region
                continue

            # Average the crop regions
            avg_x = sum(n.crop_region["x"] for n in neighbors) / len(neighbors)
            avg_y = sum(n.crop_region["y"] for n in neighbors) / len(neighbors)
            avg_width = sum(n.crop_region["width"] for n in neighbors) / len(neighbors)
            avg_height = sum(n.crop_region["height"] for n in neighbors) / len(neighbors)

            # Apply exponential smoothing towards current frame
            alpha = 0.6  # Weight for current frame
            current = detection.crop_region

            detection.smoothed_rect = {
                "x": alpha * current["x"] + (1 - alpha) * avg_x,
                "y": alpha * current["y"] + (1 - alpha) * avg_y,
                "width": alpha * current["width"] + (1 - alpha) * avg_width,
                "height": alpha * current["height"] + (1 - alpha) * avg_height,
            }

        return detections

    def generate_keyframes(
        self,
        detections: list[FaceDetection],
        min_movement: float = 0.02,
    ) -> list[dict[str, Any]]:
        """Generate keyframes for FFmpeg crop animation.

        Only generates keyframes when significant movement is detected.

        Args:
            detections: List of face detections
            min_movement: Minimum position change to generate new keyframe

        Returns:
            List of keyframe dictionaries with time and crop values
        """
        if not detections:
            return []

        keyframes = []
        last_keyframe = None

        for detection in detections:
            rect = detection.smoothed_rect or detection.crop_region
            if rect is None:
                continue

            # Check if movement is significant
            if last_keyframe is not None:
                movement = (
                    abs(rect["x"] - last_keyframe["crop"]["x"]) +
                    abs(rect["y"] - last_keyframe["crop"]["y"])
                )

                if movement < min_movement:
                    continue

            keyframe = {
                "time": detection.time,
                "crop": rect,
                "zoom": detection.zoom_factor,
            }
            keyframes.append(keyframe)
            last_keyframe = keyframe

        logger.info("Generated %d keyframes from %d detections",
                   len(keyframes), len(detections))

        return keyframes

    def generate_ffmpeg_filter(
        self,
        keyframes: list[dict[str, Any]],
        input_width: int,
        input_height: int,
        output_width: int = 1080,
        output_height: int = 1920,
        fps: int = 30,
        segment_start: float = 0.0,
    ) -> str:
        """Generate FFmpeg filter string for animated crop.

        If 0 or 1 keyframe: static crop centered on the face (or frame center).
        If 2+ keyframes: piecewise-linear interpolation using FFmpeg crop with
        dynamic x/y expressions evaluated per frame via output frame variable ``on``.

        Each keyframe dict must have:
          - ``crop``: normalised {x, y, width, height} in source frame
          - ``time``: absolute timestamp (seconds) in source video

        ``segment_start`` is used to convert absolute timestamps to
        clip-relative frame numbers (output frame 0 = segment_start).

        Returns:
            FFmpeg filter string (no surrounding ``[]`` labels)
        """
        if not keyframes:
            return self.center_crop_filter(output_width, output_height)

        return self._build_zoompan_filter(
            keyframes,
            output_width, output_height, fps, input_width, input_height,
            segment_start=segment_start,
        )

    def center_crop_filter(self, out_w: int, out_h: int) -> str:
        """Return a static center-crop + scale filter (fallback when no face detected)."""
        return f"crop={out_w}:{out_h}:(iw-{out_w})/2:(ih-{out_h})/2"

    def _build_zoompan_filter(
        self,
        keyframes: list[dict[str, Any]],
        out_w: int,
        out_h: int,
        fps: int,
        src_w: int,
        src_h: int,
        segment_start: float = 0.0,
    ) -> str:
        """Build a crop filter expression that smoothly follows the face position.

        keyframes: list of dicts with keys:
          - ``crop``: normalised {x, y, width, height}
          - ``time``: absolute source timestamp (seconds)
        """
        if not keyframes:
            return self.center_crop_filter(out_w, out_h)

        def _crop_rect(kf: dict[str, Any]) -> dict[str, float]:
            """Extract normalised crop rect from a full keyframe dict."""
            return kf.get("crop", kf)  # tolerate flat dicts (legacy)

        if len(keyframes) == 1:
            kf = _crop_rect(keyframes[0])
            x_px = int(kf["x"] * src_w)
            y_px = int(kf["y"] * src_h)
            w_px = max(2, int(kf["width"] * src_w) & ~1)
            h_px = max(2, int(kf["height"] * src_h) & ~1)
            return f"crop={w_px}:{h_px}:{x_px}:{y_px},scale={out_w}:{out_h}"

        # Convert normalised coords → pixel coords with TIME-based frame numbers.
        # `on` in FFmpeg crop expressions is the OUTPUT frame counter (0-based),
        # so frame_num = (absolute_time - segment_start) * fps.
        kf_pixels = []
        for kf in keyframes:
            crop = _crop_rect(kf)
            t = kf.get("time", segment_start)
            frame_num = max(0, int((t - segment_start) * fps))
            kf_pixels.append({
                "frame": frame_num,
                "x": int(crop["x"] * src_w),
                "y": int(crop["y"] * src_h),
                "w": max(2, int(crop["width"] * src_w) & ~1),
                "h": max(2, int(crop["height"] * src_h) & ~1),
            })

        def build_lerp_expr(coord: str) -> str:
            """Build FFmpeg if-then-else expression for piecewise linear interpolation."""
            expr = str(kf_pixels[-1][coord])  # default: last keyframe value
            for i in range(len(kf_pixels) - 2, -1, -1):
                a = kf_pixels[i]
                b = kf_pixels[i + 1]
                if b["frame"] == a["frame"]:
                    continue
                t = f"(on-{a['frame']})/({b['frame']}-{a['frame']})"
                lerp = (
                    f"({a[coord]}+({b[coord]}-{a[coord]})"
                    f"*clip({t}\\,0\\,1))"
                )
                expr = (
                    f"if(between(on\\,{a['frame']}\\,{b['frame']})"
                    f"\\,{lerp}\\,{expr})"
                )
            return expr

        x_expr = build_lerp_expr("x")
        y_expr = build_lerp_expr("y")
        # Use the first keyframe dimensions as a stable crop size
        w_expr = str(kf_pixels[0]["w"])
        h_expr = str(kf_pixels[0]["h"])

        return (
            f"crop={w_expr}:{h_expr}:'{x_expr}':'{y_expr}',"
            f"scale={out_w}:{out_h}"
        )

    def to_serializable(
        self,
        detections: list[FaceDetection],
    ) -> list[dict[str, Any]]:
        """Convert detections to JSON-serializable format."""
        return [
            {
                "time": d.time,
                "faces": [f.to_dict() for f in d.faces],
                "primary_face": d.primary_face.to_dict() if d.primary_face else None,
                "crop_region": d.crop_region,
                "zoom_factor": d.zoom_factor,
                "smoothed_rect": d.smoothed_rect,
            }
            for d in detections
        ]
