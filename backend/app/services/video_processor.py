"""Video processing foundation service with MediaPipe Pose integration.

Provides incremental frame processing, configurable FPS sampling, input validation,
transaction-safe progress persistence, MediaPipe Pose 33-landmark inference, and
failure handling without loading entire videos into memory.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import inspect
import logging
import math
from pathlib import Path
import shutil
import subprocess
from typing import Callable, List, Optional, Union
import uuid

import cv2
import numpy as np
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.base import ExerciseType, Job, JobStatus, Rep, Report
from app.services.joint_angles import calculate_body_angles
from app.services.landmark_smoother import LandmarkSmoother
from app.services.pose_detector import (
    PoseDetectionError,
    PoseDetector,
    PoseFrameResult,
)
from app.services.rep_counter import BaseRepCounter, RepDetection, create_rep_counter
from app.services.storage import (
    cleanup_path,
    get_job_processed_relative_path,
    get_job_processed_video_path,
    get_media_root,
)
from app.services.video import VideoValidationError, validate_video_file
from app.services.video_annotator import annotate_frame
from app.services.workout_analyzer import RepAnalysis, WorkoutSummary, analyze_workout

logger = logging.getLogger("workout_form_coach.video_processor")


class VideoProcessingError(Exception):
    """Exception raised when video processing fails."""
    pass


@dataclass
class ProcessingResult:
    """Internal processing summary metadata with pose, rep counting, and workout analysis."""

    job_id: uuid.UUID
    frame_count: int
    processed_frame_count: int
    duration: float
    source_fps: float
    processing_fps: float
    pose_detected_frames: int = 0
    pose_missing_frames: int = 0
    pose_detection_rate: float = 0.0
    pose_frames: Optional[List[PoseFrameResult]] = None
    reps: Optional[List[RepDetection]] = None
    rep_count: int = 0
    rep_analyses: Optional[List[RepAnalysis]] = None
    total_reps: int = 0
    average_rom: Optional[float] = None
    average_tempo: Optional[float] = None
    average_score: Optional[float] = None
    processed_video_path: Optional[str] = None


def persist_job_progress(
    db_factory: sessionmaker[Session],
    job_id: uuid.UUID,
    progress: int,
) -> None:
    """Persist job progress update in an isolated, short-lived transaction."""
    try:
        with db_factory() as session:
            stmt = select(Job).where(Job.id == job_id)
            job = session.execute(stmt).scalars().first()
            if job and job.status == JobStatus.PROCESSING:
                job.progress = progress
                session.commit()
                logger.debug("Job %s progress updated to %d%%", job_id, progress)
    except Exception as exc:
        logger.warning("Failed to persist progress for job %s: %s", job_id, exc)


def finalize_job_success(
    db_factory: sessionmaker[Session],
    job_id: uuid.UUID,
) -> None:
    """Mark job as completed with 100% progress in an isolated transaction."""
    with db_factory() as session:
        stmt = select(Job).where(Job.id == job_id)
        job = session.execute(stmt).scalars().first()
        if job:
            job.status = JobStatus.COMPLETED
            job.progress = 100
            job.completed_at = datetime.now(timezone.utc)
            session.commit()
            logger.info("Job %s marked COMPLETED (100%%)", job_id)


def finalize_job_failure(
    db_factory: sessionmaker[Session],
    job_id: uuid.UUID,
    error_message: str,
) -> None:
    """Mark job as failed with safe human-readable error message in an isolated transaction."""
    try:
        with db_factory() as session:
            stmt = select(Job).where(Job.id == job_id)
            job = session.execute(stmt).scalars().first()
            if job:
                job.status = JobStatus.FAILED
                job.error_message = error_message
                job.completed_at = datetime.now(timezone.utc)
                session.commit()
                logger.info("Job %s marked FAILED: %s", job_id, error_message)
    except Exception as exc:
        logger.exception("Failed to mark job %s as FAILED: %s", job_id, exc)


def generate_workout_summary_text(
    exercise: str,
    total_reps: int,
    average_score: Optional[float] = None,
) -> str:
    """Generate concise, deterministic summary text without external LLMs."""
    ex = exercise.lower().replace("_", "-")
    if total_reps == 0:
        return f"Completed 0 {ex} reps."
    if average_score is not None:
        return f"Completed {total_reps} {ex} reps with an average form score of {average_score:.1f}."
    return f"Completed {total_reps} {ex} reps."


def persist_workout_results(
    db_factory: sessionmaker[Session],
    job_id: uuid.UUID,
    workout_summary: WorkoutSummary,
    exercise_name: str,
    processed_video_path: Optional[str] = None,
) -> None:
    """Persist repetition records, summary report, and mark job COMPLETED in an atomic transaction."""
    with db_factory() as session:
        # 1. Clean up any previous records for this job (guaranteeing strict idempotency upon retry)
        session.execute(delete(Rep).where(Rep.job_id == job_id))
        session.execute(delete(Report).where(Report.job_id == job_id))

        # 2. Persist all completed reps
        for rep_analysis in workout_summary.rep_analyses:
            rep_record = Rep(
                job_id=job_id,
                rep_number=rep_analysis.rep_number,
                start_time=rep_analysis.start_time if rep_analysis.start_time is not None else 0.0,
                end_time=rep_analysis.end_time if rep_analysis.end_time is not None else 0.0,
                rom=rep_analysis.rom,
                tempo=rep_analysis.tempo,
                form_score=rep_analysis.form_score,
                issues=[issue.to_dict() for issue in rep_analysis.issues],
            )
            session.add(rep_record)

        # 3. Persist summary report
        summary_text = generate_workout_summary_text(
            exercise=exercise_name,
            total_reps=workout_summary.total_reps,
            average_score=workout_summary.average_score,
        )
        report_record = Report(
            job_id=job_id,
            total_reps=workout_summary.total_reps,
            average_score=workout_summary.average_score,
            average_rom=workout_summary.average_rom,
            average_tempo=workout_summary.average_tempo,
            summary=summary_text,
        )
        session.add(report_record)

        # 4. Finalize job state to COMPLETED
        stmt = select(Job).where(Job.id == job_id)
        job = session.execute(stmt).scalars().first()
        if job:
            job.status = JobStatus.COMPLETED
            job.progress = 100
            job.completed_at = datetime.now(timezone.utc)
            job.error_message = None
            if processed_video_path:
                job.processed_video_path = processed_video_path

        session.commit()
        logger.info(
            "Successfully persisted %d reps and summary report for job %s (COMPLETED 100%%)",
            workout_summary.total_reps,
            job_id,
        )


def process_video_file(
    video_path: Path,
    job_id: uuid.UUID,
    target_fps: Optional[int] = None,
    on_progress: Optional[Callable[[int], None]] = None,
    frame_consumer: Optional[Callable[..., None]] = None,
    pose_detector: Optional[PoseDetector] = None,
    landmark_smoother: Optional[LandmarkSmoother] = None,
    rep_counter: Optional[BaseRepCounter] = None,
    exercise: Optional[Union[str, ExerciseType]] = None,
    output_video_path: Optional[Path] = None,
    require_pose: bool = False,
) -> ProcessingResult:
    """Process a video file incrementally frame-by-frame at configured FPS with Pose estimation.

    Streams frames one by one without accumulating frames in memory.
    Optionally annotates frames with skeleton overlay and rep HUD to output_video_path.
    """
    fps_setting = target_fps or settings.PROCESSING_FPS

    # 1. Pre-processing file validation
    if not video_path.exists():
        raise VideoProcessingError("Video file does not exist on storage.")

    try:
        duration = validate_video_file(video_path)
    except VideoValidationError as val_err:
        raise VideoProcessingError(f"Video validation failed: {val_err}")

    # 2. Open video capture
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise VideoProcessingError("Could not open video file; unsupported codec or corrupt container.")

    detector_owner = False
    detector = pose_detector
    if detector is None:
        detector = PoseDetector()
        detector_owner = True

    smoother = landmark_smoother if landmark_smoother is not None else LandmarkSmoother()
    output_writer: Optional[cv2.VideoWriter] = None

    try:
        source_fps = cap.get(cv2.CAP_PROP_FPS)
        if source_fps <= 0 or math.isnan(source_fps):
            source_fps = float(fps_setting)

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames < 0 or math.isnan(total_frames):
            total_frames = 0

        frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if frame_width <= 0 or frame_height <= 0:
            frame_width, frame_height = 640, 480

        # Initialize VideoWriter if output video path requested
        if output_video_path is not None:
            output_video_path.parent.mkdir(parents=True, exist_ok=True)
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            output_writer = cv2.VideoWriter(
                str(output_video_path),
                fourcc,
                float(fps_setting),
                (frame_width, frame_height),
            )
            if not output_writer.isOpened():
                logger.warning("Could not initialize VideoWriter for output %s", output_video_path)
                output_writer = None

        target_interval_sec = 1.0 / float(fps_setting)
        next_target_time = 0.0
        frame_idx = 0
        processed_frame_count = 0
        pose_detected_frames = 0
        pose_missing_frames = 0
        last_persisted_progress = 0
        pose_results: List[PoseFrameResult] = []

        logger.info(
            "Starting video processing for job %s: source_fps=%.2f, target_fps=%d, total_frames=%d, duration=%.2fs",
            job_id,
            source_fps,
            fps_setting,
            total_frames,
            duration,
        )

        while True:
            current_time = frame_idx / source_fps

            # Grab frame packet without decoding full matrix into memory if not needed
            grabbed = cap.grab()
            if not grabbed:
                break

            # Check if this frame timestamp falls on the target sampling interval
            if current_time >= next_target_time - 1e-4:
                ret, frame = cap.retrieve()
                if not ret or frame is None:
                    break

                # Run MediaPipe Pose landmark extraction
                raw_pose_res = detector.process_frame(frame, frame_idx, current_time)
                if raw_pose_res.pose_detected:
                    pose_detected_frames += 1
                    smoothed_lms = smoother.smooth(raw_pose_res.landmarks)
                    angles = calculate_body_angles(smoothed_lms)
                else:
                    pose_missing_frames += 1
                    smoothed_lms = smoother.smooth([])
                    angles = calculate_body_angles([])

                # Exercise repetition counting
                if rep_counter is not None and angles:
                    rep_counter.process_frame(current_time, angles)

                pose_frame_res = PoseFrameResult(
                    frame_index=frame_idx,
                    timestamp_seconds=current_time,
                    pose_detected=raw_pose_res.pose_detected,
                    landmarks=raw_pose_res.landmarks,
                    smoothed_landmarks=smoothed_lms,
                    angles=angles,
                )

                pose_results.append(pose_frame_res)

                # Render skeleton overlay and HUD if output video requested
                if output_writer is not None:
                    current_rep_count = rep_counter.rep_count if rep_counter is not None else 0
                    exercise_str = (
                        exercise.value if hasattr(exercise, "value") else str(exercise)
                    ) if exercise else None
                    annotate_frame(
                        frame=frame,
                        landmarks=smoothed_lms if raw_pose_res.pose_detected else None,
                        rep_count=current_rep_count,
                        exercise=exercise_str,
                    )
                    output_writer.write(frame)

                # Stream to consumer if provided
                if frame_consumer is not None:
                    sig = inspect.signature(frame_consumer)
                    param_count = len(sig.parameters)
                    if param_count >= 4:
                        frame_consumer(frame, frame_idx, current_time, pose_frame_res)
                    else:
                        frame_consumer(frame, frame_idx, current_time)

                processed_frame_count += 1
                next_target_time += target_interval_sec

                # Immediately delete reference to prevent any frame accumulation in RAM
                del frame

                # Derive progress from processed frame count or timestamp
                if total_frames > 0:
                    current_progress = min(99, max(1, int((frame_idx / total_frames) * 100)))
                elif duration > 0:
                    current_progress = min(99, max(1, int((current_time / duration) * 100)))
                else:
                    current_progress = 1

                # Update progress periodically to avoid database write contention
                if on_progress and (current_progress >= last_persisted_progress + 5):
                    on_progress(current_progress)
                    last_persisted_progress = current_progress

            frame_idx += 1

        if processed_frame_count == 0:
            raise VideoProcessingError("Video contains zero decodable frames.")

        pose_detection_rate = (
            round(pose_detected_frames / processed_frame_count, 4)
            if processed_frame_count > 0
            else 0.0
        )

        logger.info(
            "Video processing finished for job %s: %d total frames read, %d processed at %d FPS. "
            "Pose detected: %d/%d (%.1f%%)",
            job_id,
            frame_idx,
            processed_frame_count,
            fps_setting,
            pose_detected_frames,
            processed_frame_count,
            pose_detection_rate * 100.0,
        )

        # Enforce no-person video policy
        if require_pose and pose_detected_frames == 0:
            raise VideoProcessingError("No person detected in the video.")

        # Validate generated processed video if requested
        relative_video_path: Optional[str] = None
        if output_video_path is not None:
            if output_writer is not None:
                output_writer.release()
                output_writer = None
            if not output_video_path.exists() or output_video_path.stat().st_size == 0:
                cleanup_path(output_video_path)
                raise VideoProcessingError("Processed video generation failed or produced empty file.")

            # If ffmpeg is available, re-encode to web-compatible H.264 (avc1/yuv420p) with faststart
            # Modern browsers (Chrome, Edge, Safari) do not play raw mp4v (MPEG-4 Part 2) in HTML5 <video>
            temp_h264_path = output_video_path.with_name(f"{output_video_path.stem}_h264.mp4")
            try:
                ffmpeg_bin = shutil.which("ffmpeg")
                if ffmpeg_bin:
                    cmd = [
                        ffmpeg_bin,
                        "-y",
                        "-i",
                        str(output_video_path),
                        "-c:v",
                        "libx264",
                        "-pix_fmt",
                        "yuv420p",
                        "-preset",
                        "fast",
                        "-movflags",
                        "+faststart",
                        str(temp_h264_path),
                    ]
                    res = subprocess.run(
                        cmd,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=60,
                    )
                    if (
                        res.returncode == 0
                        and temp_h264_path.exists()
                        and temp_h264_path.stat().st_size > 0
                    ):
                        temp_h264_path.replace(output_video_path)
                        logger.info(
                            "Successfully converted processed video to web-compatible H.264: %s",
                            output_video_path,
                        )
            except Exception as ffmpeg_err:
                logger.warning("Optional H.264 web re-encoding skipped or failed: %s", ffmpeg_err)
            finally:
                if temp_h264_path.exists():
                    cleanup_path(temp_h264_path)

            try:
                relative_video_path = str(output_video_path.relative_to(get_media_root())).replace("\\", "/")
            except ValueError:
                relative_video_path = output_video_path.as_posix()

        detected_reps = rep_counter.get_reps() if rep_counter is not None else []
        workout_summary = analyze_workout(detected_reps, exercise=exercise)

        return ProcessingResult(
            job_id=job_id,
            frame_count=frame_idx,
            processed_frame_count=processed_frame_count,
            duration=duration,
            source_fps=source_fps,
            processing_fps=float(fps_setting),
            pose_detected_frames=pose_detected_frames,
            pose_missing_frames=pose_missing_frames,
            pose_detection_rate=pose_detection_rate,
            pose_frames=pose_results,
            reps=detected_reps,
            rep_count=len(detected_reps),
            rep_analyses=workout_summary.rep_analyses,
            total_reps=workout_summary.total_reps,
            average_rom=workout_summary.average_rom,
            average_tempo=workout_summary.average_tempo,
            average_score=workout_summary.average_score,
            processed_video_path=relative_video_path,
        )

    finally:
        cap.release()
        if output_writer is not None:
            output_writer.release()
        if detector_owner and detector is not None:
            detector.close()


def process_job(
    job: Job,
    db_factory: sessionmaker[Session],
    processing_fps: Optional[int] = None,
    pose_detector: Optional[PoseDetector] = None,
    landmark_smoother: Optional[LandmarkSmoother] = None,
    rep_counter: Optional[BaseRepCounter] = None,
    generate_video: bool = True,
    require_pose: bool = False,
) -> ProcessingResult:
    """Coordinate end-to-end processing for a claimed job outside long-lived DB transactions.

    Performs:
    1. Video path verification.
    2. Incremental frame processing, MediaPipe 33-landmark extraction, rep counting, and workout analysis.
    3. Optional skeleton overlay & rep HUD video rendering.
    4. Transaction-safe atomic persistence of Reps, Report, and job completion.
    """
    logger.info("Processing service starting for job %s (exercise=%s)", job.id, job.exercise.value)

    if not job.video_path:
        error_msg = "Job has no associated video file for processing."
        finalize_job_failure(db_factory, job.id, error_msg)
        raise VideoProcessingError(error_msg)

    video_path = Path(job.video_path)
    if not video_path.is_absolute():
        video_path = video_path.resolve()

    active_rep_counter = rep_counter
    if active_rep_counter is None and job.exercise is not None:
        try:
            active_rep_counter = create_rep_counter(job.exercise)
        except Exception as exc:
            logger.warning("Could not instantiate rep counter for exercise %s: %s", job.exercise, exc)

    def progress_callback(progress_percent: int) -> None:
        persist_job_progress(db_factory, job.id, progress_percent)

    output_video_path: Optional[Path] = None
    relative_processed_path: Optional[str] = None
    if generate_video:
        output_video_path = get_job_processed_video_path(job.id)
        relative_processed_path = get_job_processed_relative_path(job.id)

    try:
        result = process_video_file(
            video_path=video_path,
            job_id=job.id,
            target_fps=processing_fps,
            on_progress=progress_callback,
            pose_detector=pose_detector,
            landmark_smoother=landmark_smoother,
            rep_counter=active_rep_counter,
            exercise=job.exercise,
            output_video_path=output_video_path,
            require_pose=require_pose,
        )

        workout_summary = analyze_workout(result.reps or [], exercise=job.exercise)

        # Atomic persistence of Reps, Report, and Job completion
        persist_workout_results(
            db_factory=db_factory,
            job_id=job.id,
            workout_summary=workout_summary,
            exercise_name=job.exercise.value if hasattr(job.exercise, "value") else str(job.exercise),
            processed_video_path=relative_processed_path if output_video_path and output_video_path.exists() else None,
        )

        return result

    except VideoProcessingError as vpe:
        if output_video_path and output_video_path.exists():
            cleanup_path(output_video_path)
        safe_msg = str(vpe)
        logger.warning("Job %s processing failed with validation error: %s", job.id, safe_msg)
        finalize_job_failure(db_factory, job.id, safe_msg)
        raise
    except PoseDetectionError as pde:
        if output_video_path and output_video_path.exists():
            cleanup_path(output_video_path)
        safe_msg = f"Pose detection initialization failed: {pde}"
        logger.error("Job %s failed on pose detector: %s", job.id, pde)
        finalize_job_failure(db_factory, job.id, safe_msg)
        raise VideoProcessingError(safe_msg) from pde
    except Exception as exc:
        if output_video_path and output_video_path.exists():
            cleanup_path(output_video_path)
        logger.exception("Unexpected error while processing video for job %s: %s", job.id, exc)
        safe_msg = "Internal error occurred during video frame processing."
        finalize_job_failure(db_factory, job.id, safe_msg)
        raise VideoProcessingError(safe_msg) from exc
