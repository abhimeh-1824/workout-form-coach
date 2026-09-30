"""Joint angle calculation service for biomechanical workout analysis.

Provides generic three-point vector angle calculations (0-180 degrees) with
numerical clamping, degenerate vector protection, visibility validation, and
standardized workout joint angle extraction (elbows, knees, hips, shoulders).
"""

import math
from typing import Dict, List, Optional, Tuple, Union

from app.core.config import settings
from app.services.pose_detector import LandmarkPoint

# Standard biomechanical joint angle definitions mapped to (Point A, Vertex B, Point C)
WORKOUT_JOINT_DEFINITIONS: Dict[str, Tuple[str, str, str]] = {
    "left_elbow": ("LEFT_SHOULDER", "LEFT_ELBOW", "LEFT_WRIST"),
    "right_elbow": ("RIGHT_SHOULDER", "RIGHT_ELBOW", "RIGHT_WRIST"),
    "left_knee": ("LEFT_HIP", "LEFT_KNEE", "LEFT_ANKLE"),
    "right_knee": ("RIGHT_HIP", "RIGHT_KNEE", "RIGHT_ANKLE"),
    "left_hip": ("LEFT_SHOULDER", "LEFT_HIP", "LEFT_KNEE"),
    "right_hip": ("RIGHT_SHOULDER", "RIGHT_HIP", "RIGHT_KNEE"),
    "left_shoulder": ("LEFT_HIP", "LEFT_SHOULDER", "LEFT_ELBOW"),
    "right_shoulder": ("RIGHT_HIP", "RIGHT_SHOULDER", "RIGHT_ELBOW"),
}


def calculate_angle(
    point_a: Union[LandmarkPoint, Tuple[float, float]],
    point_b: Union[LandmarkPoint, Tuple[float, float]],
    point_c: Union[LandmarkPoint, Tuple[float, float]],
    min_visibility: Optional[float] = None,
) -> Optional[float]:
    """Calculate the interior angle at vertex Point B between vectors BA and BC in degrees (0 - 180°).

    Uses 2D normalized coordinates (x, y) because camera perspective in workout form analysis
    is planar (sagittal or frontal). Normalized 2D coordinates are invariant to translation
    and uniform scale, and avoid noisy depth (z) estimation artifacts.

    Geometry:
        Vector BA = A - B
        Vector BC = C - B
        cos(theta) = (BA . BC) / (|BA| * |BC|)
        theta = arccos(clamp(cos(theta), -1.0, 1.0))

    Args:
        point_a: First endpoint (LandmarkPoint or (x, y) tuple).
        point_b: Vertex endpoint where angle is measured (LandmarkPoint or (x, y) tuple).
        point_c: Second endpoint (LandmarkPoint or (x, y) tuple).
        min_visibility: Minimum confidence threshold required for LandmarkPoints. Defaults to settings.LANDMARK_VISIBILITY_THRESHOLD.

    Returns:
        Angle in degrees rounded to 1 decimal place (0.0 to 180.0), or None if degenerate,
        unreliable, or missing.
    """
    threshold = (
        min_visibility
        if min_visibility is not None
        else settings.LANDMARK_VISIBILITY_THRESHOLD
    )

    if point_a is None or point_b is None or point_c is None:
        return None

    # 1. Validate visibility if points are LandmarkPoints
    for pt in (point_a, point_b, point_c):
        if isinstance(pt, LandmarkPoint):
            if pt.visibility is None or math.isnan(pt.visibility) or pt.visibility < threshold:
                return None

    # 2. Extract 2D coordinates (x, y)
    def extract_xy(pt: Union[LandmarkPoint, Tuple[float, float]]) -> Optional[Tuple[float, float]]:
        if isinstance(pt, LandmarkPoint):
            if pt.x is None or pt.y is None or math.isnan(pt.x) or math.isnan(pt.y):
                return None
            return pt.x, pt.y
        if isinstance(pt, (tuple, list)) and len(pt) >= 2:
            x, y = pt[0], pt[1]
            if x is None or y is None or math.isnan(x) or math.isnan(y):
                return None
            return float(x), float(y)
        return None

    coord_a = extract_xy(point_a)
    coord_b = extract_xy(point_b)
    coord_c = extract_xy(point_c)

    if coord_a is None or coord_b is None or coord_c is None:
        return None

    ax, ay = coord_a
    bx, by = coord_b
    cx, cy = coord_c

    # 3. Form vectors BA (from B to A) and BC (from B to C)
    ba_x = ax - bx
    ba_y = ay - by
    bc_x = cx - bx
    bc_y = cy - by

    # 4. Check for degenerate vectors (A == B or C == B)
    mag_ba = math.hypot(ba_x, ba_y)
    mag_bc = math.hypot(bc_x, bc_y)

    if mag_ba < 1e-7 or mag_bc < 1e-7:
        # Zero-length vector: cannot compute meaningful angle
        return None

    # 5. Dot product and cosine calculation
    dot_product = ba_x * bc_x + ba_y * bc_y
    cos_theta = dot_product / (mag_ba * mag_bc)

    # 6. Clamping for numerical stability (prevents float precision domain error in acos)
    clamped_cos = max(-1.0, min(1.0, cos_theta))

    # 7. Angle in degrees
    angle_rad = math.acos(clamped_cos)
    angle_deg = math.degrees(angle_rad)

    return round(angle_deg, 1)


def calculate_body_angles(
    landmarks: List[LandmarkPoint],
    min_visibility: Optional[float] = None,
) -> Dict[str, Optional[float]]:
    """Extract standard workout joint angles from a frame's landmarks.

    Exposes:
        - left_elbow
        - right_elbow
        - left_knee
        - right_knee
        - left_hip
        - right_hip
        - left_shoulder
        - right_shoulder

    Args:
        landmarks: List of detected or smoothed LandmarkPoint instances.
        min_visibility: Confidence cutoff. Points below this threshold produce None.

    Returns:
        Dictionary mapping angle names to angle values in degrees (or None).
    """
    angles: Dict[str, Optional[float]] = {}
    if not landmarks:
        return {joint: None for joint in WORKOUT_JOINT_DEFINITIONS}

    # Index landmarks by official name for O(1) triplet lookup
    landmark_map: Dict[str, LandmarkPoint] = {lm.name: lm for lm in landmarks}

    for joint_name, (name_a, name_b, name_c) in WORKOUT_JOINT_DEFINITIONS.items():
        point_a = landmark_map.get(name_a)
        point_b = landmark_map.get(name_b)
        point_c = landmark_map.get(name_c)

        if point_a is None or point_b is None or point_c is None:
            angles[joint_name] = None
        else:
            angles[joint_name] = calculate_angle(
                point_a,
                point_b,
                point_c,
                min_visibility=min_visibility,
            )

    return angles
