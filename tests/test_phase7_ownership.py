"""
CivicPulse AI — Phase 7 Complaint Ownership & Access Control API Tests
Tests complaint ownership assignment via JWT authentication, ownership authorization rules,
role-based permissions for department assignment & AI analysis, attachment ownership protection,
notification access restrictions, and preservation of unauthenticated public behavior.
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
# Test database setup — isolated in-memory SQLite per test module
# ---------------------------------------------------------------------------
TEST_DATABASE_URL = "sqlite:///:memory:"

_shared: dict = {}


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


@pytest.fixture(scope="module")
def seed_department(db_session):
    dept = Department(name="Public Safety", code="PS_P7", description="Public Safety Department")
    db_session.add(dept)
    db_session.commit()
    db_session.refresh(dept)
    return dept


@pytest.fixture(scope="module")
def user_tokens(client):
    """Register citizen1, citizen2, staff, and admin users, returning auth headers."""
    # 1. Citizen 1
    r1 = client.post("/api/v1/auth/register", json={
        "name": "Citizen One",
        "email": "citizen1.p7@test.com",
        "password": "Password123!",
        "role": UserRole.CITIZEN.value,
    })
    token1 = r1.json()["access_token"]
    user1_id = r1.json()["user"]["id"]

    # 2. Citizen 2
    r2 = client.post("/api/v1/auth/register", json={
        "name": "Citizen Two",
        "email": "citizen2.p7@test.com",
        "password": "Password123!",
        "role": UserRole.CITIZEN.value,
    })
    token2 = r2.json()["access_token"]
    user2_id = r2.json()["user"]["id"]

    # 3. Staff User
    r_staff = client.post("/api/v1/auth/register", json={
        "name": "Staff User",
        "email": "staff.p7@test.com",
        "password": "Password123!",
        "role": UserRole.STAFF.value,
    })
    token_staff = r_staff.json()["access_token"]

    # 4. Admin User
    r_admin = client.post("/api/v1/auth/register", json={
        "name": "Admin User",
        "email": "admin.p7@test.com",
        "password": "Password123!",
        "role": UserRole.ADMIN.value,
    })
    token_admin = r_admin.json()["access_token"]

    return {
        "c1": {"headers": {"Authorization": f"Bearer {token1}"}, "user_id": user1_id},
        "c2": {"headers": {"Authorization": f"Bearer {token2}"}, "user_id": user2_id},
        "staff": {"headers": {"Authorization": f"Bearer {token_staff}"}},
        "admin": {"headers": {"Authorization": f"Bearer {token_admin}"}},
    }


# ---------------------------------------------------------------------------
# Phase 7 Ownership & Authorization Tests
# ---------------------------------------------------------------------------

def test_authenticated_complaint_creation(client, user_tokens):
    """Authenticated user complaint creation sets user_id from token identity."""
    r = client.post(
        "/api/v1/complaints",
        json={
            "user_id": 99999,  # Attempting to spoof another user_id
            "title": "Citizen 1 Broken Bench in Park",
            "description": "Park bench broken at Central Park.",
        },
        headers=user_tokens["c1"]["headers"],
    )
    assert r.status_code == 201
    data = r.json()
    assert data["user_id"] == user_tokens["c1"]["user_id"]  # Overridden by authenticated user
    _shared["c1_complaint_public_id"] = data["public_id"]
    _shared["c1_complaint_id"] = data["id"]


def test_owner_can_access_own_complaint(client, user_tokens):
    """Complaint owner can retrieve their own complaint."""
    r = client.get(
        f"/api/v1/complaints/{_shared['c1_complaint_public_id']}",
        headers=user_tokens["c1"]["headers"],
    )
    assert r.status_code == 200
    assert r.json()["public_id"] == _shared["c1_complaint_public_id"]


def test_non_owner_cannot_access_protected_complaint_data(client, user_tokens):
    """Citizen 2 cannot access Citizen 1's complaint (403 Forbidden)."""
    r = client.get(
        f"/api/v1/complaints/{_shared['c1_complaint_public_id']}",
        headers=user_tokens["c2"]["headers"],
    )
    assert r.status_code == 403
    assert "lacks required permissions" in r.json()["detail"] or "Access forbidden" in r.json()["detail"]


def test_owner_cannot_modify_another_user_complaint(client, user_tokens):
    """Citizen 2 cannot update status on Citizen 1's complaint (403 Forbidden)."""
    r = client.patch(
        f"/api/v1/complaints/{_shared['c1_complaint_public_id']}/status",
        json={"status": "acknowledged", "note": "Unallowed edit attempt."},
        headers=user_tokens["c2"]["headers"],
    )
    assert r.status_code == 403


def test_authorized_staff_admin_status_update_works(client, user_tokens):
    """Staff/Admin can update status of any complaint."""
    r_staff = client.patch(
        f"/api/v1/complaints/{_shared['c1_complaint_public_id']}/status",
        json={"status": "acknowledged", "note": "Acknowledged by staff."},
        headers=user_tokens["staff"]["headers"],
    )
    assert r_staff.status_code == 200
    assert r_staff.json()["status"] == "acknowledged"


def test_unauthorized_department_assignment_rejected(client, user_tokens, seed_department):
    """Citizen cannot assign department to a complaint (403 Forbidden)."""
    r = client.patch(
        f"/api/v1/complaints/{_shared['c1_complaint_public_id']}/department",
        json={"department_id": seed_department.id},
        headers=user_tokens["c1"]["headers"],
    )
    assert r.status_code == 403


def test_authorized_department_assignment_works(client, user_tokens, seed_department):
    """Staff/Admin can assign department to a complaint."""
    r = client.patch(
        f"/api/v1/complaints/{_shared['c1_complaint_public_id']}/department",
        json={"department_id": seed_department.id},
        headers=user_tokens["admin"]["headers"],
    )
    assert r.status_code == 200
    assert r.json()["department_id"] == seed_department.id


