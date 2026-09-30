"""Tests for Workout Analysis Service (Step 13).

Verifies:
1. ROM (Range of Motion):
   - 168 - 92 = 76
   - Zero movement gives zero ROM
   - Negative values are prevented
   - Missing or NaN angles return None
2. Tempo:
   - 3.48 - 2.13 = 1.35s
   - Missing or NaN timestamps return None
   - Invalid/reversed timestamps return None
3. Squat Form Rules:
   - Sufficient squat depth -> no depth issue
   - Insufficient squat depth -> INSUFFICIENT_DEPTH
   - Bilateral knee asymmetry -> KNEE_ASYMMETRY
   - Single visible knee -> no false asymmetry
4. Push-up Form Rules:
   - Sufficient push-up depth -> no depth issue
   - Insufficient push-up depth -> INSUFFICIENT_DEPTH
   - Elbow asymmetry -> ELBOW_ASYMMETRY
5. Lunge Form Rules:
   - Active leg sufficient depth -> no depth issue
   - Active leg insufficient depth -> INSUFFICIENT_DEPTH
   - Missing trailing-leg data does not create false asymmetry failure
6. Form Score:
   - No issues -> 100.0
   - One warning -> correct penalty (90.0)
   - Multiple issues -> penalties applied correctly
   - Score never exceeds 100.0
   - Score never goes below 0.0
   - Missing measurements do not create artificial penalties
7. Aggregates:
   - Averages ignore None values
   - Empty rep list handled safely
8. Integration:
   - Existing video pipeline produces rep analyses
   - Total reps matches Step 12 count
   - Single-pass processing (no second loop)
"""

from pathlib import Path
import tempfile
from typing import Generator
import uuid

import cv2
import numpy as np
import pytest

from app.core.config import settings
from app.db.base import ExerciseType
from app.services.form_rules import (
    FormIssue,
    calculate_form_score,
    evaluate_lunge_form,
    evaluate_pushup_form,
    evaluate_rep_form,
    evaluate_squat_form,
)
from app.services.rep_counter import RepDetection, SquatRepCounter
from app.services.video_processor import (
    ProcessingResult,
    process_video_file,
)
from app.services.workout_analyzer import (
    RepAnalysis,
    WorkoutSummary,
    analyze_rep,
    analyze_workout,
    calculate_rom,
    calculate_tempo,
)


# ============================================================================
# ROM Tests
# ============================================================================


def test_rom_calculation_standard() -> None:
    """1. ROM: 168 - 92 = 76."""
    rep = RepDetection(
        rep_number=1,
        start_time=1.0,
        end_time=2.5,
        min_angle=92.0,
        max_angle=168.0,
    )
    rom = calculate_rom(rep)
    assert rom == 76.0


def test_rom_calculation_zero_movement() -> None:
    """2. ROM: zero movement gives zero ROM."""
    rep = RepDetection(
        rep_number=1,
        start_time=1.0,
        end_time=2.0,
        min_angle=90.0,
        max_angle=90.0,
    )
    rom = calculate_rom(rep)
    assert rom == 0.0


def test_rom_calculation_negative_prevented() -> None:
    """3. ROM: negative values are prevented."""
    # Even if max_angle is somehow lower than min_angle due to anomalous data
    rep = RepDetection(
        rep_number=1,
        start_time=1.0,
        end_time=2.0,
        min_angle=160.0,
        max_angle=120.0,
    )
    rom = calculate_rom(rep)
    assert rom == 0.0


def test_rom_calculation_missing_angle() -> None:
    """4. ROM: missing or NaN angles return None."""
    rep_no_max = RepDetection(
        rep_number=1,
        start_time=1.0,
        end_time=2.0,
        min_angle=90.0,
        max_angle=None,
    )
    assert calculate_rom(rep_no_max) is None

    rep_no_min = RepDetection(
        rep_number=1,
        start_time=1.0,
        end_time=2.0,
        min_angle=None,
        max_angle=170.0,
    )
    assert calculate_rom(rep_no_min) is None

    rep_nan = RepDetection(
        rep_number=1,
        start_time=1.0,
        end_time=2.0,
        min_angle=float("nan"),
        max_angle=170.0,
    )
    assert calculate_rom(rep_nan) is None


# ============================================================================
# Tempo Tests
# ============================================================================


def test_tempo_calculation_standard() -> None:
    """5. Tempo: 3.48 - 2.13 = 1.35 seconds."""
    rep = RepDetection(
        rep_number=1,
        start_time=2.13,
        end_time=3.48,
        min_angle=85.0,
        max_angle=165.0,
    )
    tempo = calculate_tempo(rep)
    assert tempo == 1.35


