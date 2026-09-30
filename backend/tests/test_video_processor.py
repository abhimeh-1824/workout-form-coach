"""Tests for Video Processing Foundation and Worker Integration (Step 9).

Verifies:
1. Successful incremental video processing transitions job to COMPLETED, 100% progress.
2. Missing video file fails safely with descriptive error.
3. Corrupt/invalid video file fails safely with descriptive error.
4. Empty video file fails safely and is not marked completed.
5. Progress tracking advances incrementally and reaches 100 only on successful completion.
6. Incremental frame processing: frames are streamed one-by-one without RAM accumulation.
7. Worker continues processing subsequent jobs after an individual job failure.
8. Configurable processing FPS correctly controls frame sampling rate.
9. Video capture resource handles are always cleanly released even on processing errors.
"""

from datetime import datetime, timezone
from pathlib import Path
import tempfile
from typing import Generator
import uuid

import cv2
import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db.base import Base, ExerciseType, Job, JobStatus, SourceType, User
from app.services.video_processor import (
    ProcessingResult,
    VideoProcessingError,
    process_job,
    process_video_file,
)
from app.worker.worker import run_worker


@pytest.fixture
def test_db_context() -> Generator[tuple[Session, sessionmaker], None, None]:
    """Provide isolated in-memory SQLite database and session factory."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, expire_on_commit=False)

    with TestingSession() as session:
        yield session, TestingSession

    Base.metadata.drop_all(engine)


@pytest.fixture
def sample_user(test_db_context) -> User:
    """Create a persistent user for video processing tests."""
    session, _ = test_db_context
    user = User(
        id=uuid.uuid4(),
        provider="google",
        provider_user_id=f"user-{uuid.uuid4().hex[:8]}",
        email=f"proc.test.{uuid.uuid4().hex[:8]}@example.com",
        name="Processor Tester",
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


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
        # Generate non-black frame with gradient
        frame = np.full((height, width, 3), (i * 8) % 256, dtype=np.uint8)
        out.write(frame)
    out.release()
    return file_path


def create_job(
    session: Session,
    user_id: uuid.UUID,
    video_path: str,
    status: JobStatus = JobStatus.QUEUED,
) -> Job:
    """Helper to insert a test job record."""
    job = Job(
        id=uuid.uuid4(),
        user_id=user_id,
        exercise=ExerciseType.SQUAT,
        source_type=SourceType.UPLOAD,
        video_path=video_path,
        status=status,
        progress=0,
        attempts=0,
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def test_process_valid_video_success(test_db_context, sample_user, temp_video_dir) -> None:
    """Verify that a valid short video processes incrementally and completes at 100% progress."""
    session, session_factory = test_db_context
    video_path = generate_synthetic_video(temp_video_dir / "valid.mp4", num_frames=30, fps=30.0)

    job = create_job(session, sample_user.id, str(video_path))

    # Process job using 15 FPS sampling
    result = process_job(job, db_factory=session_factory, processing_fps=15)

    assert isinstance(result, ProcessingResult)
    assert result.job_id == job.id
    assert result.frame_count == 30
    assert result.processed_frame_count == 15
    assert result.duration == 1.0
    assert result.processing_fps == 15.0

    # Verify persisted job state
    session.expire_all()
    refreshed = session.get(Job, job.id)
    assert refreshed.status == JobStatus.COMPLETED
    assert refreshed.progress == 100
    assert refreshed.completed_at is not None
    assert refreshed.error_message is None


def test_missing_video_fails(test_db_context, sample_user, temp_video_dir) -> None:
    """Verify missing video path fails safely and records descriptive error message."""
    session, session_factory = test_db_context
    missing_path = temp_video_dir / "non_existent.mp4"

    job = create_job(session, sample_user.id, str(missing_path))

    with pytest.raises(VideoProcessingError) as exc_info:
        process_job(job, db_factory=session_factory)

    assert "does not exist" in str(exc_info.value).lower()

    session.expire_all()
    refreshed = session.get(Job, job.id)
    assert refreshed.status == JobStatus.FAILED
    assert refreshed.progress == 0
    assert refreshed.completed_at is not None
    assert "does not exist" in refreshed.error_message.lower()


def test_corrupt_video_fails(test_db_context, sample_user, temp_video_dir) -> None:
    """Verify corrupted video file fails safely without unhandled crashes."""
    session, session_factory = test_db_context
    corrupt_path = temp_video_dir / "corrupt.mp4"
    corrupt_path.write_bytes(b"NOT_A_VALID_VIDEO_STREAM_JUST_RANDOM_GARBAGE" * 10)

    job = create_job(session, sample_user.id, str(corrupt_path))

    with pytest.raises(VideoProcessingError):
        process_job(job, db_factory=session_factory)

    session.expire_all()
    refreshed = session.get(Job, job.id)
    assert refreshed.status == JobStatus.FAILED
    assert refreshed.completed_at is not None
    assert refreshed.error_message is not None


def test_empty_video_fails(test_db_context, sample_user, temp_video_dir) -> None:
    """Verify 0-byte empty video file fails and is not marked completed."""
    session, session_factory = test_db_context
    empty_path = temp_video_dir / "empty.mp4"
    empty_path.write_bytes(b"")

    job = create_job(session, sample_user.id, str(empty_path))

    with pytest.raises(VideoProcessingError):
        process_job(job, db_factory=session_factory)

    session.expire_all()
    refreshed = session.get(Job, job.id)
    assert refreshed.status == JobStatus.FAILED
    assert refreshed.progress != 100
    assert refreshed.completed_at is not None


def test_incremental_processing_memory_and_sampling(temp_video_dir) -> None:
    """Verify frames are processed incrementally one-by-one without accumulating in RAM."""
    video_path = generate_synthetic_video(temp_video_dir / "stream_test.mp4", num_frames=60, fps=30.0)

    consumed_frames_count = 0
    sampled_timestamps = []

    def frame_consumer(frame: np.ndarray, frame_idx: int, timestamp: float) -> None:
        nonlocal consumed_frames_count
        consumed_frames_count += 1
        sampled_timestamps.append(timestamp)
        # Ensure frame is valid image array and not accumulated in a list
        assert isinstance(frame, np.ndarray)
        assert frame.shape == (64, 64, 3)

    result = process_video_file(
        video_path=video_path,
        job_id=uuid.uuid4(),
        target_fps=15,
        frame_consumer=frame_consumer,
    )

    # 60 total frames at 30fps -> 2.0s duration -> 30 sampled frames at 15fps
    assert result.frame_count == 60
    assert result.processed_frame_count == 30
    assert consumed_frames_count == 30
    assert len(sampled_timestamps) == 30

    # Verify timestamps are spaced by approximately 1 / 15 = ~0.0667 seconds
    for i in range(1, len(sampled_timestamps)):
        dt = sampled_timestamps[i] - sampled_timestamps[i - 1]
        assert 0.05 <= dt <= 0.08


def test_progress_tracking_updates_monotonically(test_db_context, sample_user, temp_video_dir) -> None:
    """Verify progress advances during processing and reaches 100% only upon completion."""
    session, session_factory = test_db_context
    # 60 frames = 2 seconds
    video_path = generate_synthetic_video(temp_video_dir / "progress_test.mp4", num_frames=60, fps=30.0)
    job = create_job(session, sample_user.id, str(video_path))

    recorded_progress = []

    def track_progress(pct: int) -> None:
        recorded_progress.append(pct)

    result = process_video_file(
        video_path=video_path,
        job_id=job.id,
        target_fps=15,
        on_progress=track_progress,
    )

    assert result.processed_frame_count == 30
    # Intermediate progress values were emitted
    assert len(recorded_progress) > 0
    # Values are monotonically increasing
    assert all(recorded_progress[i] <= recorded_progress[i + 1] for i in range(len(recorded_progress) - 1))
    # Intermediate values are strictly < 100
    assert all(p < 100 for p in recorded_progress)


def test_worker_continues_after_failure(test_db_context, sample_user, temp_video_dir) -> None:
    """Verify that worker survives a failing job and proceeds to successfully process subsequent jobs."""
    session, session_factory = test_db_context

    # Job 1: Corrupted video -> will fail
    corrupt_path = temp_video_dir / "job1_corrupt.mp4"
    corrupt_path.write_bytes(b"INVALID_DATA")
    job1 = create_job(session, sample_user.id, str(corrupt_path))

    # Job 2: Valid video -> will succeed
    valid_path = generate_synthetic_video(temp_video_dir / "job2_valid.mp4", num_frames=30, fps=30.0)
    job2 = create_job(session, sample_user.id, str(valid_path))

    # Run worker for 2 iterations
    run_worker(
        db_factory=session_factory,
        poll_interval=0.01,
        max_iterations=2,
    )

    session.expire_all()
    refreshed_job1 = session.get(Job, job1.id)
    refreshed_job2 = session.get(Job, job2.id)

    # Job 1 failed safely
    assert refreshed_job1.status == JobStatus.FAILED
    assert refreshed_job1.error_message is not None

    # Job 2 completed successfully
    assert refreshed_job2.status == JobStatus.COMPLETED
    assert refreshed_job2.progress == 100
    assert refreshed_job2.completed_at is not None


def test_configurable_processing_fps(temp_video_dir) -> None:
    """Verify different PROCESSING_FPS configurations correctly scale sampled frame counts."""
    video_path = generate_synthetic_video(temp_video_dir / "fps_test.mp4", num_frames=30, fps=30.0)

    # Target 10 FPS on 30 frames (1.0s video) -> 10 frames
    res_10 = process_video_file(video_path, uuid.uuid4(), target_fps=10)
    assert res_10.processed_frame_count == 10

    # Target 30 FPS on 30 frames (1.0s video) -> 30 frames
    res_30 = process_video_file(video_path, uuid.uuid4(), target_fps=30)
    assert res_30.processed_frame_count == 30


def test_video_capture_released_on_error(temp_video_dir) -> None:
    """Verify video file handle is released even when an error occurs during decoding."""
    video_path = generate_synthetic_video(temp_video_dir / "release_test.mp4", num_frames=30, fps=30.0)

    def crashing_consumer(frame, idx, ts):
        if idx > 5:
            raise RuntimeError("Deliberate mid-stream failure")

    with pytest.raises(RuntimeError, match="Deliberate mid-stream failure"):
        process_video_file(
            video_path=video_path,
            job_id=uuid.uuid4(),
            target_fps=15,
            frame_consumer=crashing_consumer,
        )

    # On Windows, open file handles prevent deletion.
    # If cap.release() was called in finally, unlinking succeeds immediately.
    video_path.unlink()
    assert not video_path.exists()
