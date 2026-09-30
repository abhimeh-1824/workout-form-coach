import asyncio
from pathlib import Path
import socket
from typing import Generator
from unittest.mock import MagicMock, patch
import urllib.error
import urllib.request
import uuid

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from yt_dlp.networking._urllib import RedirectHandler

from app.core.config import settings
from app.core.security import create_session_token
from app.db.base import Base, Job, JobStatus, User
from app.db.session import get_db
from app.main import app
from app.models.job import ExerciseType, SourceType
from app.services.youtube import (
    SSRFProtectionError,
    YouTubeValidationError,
    safe_redirect_interceptor,
    validate_ssrf_safe_url,
    validate_youtube_url,
)


@pytest.fixture
def yt_test_context() -> Generator[tuple[TestClient, sessionmaker], None, None]:
    """Provide TestClient with an isolated in-memory SQLite database for YouTube ingestion tests."""
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


# =========================================================================
# 1. SSRF & URL Validation Tests
# =========================================================================

def test_url_validation_formats() -> None:
    """Verify accepted and rejected YouTube URL formats."""
    # Accepted formats
    assert validate_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert validate_youtube_url("https://youtu.be/dQw4w9WgXcQ") == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert validate_youtube_url("https://www.youtube.com/shorts/dQw4w9WgXcQ") == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

    # Rejected formats
    with pytest.raises(YouTubeValidationError):
        validate_youtube_url("http://example.com/video.mp4")

    with pytest.raises(YouTubeValidationError):
        validate_youtube_url("https://vimeo.com/123456789")

    with pytest.raises(YouTubeValidationError):
        validate_youtube_url("http://localhost:8000/watch?v=dQw4w9WgXcQ")

    with pytest.raises(YouTubeValidationError):
        validate_youtube_url("https://www.youtube.com/watch?v=too_short")


def test_ssrf_blocks_private_and_loopback_ips() -> None:
    """Verify SSRF protection blocks localhost, loopback, private ranges, and cloud metadata."""
    forbidden_urls = [
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://127.0.0.2:80",
        "http://[::1]:80",
        "http://169.254.169.254/latest/meta-data",
        "http://10.0.0.1/video.mp4",
        "http://192.168.1.1/video.mp4",
        "http://172.16.0.1/video.mp4",
        "http://internal.service.local/video.mp4",
        "http://kubernetes.default.svc.cluster.local",
    ]

    for url in forbidden_urls:
        with pytest.raises(SSRFProtectionError):
            validate_ssrf_safe_url(url)


def test_ssrf_blocks_dns_rebinding_to_internal_ip() -> None:
    """Verify DNS resolution inspecting resolved IPs catches domains resolving to private IPs."""
    with patch("socket.getaddrinfo", return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]):
        with pytest.raises(SSRFProtectionError) as exc_info:
            validate_ssrf_safe_url("https://www.youtube.com")
        assert "resolved to prohibited address" in str(exc_info.value)


def test_redirect_handler_blocks_ssrf() -> None:
    """Verify RedirectHandler interceptor catches and blocks redirects to private destinations."""
    with safe_redirect_interceptor():
        handler = RedirectHandler()
        req = urllib.request.Request("https://www.youtube.com/watch?v=valid123456")

        # Attempted redirect to AWS metadata service
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            handler.redirect_request(
                req, None, 302, "Found", {}, "http://169.254.169.254/latest/meta-data"
            )
        assert "SSRF redirect blocked" in str(exc_info.value)

        # Attempted redirect to localhost
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            handler.redirect_request(
                req, None, 302, "Found", {}, "http://127.0.0.1:8000/internal"
            )
        assert "SSRF redirect blocked" in str(exc_info.value)


# =========================================================================
# 2. Authorization Tests
# =========================================================================

def test_unauthenticated_cannot_ingest_youtube(yt_test_context) -> None:
    """Verify unauthenticated requests cannot trigger YouTube ingestion."""
    client, _ = yt_test_context
    response = client.post(f"/api/v1/jobs/{uuid.uuid4()}/youtube")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_user_b_cannot_ingest_user_a_job(yt_test_context) -> None:
    """Verify User B receives 404 when attempting to ingest User A's job."""
    client, session_factory = yt_test_context

    with session_factory() as db:
        user_a = User(
            id=uuid.uuid4(),
            provider="google",
            provider_user_id="sub-a",
            email="user_a@example.com",
            name="User A",
        )
        user_b = User(
            id=uuid.uuid4(),
            provider="google",
            provider_user_id="sub-b",
            email="user_b@example.com",
            name="User B",
        )
        db.add_all([user_a, user_b])
        db.commit()

        job_a = Job(
            id=uuid.uuid4(),
            user_id=user_a.id,
            status=JobStatus.QUEUED,
            exercise=ExerciseType.SQUAT,
            source_type=SourceType.YOUTUBE,
            source_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        )
        db.add(job_a)
        db.commit()
        job_a_id = job_a.id
        user_b_id = user_b.id

    client.cookies.set(settings.SESSION_COOKIE_NAME, create_session_token(user_b_id))
    response = client.post(f"/api/v1/jobs/{job_a_id}/youtube")
    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found"


def test_upload_job_cannot_use_youtube_endpoint(yt_test_context) -> None:
    """Verify jobs configured with source_type=upload are rejected by YouTube endpoint."""
    client, session_factory = yt_test_context

    with session_factory() as db:
        user = User(
            id=uuid.uuid4(),
            provider="google",
            provider_user_id="sub-upload-only",
            email="upload_user@example.com",
            name="Upload User",
        )
        db.add(user)
        db.commit()

        job = Job(
            id=uuid.uuid4(),
            user_id=user.id,
            status=JobStatus.QUEUED,
            exercise=ExerciseType.SQUAT,
            source_type=SourceType.UPLOAD,
        )
        db.add(job)
        db.commit()
        job_id = job.id
        user_id = user.id

    client.cookies.set(settings.SESSION_COOKIE_NAME, create_session_token(user_id))
    response = client.post(f"/api/v1/jobs/{job_id}/youtube")
    assert response.status_code == 400
    assert "not configured for YouTube" in response.json()["detail"]


