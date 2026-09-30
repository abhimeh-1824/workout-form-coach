"""Tests for MediaPipe Pose 33 Landmark Keypoint Extraction (Step 10).

Verifies:
1. PoseDetector lifecycle and initialization.
2. Valid frame detection produces 33 landmarks.
3. Every landmark exposes name, x, y, z, and visibility according to MediaPipe's official enum.
4. Frames without a person handle safely (pose_detected=False, landmarks=[]) without crashing.
5. Frame index and video-timeline timestamp metadata are generated correctly.
6. Full video processing produces pose statistics and handles no-person video policy.
"""

from pathlib import Path
import tempfile
from typing import Generator
import uuid

import cv2
from mediapipe.tasks.python import vision
import numpy as np
import pytest

from app.services.pose_detector import (
    LandmarkPoint,
    PoseDetectionError,
    PoseDetector,
    PoseFrameResult,
)
from app.services.video_processor import (
    ProcessingResult,
    VideoProcessingError,
    process_video_file,
)


@pytest.fixture
def temp_video_dir() -> Generator[Path, None, None]:
    """Provide a temporary directory for test fixtures."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


def create_deterministic_person_frame(width: int = 512, height: int = 512) -> np.ndarray:
    """Generate a deterministic synthetic image containing a detectable person posture."""
    img = np.ones((height, width, 3), dtype=np.uint8) * 240
    # Head
    cv2.circle(img, (256, 100), 40, (50, 50, 50), -1)
    # Torso
    cv2.line(img, (256, 140), (256, 300), (50, 50, 50), 10)
    # Arms
    cv2.line(img, (256, 180), (180, 240), (50, 50, 50), 8)
    cv2.line(img, (256, 180), (332, 240), (50, 50, 50), 8)
    # Legs
    cv2.line(img, (256, 300), (200, 420), (50, 50, 50), 8)
    cv2.line(img, (256, 300), (312, 420), (50, 50, 50), 8)
    return img


def create_no_person_frame(width: int = 512, height: int = 512) -> np.ndarray:
    """Generate a frame with no person (solid background)."""
    return np.zeros((height, width, 3), dtype=np.uint8)


def create_person_video(
    file_path: Path,
    num_frames: int = 15,
    fps: float = 15.0,
    width: int = 512,
    height: int = 512,
) -> Path:
    """Generate a short video containing the person figure."""
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(file_path), fourcc, fps, (width, height))
    frame = create_deterministic_person_frame(width, height)
    for _ in range(num_frames):
        out.write(frame)
    out.release()
    return file_path


def create_blank_video(
    file_path: Path,
    num_frames: int = 15,
    fps: float = 15.0,
    width: int = 256,
    height: int = 256,
) -> Path:
    """Generate a short video containing no person."""
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(file_path), fourcc, fps, (width, height))
    blank = np.zeros((height, width, 3), dtype=np.uint8)
    for _ in range(num_frames):
        out.write(blank)
    out.release()
    return file_path


def test_detector_initialization() -> None:
    """Verify PoseDetector initializes and closes properly."""
    with PoseDetector(min_detection_confidence=0.1) as detector:
        assert detector._landmarker is not None
        assert detector.running_mode == vision.RunningMode.VIDEO
    # Closed after context exit
    assert detector._landmarker is None


def test_valid_frame_produces_33_landmarks() -> None:
    """Verify inference on a frame with a person detects pose and returns all 33 landmarks."""
    frame = create_deterministic_person_frame()
    with PoseDetector(min_detection_confidence=0.1, min_tracking_confidence=0.1) as detector:
        result = detector.process_frame(frame, frame_index=0, timestamp_seconds=0.0)

        assert result.pose_detected is True
        assert len(result.landmarks) == 33
        assert result.frame_index == 0
        assert result.timestamp_seconds == 0.0


def test_landmark_fields_and_official_naming() -> None:
    """Verify each landmark contains official MediaPipe names, 3D normalized coordinates, and visibility."""
    frame = create_deterministic_person_frame()
    with PoseDetector(min_detection_confidence=0.1, min_tracking_confidence=0.1) as detector:
        result = detector.process_frame(frame, frame_index=5, timestamp_seconds=0.333)

        assert result.pose_detected is True
        landmark_names = [lm.name for lm in result.landmarks]

        # Verify key landmarks are present and follow official MediaPipe enum
        assert "NOSE" in landmark_names
        assert "LEFT_SHOULDER" in landmark_names
        assert "RIGHT_SHOULDER" in landmark_names
        assert "LEFT_HIP" in landmark_names
        assert "RIGHT_HIP" in landmark_names
        assert "LEFT_KNEE" in landmark_names
        assert "RIGHT_KNEE" in landmark_names
        assert "LEFT_ANKLE" in landmark_names
        assert "RIGHT_ANKLE" in landmark_names

        for lm in result.landmarks:
            assert isinstance(lm, LandmarkPoint)
            assert isinstance(lm.name, str)
            assert isinstance(lm.x, float)
            assert isinstance(lm.y, float)
            assert isinstance(lm.z, float)
            assert isinstance(lm.visibility, float)
            assert 0.0 <= lm.visibility <= 1.0

            # Test dictionary serialization
            d = lm.to_dict()
            assert d["name"] == lm.name
            assert "x" in d and "y" in d and "z" in d and "visibility" in d


def test_no_person_frame_does_not_crash() -> None:
    """Verify frame with no person returns pose_detected=False without exceptions."""
    blank_frame = create_no_person_frame()
    with PoseDetector(min_detection_confidence=0.5) as detector:
        result = detector.process_frame(blank_frame, frame_index=1, timestamp_seconds=0.067)

        assert result.pose_detected is False
        assert len(result.landmarks) == 0
        assert result.frame_index == 1
        assert result.timestamp_seconds == 0.067


def test_frame_metadata_timeline() -> None:
    """Verify frame metadata preserves video timeline timestamps (not wall-clock time)."""
    frame = create_deterministic_person_frame()
    with PoseDetector(min_detection_confidence=0.1, min_tracking_confidence=0.1) as detector:
        # Simulate sequential frames at 15 FPS
        timestamps = [0.0, 0.0667, 0.1333, 0.2000]
        results = [
            detector.process_frame(frame, frame_index=i, timestamp_seconds=ts)
            for i, ts in enumerate(timestamps)
        ]

        for i, res in enumerate(results):
            assert res.frame_index == i
            assert res.timestamp_seconds == pytest.approx(timestamps[i], abs=1e-3)


def test_full_short_video_pose_statistics(temp_video_dir) -> None:
    """Verify full video processing runs MediaPipe, produces pose statistics, and returns ProcessingResult."""
    video_path = create_person_video(temp_video_dir / "person_workout.mp4", num_frames=15, fps=15.0)

    with PoseDetector(min_detection_confidence=0.1, min_tracking_confidence=0.1) as custom_detector:
        result = process_video_file(
            video_path=video_path,
            job_id=uuid.uuid4(),
            target_fps=15,
            pose_detector=custom_detector,
            require_pose=True,
        )

        assert isinstance(result, ProcessingResult)
        assert result.frame_count == 15
        assert result.processed_frame_count == 15
        assert result.pose_detected_frames > 0
        assert result.pose_missing_frames >= 0
        assert result.pose_detected_frames + result.pose_missing_frames == result.processed_frame_count
        assert result.pose_detection_rate > 0.5
        assert result.pose_frames is not None
        assert len(result.pose_frames) == 15


def test_no_person_video_fails_safely(temp_video_dir) -> None:
    """Verify video with 0 detected poses fails safely according to no-person policy."""
    blank_video = create_blank_video(temp_video_dir / "empty_room.mp4", num_frames=15, fps=15.0)

    with pytest.raises(VideoProcessingError) as exc_info:
        process_video_file(
            video_path=blank_video,
            job_id=uuid.uuid4(),
            target_fps=15,
            require_pose=True,
        )

    assert "No person detected in the video" in str(exc_info.value)
