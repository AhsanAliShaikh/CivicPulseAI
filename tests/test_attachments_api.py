"""
CivicPulse AI — Phase 4 Complaint Attachment API Tests
Tests attachment registration, listing, metadata retrieval, validation,
complaint association enforcement, and embedding in complaint responses.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.main import app
from backend.core.database import Base, get_db
from backend.models.user import User
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
    user = User(name="Attachment User", email="attach.user@test.com", role=UserRole.CITIZEN.value)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="module")
def seed_complaint(db_session, seed_user):
    complaint = Complaint(
        user_id=seed_user.id,
        title="Pothole Damage Photo Attachment Test",
        description="Pothole on Main Street with attached damage photos.",
        status=ComplaintStatus.SUBMITTED.value,
    )
    db_session.add(complaint)
    db_session.commit()
    db_session.refresh(complaint)
    return complaint


@pytest.fixture(scope="module")
def second_complaint(db_session, seed_user):
    complaint = Complaint(
        user_id=seed_user.id,
        title="Unrelated Street Light Issue",
        description="Street light out on Second St.",
        status=ComplaintStatus.SUBMITTED.value,
    )
    db_session.add(complaint)
    db_session.commit()
    db_session.refresh(complaint)
    return complaint


# ---------------------------------------------------------------------------
# Phase 4 Attachment API Tests
# ---------------------------------------------------------------------------
def test_create_attachment_success(client, seed_complaint):
    """Register an attachment for a valid complaint."""
    payload = {
        "file_name": "pothole_photo_1.jpg",
        "file_url": "https://storage.civicpulse.ai/uploads/pothole_photo_1.jpg",
        "file_type": "image/jpeg",
        "file_size": 204800,
    }
    r = client.post(f"/api/v1/complaints/{seed_complaint.public_id}/attachments", json=payload)
    assert r.status_code == 201
    data = r.json()
    assert data["id"] is not None
    assert data["complaint_id"] == seed_complaint.id
    assert data["file_name"] == "pothole_photo_1.jpg"
    assert data["file_url"] == "https://storage.civicpulse.ai/uploads/pothole_photo_1.jpg"
    assert data["file_type"] == "image/jpeg"
    assert data["file_size"] == 204800
    assert "created_at" in data


def test_create_attachment_complaint_not_found(client):
    """POST attachment for non-existent complaint returns 404."""
    payload = {
        "file_name": "ghost.jpg",
        "file_url": "https://storage.civicpulse.ai/uploads/ghost.jpg",
        "file_type": "image/jpeg",
        "file_size": 1024,
    }
    r = client.post("/api/v1/complaints/00000000-0000-0000-0000-000000000000/attachments", json=payload)
    assert r.status_code == 404


def test_create_attachment_invalid_size(client, seed_complaint):
    """file_size <= 0 returns 422."""
    payload = {
        "file_name": "zero_byte.jpg",
        "file_url": "https://storage.civicpulse.ai/uploads/zero_byte.jpg",
        "file_type": "image/jpeg",
        "file_size": 0,
    }
    r = client.post(f"/api/v1/complaints/{seed_complaint.public_id}/attachments", json=payload)
    assert r.status_code == 422


def test_create_attachment_empty_filename(client, seed_complaint):
    """Empty or whitespace file_name returns 422."""
    payload = {
        "file_name": "   ",
        "file_url": "https://storage.civicpulse.ai/uploads/photo.jpg",
        "file_type": "image/jpeg",
        "file_size": 1024,
    }
    r = client.post(f"/api/v1/complaints/{seed_complaint.public_id}/attachments", json=payload)
    assert r.status_code == 422


def test_list_attachments_multiple(client, seed_complaint):
    """Add a second attachment and verify list endpoint returns all attachments for complaint."""
    payload2 = {
        "file_name": "pothole_photo_2.jpg",
        "file_url": "https://storage.civicpulse.ai/uploads/pothole_photo_2.jpg",
        "file_type": "image/jpeg",
        "file_size": 409600,
    }
    client.post(f"/api/v1/complaints/{seed_complaint.public_id}/attachments", json=payload2)

    r = client.get(f"/api/v1/complaints/{seed_complaint.public_id}/attachments")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 2
    filenames = [item["file_name"] for item in data]
    assert "pothole_photo_1.jpg" in filenames
    assert "pothole_photo_2.jpg" in filenames


def test_list_attachments_complaint_not_found(client):
    """GET list for non-existent complaint returns 404."""
    r = client.get("/api/v1/complaints/00000000-0000-0000-0000-000000000000/attachments")
    assert r.status_code == 404


def test_get_attachment_by_id_success(client, seed_complaint):
    """Retrieve metadata of a specific attachment by ID."""
    # List to find an attachment ID
    r_list = client.get(f"/api/v1/complaints/{seed_complaint.public_id}/attachments")
    attachment_id = r_list.json()[0]["id"]

    r = client.get(f"/api/v1/complaints/{seed_complaint.public_id}/attachments/{attachment_id}")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == attachment_id
    assert data["complaint_id"] == seed_complaint.id


def test_get_attachment_by_id_not_found(client, seed_complaint):
    """GET attachment with non-existent attachment_id returns 404."""
    r = client.get(f"/api/v1/complaints/{seed_complaint.public_id}/attachments/999999")
    assert r.status_code == 404


def test_get_attachment_wrong_complaint(client, seed_complaint, second_complaint):
    """Attempting to access complaint A's attachment via complaint B's public_id returns 404."""
    # Fetch an attachment ID belonging to seed_complaint
    r_list = client.get(f"/api/v1/complaints/{seed_complaint.public_id}/attachments")
    attachment_id = r_list.json()[0]["id"]

    # Request that attachment ID under second_complaint
    r = client.get(f"/api/v1/complaints/{second_complaint.public_id}/attachments/{attachment_id}")
    assert r.status_code == 404


def test_complaint_retrieval_includes_attachments(client, seed_complaint):
    """GET /api/v1/complaints/{public_id} includes nested attachments list."""
    r = client.get(f"/api/v1/complaints/{seed_complaint.public_id}")
    assert r.status_code == 200
    data = r.json()
    assert "attachments" in data
    assert len(data["attachments"]) >= 2
    assert data["attachments"][0]["file_name"] == "pothole_photo_1.jpg"
