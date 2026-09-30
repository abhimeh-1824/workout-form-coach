from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_endpoint() -> None:
    """Verify GET / returns expected API message."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Workout Form Coach API"}


def test_api_v1_health_endpoint() -> None:
    """Verify GET /api/v1/health returns status ok."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

