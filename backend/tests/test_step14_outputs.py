"""Tests for Step 14: Processed Video Output, DB Persistence, and Output APIs.

Verifies:
1. Processed video generation:
   - Valid video creates processed video with skeleton overlay & HUD
   - Output video is readable and valid MP4
   - Overlay rendering does not crash on normal or edge-case frames
   - Failed rendering cleans up incomplete output
2. Database persistence & idempotency:
   - Completed reps are persisted to Rep model
   - Workout summary report is persisted to Report model
   - Rep and report fields match Step 13 analysis
   - Reprocessing/retrying a job does not create duplicate Rep or Report records
3. Authenticated APIs:
   - GET /api/v1/jobs/{job_id}/reps returns completed reps
   - GET /api/v1/jobs/{job_id}/report returns aggregate report
   - GET /api/v1/jobs/{job_id}/video securely streams processed video
   - Unauthenticated requests return 401
   - User B cannot access User A's reps, report, or video (returns 404)
   - Nonexistent job returns 404
   - Incomplete/unavailable report returns 404
4. Job lifecycle:
   - Successful processing sets status=completed, progress=100, processed_video_path
   - Failed processing sets status=failed with error_message
"""

from pathlib import Path
import tempfile
from typing import Generator
import uuid

import cv2
from fastapi.testclient import TestClient
import numpy as np
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.security import create_session_token
from app.db.base import Base, ExerciseType, Job, JobStatus, Rep, Report, SourceType, User
from app.db.session import get_db
from app.main import app
from app.services.pose_detector import LandmarkPoint
from app.services.rep_counter import SquatRepCounter
from app.services.storage import get_job_processed_video_path, get_media_root
from app.services.video_annotator import annotate_frame, draw_hud, draw_skeleton
from app.services.video_processor import (
    ProcessingResult,
    VideoProcessingError,
    process_job,
    process_video_file,
)


@pytest.fixture
def test_db_context() -> Generator[tuple[TestClient, sessionmaker], None, None]:
    """Provide TestClient with an isolated in-memory SQLite database."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, expire_on_commit=False)

    def override_get_db() -> Generator[Session, None, None]:
        with TestingSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client, TestingSession

    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)


@pytest.fixture
def users(test_db_context) -> tuple[User, User]:
    """Create two distinct users (User A and User B) for authorization isolation testing."""
    _, session_factory = test_db_context
    with session_factory() as db:
        user_a = User(
            id=uuid.uuid4(),
            provider="google",
            provider_user_id=f"user-a-{uuid.uuid4().hex[:8]}",
            email="user_a@example.com",
            name="User A",
        )
        user_b = User(
            id=uuid.uuid4(),
            provider="google",
            provider_user_id=f"user-b-{uuid.uuid4().hex[:8]}",
            email="user_b@example.com",
            name="User B",
        )
        db.add_all([user_a, user_b])
        db.commit()
        db.refresh(user_a)
        db.refresh(user_b)
        return user_a, user_b


@pytest.fixture
def temp_video_dir() -> Generator[Path, None, None]:
    """Provide a temporary directory for test video files."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


def generate_synthetic_video(
    file_path: Path,
    num_frames: int = 30,
    fps: float = 30.0,
    width: int = 128,
    height: int = 128,
) -> Path:
    """Generate a lightweight, valid MP4 video fixture using OpenCV."""
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(file_path), fourcc, fps, (width, height))
    for i in range(num_frames):
        frame = np.full((height, width, 3), (i * 8) % 256, dtype=np.uint8)
        out.write(frame)
    out.release()
    return file_path


# ============================================================================
# 1. Processed Video Tests
# ============================================================================


def test_processed_video_generation_and_readability(temp_video_dir: Path) -> None:
    """1, 2, 3: Valid video generates a processed video file that is readable via OpenCV."""
    input_video = generate_synthetic_video(temp_video_dir / "input.mp4", num_frames=30, fps=15.0)
    output_video = temp_video_dir / "processed.mp4"

    result = process_video_file(
        video_path=input_video,
        job_id=uuid.uuid4(),
        target_fps=15,
        output_video_path=output_video,
        exercise="squat",
    )

    assert isinstance(result, ProcessingResult)
    assert output_video.exists()
    assert output_video.stat().st_size > 0

    # Verify that the output video is readable by OpenCV
    cap = cv2.VideoCapture(str(output_video))
    assert cap.isOpened()
    ret, frame = cap.read()
    assert ret is True
    assert frame is not None
    assert frame.shape[0] == 128
    assert frame.shape[1] == 128
    cap.release()


