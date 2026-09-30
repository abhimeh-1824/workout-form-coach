"""Comprehensive tests for Landmark Smoothing and Joint Angle Calculation (Step 11).

Verifies:
1. Exponential Moving Average (EMA) landmark coordinate smoothing.
2. Initial frame identity behavior.
3. Alpha configuration dynamics.
4. Missing / occluded landmark resilience.
5. Cross-video session state isolation.
6. Generic 3-point angle calculation (90 deg, 180 deg, degenerate, clamped numerical stability).
7. Visibility threshold cutoff (returning None instead of 0).
8. Standard workout joint definitions (elbows, knees, hips, shoulders).
9. End-to-end video pipeline integration with smoothed landmarks and computed joint angles.
"""

import math
from pathlib import Path
import tempfile
from typing import Generator
import uuid

import numpy as np
import pytest

from app.core.config import settings
from app.services.joint_angles import (
    WORKOUT_JOINT_DEFINITIONS,
    calculate_angle,
    calculate_body_angles,
)
from app.services.landmark_smoother import LandmarkSmoother
from app.services.pose_detector import LandmarkPoint, PoseDetector
from app.services.video_processor import ProcessingResult, process_video_file
from tests.test_pose_detector import (
    create_blank_video,
    create_deterministic_person_frame,
    create_person_video,
)


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Temporary directory for test artifacts."""
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


# ============================================================================
# 1. LANDMARK SMOOTHING UNIT TESTS
# ============================================================================

def test_smoothing_first_frame_identity() -> None:
    """On the first frame with no prior state, smoothed landmarks equal raw coordinates."""
    smoother = LandmarkSmoother(alpha=0.5)

    raw_landmarks = [
        LandmarkPoint(name="NOSE", x=0.5, y=0.2, z=-0.1, visibility=0.95),
        LandmarkPoint(name="LEFT_SHOULDER", x=0.6, y=0.3, z=-0.2, visibility=0.90),
    ]

    smoothed = smoother.smooth(raw_landmarks)

    assert len(smoothed) == len(raw_landmarks)
    for raw, sm in zip(raw_landmarks, smoothed):
        assert sm.name == raw.name
        assert sm.x == pytest.approx(raw.x, abs=1e-6)
        assert sm.y == pytest.approx(raw.y, abs=1e-6)
        assert sm.z == pytest.approx(raw.z, abs=1e-6)
        # Visibility must be preserved without modification
        assert sm.visibility == pytest.approx(raw.visibility, abs=1e-6)


def test_smoothing_consecutive_frames_ema() -> None:
    """Verify EMA formula: smoothed = alpha * current + (1 - alpha) * previous.

    Given previous = 0, current = 10, alpha = 0.5 -> expected = 5.0.
    """
    smoother = LandmarkSmoother(alpha=0.5)

    # Frame 1: x = 0.0
    frame_1 = [LandmarkPoint(name="LEFT_ELBOW", x=0.0, y=0.0, z=0.0, visibility=0.9)]
    sm_1 = smoother.smooth(frame_1)
    assert sm_1[0].x == pytest.approx(0.0)

    # Frame 2: x = 10.0
    frame_2 = [LandmarkPoint(name="LEFT_ELBOW", x=10.0, y=0.0, z=0.0, visibility=0.9)]
    sm_2 = smoother.smooth(frame_2)
    # Expected: 0.5 * 10.0 + (1 - 0.5) * 0.0 = 5.0
    assert sm_2[0].x == pytest.approx(5.0)

    # Frame 3: x = 10.0 again
    # Expected: 0.5 * 10.0 + 0.5 * 5.0 = 7.5
    sm_3 = smoother.smooth(frame_2)
    assert sm_3[0].x == pytest.approx(7.5)


def test_smoothing_different_alpha_values() -> None:
    """Verify smoothing behavior adapts appropriately to configured alpha."""
    # Alpha = 0.2 (heavy smoothing, favors previous)
    smoother_low = LandmarkSmoother(alpha=0.2)
    smoother_low.smooth([LandmarkPoint(name="KNEE", x=0.0, y=0.0, z=0.0, visibility=1.0)])
    sm_low = smoother_low.smooth([LandmarkPoint(name="KNEE", x=10.0, y=0.0, z=0.0, visibility=1.0)])
    # 0.2 * 10.0 + 0.8 * 0.0 = 2.0
    assert sm_low[0].x == pytest.approx(2.0)

    # Alpha = 0.8 (light smoothing, favors current)
    smoother_high = LandmarkSmoother(alpha=0.8)
    smoother_high.smooth([LandmarkPoint(name="KNEE", x=0.0, y=0.0, z=0.0, visibility=1.0)])
    sm_high = smoother_high.smooth([LandmarkPoint(name="KNEE", x=10.0, y=0.0, z=0.0, visibility=1.0)])
    # 0.8 * 10.0 + 0.2 * 0.0 = 8.0
    assert sm_high[0].x == pytest.approx(8.0)


def test_smoothing_missing_landmark_handling() -> None:
    """Missing landmarks in a frame do not crash or invent coordinates."""
    smoother = LandmarkSmoother(alpha=0.5)

    # Frame 1: two landmarks
    frame_1 = [
        LandmarkPoint(name="LEFT_HIP", x=0.4, y=0.5, z=0.0, visibility=0.9),
        LandmarkPoint(name="RIGHT_HIP", x=0.6, y=0.5, z=0.0, visibility=0.9),
    ]
    sm_1 = smoother.smooth(frame_1)
    assert len(sm_1) == 2

    # Frame 2: RIGHT_HIP is missing/occluded
    frame_2 = [
        LandmarkPoint(name="LEFT_HIP", x=0.42, y=0.52, z=0.0, visibility=0.9),
    ]
    sm_2 = smoother.smooth(frame_2)
    assert len(sm_2) == 1
    assert sm_2[0].name == "LEFT_HIP"

    # Frame 3: Empty landmarks (e.g. no person detected) safely resets
    sm_3 = smoother.smooth([])
    assert sm_3 == []

    # Frame 4: Person returns -> starts cleanly with initial values without leap
    frame_4 = [
        LandmarkPoint(name="LEFT_HIP", x=0.5, y=0.5, z=0.0, visibility=0.9),
    ]
    sm_4 = smoother.smooth(frame_4)
    assert sm_4[0].x == pytest.approx(0.5)


def test_smoothing_no_cross_video_state_leak() -> None:
    """Different video sessions or reset() must never inherit previous smoothing history."""
    smoother = LandmarkSmoother(alpha=0.5)

    # Session 1 ends with coordinate near 100.0
    smoother.smooth([LandmarkPoint(name="WRIST", x=100.0, y=100.0, z=0.0, visibility=1.0)])

    # Reset smoother for Session 2
    smoother.reset()

    # Session 2 first frame at 10.0
    sm = smoother.smooth([LandmarkPoint(name="WRIST", x=10.0, y=10.0, z=0.0, visibility=1.0)])
    # If state leaked, it would be 0.5 * 10 + 0.5 * 100 = 55.0. Must be 10.0!
    assert sm[0].x == pytest.approx(10.0)
    assert sm[0].y == pytest.approx(10.0)


# ============================================================================
# 2. JOINT ANGLE CALCULATION UNIT TESTS
# ============================================================================

def test_angle_90_degrees() -> None:
    """Verify orthogonal 90 degree angle calculation.

    A=(0, 1), B=(0, 0), C=(1, 0)
         A (0, 1)
         |
         |
         B (0, 0) --- C (1, 0)
    """
    angle = calculate_angle((0.0, 1.0), (0.0, 0.0), (1.0, 0.0))
    assert angle == pytest.approx(90.0, abs=0.1)


def test_angle_180_degrees() -> None:
    """Verify straight line 180 degree angle calculation.

    A=(0, 1), B=(0, 0), C=(0, -1)
    """
    angle = calculate_angle((0.0, 1.0), (0.0, 0.0), (0.0, -1.0))
    assert angle == pytest.approx(180.0, abs=0.1)


def test_angle_degenerate_vectors_return_none() -> None:
    """Degenerate vectors (A == B or C == B) return None without division by zero error."""
    # A == B
    assert calculate_angle((0.5, 0.5), (0.5, 0.5), (1.0, 1.0)) is None
    # C == B
    assert calculate_angle((1.0, 1.0), (0.5, 0.5), (0.5, 0.5)) is None
    # All equal
    assert calculate_angle((0.5, 0.5), (0.5, 0.5), (0.5, 0.5)) is None


def test_angle_floating_point_clamping() -> None:
    """Collinear vectors with slight floating-point imprecision do not raise math domain errors."""
    # Almost identical vectors forming 0 degrees
    pt_b = (0.5, 0.5)
    pt_a = (0.5, 0.8)
    pt_c = (0.5, 0.80000000000001)

    angle = calculate_angle(pt_a, pt_b, pt_c)
    assert angle is not None
    assert angle == pytest.approx(0.0, abs=0.1)

    # Exactly opposite collinear vectors forming 180 degrees
    pt_opp = (0.5, 0.2)
    angle_opp = calculate_angle(pt_a, pt_b, pt_opp)
    assert angle_opp is not None
    assert angle_opp == pytest.approx(180.0, abs=0.1)


def test_angle_missing_or_none_landmarks() -> None:
    """Missing or None landmarks return None."""
    assert calculate_angle(None, (0.0, 0.0), (1.0, 0.0)) is None
    assert calculate_angle((0.0, 1.0), None, (1.0, 0.0)) is None
    assert calculate_angle((0.0, 1.0), (0.0, 0.0), None) is None


def test_angle_low_visibility_returns_none() -> None:
    """Landmarks below the visibility threshold return None, never 0.0."""
    pt_a = LandmarkPoint(name="A", x=0.0, y=1.0, z=0.0, visibility=0.9)
    pt_b = LandmarkPoint(name="B", x=0.0, y=0.0, z=0.0, visibility=0.9)
    # Low visibility on point C (< 0.5)
    pt_c_low = LandmarkPoint(name="C", x=1.0, y=0.0, z=0.0, visibility=0.3)

    angle = calculate_angle(pt_a, pt_b, pt_c_low, min_visibility=0.5)
    assert angle is None

    # Adequate visibility (>= 0.5) produces valid 90.0 angle
    pt_c_good = LandmarkPoint(name="C", x=1.0, y=0.0, z=0.0, visibility=0.6)
    angle_good = calculate_angle(pt_a, pt_b, pt_c_good, min_visibility=0.5)
    assert angle_good == pytest.approx(90.0, abs=0.1)


def test_calculate_body_angles_mappings() -> None:
    """Verify standard workout joints map to the correct anatomical landmark triplets."""
    # Synthetic landmarks arranged with known angles:
    # Left elbow: SHOULDER(0.5, 0.2) -> ELBOW(0.5, 0.4) -> WRIST(0.7, 0.4) = 90 deg
    # Left knee: HIP(0.4, 0.5) -> KNEE(0.4, 0.7) -> ANKLE(0.4, 0.9) = 180 deg
    landmarks = [
        LandmarkPoint(name="LEFT_SHOULDER", x=0.5, y=0.2, z=0.0, visibility=0.9),
        LandmarkPoint(name="LEFT_ELBOW", x=0.5, y=0.4, z=0.0, visibility=0.9),
        LandmarkPoint(name="LEFT_WRIST", x=0.7, y=0.4, z=0.0, visibility=0.9),
        LandmarkPoint(name="RIGHT_SHOULDER", x=0.6, y=0.2, z=0.0, visibility=0.9),
        LandmarkPoint(name="RIGHT_ELBOW", x=0.6, y=0.4, z=0.0, visibility=0.9),
        LandmarkPoint(name="RIGHT_WRIST", x=0.8, y=0.4, z=0.0, visibility=0.9),
        LandmarkPoint(name="LEFT_HIP", x=0.4, y=0.5, z=0.0, visibility=0.9),
        LandmarkPoint(name="LEFT_KNEE", x=0.4, y=0.7, z=0.0, visibility=0.9),
        LandmarkPoint(name="LEFT_ANKLE", x=0.4, y=0.9, z=0.0, visibility=0.9),
        LandmarkPoint(name="RIGHT_HIP", x=0.6, y=0.5, z=0.0, visibility=0.9),
        LandmarkPoint(name="RIGHT_KNEE", x=0.6, y=0.7, z=0.0, visibility=0.9),
        LandmarkPoint(name="RIGHT_ANKLE", x=0.6, y=0.9, z=0.0, visibility=0.9),
    ]

    body_angles = calculate_body_angles(landmarks, min_visibility=0.5)

    assert "left_elbow" in body_angles
    assert "right_elbow" in body_angles
    assert "left_knee" in body_angles
    assert "right_knee" in body_angles
    assert "left_hip" in body_angles
    assert "right_hip" in body_angles
    assert "left_shoulder" in body_angles
    assert "right_shoulder" in body_angles

    assert body_angles["left_elbow"] == pytest.approx(90.0, abs=0.5)
    assert body_angles["left_knee"] == pytest.approx(180.0, abs=0.5)
    assert body_angles["right_elbow"] == pytest.approx(90.0, abs=0.5)
    assert body_angles["right_knee"] == pytest.approx(180.0, abs=0.5)


def test_calculate_body_angles_empty_landmarks() -> None:
    """Empty landmarks list returns a dictionary with all joints mapped to None."""
    angles = calculate_body_angles([])
    for joint_name in WORKOUT_JOINT_DEFINITIONS:
        assert joint_name in angles
        assert angles[joint_name] is None


# ============================================================================
# 3. END-TO-END PIPELINE INTEGRATION TEST
# ============================================================================

def test_pipeline_produces_smoothed_landmarks_and_angles(temp_dir: Path) -> None:
    """Verify video processing foundation produces smoothed landmarks and angles per frame."""
    video_file = create_person_video(temp_dir / "workout_test.mp4", num_frames=10, fps=15.0)

    with PoseDetector(min_detection_confidence=0.1, min_tracking_confidence=0.1) as detector:
        smoother = LandmarkSmoother(alpha=0.5)
        result = process_video_file(
            video_path=video_file,
            job_id=uuid.uuid4(),
            target_fps=15,
            pose_detector=detector,
            landmark_smoother=smoother,
            require_pose=True,
        )

        assert isinstance(result, ProcessingResult)
        assert result.processed_frame_count == 10
        assert result.pose_frames is not None
        assert len(result.pose_frames) == 10

        # Inspect frames where pose detection succeeded
        detected_frames = [f for f in result.pose_frames if f.pose_detected]
        assert len(detected_frames) > 0

        for frame in detected_frames:
            assert frame.landmarks is not None
            assert len(frame.landmarks) == 33

            # Smoothed landmarks must be present and 33 items
            assert frame.smoothed_landmarks is not None
            assert len(frame.smoothed_landmarks) == 33

            # Joint angles must be present
            assert frame.angles is not None
            assert "left_elbow" in frame.angles
            assert "right_elbow" in frame.angles
            assert "left_knee" in frame.angles
            assert "right_knee" in frame.angles
            assert "left_hip" in frame.angles
            assert "right_hip" in frame.angles
            assert "left_shoulder" in frame.angles
            assert "right_shoulder" in frame.angles

            # Check dict serialization
            f_dict = frame.to_dict()
            assert "smoothed_landmarks" in f_dict
            assert "angles" in f_dict
            assert len(f_dict["smoothed_landmarks"]) == 33
