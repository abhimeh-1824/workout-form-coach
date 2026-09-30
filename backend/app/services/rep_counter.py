"""Exercise rep counting service using finite state machines.

Provides robust, hysteresis-based rep counting for:
1. Squats (bilateral knee angles)
2. Push-ups (bilateral elbow angles)
3. Lunges (active-leg knee angle tracking)

State Machine:
    UP -> DOWN -> UP (counts exactly 1 repetition)

Features:
- Purely in-memory, session-scoped (no cross-video state leaks).
- Hysteresis protection against noise and small threshold oscillations.
- Bilateral aggregation (average when both joints visible, fallback to single side).
- Active-leg dynamic tracking for lunges.
- Tolerates missing/invalid angles and undetected frames without throwing or assuming 0°.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
import enum
import math
from typing import Any, Dict, List, Optional, Union

from app.core.config import settings
from app.db.base import ExerciseType


class RepState(str, enum.Enum):
    """Repetition phase states."""

    UP = "UP"
    DOWN = "DOWN"


@dataclass(frozen=True)
class RepDetection:
    """In-memory representation of a completed repetition."""

    rep_number: int
    start_time: float
    end_time: float
    min_angle: float
    max_angle: float
    exercise: Optional[str] = None
    active_leg: Optional[str] = None
    max_asymmetry: Optional[float] = None
    angle_samples: Optional[List[tuple[float, float]]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize rep detection metadata."""
        return {
            "rep_number": self.rep_number,
            "start_time": round(self.start_time, 2),
            "end_time": round(self.end_time, 2),
            "min_angle": round(self.min_angle, 1),
            "max_angle": round(self.max_angle, 1),
            "exercise": self.exercise,
            "active_leg": self.active_leg,
            "max_asymmetry": round(self.max_asymmetry, 1) if self.max_asymmetry is not None else None,
        }


def get_bilateral_angle(
    angle_left: Optional[float],
    angle_right: Optional[float],
) -> Optional[float]:
    """Calculate representative angle from bilateral joint pair.

    - If both joints are valid: returns their arithmetic mean.
    - If only one joint is valid: returns that valid joint's angle.
    - If neither is valid: returns None.
    """
    left_valid = angle_left is not None and not math.isnan(angle_left)
    right_valid = angle_right is not None and not math.isnan(angle_right)

    if left_valid and right_valid:
        return (angle_left + angle_right) / 2.0
    elif left_valid:
        return angle_left
    elif right_valid:
        return angle_right
    return None


class BaseRepCounter(ABC):
    """Abstract base class for exercise repetition state machines."""

    def __init__(
        self,
        exercise: str,
        up_threshold: float,
        down_threshold: float,
    ) -> None:
        self.exercise = exercise
        self.up_threshold = up_threshold
        self.down_threshold = down_threshold

        self.state: RepState = RepState.UP
        self._reps: List[RepDetection] = []
        self._rep_number: int = 1

        # Rep tracking metrics
        self._tentative_start_time: Optional[float] = None
        self._rep_start_time: Optional[float] = None
        self._min_angle_in_rep: Optional[float] = None
        self._max_angle_in_rep: Optional[float] = None
        self._last_up_angle: Optional[float] = None
        self._max_asymmetry: Optional[float] = None
        self._angle_samples: List[tuple[float, float]] = []

    @abstractmethod
    def process_frame(
        self,
        timestamp_seconds: float,
        angles: Optional[Dict[str, Optional[float]]],
    ) -> Optional[RepDetection]:
        """Process a frame's angles and return RepDetection if this frame completes a rep."""
        pass

    def get_completed_reps(self) -> List[RepDetection]:
        """Return list of all completed repetitions detected so far."""
        return list(self._reps)

    def get_reps(self) -> List[RepDetection]:
        """Return list of all completed repetitions detected so far."""
        return list(self._reps)

    @property
    def rep_count(self) -> int:
        """Return the count of completed repetitions."""
        return len(self._reps)

    def reset(self) -> None:
        """Reset internal state machine for a clean processing session."""
        self.state = RepState.UP
        self._reps.clear()
        self._rep_number = 1
        self._tentative_start_time = None
        self._rep_start_time = None
        self._min_angle_in_rep = None
        self._max_angle_in_rep = None
        self._last_up_angle = None
        self._max_asymmetry = None
        self._angle_samples.clear()