def test_skeleton_and_hud_rendering_does_not_crash() -> None:
    """4, 5: Skeleton and HUD overlay rendering executes without errors on normal and edge cases."""
    # Test on standard frame
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    landmarks = [
        LandmarkPoint(name=f"POINT_{i}", x=0.5, y=0.5, z=0.0, visibility=0.9)
        for i in range(33)
    ]
    annotated = annotate_frame(
        frame=frame,
        landmarks=landmarks,
        rep_count=3,
        exercise="squat",
        form_score=85.0,
    )
    assert annotated is not None
    assert annotated.shape == (480, 640, 3)

    # Test on tiny frame (edge case: 64x64)
    tiny_frame = np.zeros((64, 64, 3), dtype=np.uint8)
    annotated_tiny = annotate_frame(
        frame=tiny_frame,
        landmarks=landmarks,
        rep_count=10,
        exercise="pushup",
    )
    assert annotated_tiny is not None
    assert annotated_tiny.shape == (64, 64, 3)


def test_failed_processing_cleans_up_incomplete_output(temp_video_dir: Path, test_db_context, users) -> None:
    """6: Incomplete processed video is safely removed when processing fails."""
    _, session_factory = test_db_context
    user_a, _ = users

    corrupt_video = temp_video_dir / "corrupt.mp4"
    corrupt_video.write_bytes(b"corrupt header bytes")

    with session_factory() as db:
        job = Job(
            id=uuid.uuid4(),
            user_id=user_a.id,
            exercise=ExerciseType.SQUAT,
            source_type=SourceType.UPLOAD,
            video_path=str(corrupt_video),
            status=JobStatus.QUEUED,
        )
        db.add(job)
        db.commit()
        db.refresh(job)

    out_path = get_job_processed_video_path(job.id)

    with pytest.raises(VideoProcessingError):
        process_job(job, db_factory=session_factory)

    assert not out_path.exists()

    with session_factory() as db:
        refreshed = db.get(Job, job.id)
        assert refreshed.status == JobStatus.FAILED
        assert refreshed.error_message is not None


# ============================================================================
# 2. Database Persistence & Idempotency Tests
# ============================================================================


def test_reps_and_report_persistence(temp_video_dir: Path, test_db_context, users) -> None:
    """7, 8, 9, 10: Reps and Report records are atomically persisted with matching Step 13 metrics."""
    _, session_factory = test_db_context
    user_a, _ = users
    video_path = generate_synthetic_video(temp_video_dir / "workout.mp4", num_frames=30, fps=15.0)

    with session_factory() as db:
        job = Job(
            id=uuid.uuid4(),
            user_id=user_a.id,
            exercise=ExerciseType.SQUAT,
            source_type=SourceType.UPLOAD,
            video_path=str(video_path),
            status=JobStatus.QUEUED,
        )
        db.add(job)
        db.commit()
        db.refresh(job)

    # Use a counter pre-loaded with 1 completed rep
    counter = SquatRepCounter()
    trajectory = [
        (0.1, 165.0, 165.0),
        (0.2, 130.0, 130.0),
        (0.3, 85.0, 85.0),   # down reached (sufficient depth)
        (0.4, 130.0, 130.0),
        (0.5, 165.0, 165.0), # rep completed!
    ]
    for ts, lk, rk in trajectory:
        counter.process_frame(ts, {"left_knee": lk, "right_knee": rk})

    result = process_job(
        job,
        db_factory=session_factory,
        processing_fps=15,
        rep_counter=counter,
    )

    assert result.total_reps == 1

    with session_factory() as db:
        db.expire_all()
        refreshed_job = db.get(Job, job.id)
        assert refreshed_job.status == JobStatus.COMPLETED
        assert refreshed_job.progress == 100
        assert refreshed_job.processed_video_path is not None
        assert refreshed_job.completed_at is not None

        # Verify Reps
        reps = db.execute(select(Rep).where(Rep.job_id == job.id)).scalars().all()
        assert len(reps) == 1
        rep = reps[0]
        assert rep.rep_number == 1
        assert rep.rom == 80.0  # 165 - 85 = 80
        assert rep.tempo == 0.3  # 0.5 - 0.2 = 0.30
        assert rep.form_score == 100.0
        assert rep.issues == []

        # Verify Report
        report = db.execute(select(Report).where(Report.job_id == job.id)).scalar_one_or_none()
        assert report is not None
        assert report.total_reps == 1
        assert report.average_rom == 80.0
        assert report.average_tempo == 0.30
        assert report.average_score == 100.0
        assert "Completed 1 squat reps with an average form score of 100.0." in report.summary


