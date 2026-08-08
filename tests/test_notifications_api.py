"""
CivicPulse AI — Phase 5 Notification & Event API Tests
Tests notification persistence across complaint lifecycle events (creation, status update,
department assignment, AI analysis), user notification retrieval, read status updates, and error handling.
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
from backend.models.enums import UserRole, ComplaintStatus, NotificationType

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
    user = User(name="Notification Test User", email="notif.user@test.com", role=UserRole.CITIZEN.value)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="module")
def seed_department(db_session):
    dept = Department(name="Traffic Management", code="TM_NOTIF", description="Traffic Dept")
    db_session.add(dept)
    db_session.commit()
    db_session.refresh(dept)
    return dept


# ---------------------------------------------------------------------------
# Phase 5 Notification Tests
# ---------------------------------------------------------------------------
def test_complaint_creation_generates_notification(client, seed_user):
    """Creating a complaint automatically triggers a COMPLAINT_CREATED notification."""
    r_comp = client.post("/api/v1/complaints", json={
        "user_id": seed_user.id,
        "title": "Broken Traffic Signal at 5th and Main",
        "description": "Traffic signal is completely dark causing near misses.",
    })
    assert r_comp.status_code == 201
    comp_data = r_comp.json()
    public_id = comp_data["public_id"]

    # Verify notification for user
    r_notif = client.get(f"/api/v1/notifications/user/{seed_user.id}")
    assert r_notif.status_code == 200
    notif_data = r_notif.json()
    assert notif_data["total"] >= 1
    assert notif_data["unread_count"] >= 1

    types = [item["notification_type"] for item in notif_data["items"]]
    assert NotificationType.COMPLAINT_CREATED.value in types



def test_lifecycle_events_generate_notifications(client, seed_user, seed_department):
    """Status change, department assignment, and AI analysis trigger event notifications."""
    # 1. Create complaint
    r_comp = client.post("/api/v1/complaints", json={
        "user_id": seed_user.id,
        "title": "Street Flooding Near Elm St",
        "description": "Clogged storm drain causing localized street flooding.",
    })
    assert r_comp.status_code == 201
    public_id = r_comp.json()["public_id"]

    # 2. Update status (Submitted -> Acknowledged)
    r_status = client.patch(f"/api/v1/complaints/{public_id}/status", json={
        "status": "acknowledged",
        "note": "Officer dispatched to inspect drain.",
    })
    assert r_status.status_code == 200

    # 3. Assign department
    r_dept = client.patch(f"/api/v1/complaints/{public_id}/department", json={
        "department_id": seed_department.id,
    })
    assert r_dept.status_code == 200

    # 4. Record AI analysis
    r_ai = client.post(f"/api/v1/complaints/{public_id}/ai-analysis", json={
        "model_name": "gemini-1.5-flash",
        "model_version": "1.0",
        "category": "Drainage",
        "priority": "high",
        "confidence": 0.92,
    })
    assert r_ai.status_code == 201

    # Verify complaint-level notifications endpoint
    r_comp_notifs = client.get(f"/api/v1/complaints/{public_id}/notifications")
    assert r_comp_notifs.status_code == 200
    comp_notifs = r_comp_notifs.json()
    assert len(comp_notifs) >= 4

    types = [n["notification_type"] for n in comp_notifs]
    assert NotificationType.COMPLAINT_CREATED.value in types
    assert NotificationType.STATUS_CHANGED.value in types
    assert NotificationType.DEPARTMENT_ASSIGNED.value in types
    assert NotificationType.AI_ANALYSIS_RECORDED.value in types


def test_mark_notification_read(client, seed_user):
    """Marking a single notification as read updates its state and user unread count."""
    r_list = client.get(f"/api/v1/notifications/user/{seed_user.id}")
    assert r_list.status_code == 200
    initial_unread = r_list.json()["unread_count"]
    notif_id = r_list.json()["items"][0]["id"]

    # Mark read
    r_read = client.patch(f"/api/v1/notifications/{notif_id}/read")
    assert r_read.status_code == 200
    assert r_read.json()["is_read"] is True

    # Check unread count decreased
    r_after = client.get(f"/api/v1/notifications/user/{seed_user.id}")
    assert r_after.json()["unread_count"] == initial_unread - 1


def test_filter_unread_notifications(client, seed_user):
    """unread_only=True query parameter returns only unread notifications."""
    r = client.get(f"/api/v1/notifications/user/{seed_user.id}?unread_only=true")
    assert r.status_code == 200
    data = r.json()
    for item in data["items"]:
        assert item["is_read"] is False


def test_mark_all_notifications_read(client, seed_user):
    """Marking all notifications read clears all unread notifications for the user."""
    r_action = client.post(f"/api/v1/notifications/user/{seed_user.id}/read-all")
    assert r_action.status_code == 200
    assert r_action.json()["updated"] >= 1

    r_check = client.get(f"/api/v1/notifications/user/{seed_user.id}")
    assert r_check.json()["unread_count"] == 0


def test_notification_user_not_found(client):
    """GET notifications for non-existent user returns 404."""
    r = client.get("/api/v1/notifications/user/999999")
    assert r.status_code == 404


def test_mark_notification_read_not_found(client):
    """PATCH read for non-existent notification returns 404."""
    r = client.patch("/api/v1/notifications/999999/read")
    assert r.status_code == 404


def test_mark_all_read_user_not_found(client):
    """POST read-all for non-existent user returns 404."""
    r = client.post("/api/v1/notifications/user/999999/read-all")
    assert r.status_code == 404