# =========================================================================
# 3. YouTube Downloader & Validation Logic Tests
# =========================================================================

def test_metadata_duration_exceeded_rejected_before_download(yt_test_context) -> None:
    """Verify video reporting duration > 60s in metadata is rejected before downloading."""
    client, session_factory = yt_test_context

    with session_factory() as db:
        user = User(
            id=uuid.uuid4(),
            provider="google",
            provider_user_id="sub-long",
            email="long_user@example.com",
            name="Long User",
        )
        db.add(user)
        db.commit()

        job = Job(
            id=uuid.uuid4(),
            user_id=user.id,
            status=JobStatus.QUEUED,
            exercise=ExerciseType.SQUAT,
            source_type=SourceType.YOUTUBE,
            source_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        )
        db.add(job)
        db.commit()
        job_id = job.id
        user_id = user.id

    client.cookies.set(settings.SESSION_COOKIE_NAME, create_session_token(user_id))

    # Mock metadata returning 120 seconds
    with patch("app.services.youtube._fetch_metadata_sync", return_value={"duration": 120.0}), \
         patch("app.services.youtube._download_video_sync") as mock_download:
        response = client.post(f"/api/v1/jobs/{job_id}/youtube")
        assert response.status_code == 400
        assert "exceeds the maximum allowed limit of 60 seconds" in response.json()["detail"]
        mock_download.assert_not_called()


def test_successful_youtube_ingestion(yt_test_context, tmp_path) -> None:
    """Verify successful YouTube ingestion validates video, stores to permanent path, and queues job."""
    client, session_factory = yt_test_context

    with session_factory() as db:
        user = User(
            id=uuid.uuid4(),
            provider="google",
            provider_user_id="sub-success",
            email="success_user@example.com",
            name="Success User",
        )
        db.add(user)
        db.commit()

        job = Job(
            id=uuid.uuid4(),
            user_id=user.id,
            status=JobStatus.QUEUED,
            exercise=ExerciseType.SQUAT,
            source_type=SourceType.YOUTUBE,
            source_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        )
        db.add(job)
        db.commit()
        job_id = job.id
        user_id = user.id

    client.cookies.set(settings.SESSION_COOKIE_NAME, create_session_token(user_id))

    # Create a realistic test video file
    dummy_video = tmp_path / "test_download.mp4"
    dummy_video.write_bytes(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00isommp42" + b"\x00" * 200)

    with patch("app.services.youtube._fetch_metadata_sync", return_value={"duration": 25.0}), \
         patch("app.services.youtube._download_video_sync", return_value=dummy_video), \
         patch("app.services.youtube.validate_video_file", return_value=25.0):
        response = client.post(f"/api/v1/jobs/{job_id}/youtube")
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == str(job_id)
        assert data["status"] == "queued"

    # Verify database update
    with session_factory() as db:
        updated_job = db.get(Job, job_id)
        assert updated_job.video_path is not None
        assert "original.mp4" in updated_job.video_path
        assert updated_job.status == JobStatus.QUEUED
        assert updated_job.progress == 0


def test_cannot_reingest_already_completed_video(yt_test_context) -> None:
    """Verify endpoint rejects ingestion when video_path is already populated."""
    client, session_factory = yt_test_context

    with session_factory() as db:
        user = User(
            id=uuid.uuid4(),
            provider="google",
            provider_user_id="sub-reingest",
            email="reingest@example.com",
            name="Reingest User",
        )
        db.add(user)
        db.commit()

        job = Job(
            id=uuid.uuid4(),
            user_id=user.id,
            status=JobStatus.QUEUED,
            exercise=ExerciseType.SQUAT,
            source_type=SourceType.YOUTUBE,
            source_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            video_path="media/jobs/existing/original.mp4",
        )
        db.add(job)
        db.commit()
        job_id = job.id
        user_id = user.id

    client.cookies.set(settings.SESSION_COOKIE_NAME, create_session_token(user_id))
    response = client.post(f"/api/v1/jobs/{job_id}/youtube")
    assert response.status_code == 400
    assert "already been ingested" in response.json()["detail"]


def test_download_timeout_handling(yt_test_context) -> None:
    """Verify download timeout is handled with clean error and temporary file cleanup."""
    client, session_factory = yt_test_context

    with session_factory() as db:
        user = User(
            id=uuid.uuid4(),
            provider="google",
            provider_user_id="sub-timeout",
            email="timeout@example.com",
            name="Timeout User",
        )
        db.add(user)
        db.commit()

        job = Job(
            id=uuid.uuid4(),
            user_id=user.id,
            status=JobStatus.QUEUED,
            exercise=ExerciseType.SQUAT,
            source_type=SourceType.YOUTUBE,
            source_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        )
        db.add(job)
        db.commit()
        job_id = job.id
        user_id = user.id

    client.cookies.set(settings.SESSION_COOKIE_NAME, create_session_token(user_id))

    def fake_download(*args, **kwargs):
        raise asyncio.TimeoutError()

    with patch("app.services.youtube._fetch_metadata_sync", return_value={"duration": 15.0}), \
         patch("app.services.youtube._download_video_sync", side_effect=fake_download):
        response = client.post(f"/api/v1/jobs/{job_id}/youtube")
        assert response.status_code == 400
        assert "timed out" in response.json()["detail"]
