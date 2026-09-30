from typing import Generator
import uuid

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.security import create_session_token
from app.db.base import Base, User
from app.db.session import get_db
from app.main import app


@pytest.fixture
def job_test_context() -> Generator[tuple[TestClient, sessionmaker], None, None]:
    """Provide TestClient with an isolated in-memory SQLite database for jobs tests."""
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


def test_unauthenticated_cannot_create_job(job_test_context) -> None:
    """Verify unauthenticated requests cannot create jobs."""
    client, _ = job_test_context
    response = client.post(
        "/api/v1/jobs",
        json={"exercise": "squat", "source_type": "upload"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_unauthenticated_cannot_list_or_get_jobs(job_test_context) -> None:
    """Verify unauthenticated requests cannot list or get jobs."""
    client, _ = job_test_context
    assert client.get("/api/v1/jobs").status_code == 401
    assert client.get(f"/api/v1/jobs/{uuid.uuid4()}").status_code == 401


def test_create_upload_job_success(job_test_context) -> None:
    """Verify authenticated user can create an upload job with default initial state."""
    client, session_factory = job_test_context

    with session_factory() as db:
        user = User(
            id=uuid.uuid4(),
            provider="google",
            provider_user_id="user-sub-upload",
            email="upload.user@example.com",
            name="Upload User",
        )
        db.add(user)
        db.commit()
        user_id = user.id

    client.cookies.set(settings.SESSION_COOKIE_NAME, create_session_token(user_id))
    response = client.post(
        "/api/v1/jobs",
        json={"exercise": "squat", "source_type": "upload"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "queued"
    assert data["exercise"] == "squat"
    assert data["source_type"] == "upload"
    assert data["source_url"] is None
    assert data["progress"] == 0
    assert data["attempts"] == 0
    assert "job_id" in data
    assert "created_at" in data


def test_create_youtube_job_success(job_test_context) -> None:
    """Verify authenticated user can create a youtube job with source_url."""
    client, session_factory = job_test_context

    with session_factory() as db:
        user = User(
            id=uuid.uuid4(),
            provider="google",
            provider_user_id="user-sub-yt",
            email="yt.user@example.com",
            name="YouTube User",
        )
        db.add(user)
        db.commit()
        user_id = user.id

    client.cookies.set(settings.SESSION_COOKIE_NAME, create_session_token(user_id))
    youtube_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    response = client.post(
        "/api/v1/jobs",
        json={
            "exercise": "pushup",
            "source_type": "youtube",
            "source_url": youtube_url,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "queued"
    assert data["exercise"] == "pushup"
    assert data["source_type"] == "youtube"
    assert data["source_url"] == youtube_url


def test_validation_errors(job_test_context) -> None:
    """Verify validation errors for invalid exercise, source_type, or source_url combinations."""
    client, session_factory = job_test_context

    with session_factory() as db:
        user = User(
            id=uuid.uuid4(),
            provider="google",
            provider_user_id="user-sub-val",
            email="validation.user@example.com",
            name="Validation User",
        )
        db.add(user)
        db.commit()
        user_id = user.id

    client.cookies.set(settings.SESSION_COOKIE_NAME, create_session_token(user_id))

    # Invalid exercise
    res_bad_ex = client.post(
        "/api/v1/jobs",
        json={"exercise": "bicep_curl", "source_type": "upload"},
    )
    assert res_bad_ex.status_code == 422

    # Invalid source_type
    res_bad_src = client.post(
        "/api/v1/jobs",
        json={"exercise": "squat", "source_type": "vimeo"},
    )
    assert res_bad_src.status_code == 422

    # YouTube source without source_url
    res_missing_url = client.post(
        "/api/v1/jobs",
        json={"exercise": "lunge", "source_type": "youtube"},
    )
    assert res_missing_url.status_code == 422

    # Upload source with source_url provided
    res_unexpected_url = client.post(
        "/api/v1/jobs",
        json={
            "exercise": "squat",
            "source_type": "upload",
            "source_url": "https://example.com/clip.mp4",
        },
    )
    assert res_unexpected_url.status_code == 422


def test_security_authorization_isolation(job_test_context) -> None:
    """Mandatory Security Test: Verify User B cannot access User A's job, returning HTTP 404."""
    client, session_factory = job_test_context

    # Create User A and User B
    with session_factory() as db:
        user_a = User(
            id=uuid.uuid4(),
            provider="google",
            provider_user_id="sub-athlete-a",
            email="athlete_a@domain.com",
            name="Athlete A",
        )
        user_b = User(
            id=uuid.uuid4(),
            provider="google",
            provider_user_id="sub-athlete-b",
            email="athlete_b@domain.com",
            name="Athlete B",
        )
        db.add_all([user_a, user_b])
        db.commit()
        user_a_id = user_a.id
        user_b_id = user_b.id

    token_a = create_session_token(user_a_id)
    token_b = create_session_token(user_b_id)

    # 1. User A creates Job A
    client.cookies.set(settings.SESSION_COOKIE_NAME, token_a)
    create_resp = client.post(
        "/api/v1/jobs",
        json={"exercise": "squat", "source_type": "upload"},
    )
    assert create_resp.status_code == 201
    job_a_id = create_resp.json()["job_id"]

    # 2. User A retrieves Job A -> 200 OK
    get_resp_a = client.get(f"/api/v1/jobs/{job_a_id}")
    assert get_resp_a.status_code == 200
    assert get_resp_a.json()["job_id"] == job_a_id

    # 3. User B requests Job A -> 404 NOT FOUND (never 403, zero metadata leaked)
    client.cookies.set(settings.SESSION_COOKIE_NAME, token_b)
    get_resp_b = client.get(f"/api/v1/jobs/{job_a_id}")
    assert get_resp_b.status_code == 404
    assert get_resp_b.json() == {"detail": "Job not found"}

    # 4. User B lists jobs -> returns empty list (no jobs of User A)
    list_b = client.get("/api/v1/jobs")
    assert list_b.status_code == 200
    assert list_b.json()["total"] == 0
    assert list_b.json()["items"] == []

    # 5. User B creates Job B
    create_b = client.post(
        "/api/v1/jobs",
        json={
            "exercise": "lunge",
            "source_type": "youtube",
            "source_url": "https://www.youtube.com/watch?v=123",
        },
    )
    assert create_b.status_code == 201
    job_b_id = create_b.json()["job_id"]

    # 6. Verify User B list contains ONLY Job B
    list_b_updated = client.get("/api/v1/jobs")
    assert list_b_updated.json()["total"] == 1
    assert list_b_updated.json()["items"][0]["job_id"] == job_b_id

    # 7. Switch back to User A -> list contains ONLY Job A
    client.cookies.set(settings.SESSION_COOKIE_NAME, token_a)
    list_a = client.get("/api/v1/jobs")
    assert list_a.json()["total"] == 1
    assert list_a.json()["items"][0]["job_id"] == job_a_id


def test_job_pagination(job_test_context) -> None:
    """Verify job list pagination and ordering (newest first)."""
    client, session_factory = job_test_context

    with session_factory() as db:
        user = User(
            id=uuid.uuid4(),
            provider="google",
            provider_user_id="user-sub-page",
            email="page.user@example.com",
            name="Page User",
        )
        db.add(user)
        db.commit()
        user_id = user.id

    client.cookies.set(settings.SESSION_COOKIE_NAME, create_session_token(user_id))

    # Create 3 jobs
    for exercise in ["squat", "pushup", "lunge"]:
        client.post(
            "/api/v1/jobs",
            json={"exercise": exercise, "source_type": "upload"},
        )

    # Page 1 (limit 2, offset 0)
    page_1 = client.get("/api/v1/jobs?limit=2&offset=0")
    assert page_1.status_code == 200
    p1_data = page_1.json()
    assert p1_data["total"] == 3
    assert len(p1_data["items"]) == 2
    assert p1_data["items"][0]["exercise"] == "lunge"  # Newest first

    # Page 2 (limit 2, offset 2)
    page_2 = client.get("/api/v1/jobs?limit=2&offset=2")
    assert page_2.status_code == 200
    p2_data = page_2.json()
    assert p2_data["total"] == 3
    assert len(p2_data["items"]) == 1
    assert p2_data["items"][0]["exercise"] == "squat"  # Oldest
