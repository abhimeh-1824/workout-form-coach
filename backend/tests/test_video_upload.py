from io import BytesIO
from pathlib import Path
import tempfile
from typing import Generator
from unittest.mock import patch
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
from app.db.base import Base, ExerciseType, Job, JobStatus, SourceType, User
from app.db.session import get_db
from app.main import app
from app.services.storage import get_media_root


@pytest.fixture
def upload_test_context() -> Generator[tuple[TestClient, sessionmaker], None, None]:
    """Provide TestClient with an isolated in-memory SQLite database for upload tests."""
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


def make_valid_mp4_bytes(num_frames: int = 15, fps: float = 15.0) -> bytes:
    """Generate in-memory bytes of a valid, minimal MP4 video."""
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out = cv2.VideoWriter(str(tmp_path), fourcc, fps, (64, 64))
        for i in range(num_frames):
            frame = np.full((64, 64, 3), (i * 10) % 256, dtype=np.uint8)
            out.write(frame)
        out.release()
        return tmp_path.read_bytes()
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def test_unauthenticated_upload_rejected(upload_test_context) -> None:
    """Verify unauthenticated video upload returns 401."""
    client, _ = upload_test_context
    job_id = uuid.uuid4()
    files = {"file": ("video.mp4", b"fake content", "video/mp4")}
    resp = client.post(f"/api/v1/jobs/{job_id}/video", files=files)
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Not authenticated"


def test_user_b_cannot_upload_to_user_a_job(upload_test_context) -> None:
    """Verify User B receives 404 when attempting to upload to User A's job."""
    client, session_factory = upload_test_context

    with session_factory() as db:
        user_a = User(id=uuid.uuid4(), provider="google", provider_user_id="user_a", email="a@example.com")
        user_b = User(id=uuid.uuid4(), provider="google", provider_user_id="user_b", email="b@example.com")
        job = Job(
            id=uuid.uuid4(),
            user_id=user_a.id,
            exercise=ExerciseType.SQUAT,
            source_type=SourceType.UPLOAD,
            status=JobStatus.QUEUED,
        )
        db.add_all([user_a, user_b, job])
        db.commit()
        job_id = job.id
        token_b = create_session_token(user_b.id)

    client.cookies.set(settings.SESSION_COOKIE_NAME, token_b)
    files = {"file": ("video.mp4", make_valid_mp4_bytes(), "video/mp4")}
    resp = client.post(f"/api/v1/jobs/{job_id}/video", files=files)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Job not found"


def test_non_upload_job_cannot_use_upload_endpoint(upload_test_context) -> None:
    """Verify jobs created for YouTube source cannot accept direct uploads."""
    client, session_factory = upload_test_context

    with session_factory() as db:
        user = User(id=uuid.uuid4(), provider="google", provider_user_id="user_yt", email="yt@example.com")
        job = Job(
            id=uuid.uuid4(),
            user_id=user.id,
            exercise=ExerciseType.SQUAT,
            source_type=SourceType.YOUTUBE,
            source_url="https://www.youtube.com/watch?v=123",
            status=JobStatus.QUEUED,
        )
        db.add_all([user, job])
        db.commit()
        job_id = job.id
        token = create_session_token(user.id)

    client.cookies.set(settings.SESSION_COOKIE_NAME, token)
    files = {"file": ("video.mp4", make_valid_mp4_bytes(), "video/mp4")}
    resp = client.post(f"/api/v1/jobs/{job_id}/video", files=files)
    assert resp.status_code == 400
    assert "Job is not configured for upload source" in resp.json()["detail"]


def test_authenticated_user_can_upload_valid_video(upload_test_context) -> None:
    """Verify an authenticated user successfully uploads a valid video file."""
    client, session_factory = upload_test_context

    with session_factory() as db:
        user = User(id=uuid.uuid4(), provider="google", provider_user_id="uploader", email="uploader@example.com")
        job = Job(
            id=uuid.uuid4(),
            user_id=user.id,
            exercise=ExerciseType.SQUAT,
            source_type=SourceType.UPLOAD,
            status=JobStatus.QUEUED,
        )
        db.add_all([user, job])
        db.commit()
        job_id = job.id
        token = create_session_token(user.id)

    client.cookies.set(settings.SESSION_COOKIE_NAME, token)
    video_bytes = make_valid_mp4_bytes(num_frames=15, fps=15.0)
    files = {"file": ("workout.mp4", video_bytes, "video/mp4")}
    resp = client.post(f"/api/v1/jobs/{job_id}/video", files=files)
    assert resp.status_code == 200
    data = resp.json()
    assert data["job_id"] == str(job_id)
    assert data["status"] == "queued"

    # Verify database was updated
    with session_factory() as db:
        updated_job = db.execute(select(Job).where(Job.id == job_id)).scalar_one()
        assert updated_job.video_path is not None
        assert updated_job.status == JobStatus.QUEUED
        assert Path(updated_job.video_path).exists()