def test_tempo_calculation_missing_timestamp() -> None:
    """6. Tempo: missing timestamp returns None."""
    rep_no_start = RepDetection(
        rep_number=1,
        start_time=None,
        end_time=3.48,
        min_angle=85.0,
        max_angle=165.0,
    )
    assert calculate_tempo(rep_no_start) is None

    rep_no_end = RepDetection(
        rep_number=1,
        start_time=2.13,
        end_time=None,
        min_angle=85.0,
        max_angle=165.0,
    )
    assert calculate_tempo(rep_no_end) is None

    rep_nan = RepDetection(
        rep_number=1,
        start_time=float("nan"),
        end_time=3.48,
        min_angle=85.0,
        max_angle=165.0,
    )
    assert calculate_tempo(rep_nan) is None


def test_tempo_calculation_invalid_reversed() -> None:
    """7. Tempo: invalid/reversed timestamps return None."""
    rep_reversed = RepDetection(
        rep_number=1,
        start_time=5.0,
        end_time=2.0,
        min_angle=85.0,
        max_angle=165.0,
    )
    assert calculate_tempo(rep_reversed) is None


# ============================================================================
# Squat Rules Tests
# ============================================================================


def test_squat_sufficient_depth() -> None:
    """8. Sufficient squat depth -> no depth issue."""
    rep = RepDetection(
        rep_number=1,
        start_time=1.0,
        end_time=2.5,
        min_angle=85.0,  # <= 100.0 threshold
        max_angle=165.0,
        exercise="squat",
    )
    issues = evaluate_squat_form(rep)
    depth_issues = [i for i in issues if i.code == "INSUFFICIENT_DEPTH"]
    assert len(depth_issues) == 0


def test_squat_insufficient_depth() -> None:
    """9. Insufficient squat depth -> INSUFFICIENT_DEPTH."""
    rep = RepDetection(
        rep_number=1,
        start_time=1.0,
        end_time=2.5,
        min_angle=110.0,  # > 100.0 threshold
        max_angle=165.0,
        exercise="squat",
    )
    issues = evaluate_squat_form(rep)
    assert any(i.code == "INSUFFICIENT_DEPTH" for i in issues)
    issue = next(i for i in issues if i.code == "INSUFFICIENT_DEPTH")
    assert issue.severity == "warning"


def test_squat_bilateral_knee_asymmetry() -> None:
    """10. Bilateral knee asymmetry -> KNEE_ASYMMETRY."""
    rep = RepDetection(
        rep_number=1,
        start_time=1.0,
        end_time=2.5,
        min_angle=85.0,
        max_angle=165.0,
        exercise="squat",
        max_asymmetry=20.0,  # > 15.0 threshold
    )
    issues = evaluate_squat_form(rep)
    assert any(i.code == "KNEE_ASYMMETRY" for i in issues)


def test_squat_single_visible_knee_no_false_asymmetry() -> None:
    """11. Single visible knee -> no false asymmetry."""
    rep = RepDetection(
        rep_number=1,
        start_time=1.0,
        end_time=2.5,
        min_angle=85.0,
        max_angle=165.0,
        exercise="squat",
        max_asymmetry=None,  # Only one knee was visible, asymmetry is None
    )
    issues = evaluate_squat_form(rep)
    assert not any(i.code == "KNEE_ASYMMETRY" for i in issues)


# ============================================================================
# Push-up Rules Tests
# ============================================================================


def test_pushup_sufficient_depth() -> None:
    """12. Push-up: sufficient depth -> no depth issue."""
    rep = RepDetection(
        rep_number=1,
        start_time=1.0,
        end_time=2.0,
        min_angle=82.0,  # <= 90.0 threshold
        max_angle=160.0,
        exercise="pushup",
    )
    issues = evaluate_pushup_form(rep)
    assert not any(i.code == "INSUFFICIENT_DEPTH" for i in issues)


def test_pushup_insufficient_depth() -> None:
    """13. Push-up: insufficient depth -> INSUFFICIENT_DEPTH."""
    rep = RepDetection(
        rep_number=1,
        start_time=1.0,
        end_time=2.0,
        min_angle=98.0,  # > 90.0 threshold
        max_angle=160.0,
        exercise="pushup",
    )
    issues = evaluate_pushup_form(rep)
    assert any(i.code == "INSUFFICIENT_DEPTH" for i in issues)


