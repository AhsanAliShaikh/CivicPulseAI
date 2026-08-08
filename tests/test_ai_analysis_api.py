"""
CivicPulse AI — Phase 3 AI Analysis API Tests
Tests recording AI triage results, retrieving analysis history,
complaint AI metadata updates, department auto-routing, and error handling.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.main import app
from backend.core.database import Base, get_db
from backend.models.user import User
from backend.models.department import Department
from backend.models.complaint import Complaint
from backend.models.enums import UserRole, ComplaintStatus

# ---------------------------------------------------------------------------
# Test database setup — isolated in-memory SQLite per test module
# ---------------------------------------------------------------------------
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="module")
def test_engine():
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def set_fk_pragma(dbapi_connection, _):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    import backend.models  # noqa: register all models
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="module")
def db_session(test_engine):
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestingSession()
    yield session
    session.close()


@pytest.fixture(scope="module")
def client(test_engine):
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Seed fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def seed_user(db_session):
    user = User(name="AI Test User", email="ai.user@test.com", role=UserRole.CITIZEN.value)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="module")
def seed_department(db_session):
    dept = Department(name="Public Works", code="PW_AI_TEST", description="Public Works Dept")
    db_session.add(dept)
    db_session.commit()
    db_session.refresh(dept)
    return dept


@pytest.fixture(scope="module")
def seed_complaint(db_session, seed_user):
    complaint = Complaint(
        user_id=seed_user.id,
        title="Water Pipe Leak on Elm Street",
        description="Major water pipe leakage flooding the sidewalk.",
        status=ComplaintStatus.SUBMITTED.value,
    )
    db_session.add(complaint)
    db_session.commit()
    db_session.refresh(complaint)
    return complaint


# ---------------------------------------------------------------------------
# Phase 3 Tests
# ---------------------------------------------------------------------------
def test_record_ai_analysis_success(client, seed_complaint, seed_department):
    """Recording AI analysis updates the analysis table and complaint metadata."""
    payload = {
        "model_name": "gemini-1.5-pro",
        "model_version": "1.0",
        "category": "Water & Sanitation",
        "priority": "high",
        "confidence": 0.95,
        "summary": "Critical water infrastructure failure.",
        "reasoning": "High water flow observed near main pipeline.",
        "suggested_department_id": seed_department.id,
    }
    r = client.post(f"/api/v1/complaints/{seed_complaint.public_id}/ai-analysis", json=payload)
    assert r.status_code == 201
    data = r.json()
    assert data["model_name"] == "gemini-1.5-pro"
    assert data["category"] == "Water & Sanitation"
    assert data["confidence"] == 0.95

    # Check updated complaint
    r_comp = client.get(f"/api/v1/complaints/{seed_complaint.public_id}")
    assert r_comp.status_code == 200
    comp_data = r_comp.json()
    assert comp_data["ai_category"] == "Water & Sanitation"
    assert comp_data["ai_priority"] == "high"
    assert comp_data["ai_confidence"] == 0.95
    assert comp_data["ai_summary"] == "Critical water infrastructure failure."
    # Department auto-routing check
    assert comp_data["department_id"] == seed_department.id


def test_get_ai_analyses_list(client, seed_complaint):
    """GET endpoint returns recorded AI analyses for a complaint."""
    r = client.get(f"/api/v1/complaints/{seed_complaint.public_id}/ai-analysis")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["model_name"] == "gemini-1.5-pro"


def test_record_ai_analysis_invalid_confidence(client, seed_complaint):
    """Confidence outside [0, 1] range returns 422."""
    payload = {
        "model_name": "gemini-1.5-pro",
        "model_version": "1.0",
        "confidence": 1.5,
    }
    r = client.post(f"/api/v1/complaints/{seed_complaint.public_id}/ai-analysis", json=payload)
    assert r.status_code == 422


def test_record_ai_analysis_empty_model_name(client, seed_complaint):
    """Empty model_name returns 422."""
    payload = {
        "model_name": "   ",
        "model_version": "1.0",
    }
    r = client.post(f"/api/v1/complaints/{seed_complaint.public_id}/ai-analysis", json=payload)
    assert r.status_code == 422


def test_record_ai_analysis_complaint_not_found(client):
    """Non-existent complaint returns 404."""
    payload = {
        "model_name": "gemini-1.5-pro",
        "model_version": "1.0",
    }
    r = client.post("/api/v1/complaints/00000000-0000-0000-0000-000000000000/ai-analysis", json=payload)
    assert r.status_code == 404


def test_get_ai_analyses_complaint_not_found(client):
    """GET for non-existent complaint returns 404."""
    r = client.get("/api/v1/complaints/00000000-0000-0000-0000-000000000000/ai-analysis")
    assert r.status_code == 404