def test_already_uploaded_video_rejected(upload_test_context) -> None:
    """Verify that uploading twice to the same job is rejected with 400."""
    client, session_factory = upload_test_context

    with session_factory() as db:
        user = User(id=uuid.uuid4(), provider="google", provider_user_id="uploader2", email="uploader2@example.com")
        job = Job(
            id=uuid.uuid4(),
            user_id=user.id,
            exercise=ExerciseType.SQUAT,
            source_type=SourceType.UPLOAD,
            video_path="some/existing/path.mp4",
            status=JobStatus.QUEUED,
        )
        db.add_all([user, job])
        db.commit()
        job_id = job.id
        token = create_session_token(user.id)

    client.cookies.set(settings.SESSION_COOKIE_NAME, token)
    files = {"file": ("workout.mp4", make_valid_mp4_bytes(), "video/mp4")}
    resp = client.post(f"/api/v1/jobs/{job_id}/video", files=files)
    assert resp.status_code == 400
    assert "Video has already been uploaded" in resp.json()["detail"]


def test_invalid_corrupt_video_rejected(upload_test_context) -> None:
    """Verify that uploading a corrupt/non-video file is rejected."""
    client, session_factory = upload_test_context

    with session_factory() as db:
        user = User(id=uuid.uuid4(), provider="google", provider_user_id="uploader3", email="uploader3@example.com")
        job = Job(
            id=uuid.uuid4(),
            user_id=user.id,
            exercise=ExerciseType.SQUAT,
            source_type=SourceType.UPLOAD,
            status=JobStatus.QUEUED,
        )
        db.add_all([user, job])
        db.commit()
        job_id = job.id
        token = create_session_token(user.id)

    client.cookies.set(settings.SESSION_COOKIE_NAME, token)
    files = {"file": ("corrupt.mp4", b"NOT A VALID VIDEO FILE AT ALL", "video/mp4")}
    resp = client.post(f"/api/v1/jobs/{job_id}/video", files=files)
    assert resp.status_code == 400
    assert "recognized video header" in resp.json()["detail"]


def test_oversized_video_rejected(upload_test_context) -> None:
    """Verify that video exceeding MAX_VIDEO_SIZE_MB is rejected."""
    client, session_factory = upload_test_context

    with session_factory() as db:
        user = User(id=uuid.uuid4(), provider="google", provider_user_id="uploader4", email="uploader4@example.com")
        job = Job(
            id=uuid.uuid4(),
            user_id=user.id,
            exercise=ExerciseType.SQUAT,
            source_type=SourceType.UPLOAD,
            status=JobStatus.QUEUED,
        )
        db.add_all([user, job])
        db.commit()
        job_id = job.id
        token = create_session_token(user.id)

    client.cookies.set(settings.SESSION_COOKIE_NAME, token)
    # Temporarily set max limit to 0 MB to trigger size error immediately
    with patch.object(settings, "MAX_VIDEO_SIZE_MB", 0):
        files = {"file": ("huge.mp4", make_valid_mp4_bytes(), "video/mp4")}
        resp = client.post(f"/api/v1/jobs/{job_id}/video", files=files)
    assert resp.status_code == 400
    assert "exceeds maximum limit" in resp.json()["detail"]


def test_duration_exceeding_limit_rejected(upload_test_context) -> None:
    """Verify that video longer than MAX_VIDEO_DURATION_SECONDS is rejected."""
    client, session_factory = upload_test_context

    with session_factory() as db:
        user = User(id=uuid.uuid4(), provider="google", provider_user_id="uploader5", email="uploader5@example.com")
        job = Job(
            id=uuid.uuid4(),
            user_id=user.id,
            exercise=ExerciseType.SQUAT,
            source_type=SourceType.UPLOAD,
            status=JobStatus.QUEUED,
        )
        db.add_all([user, job])
        db.commit()
        job_id = job.id
        token = create_session_token(user.id)

    client.cookies.set(settings.SESSION_COOKIE_NAME, token)
    with patch("app.api.routes.jobs.validate_video_file") as mock_validate:
        from app.services.video import VideoValidationError
        mock_validate.side_effect = VideoValidationError("Video duration (65.2s) exceeds maximum allowed 60s")
        files = {"file": ("long.mp4", make_valid_mp4_bytes(), "video/mp4")}
        resp = client.post(f"/api/v1/jobs/{job_id}/video", files=files)
    assert resp.status_code == 400
    assert "exceeds maximum allowed 60s" in resp.json()["detail"]


def test_failed_upload_cleans_temporary_file(upload_test_context) -> None:
    """Verify that when validation fails, temporary files are removed."""
    client, session_factory = upload_test_context

    with session_factory() as db:
        user = User(id=uuid.uuid4(), provider="google", provider_user_id="uploader6", email="uploader6@example.com")
        job = Job(
            id=uuid.uuid4(),
            user_id=user.id,
            exercise=ExerciseType.SQUAT,
            source_type=SourceType.UPLOAD,
            status=JobStatus.QUEUED,
        )
        db.add_all([user, job])
        db.commit()
        job_id = job.id
        token = create_session_token(user.id)

    temp_dir = get_media_root() / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    initial_temp_files = set(temp_dir.glob(f"job_{job_id}_*"))

    client.cookies.set(settings.SESSION_COOKIE_NAME, token)
    files = {"file": ("bad.mp4", b"not a valid mp4 header string", "video/mp4")}
    resp = client.post(f"/api/v1/jobs/{job_id}/video", files=files)
    assert resp.status_code == 400

    # Ensure no lingering temp files for this job
    after_temp_files = set(temp_dir.glob(f"job_{job_id}_*"))
    assert after_temp_files == initial_temp_files