def test_unauthorized_ai_analysis_recording_rejected(client, user_tokens):
    """Citizen cannot record AI analysis (403 Forbidden)."""
    r = client.post(
        f"/api/v1/complaints/{_shared['c1_complaint_public_id']}/ai-analysis",
        json={
            "model_name": "gemini-1.5-flash",
            "model_version": "1.0",
            "confidence": 0.88,
        },
        headers=user_tokens["c1"]["headers"],
    )
    assert r.status_code == 403


def test_authorized_ai_analysis_recording_works(client, user_tokens):
    """Staff/Admin can record AI analysis (201 Created)."""
    r = client.post(
        f"/api/v1/complaints/{_shared['c1_complaint_public_id']}/ai-analysis",
        json={
            "model_name": "gemini-1.5-flash",
            "model_version": "1.0",
            "category": "Parks",
            "priority": "medium",
            "confidence": 0.90,
            "summary": "Damaged park seating.",
        },
        headers=user_tokens["staff"]["headers"],
    )
    assert r.status_code == 201


def test_ai_analysis_history_access_rules(client, user_tokens):
    """Owner can access AI analysis history; non-owner citizen is rejected (403)."""
    # Owner access -> 200
    r_owner = client.get(
        f"/api/v1/complaints/{_shared['c1_complaint_public_id']}/ai-analysis",
        headers=user_tokens["c1"]["headers"],
    )
    assert r_owner.status_code == 200
    assert len(r_owner.json()) >= 1

    # Non-owner citizen access -> 403
    r_non_owner = client.get(
        f"/api/v1/complaints/{_shared['c1_complaint_public_id']}/ai-analysis",
        headers=user_tokens["c2"]["headers"],
    )
    assert r_non_owner.status_code == 403


def test_attachment_access_ownership_rules(client, user_tokens):
    """Attachment creation/retrieval follows complaint ownership rules."""
    # 1. Owner creates attachment -> 201
    r_create = client.post(
        f"/api/v1/complaints/{_shared['c1_complaint_public_id']}/attachments",
        json={
            "file_name": "bench.jpg",
            "file_url": "https://storage.civicpulse.ai/bench.jpg",
            "file_type": "image/jpeg",
            "file_size": 10240,
        },
        headers=user_tokens["c1"]["headers"],
    )
    assert r_create.status_code == 201
    att_id = r_create.json()["id"]

    # 2. Non-owner cannot create attachment -> 403
    r_create_non_owner = client.post(
        f"/api/v1/complaints/{_shared['c1_complaint_public_id']}/attachments",
        json={
            "file_name": "hacked.jpg",
            "file_url": "https://storage.civicpulse.ai/hacked.jpg",
            "file_type": "image/jpeg",
            "file_size": 10240,
        },
        headers=user_tokens["c2"]["headers"],
    )
    assert r_create_non_owner.status_code == 403

    # 3. Owner lists attachments -> 200
    r_list = client.get(
        f"/api/v1/complaints/{_shared['c1_complaint_public_id']}/attachments",
        headers=user_tokens["c1"]["headers"],
    )
    assert r_list.status_code == 200

    # 4. Non-owner lists attachments -> 403
    r_list_non_owner = client.get(
        f"/api/v1/complaints/{_shared['c1_complaint_public_id']}/attachments",
        headers=user_tokens["c2"]["headers"],
    )
    assert r_list_non_owner.status_code == 403

    # 5. Non-owner gets single attachment -> 403
    r_get_non_owner = client.get(
        f"/api/v1/complaints/{_shared['c1_complaint_public_id']}/attachments/{att_id}",
        headers=user_tokens["c2"]["headers"],
    )
    assert r_get_non_owner.status_code == 403


def test_notification_access_protection(client, user_tokens):
    """Citizens cannot access or mark read another user's notifications (403)."""
    user1_id = user_tokens["c1"]["user_id"]
    user2_id = user_tokens["c2"]["user_id"]

    # 1. Citizen 2 retrieving Citizen 1's notifications -> 403
    r_get_notif = client.get(
        f"/api/v1/notifications/user/{user1_id}",
        headers=user_tokens["c2"]["headers"],
    )
    assert r_get_notif.status_code == 403

    # 2. Citizen 1 retrieving own notifications -> 200
    r_own_notif = client.get(
        f"/api/v1/notifications/user/{user1_id}",
        headers=user_tokens["c1"]["headers"],
    )
    assert r_own_notif.status_code == 200
    notifs = r_own_notif.json()["items"]
    assert len(notifs) >= 1
    notif_id = notifs[0]["id"]

    # 3. Citizen 2 trying to mark Citizen 1's notification read -> 403
    r_read_other = client.patch(
        f"/api/v1/notifications/{notif_id}/read",
        headers=user_tokens["c2"]["headers"],
    )
    assert r_read_other.status_code == 403

    # 4. Citizen 2 trying to mark-all-read for Citizen 1 -> 403
    r_all_other = client.post(
        f"/api/v1/notifications/user/{user1_id}/read-all",
        headers=user_tokens["c2"]["headers"],
    )
    assert r_all_other.status_code == 403


def test_unauthenticated_public_behavior_intact(client):
    """Unauthenticated calls without token maintain public behavior for backward compatibility."""
    # 1. Unauthenticated complaint retrieval -> 200
    r_get = client.get(f"/api/v1/complaints/{_shared['c1_complaint_public_id']}")
    assert r_get.status_code == 200

    # 2. Unauthenticated complaint listing -> 200
    r_list = client.get("/api/v1/complaints")
    assert r_list.status_code == 200

