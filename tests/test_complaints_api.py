"""
CivicPulse AI — Phase 2 Complaint API Tests
Tests complaint creation, retrieval, listing, filtering, pagination,
status transitions, history recording, department assignment,
and regression of Phase 0/1 tests.
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
from backend.models.enums import UserRole, ComplaintStatus

# ---------------------------------------------------------------------------
# Module-level shared state for complaint IDs set by creation tests
# ---------------------------------------------------------------------------
_shared: dict = {}

# ---------------------------------------------------------------------------
# Test database setup — isolated in-memory SQLite per test session
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
    """FastAPI test client backed by the isolated in-memory DB."""
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
# Seed fixtures — user and department that tests can reference
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def seed_user(db_session):
    user = User(name="Alice Citizen", email="alice.citizen@test.com", role=UserRole.CITIZEN.value)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="module")
def seed_department(db_session):
    dept = Department(name="Roads & Transport", code="RD_TEST", description="Test department")
    db_session.add(dept)
    db_session.commit()
    db_session.refresh(dept)
    return dept


# ---------------------------------------------------------------------------
# Phase 0 regression
# ---------------------------------------------------------------------------
def test_phase0_landing(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"CivicPulse" in r.content


def test_phase0_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "healthy"


def test_phase0_docs(client):
    r = client.get("/docs")
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# UI page routes
# ---------------------------------------------------------------------------
def test_report_page(client):
    r = client.get("/report")
    assert r.status_code == 200
    assert b"Report" in r.content


def test_track_page(client):
    r = client.get("/track")
    assert r.status_code == 200
    assert b"Track" in r.content


# ---------------------------------------------------------------------------
# Complaint creation
# ---------------------------------------------------------------------------
def test_create_complaint_success(client, seed_user, seed_department):
    """Full complaint creation with all optional fields."""
    r = client.post("/api/v1/complaints", json={
        "user_id": seed_user.id,
        "title": "Large Pothole on Main Street",
        "description": "Dangerous pothole approximately 30cm wide, causing vehicle damage.",
        "category": "Roads & Infrastructure",
        "subcategory": "Pothole",
        "address": "42 Main Street",
        "latitude": 40.7128,
        "longitude": -74.0060,
        "department_id": seed_department.id,
    })
    assert r.status_code == 201
    data = r.json()
    assert data["title"] == "Large Pothole on Main Street"
    assert data["status"] == ComplaintStatus.SUBMITTED.value
    assert data["public_id"] is not None
    assert len(data["public_id"]) == 36  # UUID
    assert data["user_id"] == seed_user.id
    assert len(data["status_history"]) == 1
    assert data["status_history"][0]["old_status"] is None
    assert data["status_history"][0]["new_status"] == "submitted"
    # Store public_id for later tests
    _shared["complaint_public_id"] = data["public_id"]
    _shared["complaint_id"] = data["id"]


def test_create_complaint_minimal(client, seed_user):
    """Complaint with only required fields."""
    r = client.post("/api/v1/complaints", json={
        "user_id": seed_user.id,
        "title": "Broken Street Light",
        "description": "Street light on Oak Avenue has been out for two weeks.",
    })
    assert r.status_code == 201
    data = r.json()
    assert data["category"] is None
    assert data["department"] is None
    assert data["status"] == "submitted"
    _shared["complaint2_public_id"] = data["public_id"]


def test_create_complaint_invalid_user(client):
    """Should return 400 when user_id does not exist."""
    r = client.post("/api/v1/complaints", json={
        "user_id": 999999,
        "title": "Ghost complaint title",
        "description": "This should fail because user does not exist.",
    })
    assert r.status_code == 400
    assert "999999" in r.json()["detail"]


def test_create_complaint_title_too_short(client, seed_user):
    """422 on title < 5 chars."""
    r = client.post("/api/v1/complaints", json={
        "user_id": seed_user.id,
        "title": "Pot",
        "description": "Short title should fail validation.",
    })
    assert r.status_code == 422


def test_create_complaint_description_too_short(client, seed_user):
    """422 on description < 10 chars."""
    r = client.post("/api/v1/complaints", json={
        "user_id": seed_user.id,
        "title": "Valid title here",
        "description": "Too short",
    })
    assert r.status_code == 422


def test_create_complaint_invalid_department(client, seed_user):
    """Should return 400 when department_id does not exist."""
    r = client.post("/api/v1/complaints", json={
        "user_id": seed_user.id,
        "title": "Another valid title",
        "description": "Department does not exist in this database.",
        "department_id": 888888,
    })
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Complaint retrieval
# ---------------------------------------------------------------------------
def test_get_complaint_by_public_id(client):
    """Retrieve an existing complaint by its public UUID."""
    r = client.get(f"/api/v1/complaints/{_shared['complaint_public_id']}")
    assert r.status_code == 200
    data = r.json()
    assert data["public_id"] == _shared["complaint_public_id"]
    assert data["title"] == "Large Pothole on Main Street"
    assert data["status"] == "submitted"
    assert isinstance(data["status_history"], list)
    assert isinstance(data["attachments"], list)
    assert isinstance(data["ai_analyses"], list)


def test_get_complaint_not_found(client):
    """Non-existent complaint must return 404."""
    r = client.get("/api/v1/complaints/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Complaint listing
# ---------------------------------------------------------------------------
def test_list_complaints_default(client):
    """Default listing returns paginated response."""
    r = client.get("/api/v1/complaints")
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "page_size" in data
    assert "pages" in data
    assert data["page"] == 1
    assert data["total"] >= 2


def test_list_complaints_filter_status(client):
    """Filter by status returns only matching records."""
    r = client.get("/api/v1/complaints?status=submitted")
    assert r.status_code == 200
    data = r.json()
    for item in data["items"]:
        assert item["status"] == "submitted"


def test_list_complaints_filter_category(client):
    """Filter by category."""
    r = client.get("/api/v1/complaints?category=Roads+%26+Infrastructure")
    assert r.status_code == 200
    data = r.json()
    for item in data["items"]:
        assert item["category"] == "Roads & Infrastructure"


def test_list_complaints_filter_user(client, seed_user):
    """Filter by user_id."""
    r = client.get(f"/api/v1/complaints?user_id={seed_user.id}")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 1
    for item in data["items"]:
        assert item["user_id"] == seed_user.id


def test_list_complaints_pagination(client):
    """Pagination: page_size=1 should return only 1 item with pages > 1."""
    r = client.get("/api/v1/complaints?page_size=1")
    assert r.status_code == 200
    data = r.json()
    assert len(data["items"]) == 1
    assert data["page_size"] == 1
    assert data["pages"] >= 2


def test_list_complaints_page2(client):
    """Page 2 should return different items than page 1."""
    r1 = client.get("/api/v1/complaints?page=1&page_size=1")
    r2 = client.get("/api/v1/complaints?page=2&page_size=1")
    assert r1.status_code == 200
    assert r2.status_code == 200
    items1 = r1.json()["items"]
    items2 = r2.json()["items"]
    if items1 and items2:
        assert items1[0]["public_id"] != items2[0]["public_id"]


# ---------------------------------------------------------------------------
# Status update
# ---------------------------------------------------------------------------
def test_status_update_valid_transition(client):
    """submitted → acknowledged is a valid transition."""
    r = client.patch(
        f"/api/v1/complaints/{_shared['complaint_public_id']}/status",
        json={"status": "acknowledged", "note": "Complaint reviewed and acknowledged."},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "acknowledged"
    # History should now have 2 records
    assert len(data["status_history"]) == 2
    last = sorted(data["status_history"], key=lambda x: x["created_at"])[-1]
    assert last["old_status"] == "submitted"
    assert last["new_status"] == "acknowledged"
    assert last["note"] == "Complaint reviewed and acknowledged."


def test_status_update_to_in_progress(client):
    """acknowledged → in_progress."""
    r = client.patch(
        f"/api/v1/complaints/{_shared['complaint_public_id']}/status",
        json={"status": "in_progress", "note": "Repair crew dispatched."},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "in_progress"


def test_status_update_to_resolved_sets_resolved_at(client):
    """Resolving a complaint sets resolved_at timestamp."""
    r = client.patch(
        f"/api/v1/complaints/{_shared['complaint_public_id']}/status",
        json={"status": "resolved", "note": "Pothole repaired."},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "resolved"
    assert data["resolved_at"] is not None


def test_status_update_reopen_clears_resolved_at(client):
    """Reopening a resolved complaint clears resolved_at."""
    r = client.patch(
        f"/api/v1/complaints/{_shared['complaint_public_id']}/status",
        json={"status": "reopened", "note": "Pothole returned after rain."},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "reopened"
    assert data["resolved_at"] is None


def test_status_update_invalid_transition(client):
    """reopened → submitted is not a valid transition — must return 400."""
    r = client.patch(
        f"/api/v1/complaints/{_shared['complaint_public_id']}/status",
        json={"status": "submitted"},
    )
    assert r.status_code == 400
    assert "not permitted" in r.json()["detail"]


def test_status_update_invalid_status_value(client):
    """Unknown status string must return 422."""
    r = client.patch(
        f"/api/v1/complaints/{_shared['complaint_public_id']}/status",
        json={"status": "flying"},
    )
    assert r.status_code == 422


def test_status_update_not_found(client):
    """Non-existent complaint returns 404."""
    r = client.patch(
        "/api/v1/complaints/00000000-0000-0000-0000-000000000000/status",
        json={"status": "acknowledged"},
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Status history preserved
# ---------------------------------------------------------------------------
def test_status_history_preserved_on_retrieval(client):
    """Full history is returned in retrieval, not just the latest."""
    r = client.get(f"/api/v1/complaints/{_shared['complaint_public_id']}")
    assert r.status_code == 200
    history = r.json()["status_history"]
    assert len(history) >= 4  # submitted, acknowledged, in_progress, resolved, reopened
    statuses = [h["new_status"] for h in history]
    assert "submitted" in statuses
    assert "acknowledged" in statuses
    assert "resolved" in statuses
    assert "reopened" in statuses


# ---------------------------------------------------------------------------
# Department assignment
# ---------------------------------------------------------------------------
def test_assign_department_success(client, seed_department):
    """Assign a department to the second complaint."""
    r = client.patch(
        f"/api/v1/complaints/{_shared['complaint2_public_id']}/department",
        json={"department_id": seed_department.id},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["department_id"] == seed_department.id
    assert data["department"]["code"] == "RD_TEST"


def test_assign_department_invalid(client):
    """Invalid department_id returns 400."""
    r = client.patch(
        f"/api/v1/complaints/{_shared['complaint2_public_id']}/department",
        json={"department_id": 777777},
    )
    assert r.status_code == 400


def test_assign_department_complaint_not_found(client, seed_department):
    """Non-existent complaint returns 404."""
    r = client.patch(
        "/api/v1/complaints/00000000-0000-0000-0000-000000000000/department",
        json={"department_id": seed_department.id},
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# System endpoint regression
# ---------------------------------------------------------------------------
def test_database_summary_endpoint(client):
    r = client.get("/api/v1/system/database-summary")
    assert r.status_code == 200
    data = r.json()
    assert "tables" in data