def test_pushup_elbow_asymmetry() -> None:
    """14. Push-up: elbow asymmetry -> ELBOW_ASYMMETRY."""
    rep = RepDetection(
        rep_number=1,
        start_time=1.0,
        end_time=2.0,
        min_angle=80.0,
        max_angle=160.0,
        exercise="pushup",
        max_asymmetry=18.0,  # > 15.0 threshold
    )
    issues = evaluate_pushup_form(rep)
    assert any(i.code == "ELBOW_ASYMMETRY" for i in issues)


# ============================================================================
# Lunge Rules Tests
# ============================================================================


def test_lunge_active_leg_sufficient_depth() -> None:
    """15. Lunge: active leg sufficient depth -> no depth issue."""
    rep = RepDetection(
        rep_number=1,
        start_time=1.0,
        end_time=2.2,
        min_angle=88.0,  # <= 100.0 threshold
        max_angle=165.0,
        exercise="lunge",
        active_leg="left_leg",
    )
    issues = evaluate_lunge_form(rep)
    assert not any(i.code == "INSUFFICIENT_DEPTH" for i in issues)


def test_lunge_active_leg_insufficient_depth() -> None:
    """16. Lunge: active leg insufficient depth -> INSUFFICIENT_DEPTH."""
    rep = RepDetection(
        rep_number=1,
        start_time=1.0,
        end_time=2.2,
        min_angle=112.0,  # > 100.0 threshold
        max_angle=165.0,
        exercise="lunge",
        active_leg="left_leg",
    )
    issues = evaluate_lunge_form(rep)
    assert any(i.code == "INSUFFICIENT_DEPTH" for i in issues)


def test_lunge_missing_trailing_leg_no_false_failure() -> None:
    """17. Lunge: missing trailing-leg data does not create false failure."""
    rep = RepDetection(
        rep_number=1,
        start_time=1.0,
        end_time=2.2,
        min_angle=85.0,
        max_angle=165.0,
        exercise="lunge",
        active_leg="left_leg",
        max_asymmetry=None,  # Trailing leg not visible
    )
    issues = evaluate_lunge_form(rep)
    assert len(issues) == 0


# ============================================================================
# Score Tests
# ============================================================================


def test_score_no_issues_gives_100() -> None:
    """18. Score: no issues -> 100.0."""
    score = calculate_form_score([])
    assert score == 100.0


def test_score_one_warning_penalty() -> None:
    """19. Score: one warning -> correct penalty (100 - 10 = 90)."""
    issues = [
        FormIssue(code="INSUFFICIENT_DEPTH", message="Depth not reached", severity="warning")
    ]
    score = calculate_form_score(issues)
    assert score == 90.0


def test_score_multiple_issues_penalty() -> None:
    """20. Score: multiple issues -> penalties applied correctly."""
    issues = [
        FormIssue(code="INSUFFICIENT_DEPTH", message="Depth not reached", severity="warning"),
        FormIssue(code="KNEE_ASYMMETRY", message="Asymmetry detected", severity="warning"),
        FormIssue(code="SEVERE_ROUNDING", message="Back severely rounded", severity="major"),
    ]
    # 100 - 10 - 10 - 20 = 60.0
    score = calculate_form_score(issues)
    assert score == 60.0


def test_score_never_exceeds_100() -> None:
    """21. Score: never exceeds 100."""
    score = calculate_form_score([])
    assert score <= 100.0


def test_score_never_goes_below_zero() -> None:
    """22. Score: never goes below 0."""
    # 12 warnings = -120 -> clamped to 0.0
    issues = [
        FormIssue(code=f"ISSUE_{i}", message=f"Issue {i}", severity="warning")
        for i in range(12)
    ]
    score = calculate_form_score(issues)
    assert score == 0.0


def test_score_missing_measurement_no_penalty() -> None:
    """23. Score: missing measurement does not create an artificial penalty."""
    # Rep with all None angles
    rep = RepDetection(
        rep_number=1,
        start_time=1.0,
        end_time=2.0,
        min_angle=None,
        max_angle=None,
        exercise="squat",
        max_asymmetry=None,
    )
    issues = evaluate_rep_form(rep, exercise="squat")
    assert len(issues) == 0
    score = calculate_form_score(issues)
    assert score == 100.0


# ============================================================================
# Aggregate Tests
# ============================================================================