def test_idempotent_reprocessing_does_not_duplicate_records(temp_video_dir: Path, test_db_context, users) -> None:
    """11, 12: Reprocessing a job replaces previous records and does not create duplicates."""
    _, session_factory = test_db_context
    user_a, _ = users
    video_path = generate_synthetic_video(temp_video_dir / "idempotent.mp4", num_frames=30, fps=15.0)

    with session_factory() as db:
        job = Job(
            id=uuid.uuid4(),
            user_id=user_a.id,
            exercise=ExerciseType.SQUAT,
            source_type=SourceType.UPLOAD,
            video_path=str(video_path),
            status=JobStatus.QUEUED,
        )
        db.add(job)
        db.commit()
        db.refresh(job)

    # First pass
    counter1 = SquatRepCounter()
    counter1.process_frame(0.1, {"left_knee": 165.0, "right_knee": 165.0})
    counter1.process_frame(0.2, {"left_knee": 85.0, "right_knee": 85.0})
    counter1.process_frame(0.3, {"left_knee": 165.0, "right_knee": 165.0})

    process_job(job, db_factory=session_factory, processing_fps=15, rep_counter=counter1)

    with session_factory() as db:
        assert len(db.execute(select(Rep).where(Rep.job_id == job.id)).scalars().all()) == 1
        assert len(db.execute(select(Report).where(Report.job_id == job.id)).scalars().all()) == 1

    # Second pass (retry)
    counter2 = SquatRepCounter()
    counter2.process_frame(0.1, {"left_knee": 165.0, "right_knee": 165.0})
    counter2.process_frame(0.2, {"left_knee": 85.0, "right_knee": 85.0})
    counter2.process_frame(0.3, {"left_knee": 165.0, "right_knee": 165.0})

    process_job(job, db_factory=session_factory, processing_fps=15, rep_counter=counter2)

    with session_factory() as db:
        reps = db.execute(select(Rep).where(Rep.job_id == job.id)).scalars().all()
        reports = db.execute(select(Report).where(Report.job_id == job.id)).scalars().all()
        # Strictly one report and one rep record (no duplicate rows)
        assert len(reps) == 1
        assert len(reports) == 1


# ============================================================================
# 3. API Tests (Reps, Report, Processed Video, Auth & Security)
# ============================================================================


def test_api_reps_and_report_authenticated_success(temp_video_dir: Path, test_db_context, users) -> None:
    """13, 14, 15: Authenticated owner can fetch reps, report, and processed video."""
    client, session_factory = test_db_context
    user_a, _ = users
    video_path = generate_synthetic_video(temp_video_dir / "api_test.mp4", num_frames=30, fps=15.0)

    with session_factory() as db:
        job = Job(
            id=uuid.uuid4(),
            user_id=user_a.id,
            exercise=ExerciseType.SQUAT,
            source_type=SourceType.UPLOAD,
            video_path=str(video_path),
            status=JobStatus.QUEUED,
        )
        db.add(job)
        db.commit()
        db.refresh(job)

    counter = SquatRepCounter()
    counter.process_frame(0.1, {"left_knee": 165.0, "right_knee": 165.0})
    counter.process_frame(0.2, {"left_knee": 85.0, "right_knee": 85.0})
    counter.process_frame(0.3, {"left_knee": 165.0, "right_knee": 165.0})

    process_job(job, db_factory=session_factory, processing_fps=15, rep_counter=counter)

    # Authenticate as User A
    client.cookies.set(settings.SESSION_COOKIE_NAME, create_session_token(user_a.id))

    # 1. Fetch Reps
    reps_res = client.get(f"/api/v1/jobs/{job.id}/reps")
    assert reps_res.status_code == 200
    reps_data = reps_res.json()
    assert reps_data["job_id"] == str(job.id)
    assert reps_data["total_reps"] == 1
    assert len(reps_data["reps"]) == 1
    assert reps_data["reps"][0]["rep_number"] == 1
    assert reps_data["reps"][0]["rom"] == 80.0
    assert reps_data["reps"][0]["form_score"] == 100.0

    # 2. Fetch Report
    report_res = client.get(f"/api/v1/jobs/{job.id}/report")
    assert report_res.status_code == 200
    report_data = report_res.json()
    assert report_data["job_id"] == str(job.id)
    assert report_data["total_reps"] == 1
    assert report_data["average_rom"] == 80.0
    assert report_data["average_score"] == 100.0
    assert "Completed 1 squat reps" in report_data["summary"]

    # 3. Fetch Processed Video
    video_res = client.get(f"/api/v1/jobs/{job.id}/video")
    assert video_res.status_code == 200
    assert video_res.headers["content-type"] == "video/mp4"
    assert len(video_res.content) > 0


def test_api_unauthenticated_requests_return_401(test_db_context) -> None:
    """16, 17, 18: Unauthenticated requests to /reps, /report, and /video return 401."""
    client, _ = test_db_context
    dummy_job_id = uuid.uuid4()

    assert client.get(f"/api/v1/jobs/{dummy_job_id}/reps").status_code == 401
    assert client.get(f"/api/v1/jobs/{dummy_job_id}/report").status_code == 401
    assert client.get(f"/api/v1/jobs/{dummy_job_id}/video").status_code == 401