class BilateralRepCounter(BaseRepCounter):
    """Reusable state machine for symmetrical bilateral exercises (Squats & Push-ups)."""

    def __init__(
        self,
        exercise: str,
        left_joint_key: str,
        right_joint_key: str,
        up_threshold: float,
        down_threshold: float,
    ) -> None:
        super().__init__(exercise=exercise, up_threshold=up_threshold, down_threshold=down_threshold)
        self.left_joint_key = left_joint_key
        self.right_joint_key = right_joint_key

    def process_frame(
        self,
        timestamp_seconds: float,
        angles: Optional[Dict[str, Optional[float]]],
    ) -> Optional[RepDetection]:
        if not angles:
            return None

        left_angle = angles.get(self.left_joint_key)
        right_angle = angles.get(self.right_joint_key)
        rep_angle = get_bilateral_angle(left_angle, right_angle)

        if rep_angle is None or math.isnan(rep_angle):
            return None

        # State: UP
        if self.state == RepState.UP:
            if rep_angle >= self.up_threshold:
                self._last_up_angle = rep_angle
                self._tentative_start_time = None
                self._max_asymmetry = None
                self._angle_samples.clear()
            else:
                # Angle has started descending below extension threshold
                if self._tentative_start_time is None:
                    self._tentative_start_time = timestamp_seconds

                if left_angle is not None and right_angle is not None:
                    if not math.isnan(left_angle) and not math.isnan(right_angle):
                        diff = abs(left_angle - right_angle)
                        self._max_asymmetry = (
                            max(self._max_asymmetry, diff)
                            if self._max_asymmetry is not None
                            else diff
                        )

                # Check if flexion reaches DOWN threshold
                if rep_angle <= self.down_threshold:
                    self.state = RepState.DOWN
                    self._rep_start_time = (
                        self._tentative_start_time
                        if self._tentative_start_time is not None
                        else timestamp_seconds
                    )
                    self._min_angle_in_rep = rep_angle
                    self._max_angle_in_rep = max(
                        self._last_up_angle if self._last_up_angle is not None else rep_angle,
                        rep_angle,
                    )
                    self._angle_samples.append((timestamp_seconds, rep_angle))
            return None

        # State: DOWN
        elif self.state == RepState.DOWN:
            self._min_angle_in_rep = (
                min(self._min_angle_in_rep, rep_angle)
                if self._min_angle_in_rep is not None
                else rep_angle
            )
            self._max_angle_in_rep = (
                max(self._max_angle_in_rep, rep_angle)
                if self._max_angle_in_rep is not None
                else rep_angle
            )
            self._angle_samples.append((timestamp_seconds, rep_angle))

            if left_angle is not None and right_angle is not None:
                if not math.isnan(left_angle) and not math.isnan(right_angle):
                    diff = abs(left_angle - right_angle)
                    self._max_asymmetry = (
                        max(self._max_asymmetry, diff)
                        if self._max_asymmetry is not None
                        else diff
                    )

            # Check if returned to UP extension
            if rep_angle >= self.up_threshold:
                self.state = RepState.UP
                completed_rep = RepDetection(
                    rep_number=self._rep_number,
                    start_time=self._rep_start_time if self._rep_start_time is not None else timestamp_seconds,
                    end_time=timestamp_seconds,
                    min_angle=self._min_angle_in_rep,
                    max_angle=self._max_angle_in_rep,
                    exercise=self.exercise,
                    max_asymmetry=self._max_asymmetry,
                    angle_samples=list(self._angle_samples) if self._angle_samples else None,
                )
                self._reps.append(completed_rep)
                self._rep_number += 1

                # Reset rep-specific tracking
                self._tentative_start_time = None
                self._rep_start_time = None
                self._min_angle_in_rep = None
                self._max_angle_in_rep = None
                self._last_up_angle = rep_angle
                self._max_asymmetry = None
                self._angle_samples.clear()
                return completed_rep

        return None


