"""
CivicPulse AI — Phase 8 AI Triage Engine & Municipal Department API Tests
Tests department listing, detail retrieval, admin creation, RBAC authorization, duplicate checks,
unauthenticated access, local AI triage text classification across categories, determinism,
manual triage trigger endpoints, complaint AI field updates, and department auto-routing.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.main import app
from backend.core.database import Base, get_db
from backend.models.department import Department
from backend.models.enums import UserRole, ComplaintStatus
from backend.services import ai_triage_engine, complaint_service

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
def seed_departments_and_users(client, db_session):
    """Seed core municipal departments and register test users (citizen, staff, admin)."""
    # Seed core departments
    depts = [
        Department(name="Roads & Infrastructure", code="RD", description="Roads dept", is_active=True),
        Department(name="Water & Sewage Services", code="WTR", description="Water dept", is_active=True),
        Department(name="Street Lighting", code="STL", description="Lighting dept", is_active=True),
        Department(name="Sanitation & Waste", code="SAN", description="Sanitation dept", is_active=True),
        Department(name="Parks & Recreation", code="PRK", description="Parks dept", is_active=True),
        Department(name="Traffic Management", code="TRF", description="Traffic dept", is_active=True),
        Department(name="Electricity & Power", code="ELE", description="Power dept", is_active=True),
        Department(name="General Municipal Services", code="GEN", description="General dept", is_active=True),
    ]
    db_session.add_all(depts)
    db_session.commit()

    # Register users
    r_cit = client.post("/api/v1/auth/register", json={
        "name": "Phase8 Citizen",
        "email": "cit.p8@test.com",
        "password": "Password123!",
        "role": UserRole.CITIZEN.value,
    })
    token_cit = r_cit.json()["access_token"]
    user_cit_id = r_cit.json()["user"]["id"]

    r_staff = client.post("/api/v1/auth/register", json={
        "name": "Phase8 Staff",
        "email": "staff.p8@test.com",
        "password": "Password123!",
        "role": UserRole.STAFF.value,
    })
    token_staff = r_staff.json()["access_token"]

    r_admin = client.post("/api/v1/auth/register", json={
        "name": "Phase8 Admin",
        "email": "admin.p8@test.com",
        "password": "Password123!",
        "role": UserRole.ADMIN.value,
    })
    token_admin = r_admin.json()["access_token"]

    return {
        "cit": {"headers": {"Authorization": f"Bearer {token_cit}"}, "id": user_cit_id},
        "staff": {"headers": {"Authorization": f"Bearer {token_staff}"}},
        "admin": {"headers": {"Authorization": f"Bearer {token_admin}"}},
    }


# ---------------------------------------------------------------------------
# Department API Tests
# ---------------------------------------------------------------------------

def test_list_departments_public(client, seed_departments_and_users):
    """GET /api/v1/departments is public and lists active departments."""
    r = client.get("/api/v1/departments")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 8
    codes = [d["code"] for d in data]
    assert "RD" in codes
    assert "WTR" in codes


def test_get_department_by_id_success(client, seed_departments_and_users):
    """GET /api/v1/departments/{id} returns details of department."""
    r_list = client.get("/api/v1/departments")
    dept_id = r_list.json()[0]["id"]

    r = client.get(f"/api/v1/departments/{dept_id}")
    assert r.status_code == 200
    assert r.json()["id"] == dept_id


def test_get_department_by_id_not_found(client, seed_departments_and_users):
    """GET /api/v1/departments/999999 returns 404."""
    r = client.get("/api/v1/departments/999999")
    assert r.status_code == 404


def test_create_department_admin_success(client, seed_departments_and_users):
    """Admin can create a new department (201 Created)."""
    payload = {
        "name": "Health & Hygiene Services",
        "code": "HLT",
        "description": "Public health inspection and hygiene",
    }
    r = client.post("/api/v1/departments", json=payload, headers=seed_departments_and_users["admin"]["headers"])
    assert r.status_code == 201
    data = r.json()
    assert data["code"] == "HLT"
    assert data["is_active"] is True


def test_create_department_citizen_staff_forbidden(client, seed_departments_and_users):
    """Citizen and Staff cannot create department (403 Forbidden)."""
    payload = {"name": "Unauthorized Dept", "code": "UNAUTH"}

    # Citizen -> 403
    r_cit = client.post("/api/v1/departments", json=payload, headers=seed_departments_and_users["cit"]["headers"])
    assert r_cit.status_code == 403

    # Staff -> 403
    r_staff = client.post("/api/v1/departments", json=payload, headers=seed_departments_and_users["staff"]["headers"])
    assert r_staff.status_code == 403


def test_create_department_duplicate_code_fails(client, seed_departments_and_users):
    """Creating department with existing code returns 400 Bad Request."""
    payload = {"name": "Duplicate Roads", "code": "RD"}
    r = client.post("/api/v1/departments", json=payload, headers=seed_departments_and_users["admin"]["headers"])
    assert r.status_code == 400
    assert "already exists" in r.json()["detail"]


# ---------------------------------------------------------------------------
# Local AI Triage Engine Unit Tests
# ---------------------------------------------------------------------------

def test_triage_engine_classification_categories():
    """Triage engine accurately classifies text into categories and confidence range."""
    # Water leak
    res1 = ai_triage_engine.classify_text("Water pipe leak bursting on sidewalk")
    assert res1["code"] == "WTR"
    assert 0.0 <= res1["confidence"] <= 1.0

    # Pothole
    res2 = ai_triage_engine.classify_text("Large pothole on main street asphalt")
    assert res2["code"] == "RD"

    # Street Light
    res3 = ai_triage_engine.classify_text("Dark street lamp out on Oak Avenue")
    assert res3["code"] == "STL"

    # Garbage
    res4 = ai_triage_engine.classify_text("Overflowing trash and garbage bin")
    assert res4["code"] == "SAN"

    # Park
    res5 = ai_triage_engine.classify_text("Broken bench in central park")
    assert res5["code"] == "PRK"

    # Power
    res6 = ai_triage_engine.classify_text("Transformer outage causing power loss")
    assert res6["code"] == "ELE"

    # Traffic
    res7 = ai_triage_engine.classify_text("Traffic signal light stuck red")
    assert res7["code"] == "TRF"

    # General Fallback
    res8 = ai_triage_engine.classify_text("Random uncategorized inquiry")
    assert res8["code"] == "GEN"
    assert res8["confidence"] == 0.70


def test_triage_engine_determinism():
    """Executing triage on the same text produces identical deterministic results."""
    text = "Severe water pipe leak on Elm Street"
    res_a = ai_triage_engine.classify_text(text)
    res_b = ai_triage_engine.classify_text(text)
    assert res_a == res_b


# ---------------------------------------------------------------------------
# Manual Triage Route Tests
# ---------------------------------------------------------------------------

def test_trigger_triage_endpoint_staff_success(client, seed_departments_and_users):
    """Staff triggering triage on complaint returns 201 and auto-routes department."""
    # 1. Citizen creates complaint without department
    r_comp = client.post(
        "/api/v1/complaints",
        json={
            "user_id": seed_departments_and_users["cit"]["id"],
            "title": "Severe Water Pipe Leak",
            "description": "Water leaking rapidly into street from underground main pipe.",
        },
        headers=seed_departments_and_users["cit"]["headers"],
    )
    assert r_comp.status_code == 201
    public_id = r_comp.json()["public_id"]

    # 2. Staff triggers triage
    r_triage = client.post(
        f"/api/v1/complaints/{public_id}/triage",
        headers=seed_departments_and_users["staff"]["headers"],
    )
    assert r_triage.status_code == 201
    triage_data = r_triage.json()
    assert triage_data["model_name"] == "civicpulse-triage-v1"
    assert triage_data["confidence"] == 0.95

    # 3. Check updated complaint fields & auto-routing
    r_check = client.get(f"/api/v1/complaints/{public_id}", headers=seed_departments_and_users["staff"]["headers"])
    assert r_check.status_code == 200
    comp_data = r_check.json()
    assert comp_data["ai_category"] == "Water & Sewage Services"
    assert comp_data["ai_priority"] == "high"
    assert comp_data["ai_confidence"] == 0.95
    assert comp_data["department"] is not None
    assert comp_data["department"]["code"] == "WTR"


def test_trigger_triage_endpoint_citizen_forbidden(client, seed_departments_and_users):
    """Citizen triggering manual triage endpoint returns 403 Forbidden."""
    r_comp = client.post(
        "/api/v1/complaints",
        json={
            "user_id": seed_departments_and_users["cit"]["id"],
            "title": "Broken Park Swing",
            "description": "Swing set in park is damaged.",
        },
        headers=seed_departments_and_users["cit"]["headers"],
    )
    public_id = r_comp.json()["public_id"]

    r_triage = client.post(
        f"/api/v1/complaints/{public_id}/triage",
        headers=seed_departments_and_users["cit"]["headers"],
    )
    assert r_triage.status_code == 403


def test_trigger_triage_unauthenticated_unauthorized(client, seed_departments_and_users):
    """Unauthenticated call to triage endpoint returns 401 Unauthorized."""
    r_comp = client.post(
        "/api/v1/complaints",
        json={
            "user_id": seed_departments_and_users["cit"]["id"],
            "title": "Broken Street Lamp",
            "description": "Dark street lamp on main st.",
        },
        headers=seed_departments_and_users["cit"]["headers"],
    )
    public_id = r_comp.json()["public_id"]

    r_triage = client.post(f"/api/v1/complaints/{public_id}/triage")
    assert r_triage.status_code == 401


def test_trigger_triage_missing_complaint_not_found(client, seed_departments_and_users):
    """Triggering triage on non-existent complaint returns 404 Not Found."""
    r = client.post(
        "/api/v1/complaints/00000000-0000-0000-0000-000000000000/triage",
        headers=seed_departments_and_users["admin"]["headers"],
    )
    assert r.status_code == 404