def test_api_user_b_cannot_access_user_a_outputs(temp_video_dir: Path, test_db_context, users) -> None:
    """19, 20, 21: User B receives 404 on User A's reps, report, and video (authorization isolation)."""
    client, session_factory = test_db_context
    user_a, user_b = users
    video_path = generate_synthetic_video(temp_video_dir / "isolation.mp4", num_frames=30, fps=15.0)

    with session_factory() as db:
        job = Job(
            id=uuid.uuid4(),
            user_id=user_a.id,
            exercise=ExerciseType.SQUAT,
            source_type=SourceType.UPLOAD,
            video_path=str(video_path),
            status=JobStatus.QUEUED,
        )
        db.add(job)
        db.commit()
        db.refresh(job)

    process_job(job, db_factory=session_factory, processing_fps=15)

    # Authenticate as User B (not the owner)
    client.cookies.set(settings.SESSION_COOKIE_NAME, create_session_token(user_b.id))

    assert client.get(f"/api/v1/jobs/{job.id}/reps").status_code == 404
    assert client.get(f"/api/v1/jobs/{job.id}/report").status_code == 404
    assert client.get(f"/api/v1/jobs/{job.id}/video").status_code == 404


def test_api_nonexistent_job_returns_404(test_db_context, users) -> None:
    """22: Nonexistent job ID returns 404 for reps, report, and video."""
    client, _ = test_db_context
    user_a, _ = users
    client.cookies.set(settings.SESSION_COOKIE_NAME, create_session_token(user_a.id))

    random_id = uuid.uuid4()
    assert client.get(f"/api/v1/jobs/{random_id}/reps").status_code == 404
    assert client.get(f"/api/v1/jobs/{random_id}/report").status_code == 404
    assert client.get(f"/api/v1/jobs/{random_id}/video").status_code == 404


def test_api_report_and_video_unavailable_returns_404(test_db_context, users) -> None:
    """23: Job in queued state with no report or processed video yet returns 404."""
    client, session_factory = test_db_context
    user_a, _ = users

    with session_factory() as db:
        job = Job(
            id=uuid.uuid4(),
            user_id=user_a.id,
            exercise=ExerciseType.SQUAT,
            source_type=SourceType.UPLOAD,
            status=JobStatus.QUEUED,
        )
        db.add(job)
        db.commit()
        db.refresh(job)

    client.cookies.set(settings.SESSION_COOKIE_NAME, create_session_token(user_a.id))

    # Reps returns empty list (200) or report returns 404
    reps_res = client.get(f"/api/v1/jobs/{job.id}/reps")
    assert reps_res.status_code == 200
    assert reps_res.json()["total_reps"] == 0

    report_res = client.get(f"/api/v1/jobs/{job.id}/report")
    assert report_res.status_code == 404

    video_res = client.get(f"/api/v1/jobs/{job.id}/video")
    assert video_res.status_code == 404


# ============================================================================
# 4. Job State Tests
# ============================================================================


def test_job_state_completed_and_failed_transitions(temp_video_dir: Path, test_db_context, users) -> None:
    """24, 25, 26, 27: Successful processing ends in completed at 100%; errors end in failed."""
    _, session_factory = test_db_context
    user_a, _ = users
    video_path = generate_synthetic_video(temp_video_dir / "lifecycle.mp4", num_frames=30, fps=15.0)

    # Test SUCCESS
    with session_factory() as db:
        job_success = Job(
            id=uuid.uuid4(),
            user_id=user_a.id,
            exercise=ExerciseType.SQUAT,
            source_type=SourceType.UPLOAD,
            video_path=str(video_path),
            status=JobStatus.QUEUED,
        )
        db.add(job_success)
        db.commit()
        db.refresh(job_success)

    process_job(job_success, db_factory=session_factory, processing_fps=15)

    with session_factory() as db:
        refreshed = db.get(Job, job_success.id)
        assert refreshed.status == JobStatus.COMPLETED
        assert refreshed.progress == 100
        assert refreshed.processed_video_path is not None
        assert refreshed.completed_at is not None
        assert refreshed.error_message is None

    # Test FAILURE
    with session_factory() as db:
        job_fail = Job(
            id=uuid.uuid4(),
            user_id=user_a.id,
            exercise=ExerciseType.SQUAT,
            source_type=SourceType.UPLOAD,
            video_path=str(temp_video_dir / "nonexistent.mp4"),
            status=JobStatus.QUEUED,
        )
        db.add(job_fail)
        db.commit()
        db.refresh(job_fail)

    with pytest.raises(VideoProcessingError):
        process_job(job_fail, db_factory=session_factory)

    with session_factory() as db:
        refreshed_fail = db.get(Job, job_fail.id)
        assert refreshed_fail.status == JobStatus.FAILED
        assert refreshed_fail.error_message is not None
