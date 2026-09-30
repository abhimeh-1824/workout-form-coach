"""MediaPipe Pose detection service for 33 landmark keypoint extraction.

Provides a decoupled, reusable PoseDetector lifecycle manager configured for
sequential video tracking, extracting all 33 body landmarks with normalized
coordinates, depth, and visibility confidence.
"""

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any, List, Optional

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import numpy as np

from app.core.config import settings

logger = logging.getLogger("workout_form_coach.pose_detector")


class PoseDetectionError(Exception):
    """Exception raised when pose detector initialization or inference fails."""
    pass


@dataclass(frozen=True)
class LandmarkPoint:
    """Single normalized 3D pose landmark with confidence visibility."""

    name: str
    x: float
    y: float
    z: float
    visibility: float

    def to_dict(self) -> dict[str, Any]:
        """Serialize landmark point to dictionary for JSON persistence."""
        return {
            "name": self.name,
            "x": round(self.x, 6),
            "y": round(self.y, 6),
            "z": round(self.z, 6),
            "visibility": round(self.visibility, 4),
        }


@dataclass(frozen=True)
class PoseFrameResult:
    """Pose estimation output for a single processed video frame."""

    frame_index: int
    timestamp_seconds: float
    pose_detected: bool
    landmarks: List[LandmarkPoint]
    smoothed_landmarks: Optional[List[LandmarkPoint]] = None
    angles: Optional[dict[str, Optional[float]]] = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize frame result to dictionary."""
        return {
            "frame_index": self.frame_index,
            "timestamp_seconds": round(self.timestamp_seconds, 4),
            "pose_detected": self.pose_detected,
            "landmarks": [lm.to_dict() for lm in self.landmarks],
            "smoothed_landmarks": (
                [lm.to_dict() for lm in self.smoothed_landmarks]
                if self.smoothed_landmarks is not None
                else None
            ),
            "angles": self.angles,
        }


class PoseDetector:
    """MediaPipe Pose detector lifecycle manager.

    Maintains a single detector instance across sequential video frames in VIDEO
    running mode, utilizing temporal keypoint tracking for high performance.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        min_detection_confidence: Optional[float] = None,
        min_tracking_confidence: Optional[float] = None,
        running_mode: Optional[vision.RunningMode] = None,
    ) -> None:
        self.model_path = Path(model_path or settings.POSE_MODEL_PATH)
        self.min_detection_confidence = (
            min_detection_confidence
            if min_detection_confidence is not None
            else settings.POSE_MIN_DETECTION_CONFIDENCE
        )
        self.min_tracking_confidence = (
            min_tracking_confidence
            if min_tracking_confidence is not None
            else settings.POSE_MIN_TRACKING_CONFIDENCE
        )
        self.running_mode = running_mode or vision.RunningMode.VIDEO

        self._landmarker: Optional[vision.PoseLandmarker] = None
        self._last_timestamp_ms: int = -1

        self._initialize_detector()

    def _initialize_detector(self) -> None:
        """Initialize the underlying MediaPipe PoseLandmarker task."""
        if not self.model_path.is_absolute():
            # Resolve relative to backend root
            resolved_path = (Path.cwd() / self.model_path).resolve()
            if not resolved_path.exists():
                # Also check relative to this file's parent directories
                alt_path = (Path(__file__).resolve().parent.parent / "models" / "assets" / self.model_path.name).resolve()
                if alt_path.exists():
                    resolved_path = alt_path
            self.model_path = resolved_path

        if not self.model_path.exists():
            raise PoseDetectionError(
                f"MediaPipe pose model asset not found at '{self.model_path}'. "
                "Ensure pose_landmarker_lite.task is present in app/models/assets/."
            )

        try:
            base_options = python.BaseOptions(model_asset_path=str(self.model_path))
            options = vision.PoseLandmarkerOptions(
                base_options=base_options,
                running_mode=self.running_mode,
                num_poses=1,  # Single-person workout form analysis
                min_pose_detection_confidence=self.min_detection_confidence,
                min_tracking_confidence=self.min_tracking_confidence,
                output_segmentation_masks=False,  # Keep processing lightweight
            )
            self._landmarker = vision.PoseLandmarker.create_from_options(options)
            logger.info(
                "PoseDetector initialized successfully (mode=%s, det_conf=%.2f, track_conf=%.2f, model=%s)",
                self.running_mode.name,
                self.min_detection_confidence,
                self.min_tracking_confidence,
                self.model_path.name,
            )
        except Exception as exc:
            logger.exception("Failed to initialize MediaPipe PoseLandmarker: %s", exc)
            raise PoseDetectionError(f"Failed to initialize MediaPipe Pose detector: {exc}") from exc

    def process_frame(
        self,
        frame: np.ndarray,
        frame_index: int,
        timestamp_seconds: float,
    ) -> PoseFrameResult:
        """Perform pose estimation on a single OpenCV video frame.

        Converts frame from BGR to RGB, constructs a MediaPipe Image, and extracts
        all 33 normalized landmarks.

        Args:
            frame: Raw BGR image matrix from OpenCV.
            frame_index: Zero-indexed position of the frame in the video stream.
            timestamp_seconds: Video timestamp in seconds (derived from FPS).

        Returns:
            PoseFrameResult containing detection status and 33 LandmarkPoint objects.
        """
        if self._landmarker is None:
            raise PoseDetectionError("Cannot process frame: PoseDetector has been closed.")

        if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
            logger.warning("Empty or invalid frame passed to pose detector at index %d", frame_index)
            return PoseFrameResult(
                frame_index=frame_index,
                timestamp_seconds=timestamp_seconds,
                pose_detected=False,
                landmarks=[],
            )

        try:
            # 1. Color conversion: OpenCV BGR -> MediaPipe RGB
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

            # 2. Monotonic millisecond timestamp for sequential tracking mode
            timestamp_ms = int(timestamp_seconds * 1000)
            if timestamp_ms <= self._last_timestamp_ms:
                timestamp_ms = self._last_timestamp_ms + 1
            self._last_timestamp_ms = timestamp_ms

            # 3. Execute inference
            if self.running_mode == vision.RunningMode.VIDEO:
                detection_result = self._landmarker.detect_for_video(mp_image, timestamp_ms)
            else:
                detection_result = self._landmarker.detect(mp_image)

            # 4. Extract landmarks if a person was detected
            if detection_result.pose_landmarks and len(detection_result.pose_landmarks) > 0:
                raw_landmarks = detection_result.pose_landmarks[0]
                landmarks: List[LandmarkPoint] = []

                for idx, lm in enumerate(raw_landmarks):
                    try:
                        landmark_name = vision.PoseLandmark(idx).name
                    except ValueError:
                        landmark_name = f"LANDMARK_{idx}"

                    landmarks.append(
                        LandmarkPoint(
                            name=landmark_name,
                            x=float(lm.x),
                            y=float(lm.y),
                            z=float(lm.z),
                            visibility=float(lm.visibility) if lm.visibility is not None else 1.0,
                        )
                    )

                return PoseFrameResult(
                    frame_index=frame_index,
                    timestamp_seconds=timestamp_seconds,
                    pose_detected=True,
                    landmarks=landmarks,
                )

            # No person detected in this frame
            return PoseFrameResult(
                frame_index=frame_index,
                timestamp_seconds=timestamp_seconds,
                pose_detected=False,
                landmarks=[],
            )

        except Exception as exc:
            logger.warning(
                "Error processing pose on frame %d (ts=%.2fs): %s",
                frame_index,
                timestamp_seconds,
                exc,
            )
            return PoseFrameResult(
                frame_index=frame_index,
                timestamp_seconds=timestamp_seconds,
                pose_detected=False,
                landmarks=[],
            )

    def close(self) -> None:
        """Release underlying MediaPipe C++ runtime resources."""
        if self._landmarker is not None:
            try:
                self._landmarker.close()
                logger.info("PoseDetector resources released.")
            except Exception as exc:
                logger.warning("Error releasing PoseDetector resources: %s", exc)
            finally:
                self._landmarker = None

    def __enter__(self) -> "PoseDetector":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
