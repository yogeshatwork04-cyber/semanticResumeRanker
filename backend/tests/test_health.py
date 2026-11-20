"""Health endpoint tests."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """Create test client fixture."""
    return TestClient(app)


def test_health_check_endpoint(client):
    """Test health check returns 200 and expected payload."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "ok"
    assert "models" in data
    assert data["models"]["embedding"] == "all-MiniLM-L6-v2"
    assert data["models"]["spacy"] == "en_core_web_sm"
    assert "weights" in data
    assert pytest.approx(sum(data["weights"].values())) == 1.0


def test_root_health_check_endpoint(client):
    """Test /health root alias returns 200."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

