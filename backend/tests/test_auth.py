from typing import Generator
import uuid
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.security import create_oauth_state_token, create_session_token
from app.db.base import Base, User
from app.db.session import get_db
from app.main import app


@pytest.fixture
def auth_test_context() -> Generator[tuple[TestClient, sessionmaker], None, None]:
    """Provide TestClient with an isolated in-memory SQLite database for authentication tests."""
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


def test_unauthenticated_request_returns_401(auth_test_context) -> None:
    """Verify protected /api/v1/auth/me rejects requests without session cookie."""
    client, _ = auth_test_context
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_invalid_session_cookie_returns_401(auth_test_context) -> None:
    """Verify protected endpoint rejects invalid or tampered session token."""
    client, _ = auth_test_context
    client.cookies.set(settings.SESSION_COOKIE_NAME, "tampered.session.token")
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert "Invalid or expired session" in response.json()["detail"]


def test_authenticated_get_me_returns_profile(auth_test_context) -> None:
    """Verify authenticated user can retrieve profile details."""
    client, session_factory = auth_test_context

    with session_factory() as db:
        user = User(
            id=uuid.uuid4(),
            provider="google",
            provider_user_id="google-sub-1001",
            email="athlete.test@example.com",
            name="Workout Athlete",
        )
        db.add(user)
        db.commit()
        user_id = user.id

    session_token = create_session_token(user_id)
    client.cookies.set(settings.SESSION_COOKIE_NAME, session_token)
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(user_id)
    assert data["email"] == "athlete.test@example.com"
    assert data["name"] == "Workout Athlete"
    assert data["provider"] == "google"


def test_logout_clears_session_cookie(auth_test_context) -> None:
    """Verify POST /api/v1/auth/logout clears the session cookie."""
    client, _ = auth_test_context
    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 200
    assert response.json() == {"message": "Successfully logged out"}

    # Verify session cookie deletion in Set-Cookie header
    set_cookie_headers = response.headers.get_list("set-cookie")
    assert any("session=" in sc and ("Max-Age=0" in sc or "expires=" in sc.lower()) for sc in set_cookie_headers)


def test_login_returns_503_when_unconfigured(auth_test_context, monkeypatch) -> None:
    """Verify login endpoint fails gracefully when OAuth is not configured."""
    client, _ = auth_test_context
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "")

    response = client.get("/api/v1/auth/google/login", follow_redirects=False)
    assert response.status_code == 503
    assert "not configured" in response.json()["detail"]


def test_login_redirect_with_pkce_when_configured(auth_test_context, monkeypatch) -> None:
    """Verify login redirects to Google with Authorization Code and PKCE parameters."""
    client, _ = auth_test_context
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "mock-client-id-123")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "mock-client-secret-456")

    response = client.get("/api/v1/auth/google/login", follow_redirects=False)
    assert response.status_code == 302
    assert "oauth_state" in response.cookies

    target_url = response.headers["location"]
    parsed = urlparse(target_url)
    assert parsed.netloc == "accounts.google.com"
    query_params = parse_qs(parsed.query)

    assert query_params["client_id"] == ["mock-client-id-123"]
    assert query_params["response_type"] == ["code"]
    assert query_params["code_challenge_method"] == ["S256"]
    assert "code_challenge" in query_params
    assert "state" in query_params


def test_callback_rejects_missing_state_or_code(auth_test_context) -> None:
    """Verify callback rejects requests missing required OAuth parameters."""
    client, _ = auth_test_context
    response = client.get("/api/v1/auth/google/callback")
    assert response.status_code == 400
    assert "Missing" in response.json()["detail"]


def test_callback_rejects_invalid_state_cookie(auth_test_context) -> None:
    """Verify callback rejects requests with state mismatch."""
    client, _ = auth_test_context
    client.cookies.set("oauth_state", "tampered-state-cookie")
    response = client.get("/api/v1/auth/google/callback?code=test-code&state=mismatched-state")
    assert response.status_code == 400


def test_callback_successful_exchange_with_mocked_google(auth_test_context, monkeypatch) -> None:
    """Verify callback exchanges code, upserts user, sets session cookie, and redirects."""
    client, session_factory = auth_test_context
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "mock-client-id")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "mock-client-secret")

    test_state = "test-valid-state-abc"
    test_verifier = "test-pkce-verifier-xyz"
    state_cookie = create_oauth_state_token(test_state, test_verifier)

    async def mock_post(*args, **kwargs) -> MagicMock:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"access_token": "mock-access-token-123"}
        return mock_resp

    async def mock_get(*args, **kwargs) -> MagicMock:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "sub": "google-sub-2002",
            "email": "coach@example.com",
            "name": "Head Coach",
        }
        return mock_resp

    client.cookies.set("oauth_state", state_cookie)
    with patch("httpx.AsyncClient.post", new=mock_post), \
         patch("httpx.AsyncClient.get", new=mock_get):
        response = client.get(
            f"/api/v1/auth/google/callback?code=valid-code&state={test_state}",
            follow_redirects=False,
        )

    assert response.status_code == 302
    assert response.headers["location"] == settings.FRONTEND_URL
    assert settings.SESSION_COOKIE_NAME in response.cookies

    # Verify user was created in DB
    with session_factory() as db:
        user = db.query(User).filter(User.provider_user_id == "google-sub-2002").first()
        assert user is not None
        assert user.email == "coach@example.com"
        assert user.name == "Head Coach"
        assert user.provider == "google"