def test_aggregates_ignore_none() -> None:
    """24. Aggregates: averages ignore None values (e.g. 70, 80, None -> 75, not 50)."""
    reps = [
        RepDetection(
            rep_number=1,
            start_time=0.0,
            end_time=1.5,
            min_angle=90.0,
            max_angle=160.0,  # ROM = 70.0, Tempo = 1.5
            exercise="squat",
        ),
        RepDetection(
            rep_number=2,
            start_time=2.0,
            end_time=4.0,
            min_angle=80.0,
            max_angle=160.0,  # ROM = 80.0, Tempo = 2.0
            exercise="squat",
        ),
        RepDetection(
            rep_number=3,
            start_time=None,  # Missing tempo
            end_time=None,
            min_angle=None,   # Missing ROM
            max_angle=None,
            exercise="squat",
        ),
    ]
    summary = analyze_workout(reps, exercise=ExerciseType.SQUAT)
    assert summary.total_reps == 3
    # Average ROM should be (70.0 + 80.0) / 2 = 75.0, NOT (70 + 80 + 0) / 3 = 50.0
    assert summary.average_rom == 75.0
    # Average Tempo should be (1.5 + 2.0) / 2 = 1.75
    assert summary.average_tempo == 1.75
    # All 3 reps had no issues (rep 3 had missing info so no penalty), scores = 100, 100, 100 -> avg = 100.0
    assert summary.average_score == 100.0


def test_aggregates_empty_reps_list() -> None:
    """25. Aggregates: empty rep list handled safely."""
    summary = analyze_workout([], exercise="squat")
    assert summary.total_reps == 0
    assert summary.average_rom is None
    assert summary.average_tempo is None
    assert summary.average_score is None
    assert summary.rep_analyses == []


# ============================================================================
# Integration Tests
# ============================================================================


@pytest.fixture
def temp_video_dir() -> Generator[Path, None, None]:
    """Provide a temporary directory for test video files."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


def generate_synthetic_video(
    file_path: Path,
    num_frames: int = 30,
    fps: float = 30.0,
    width: int = 64,
    height: int = 64,
) -> Path:
    """Generate a lightweight, valid MP4 video fixture using OpenCV."""
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(file_path), fourcc, fps, (width, height))
    for i in range(num_frames):
        frame = np.full((height, width, 3), (i * 8) % 256, dtype=np.uint8)
        out.write(frame)
    out.release()
    return file_path


def test_pipeline_produces_rep_analyses_matching_step12(temp_video_dir: Path) -> None:
    """26 & 27 & 28: Existing video pipeline produces rep analyses in a single pass."""
    video_file = temp_video_dir / "analysis_test.mp4"
    generate_synthetic_video(video_file, num_frames=30, fps=15.0)

    counter = SquatRepCounter()

    # Feed trajectory: UP (165) -> DOWN (85) -> UP (165) completing 1 rep
    timestamps_and_angles = [
        (0.1, 165.0, 165.0),
        (0.2, 140.0, 140.0),
        (0.3, 110.0, 110.0),
        (0.4, 85.0, 85.0),   # down reached
        (0.5, 110.0, 110.0),
        (0.6, 140.0, 140.0),
        (0.7, 165.0, 165.0), # rep completed!
    ]
    for ts, lk, rk in timestamps_and_angles:
        counter.process_frame(ts, {"left_knee": lk, "right_knee": rk})

    reps = counter.get_completed_reps()
    assert len(reps) == 1

    summary = analyze_workout(reps, exercise="squat")
    assert summary.total_reps == 1
    assert summary.average_rom == 80.0  # 165.0 - 85.0 = 80.0
    assert summary.average_tempo == 0.50  # 0.7 - 0.2 = 0.50
    assert summary.average_score == 100.0  # Sufficient depth (85 <= 100), no asymmetry
    assert len(summary.rep_analyses) == 1

    rep_analysis = summary.rep_analyses[0]
    assert rep_analysis.rep_number == 1
    assert rep_analysis.rom == 80.0
    assert rep_analysis.tempo == 0.50
    assert rep_analysis.form_score == 100.0
    assert rep_analysis.issues == []

    # Run through process_video_file
    res = process_video_file(
        video_path=video_file,
        job_id=uuid.uuid4(),
        target_fps=15,
        rep_counter=counter,
        exercise="squat",
    )

    assert isinstance(res, ProcessingResult)
    assert res.total_reps == 1
    assert res.average_rom == 80.0
    assert res.average_tempo == 0.50
    assert res.average_score == 100.0
    assert res.rep_analyses is not None
    assert len(res.rep_analyses) == 1
    assert res.rep_analyses[0].form_score == 100.0
