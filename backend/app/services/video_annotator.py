"""Video annotation service for pose skeleton overlay and rep counter HUD.

Draws MediaPipe pose landmarks, joint connections, and workout HUD overlays
directly onto video frames during the video processing pass.
"""

from typing import List, Optional

import cv2
import numpy as np

from app.services.pose_detector import LandmarkPoint

# Standard 35 MediaPipe Pose landmark connections (0 to 32)
POSE_CONNECTIONS = [
    # Torso
    (11, 12),
    (11, 23),
    (12, 24),
    (23, 24),
    # Left Arm
    (11, 13),
    (13, 15),
    (15, 17),
    (15, 19),
    (15, 21),
    (17, 19),
    # Right Arm
    (12, 14),
    (14, 16),
    (16, 18),
    (16, 20),
    (16, 22),
    (18, 20),
    # Left Leg
    (23, 25),
    (25, 27),
    (27, 29),
    (27, 31),
    (29, 31),
    # Right Leg
    (24, 26),
    (26, 28),
    (28, 30),
    (28, 32),
    (30, 32),
    # Face
    (0, 1),
    (1, 2),
    (2, 3),
    (3, 7),
    (0, 4),
    (4, 5),
    (5, 6),
    (6, 8),
    (9, 10),
]


def draw_skeleton(
    frame: np.ndarray,
    landmarks: List[LandmarkPoint],
    min_visibility: float = 0.5,
) -> None:
    """Draw pose skeleton landmarks and connection lines directly onto the frame."""
    if not landmarks or frame is None:
        return

    height, width = frame.shape[:2]
    if width <= 0 or height <= 0:
        return

    scale = max(0.4, min(1.5, width / 640.0))
    pt_radius = max(2, int(4 * scale))
    line_thick = max(1, int(2 * scale))

    # 1. Draw connection lines
    for idx1, idx2 in POSE_CONNECTIONS:
        if idx1 < len(landmarks) and idx2 < len(landmarks):
            pt1 = landmarks[idx1]
            pt2 = landmarks[idx2]
            if pt1.visibility >= min_visibility and pt2.visibility >= min_visibility:
                x1 = int(pt1.x * width)
                y1 = int(pt1.y * height)
                x2 = int(pt2.x * width)
                y2 = int(pt2.y * height)
                # Ensure within frame bounds
                if 0 <= x1 < width and 0 <= y1 < height and 0 <= x2 < width and 0 <= y2 < height:
                    cv2.line(
                        frame,
                        (x1, y1),
                        (x2, y2),
                        (0, 230, 255),  # Bright cyan/gold
                        line_thick,
                        cv2.LINE_AA,
                    )

    # 2. Draw keypoint circles
    for pt in landmarks:
        if pt.visibility >= min_visibility:
            px = int(pt.x * width)
            py = int(pt.y * height)
            if 0 <= px < width and 0 <= py < height:
                # Outer glowing circle
                cv2.circle(
                    frame,
                    (px, py),
                    pt_radius,
                    (0, 255, 128),  # Neon green
                    -1,
                    cv2.LINE_AA,
                )
                # Inner contrast center
                cv2.circle(
                    frame,
                    (px, py),
                    max(1, pt_radius - 1),
                    (255, 255, 255),  # White
                    -1,
                    cv2.LINE_AA,
                )


def draw_hud(
    frame: np.ndarray,
    rep_count: int,
    exercise: Optional[str] = None,
    form_score: Optional[float] = None,
) -> None:
    """Draw a clean, semi-transparent HUD banner with visible rep count."""
    if frame is None:
        return

    height, width = frame.shape[:2]
    if width <= 0 or height <= 0:
        return

    scale = max(0.4, min(1.2, width / 640.0))
    box_w = max(60, min(width - 10, int(180 * scale)))
    box_h = max(25, min(height - 10, int(58 * scale)))
    margin = max(4, int(10 * scale))

    x1, y1 = margin, margin
    x2, y2 = min(width - 1, x1 + box_w), min(height - 1, y1 + box_h)

    if x2 <= x1 or y2 <= y1:
        return

    # Semi-transparent background box
    roi = frame[y1:y2, x1:x2]
    dark_overlay = np.full_like(roi, 20)
    cv2.addWeighted(dark_overlay, 0.75, roi, 0.25, 0, roi)
    frame[y1:y2, x1:x2] = roi

    # Border around HUD
    cv2.rectangle(frame, (x1, y1), (x2, y2), (80, 80, 80), 1, cv2.LINE_AA)

    # Primary HUD text: REPS: <count>
    font_scale = max(0.35, 0.7 * scale)
    thick = max(1, int(2 * scale))
    text_y1 = min(y2 - 4, y1 + int(24 * scale))
    text_x = x1 + max(4, int(8 * scale))

    cv2.putText(
        frame,
        f"REPS: {rep_count}",
        (text_x, text_y1),
        cv2.FONT_HERSHEY_SIMPLEX,
        font_scale,
        (0, 255, 128),  # Vibrant neon green
        thick,
        cv2.LINE_AA,
    )

    # Secondary text: EXERCISE or SCORE
    sub_scale = max(0.28, 0.38 * scale)
    text_y2 = min(y2 - 3, y1 + int(46 * scale))
    if exercise:
        sub_title = f"{exercise.upper()}"
        if form_score is not None:
            sub_title += f" | {form_score:.0f} pts"
        cv2.putText(
            frame,
            sub_title,
            (text_x, text_y2),
            cv2.FONT_HERSHEY_SIMPLEX,
            sub_scale,
            (220, 220, 220),  # Soft white
            1,
            cv2.LINE_AA,
        )


def annotate_frame(
    frame: np.ndarray,
    landmarks: Optional[List[LandmarkPoint]],
    rep_count: int,
    exercise: Optional[str] = None,
    form_score: Optional[float] = None,
    min_visibility: float = 0.5,
) -> np.ndarray:
    """Annotate frame with pose skeleton overlay and rep counter HUD in-place."""
    if frame is None:
        return frame

    if landmarks:
        draw_skeleton(frame, landmarks, min_visibility=min_visibility)

    draw_hud(frame, rep_count=rep_count, exercise=exercise, form_score=form_score)
    return frame
