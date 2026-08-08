import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.core.database import check_database_connection

client = TestClient(app)

def test_landing_page():
    """Verify landing page GET / renders successfully with HTTP 200 and correct title."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "CivicPulse" in response.text

def test_health_endpoint():
    """Verify top-level GET /health returns structured JSON status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["service"] == "CivicPulse AI"
    assert "version" in data
    assert "database" in data
    assert data["database"]["status"] == "connected"

def test_swagger_docs():
    """Verify OpenAPI documentation GET /docs is accessible."""
    response = client.get("/docs")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

def test_direct_db_check():
    """Verify check_database_connection helper function returns connected status."""
    result = check_database_connection()
    assert isinstance(result, dict)
    assert result["status"] == "connected"
