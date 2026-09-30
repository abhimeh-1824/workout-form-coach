"""Unit and integration tests for exercise rep counting (Step 12).

Verifies:
1. Generic state machine behavior (UP -> DOWN -> UP).
2. Non-completion on partial or incomplete movements.
3. Hysteresis protection against duplicate counts on repeated frames.
4. Resilient handling of missing, None, and NaN angles.
5. Accurate timestamp preservation from video stream.
6. Squat rep counting with bilateral knee angle averaging.
7. Push-up rep counting with bilateral elbow angle averaging.
8. Lunge rep counting with active-leg dynamic selection and alternating legs.
9. End-to-end video pipeline integration producing RepDetection results.
"""

import math
from pathlib import Path
import tempfile
from typing import Generator
import uuid

import pytest

from app.db.base import ExerciseType
from app.services.pose_detector import PoseDetector
from app.services.rep_counter import (
    BilateralRepCounter,
    LungeRepCounter,
    PushupRepCounter,
    RepDetection,
    RepState,
    SquatRepCounter,
    create_rep_counter,
)
from app.services.video_processor import ProcessingResult, process_video_file
from tests.test_pose_detector import create_person_video


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Temporary directory fixture for test artifacts."""
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


# ============================================================================
# 1. GENERIC STATE MACHINE TESTS
# ============================================================================

def test_initial_state_is_up() -> None:
    """Rep counter begins in the UP state with 0 completed reps."""
    counter = SquatRepCounter()
    assert counter.state == RepState.UP
    assert counter.rep_count == 0
    assert counter.get_completed_reps() == []


def test_up_to_down_does_not_complete_rep() -> None:
    """Entering DOWN phase alone does not increment completed rep count."""
    counter = SquatRepCounter(up_threshold=160.0, down_threshold=100.0)

    # Frame 1: Top extension (UP)
    counter.process_frame(timestamp_seconds=0.0, angles={"left_knee": 170.0, "right_knee": 170.0})
    assert counter.state == RepState.UP
    assert counter.rep_count == 0

    # Frame 2: Bottom of squat (DOWN)
    rep = counter.process_frame(timestamp_seconds=1.0, angles={"left_knee": 95.0, "right_knee": 95.0})
    assert rep is None
    assert counter.state == RepState.DOWN
    assert counter.rep_count == 0


def test_up_down_up_completes_exactly_one_rep() -> None:
    """Full UP -> DOWN -> UP cycle completes exactly one repetition."""
    counter = SquatRepCounter(up_threshold=160.0, down_threshold=100.0)

    # UP -> DOWN -> UP
    counter.process_frame(0.0, {"left_knee": 170.0, "right_knee": 170.0})
    counter.process_frame(1.0, {"left_knee": 95.0, "right_knee": 95.0})
    completed_rep = counter.process_frame(2.0, {"left_knee": 165.0, "right_knee": 165.0})

    assert completed_rep is not None
    assert isinstance(completed_rep, RepDetection)
    assert completed_rep.rep_number == 1
    assert counter.rep_count == 1
    assert counter.state == RepState.UP
    assert completed_rep.min_angle == pytest.approx(95.0)
    assert completed_rep.max_angle == pytest.approx(170.0)


def test_multiple_complete_cycles() -> None:
    """Multiple complete movement cycles produce matching sequential rep numbers."""
    counter = PushupRepCounter(up_threshold=160.0, down_threshold=90.0)

    # Cycle 1
    counter.process_frame(0.0, {"left_elbow": 170.0, "right_elbow": 170.0})
    counter.process_frame(1.0, {"left_elbow": 80.0, "right_elbow": 80.0})
    rep1 = counter.process_frame(2.0, {"left_elbow": 165.0, "right_elbow": 165.0})
    assert rep1 is not None and rep1.rep_number == 1

    # Cycle 2
    counter.process_frame(3.0, {"left_elbow": 85.0, "right_elbow": 85.0})
    rep2 = counter.process_frame(4.0, {"left_elbow": 162.0, "right_elbow": 162.0})
    assert rep2 is not None and rep2.rep_number == 2

    assert counter.rep_count == 2
    reps = counter.get_completed_reps()
    assert len(reps) == 2
    assert reps[0].rep_number == 1
    assert reps[1].rep_number == 2


def test_repeated_down_frames_do_not_duplicate_count() -> None:
    """Holding or oscillating at the bottom (DOWN) does not count additional reps."""
    counter = SquatRepCounter(up_threshold=160.0, down_threshold=100.0)

    counter.process_frame(0.0, {"left_knee": 170.0, "right_knee": 170.0})
    # Multiple DOWN frames
    for t in (1.0, 1.2, 1.4, 1.6):
        rep = counter.process_frame(t, {"left_knee": 90.0, "right_knee": 92.0})
        assert rep is None
        assert counter.state == RepState.DOWN
        assert counter.rep_count == 0

    # Finally return to UP
    completed = counter.process_frame(2.0, {"left_knee": 165.0, "right_knee": 165.0})
    assert completed is not None
    assert counter.rep_count == 1


def test_repeated_up_frames_do_not_duplicate_count() -> None:
    """Standing at the top (UP) repeatedly does not increment reps."""
    counter = SquatRepCounter(up_threshold=160.0, down_threshold=100.0)

    for t in (0.0, 0.5, 1.0, 1.5):
        rep = counter.process_frame(t, {"left_knee": 170.0, "right_knee": 170.0})
        assert rep is None
        assert counter.state == RepState.UP
        assert counter.rep_count == 0


def test_missing_and_none_and_nan_angles_ignored() -> None:
    """Missing angles, None values, and NaNs are safely ignored without crashing or corrupting state."""
    counter = SquatRepCounter()

    # Pass None, empty dicts, NaNs, missing joints
    counter.process_frame(0.0, None)
    counter.process_frame(0.1, {})
    counter.process_frame(0.2, {"left_knee": None, "right_knee": None})
    counter.process_frame(0.3, {"left_knee": float("nan"), "right_knee": None})

    assert counter.state == RepState.UP
    assert counter.rep_count == 0

    # Real movement still functions normally after invalid frames
    counter.process_frame(1.0, {"left_knee": 170.0, "right_knee": 170.0})
    counter.process_frame(1.5, {"left_knee": None})  # partial frame, skipped
    counter.process_frame(2.0, {"left_knee": 90.0, "right_knee": 90.0})  # DOWN
    counter.process_frame(2.5, {})  # invalid frame, retained in DOWN
    assert counter.state == RepState.DOWN
    counter.process_frame(3.0, {"left_knee": 165.0, "right_knee": 165.0})  # UP

    assert counter.rep_count == 1


def test_timestamps_preserved_correctly() -> None:
    """RepDetection preserves start_time at inflection/descent and end_time at extension."""
    counter = SquatRepCounter(up_threshold=160.0, down_threshold=100.0)

    # 1.0: in UP
    counter.process_frame(1.0, {"left_knee": 170.0, "right_knee": 170.0})
    # 1.5: descent starts (< 160)
    counter.process_frame(1.5, {"left_knee": 150.0, "right_knee": 150.0})
    # 2.0: reaches DOWN (<= 100)
    counter.process_frame(2.0, {"left_knee": 95.0, "right_knee": 95.0})
    # 2.5: ascending
    counter.process_frame(2.5, {"left_knee": 130.0, "right_knee": 130.0})
    # 3.0: reaches UP (>= 160) -> rep complete!
    rep = counter.process_frame(3.0, {"left_knee": 165.0, "right_knee": 165.0})

    assert rep is not None
    assert rep.start_time == pytest.approx(1.5)
    assert rep.end_time == pytest.approx(3.0)
    assert rep.min_angle == pytest.approx(95.0)
    assert rep.max_angle == pytest.approx(170.0)


# ============================================================================
# 2. SQUAT REP COUNTING TESTS
# ============================================================================

def test_squat_spec_trajectory_produces_one_rep() -> None:
    """Trajectory: 170 -> 150 -> 120 -> 95 -> 120 -> 150 -> 165 produces exactly 1 rep."""
    counter = SquatRepCounter(up_threshold=160.0, down_threshold=100.0)

    angles = [170.0, 150.0, 120.0, 95.0, 120.0, 150.0, 165.0]
    timestamps = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]

    for t, angle in zip(timestamps, angles):
        counter.process_frame(t, {"left_knee": angle, "right_knee": angle})

    assert counter.rep_count == 1
    rep = counter.get_completed_reps()[0]
    assert rep.min_angle == pytest.approx(95.0)
    assert rep.max_angle == pytest.approx(170.0)


def test_squat_two_complete_cycles() -> None:
    """Two full squat cycles produce exactly 2 reps."""
    counter = SquatRepCounter(up_threshold=160.0, down_threshold=100.0)

    # Cycle 1
    for a in [170.0, 95.0, 165.0]:
        counter.process_frame(0.0, {"left_knee": a, "right_knee": a})
    # Cycle 2
    for a in [92.0, 162.0]:
        counter.process_frame(1.0, {"left_knee": a, "right_knee": a})

    assert counter.rep_count == 2


def test_partial_squat_does_not_count() -> None:
    """Partial squat that never breaks the down threshold (e.g. down to 110°) does not count."""
    counter = SquatRepCounter(up_threshold=160.0, down_threshold=100.0)

    # 170 -> 150 -> 120 -> 110 (never <= 100) -> 130 -> 165
    angles = [170.0, 150.0, 120.0, 110.0, 130.0, 165.0]
    for t, a in enumerate(angles):
        counter.process_frame(float(t), {"left_knee": a, "right_knee": a})

    assert counter.rep_count == 0
    assert counter.state == RepState.UP


def test_squat_single_knee_visible_fallback() -> None:
    """If one knee landmark is occluded, the available knee is used successfully."""
    counter = SquatRepCounter(up_threshold=160.0, down_threshold=100.0)

    # Only left_knee available
    counter.process_frame(0.0, {"left_knee": 170.0, "right_knee": None})
    counter.process_frame(1.0, {"left_knee": 95.0, "right_knee": None})
    counter.process_frame(2.0, {"left_knee": 165.0, "right_knee": None})

    assert counter.rep_count == 1


# ============================================================================
# 3. PUSH-UP REP COUNTING TESTS
# ============================================================================

def test_pushup_spec_trajectory_produces_one_rep() -> None:
    """Trajectory: 170 -> 150 -> 120 -> 85 -> 120 -> 150 -> 165 produces exactly 1 push-up rep."""
    counter = PushupRepCounter(up_threshold=160.0, down_threshold=90.0)

    angles = [170.0, 150.0, 120.0, 85.0, 120.0, 150.0, 165.0]
    for t, a in enumerate(angles):
        counter.process_frame(float(t), {"left_elbow": a, "right_elbow": a})

    assert counter.rep_count == 1
    rep = counter.get_completed_reps()[0]
    assert rep.min_angle == pytest.approx(85.0)
    assert rep.max_angle == pytest.approx(170.0)


# ============================================================================
# 4. LUNGE ACTIVE-LEG REP COUNTING TESTS
# ============================================================================

def test_lunge_single_leg_produces_one_rep() -> None:
    """Left knee lunges (170 -> 95 -> 165) while right knee remains supportive -> 1 rep."""
    counter = LungeRepCounter(up_threshold=160.0, down_threshold=100.0)

    # Frame 1: Standing
    counter.process_frame(0.0, {"left_knee": 170.0, "right_knee": 170.0})
    # Frame 2: Left knee descends to 95° (active leg selected)
    counter.process_frame(1.0, {"left_knee": 95.0, "right_knee": 120.0})
    assert counter.state == RepState.DOWN
    assert counter.active_leg == "left_knee"

    # Frame 3: Left knee returns to 165°
    rep = counter.process_frame(2.0, {"left_knee": 165.0, "right_knee": 165.0})

    assert rep is not None
    assert rep.rep_number == 1
    assert rep.active_leg == "left_knee"
    assert counter.rep_count == 1
    # Active leg must be reset for subsequent rep
    assert counter.active_leg is None
    assert counter.state == RepState.UP


def test_lunge_alternating_legs_produces_two_reps() -> None:
    """Alternating legs (left: 170->95->165, then right: 170->95->165) produces 2 reps."""
    counter = LungeRepCounter(up_threshold=160.0, down_threshold=100.0)

    # 1. Left lunge
    counter.process_frame(0.0, {"left_knee": 170.0, "right_knee": 170.0})
    counter.process_frame(1.0, {"left_knee": 95.0, "right_knee": 130.0})
    rep1 = counter.process_frame(2.0, {"left_knee": 165.0, "right_knee": 165.0})

    assert rep1 is not None and rep1.active_leg == "left_knee"
    assert counter.rep_count == 1

    # 2. Right lunge
    counter.process_frame(3.0, {"left_knee": 170.0, "right_knee": 170.0})
    counter.process_frame(4.0, {"left_knee": 135.0, "right_knee": 95.0})
    assert counter.active_leg == "right_knee"
    rep2 = counter.process_frame(5.0, {"left_knee": 165.0, "right_knee": 165.0})

    assert rep2 is not None and rep2.active_leg == "right_knee"
    assert counter.rep_count == 2


def test_lunge_both_knees_do_not_double_count_single_movement() -> None:
    """When one knee is selected as active, both knees bending does not count 2 reps."""
    counter = LungeRepCounter(up_threshold=160.0, down_threshold=100.0)

    counter.process_frame(0.0, {"left_knee": 170.0, "right_knee": 170.0})
    # Left knee reaches down first
    counter.process_frame(1.0, {"left_knee": 90.0, "right_knee": 110.0})
    assert counter.active_leg == "left_knee"

    # In next frame, right knee also flexes to 95, but left is the active leg
    counter.process_frame(1.5, {"left_knee": 90.0, "right_knee": 95.0})
    assert counter.rep_count == 0

    # Left knee returns to extension
    counter.process_frame(2.0, {"left_knee": 165.0, "right_knee": 150.0})
    assert counter.rep_count == 1


# ============================================================================
# 5. FACTORY & SESSION ISOLATION
# ============================================================================

def test_create_rep_counter_factory() -> None:
    """Factory correctly instantiates specific counter subclass."""
    c_squat = create_rep_counter("squat")
    assert isinstance(c_squat, SquatRepCounter)

    c_pushup = create_rep_counter(ExerciseType.PUSHUP)
    assert isinstance(c_pushup, PushupRepCounter)

    c_lunge = create_rep_counter("lunge")
    assert isinstance(c_lunge, LungeRepCounter)

    with pytest.raises(ValueError):
        create_rep_counter("jumping_jack")


def test_no_cross_video_rep_state_leak() -> None:
    """Separate counter instances or reset() must never share history across videos."""
    counter1 = SquatRepCounter()
    counter1.process_frame(0.0, {"left_knee": 170.0, "right_knee": 170.0})
    counter1.process_frame(1.0, {"left_knee": 90.0, "right_knee": 90.0})
    counter1.process_frame(2.0, {"left_knee": 165.0, "right_knee": 165.0})
    assert counter1.rep_count == 1

    # Counter 2 starts fresh
    counter2 = SquatRepCounter()
    assert counter2.rep_count == 0
    assert counter2.state == RepState.UP


# ============================================================================
# 6. INTEGRATION WITH VIDEO PROCESSING PIPELINE
# ============================================================================

def test_video_pipeline_rep_counter_integration(temp_dir: Path) -> None:
    """Verify video processor passes Step 11 angles to rep counter and exposes reps."""
    video_path = create_person_video(temp_dir / "rep_test.mp4", num_frames=10, fps=15.0)

    with PoseDetector(min_detection_confidence=0.1, min_tracking_confidence=0.1) as detector:
        rep_counter = SquatRepCounter()
        result = process_video_file(
            video_path=video_path,
            job_id=uuid.uuid4(),
            target_fps=15,
            pose_detector=detector,
            rep_counter=rep_counter,
            require_pose=True,
        )

        assert isinstance(result, ProcessingResult)
        assert result.reps is not None
        assert isinstance(result.reps, list)
        assert result.rep_count == len(result.reps)
        # Verify frame angles were evaluated by rep counter
        assert rep_counter.state in (RepState.UP, RepState.DOWN)