class SquatRepCounter(BilateralRepCounter):
    """Squat repetition counter tracking knee flexion and extension."""

    def __init__(
        self,
        up_threshold: Optional[float] = None,
        down_threshold: Optional[float] = None,
    ) -> None:
        super().__init__(
            exercise=ExerciseType.SQUAT.value,
            left_joint_key="left_knee",
            right_joint_key="right_knee",
            up_threshold=up_threshold if up_threshold is not None else settings.SQUAT_UP_ANGLE,
            down_threshold=down_threshold if down_threshold is not None else settings.SQUAT_DOWN_ANGLE,
        )


class PushupRepCounter(BilateralRepCounter):
    """Push-up repetition counter tracking elbow flexion and extension."""

    def __init__(
        self,
        up_threshold: Optional[float] = None,
        down_threshold: Optional[float] = None,
    ) -> None:
        super().__init__(
            exercise=ExerciseType.PUSHUP.value,
            left_joint_key="left_elbow",
            right_joint_key="right_elbow",
            up_threshold=up_threshold if up_threshold is not None else settings.PUSHUP_UP_ANGLE,
            down_threshold=down_threshold if down_threshold is not None else settings.PUSHUP_DOWN_ANGLE,
        )


class LungeRepCounter(BaseRepCounter):
    """Lunge repetition counter with active-leg dynamic selection.

    Lunge Active-Leg Strategy:
    1. While in UP, monitors both knees.
    2. When one knee crosses the DOWN threshold (flexion <= 100°), that knee is selected
       as the active leg for the repetition.
    3. During the repetition, only the active knee is evaluated to prevent double-counting
       the trailing/supporting leg.
    4. Upon returning to UP (extension >= 160°), the repetition is completed, and active-leg
       selection is reset for the subsequent movement (allowing alternating lunges).
    """

    def __init__(
        self,
        up_threshold: Optional[float] = None,
        down_threshold: Optional[float] = None,
    ) -> None:
        super().__init__(
            exercise=ExerciseType.LUNGE.value,
            up_threshold=up_threshold if up_threshold is not None else settings.LUNGE_UP_ANGLE,
            down_threshold=down_threshold if down_threshold is not None else settings.LUNGE_DOWN_ANGLE,
        )
        self.active_leg: Optional[str] = None
        self._tentative_starts: Dict[str, float] = {}
        self._last_up_angles: Dict[str, float] = {}

    def process_frame(
        self,
        timestamp_seconds: float,
        angles: Optional[Dict[str, Optional[float]]],
    ) -> Optional[RepDetection]:
        if not angles:
            return None

        left_knee = angles.get("left_knee")
        right_knee = angles.get("right_knee")

        lk_valid = left_knee is not None and not math.isnan(left_knee)
        rk_valid = right_knee is not None and not math.isnan(right_knee)

        if not lk_valid and not rk_valid:
            return None

        # State: UP (waiting for either knee to initiate flexion towards DOWN)
        if self.state == RepState.UP:
            if lk_valid:
                if left_knee >= self.up_threshold:
                    self._last_up_angles["left_knee"] = left_knee
                    self._tentative_starts.pop("left_knee", None)
                elif "left_knee" not in self._tentative_starts:
                    self._tentative_starts["left_knee"] = timestamp_seconds

            if rk_valid:
                if right_knee >= self.up_threshold:
                    self._last_up_angles["right_knee"] = right_knee
                    self._tentative_starts.pop("right_knee", None)
                elif "right_knee" not in self._tentative_starts:
                    self._tentative_starts["right_knee"] = timestamp_seconds

            # Check if any knee reached the DOWN threshold first
            selected_leg: Optional[str] = None
            if lk_valid and rk_valid and left_knee <= self.down_threshold and right_knee <= self.down_threshold:
                # Both reached DOWN: select the one with deeper flexion
                selected_leg = "left_knee" if left_knee <= right_knee else "right_knee"
            elif lk_valid and left_knee <= self.down_threshold:
                selected_leg = "left_knee"
            elif rk_valid and right_knee <= self.down_threshold:
                selected_leg = "right_knee"

            if selected_leg is not None:
                self.active_leg = selected_leg
                self.state = RepState.DOWN
                active_angle = left_knee if selected_leg == "left_knee" else right_knee
                self._rep_start_time = self._tentative_starts.get(selected_leg, timestamp_seconds)
                self._min_angle_in_rep = active_angle
                last_up = self._last_up_angles.get(selected_leg, active_angle)
                self._max_angle_in_rep = max(last_up, active_angle)
                self._angle_samples.append((timestamp_seconds, active_angle))
                if lk_valid and rk_valid:
                    self._max_asymmetry = abs(left_knee - right_knee)

            return None

        # State: DOWN (tracking the designated active leg until it extends to UP)
        elif self.state == RepState.DOWN:
            if not self.active_leg:
                self.reset()
                return None

            active_angle = angles.get(self.active_leg)
            if active_angle is None or math.isnan(active_angle):
                return None

            self._min_angle_in_rep = (
                min(self._min_angle_in_rep, active_angle)
                if self._min_angle_in_rep is not None
                else active_angle
            )
            self._max_angle_in_rep = (
                max(self._max_angle_in_rep, active_angle)
                if self._max_angle_in_rep is not None
                else active_angle
            )
            self._angle_samples.append((timestamp_seconds, active_angle))

            if lk_valid and rk_valid:
                diff = abs(left_knee - right_knee)
                self._max_asymmetry = (
                    max(self._max_asymmetry, diff)
                    if self._max_asymmetry is not None
                    else diff
                )

            # Check if active knee returned to UP extension
            if active_angle >= self.up_threshold:
                completed_rep = RepDetection(
                    rep_number=self._rep_number,
                    start_time=self._rep_start_time if self._rep_start_time is not None else timestamp_seconds,
                    end_time=timestamp_seconds,
                    min_angle=self._min_angle_in_rep,
                    max_angle=self._max_angle_in_rep,
                    exercise=self.exercise,
                    active_leg=self.active_leg,
                    max_asymmetry=self._max_asymmetry,
                    angle_samples=list(self._angle_samples) if self._angle_samples else None,
                )
                self._reps.append(completed_rep)
                self._rep_number += 1

                # Reset active leg and state for next repetition (enables alternating legs)
                self.state = RepState.UP
                self.active_leg = None
                self._tentative_starts.clear()
                self._rep_start_time = None
                self._min_angle_in_rep = None
                self._max_angle_in_rep = None
                self._max_asymmetry = None
                self._angle_samples.clear()
                if lk_valid and left_knee >= self.up_threshold:
                    self._last_up_angles["left_knee"] = left_knee
                if rk_valid and right_knee >= self.up_threshold:
                    self._last_up_angles["right_knee"] = right_knee

                return completed_rep

        return None

    def reset(self) -> None:
        super().reset()
        self.active_leg = None
        self._tentative_starts.clear()
        self._last_up_angles.clear()


def create_rep_counter(
    exercise: Union[str, ExerciseType],
    up_threshold: Optional[float] = None,
    down_threshold: Optional[float] = None,
) -> BaseRepCounter:
    """Factory creating an exercise-specific rep counter instance."""
    ex_str = exercise.value if isinstance(exercise, ExerciseType) else str(exercise).lower().strip()

    if ex_str == "squat":
        return SquatRepCounter(up_threshold=up_threshold, down_threshold=down_threshold)
    elif ex_str in ("pushup", "push_up", "push-up"):
        return PushupRepCounter(up_threshold=up_threshold, down_threshold=down_threshold)
    elif ex_str == "lunge":
        return LungeRepCounter(up_threshold=up_threshold, down_threshold=down_threshold)
    else:
        raise ValueError(f"Unsupported exercise type for rep counting: {exercise}")
