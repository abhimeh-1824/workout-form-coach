"""Rule-based exercise form evaluation and scoring service.

Provides deterministic, explainable form quality rules for:
1. Squats: Insufficient depth (knee angle > 100°), Knee asymmetry (> 15°).
2. Push-ups: Insufficient depth (elbow angle > 90°), Elbow asymmetry (> 15°).
3. Lunges: Insufficient depth (active knee > 100°), Lunge asymmetry (> 15°).

Scoring Policy:
- Starts at 100.0.
- Warning issues deduct 10.0 points.
- Major issues deduct 20.0 points.
- Score is bounded between 0.0 and 100.0.
- Missing or occluded measurements represent 'insufficient evidence' and are NOT penalized.
"""

from dataclasses import dataclass
import math
from typing import Any, Dict, List, Optional, Union

from app.core.config import settings
from app.db.base import ExerciseType
from app.services.rep_counter import RepDetection


@dataclass(frozen=True)
class FormIssue:
    """Structured form feedback item for a single repetition."""

    code: str
    message: str
    severity: str = "warning"  # "warning" or "major"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize form issue to dictionary."""
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
        }


def evaluate_squat_form(
    rep: RepDetection,
    depth_angle: Optional[float] = None,
    asymmetry_threshold: Optional[float] = None,
) -> List[FormIssue]:
    """Evaluate squat form for insufficient depth and knee asymmetry."""
    issues: List[FormIssue] = []
    target_depth = depth_angle if depth_angle is not None else settings.SQUAT_DEPTH_ANGLE
    target_asym = asymmetry_threshold if asymmetry_threshold is not None else settings.KNEE_ASYMMETRY_THRESHOLD

    # 1. Depth check (knee angle must reach <= target_depth)
    if rep.min_angle is not None and not math.isnan(rep.min_angle):
        if rep.min_angle > target_depth:
            issues.append(
                FormIssue(
                    code="INSUFFICIENT_DEPTH",
                    message=f"Squat depth was insufficient (knee angle {rep.min_angle:.1f}° did not reach {target_depth:.0f}°)",
                    severity="warning",
                )
            )

    # 2. Asymmetry check (only when bilateral data is available)
    if rep.max_asymmetry is not None and not math.isnan(rep.max_asymmetry):
        if rep.max_asymmetry > target_asym:
            issues.append(
                FormIssue(
                    code="KNEE_ASYMMETRY",
                    message=f"Significant knee asymmetry detected ({rep.max_asymmetry:.1f}° difference exceeds {target_asym:.0f}°)",
                    severity="warning",
                )
            )

    return issues


def evaluate_pushup_form(
    rep: RepDetection,
    depth_angle: Optional[float] = None,
    asymmetry_threshold: Optional[float] = None,
) -> List[FormIssue]:
    """Evaluate push-up form for insufficient depth and elbow asymmetry."""
    issues: List[FormIssue] = []
    target_depth = depth_angle if depth_angle is not None else settings.PUSHUP_DEPTH_ANGLE
    target_asym = asymmetry_threshold if asymmetry_threshold is not None else settings.ELBOW_ASYMMETRY_THRESHOLD

    # 1. Depth check (elbow angle must reach <= target_depth)
    if rep.min_angle is not None and not math.isnan(rep.min_angle):
        if rep.min_angle > target_depth:
            issues.append(
                FormIssue(
                    code="INSUFFICIENT_DEPTH",
                    message=f"Push-up depth was insufficient (elbow angle {rep.min_angle:.1f}° did not reach {target_depth:.0f}°)",
                    severity="warning",
                )
            )

    # 2. Asymmetry check (only when both elbows are available)
    if rep.max_asymmetry is not None and not math.isnan(rep.max_asymmetry):
        if rep.max_asymmetry > target_asym:
            issues.append(
                FormIssue(
                    code="ELBOW_ASYMMETRY",
                    message=f"Significant elbow asymmetry detected ({rep.max_asymmetry:.1f}° difference exceeds {target_asym:.0f}°)",
                    severity="warning",
                )
            )

    return issues


def evaluate_lunge_form(
    rep: RepDetection,
    depth_angle: Optional[float] = None,
    asymmetry_threshold: Optional[float] = None,
) -> List[FormIssue]:
    """Evaluate lunge form for active knee depth and bilateral asymmetry."""
    issues: List[FormIssue] = []
    target_depth = depth_angle if depth_angle is not None else settings.LUNGE_DEPTH_ANGLE
    target_asym = asymmetry_threshold if asymmetry_threshold is not None else settings.LUNGE_ASYMMETRY_THRESHOLD

    # 1. Active leg depth check
    if rep.min_angle is not None and not math.isnan(rep.min_angle):
        if rep.min_angle > target_depth:
            issues.append(
                FormIssue(
                    code="INSUFFICIENT_DEPTH",
                    message=f"Lunge depth was insufficient (active knee angle {rep.min_angle:.1f}° did not reach {target_depth:.0f}°)",
                    severity="warning",
                )
            )

    # 2. Asymmetry check (only when bilateral knee data exists)
    if rep.max_asymmetry is not None and not math.isnan(rep.max_asymmetry):
        if rep.max_asymmetry > target_asym:
            issues.append(
                FormIssue(
                    code="LUNGE_ASYMMETRY",
                    message=f"Significant asymmetry detected between active and trailing leg ({rep.max_asymmetry:.1f}° exceeds {target_asym:.0f}°)",
                    severity="warning",
                )
            )

    return issues


def evaluate_rep_form(
    rep: RepDetection,
    exercise: Optional[Union[str, ExerciseType]] = None,
    depth_angle: Optional[float] = None,
    asymmetry_threshold: Optional[float] = None,
) -> List[FormIssue]:
    """Evaluate form rules for a repetition based on exercise type."""
    raw_ex = exercise if exercise is not None else rep.exercise
    if raw_ex is None:
        return []

    ex_str = raw_ex.value if isinstance(raw_ex, ExerciseType) else str(raw_ex).lower().strip()

    if ex_str == "squat":
        return evaluate_squat_form(
            rep,
            depth_angle=depth_angle,
            asymmetry_threshold=asymmetry_threshold,
        )
    elif ex_str in ("pushup", "push_up", "push-up"):
        return evaluate_pushup_form(
            rep,
            depth_angle=depth_angle,
            asymmetry_threshold=asymmetry_threshold,
        )
    elif ex_str == "lunge":
        return evaluate_lunge_form(
            rep,
            depth_angle=depth_angle,
            asymmetry_threshold=asymmetry_threshold,
        )
    else:
        return []


def calculate_form_score(
    issues: List[FormIssue],
    warning_penalty: Optional[float] = None,
    major_penalty: Optional[float] = None,
) -> float:
    """Calculate deterministic form score (0.0 to 100.0) from detected form issues."""
    warn_pen = warning_penalty if warning_penalty is not None else settings.FORM_WARNING_PENALTY
    maj_pen = major_penalty if major_penalty is not None else settings.FORM_MAJOR_PENALTY

    score = 100.0
    for issue in issues:
        if issue.severity == "major":
            score -= maj_pen
        else:
            score -= warn_pen

    # Clamp to [0.0, 100.0]
    clamped_score = max(0.0, min(100.0, score))
    return round(clamped_score, 1)
