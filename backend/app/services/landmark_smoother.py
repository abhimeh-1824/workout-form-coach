"""Landmark smoothing service using Exponential Moving Average (EMA).

Stabilizes raw 3D pose landmark coordinates across sequential video frames,
reducing MediaPipe jitter without introducing ML complexity or cross-video state leaks.
"""

from typing import Dict, List, Optional, Tuple

from app.core.config import settings
from app.services.pose_detector import LandmarkPoint


class LandmarkSmoother:
    """Session-scoped Exponential Moving Average (EMA) landmark coordinate smoother.

    Formula:
        S_t = alpha * X_t + (1 - alpha) * S_{t-1}

    Attributes:
        alpha: Smoothing factor between 0.0 (maximum smoothing) and 1.0 (no smoothing).
        _previous_landmarks: Dictionary mapping landmark name to previous (x, y, z) tuple.
    """

    def __init__(self, alpha: Optional[float] = None) -> None:
        raw_alpha = alpha if alpha is not None else settings.LANDMARK_SMOOTHING_ALPHA
        # Clamp alpha to valid range (0.0 < alpha <= 1.0)
        self.alpha: float = max(0.01, min(1.0, float(raw_alpha)))
        self._previous_landmarks: Dict[str, Tuple[float, float, float]] = {}

    def smooth(self, landmarks: List[LandmarkPoint]) -> List[LandmarkPoint]:
        """Apply exponential moving average to a list of landmarks.

        Args:
            landmarks: Raw LandmarkPoint detections from current frame.

        Returns:
            List of smoothed LandmarkPoint instances with updated (x, y, z) coordinates.
            Preserves official landmark names and raw visibility confidence.
        """
        if not landmarks:
            # If no landmarks are detected (person occluded or missing), reset previous
            # state to prevent erratic velocity jumps when the person reappears.
            self.reset()
            return []

        smoothed_points: List[LandmarkPoint] = []
        new_state: Dict[str, Tuple[float, float, float]] = {}

        for lm in landmarks:
            if lm.name in self._previous_landmarks:
                prev_x, prev_y, prev_z = self._previous_landmarks[lm.name]
                sm_x = self.alpha * lm.x + (1.0 - self.alpha) * prev_x
                sm_y = self.alpha * lm.y + (1.0 - self.alpha) * prev_y
                sm_z = self.alpha * lm.z + (1.0 - self.alpha) * prev_z
            else:
                # First appearance of this landmark: initialize without smoothing
                sm_x = lm.x
                sm_y = lm.y
                sm_z = lm.z

            new_state[lm.name] = (sm_x, sm_y, sm_z)

            smoothed_points.append(
                LandmarkPoint(
                    name=lm.name,
                    x=sm_x,
                    y=sm_y,
                    z=sm_z,
                    visibility=lm.visibility,
                )
            )

        self._previous_landmarks = new_state
        return smoothed_points

    def reset(self) -> None:
        """Clear historical landmark state for a new video session."""
        self._previous_landmarks.clear()
