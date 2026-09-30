"""Workout analysis service for ROM, tempo, form issues, and scores.

Calculates biomechanical workout metrics for completed repetitions:
1. ROM (Range of Motion): max_angle - min_angle (degrees).
2. Tempo: end_time - start_time (seconds).
3. Form issues: rule-based violations.
4. Form score: 0-100 score based on penalty deductions.
5. Workout aggregates: total_reps, average_rom, average_tempo, average_score (excluding None values).
"""

from dataclasses import dataclass
import math
from typing import Any, Dict, List, Optional, Union

from app.db.base import ExerciseType
from app.services.form_rules import (
    FormIssue,
    calculate_form_score,
    evaluate_rep_form,
)
from app.services.rep_counter import RepDetection


@dataclass(frozen=True)
class RepAnalysis:
    """Detailed form and biomechanical analysis for a single completed repetition."""

    rep_number: int
    start_time: Optional[float]
    end_time: Optional[float]
    rom: Optional[float]
    tempo: Optional[float]
    form_score: float
    issues: List[FormIssue]
    exercise: Optional[str] = None
    active_leg: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize rep analysis to dictionary."""
        return {
            "rep_number": self.rep_number,
            "start_time": round(self.start_time, 2) if self.start_time is not None else None,
            "end_time": round(self.end_time, 2) if self.end_time is not None else None,
            "rom": round(self.rom, 1) if self.rom is not None else None,
            "tempo": round(self.tempo, 2) if self.tempo is not None else None,
            "form_score": round(self.form_score, 1),
            "issues": [issue.to_dict() for issue in self.issues],
            "exercise": self.exercise,
            "active_leg": self.active_leg,
        }


@dataclass(frozen=True)
class WorkoutSummary:
    """Aggregate metrics across all repetitions of a workout session."""

    total_reps: int
    average_rom: Optional[float]
    average_tempo: Optional[float]
    average_score: Optional[float]
    rep_analyses: List[RepAnalysis]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize workout summary to dictionary."""
        return {
            "total_reps": self.total_reps,
            "average_rom": round(self.average_rom, 1) if self.average_rom is not None else None,
            "average_tempo": round(self.average_tempo, 2) if self.average_tempo is not None else None,
            "average_score": round(self.average_score, 1) if self.average_score is not None else None,
            "rep_analyses": [ra.to_dict() for ra in self.rep_analyses],
        }


def calculate_rom(rep: RepDetection) -> Optional[float]:
    """Calculate angular Range of Motion (ROM = max_angle - min_angle) in degrees.

    Returns:
        ROM rounded to 1 decimal place, or None if angles are missing or invalid.
        Never returns negative values.
    """
    if rep.max_angle is None or rep.min_angle is None:
        return None
    if math.isnan(rep.max_angle) or math.isnan(rep.min_angle):
        return None

    raw_rom = rep.max_angle - rep.min_angle
    # Prevent negative ROM
    clamped_rom = max(0.0, raw_rom)
    return round(clamped_rom, 1)


def calculate_tempo(rep: RepDetection) -> Optional[float]:
    """Calculate rep duration/tempo (tempo = end_time - start_time) in seconds.

    Returns:
        Tempo rounded to 2 decimal places, or None if timestamps are missing or invalid.
    """
    if rep.start_time is None or rep.end_time is None:
        return None
    if math.isnan(rep.start_time) or math.isnan(rep.end_time):
        return None
    if rep.end_time < rep.start_time:
        return None

    duration = rep.end_time - rep.start_time
    return round(max(0.0, duration), 2)


def analyze_rep(
    rep: RepDetection,
    exercise: Optional[Union[str, ExerciseType]] = None,
) -> RepAnalysis:
    """Analyze a single completed repetition for ROM, tempo, form issues, and score."""
    rom = calculate_rom(rep)
    tempo = calculate_tempo(rep)
    issues = evaluate_rep_form(rep, exercise=exercise)
    form_score = calculate_form_score(issues)

    ex_str = rep.exercise
    if ex_str is None and exercise is not None:
        ex_str = exercise.value if isinstance(exercise, ExerciseType) else str(exercise)

    return RepAnalysis(
        rep_number=rep.rep_number,
        start_time=rep.start_time,
        end_time=rep.end_time,
        rom=rom,
        tempo=tempo,
        form_score=form_score,
        issues=issues,
        exercise=ex_str,
        active_leg=rep.active_leg,
    )


def analyze_workout(
    reps: List[RepDetection],
    exercise: Optional[Union[str, ExerciseType]] = None,
) -> WorkoutSummary:
    """Analyze all completed repetitions of a workout session and compute aggregate metrics."""
    if not reps:
        return WorkoutSummary(
            total_reps=0,
            average_rom=None,
            average_tempo=None,
            average_score=None,
            rep_analyses=[],
        )

    analyses = [analyze_rep(rep, exercise=exercise) for rep in reps]

    # Calculate average ROM (ignoring None values)
    valid_roms = [ra.rom for ra in analyses if ra.rom is not None]
    avg_rom = round(sum(valid_roms) / len(valid_roms), 1) if valid_roms else None

    # Calculate average tempo (ignoring None values)
    valid_tempos = [ra.tempo for ra in analyses if ra.tempo is not None]
    avg_tempo = round(sum(valid_tempos) / len(valid_tempos), 2) if valid_tempos else None

    # Calculate average form score
    valid_scores = [ra.form_score for ra in analyses if ra.form_score is not None]
    avg_score = round(sum(valid_scores) / len(valid_scores), 1) if valid_scores else None

    return WorkoutSummary(
        total_reps=len(analyses),
        average_rom=avg_rom,
        average_tempo=avg_tempo,
        average_score=avg_score,
        rep_analyses=analyses,
    )
