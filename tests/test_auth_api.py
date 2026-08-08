"""
CivicPulse AI — Phase 6 Authentication & Authorization API Tests
Tests user registration, duplicate registration checks, login, credential verification,
JWT access token validation, authenticated user retrieval, role authorization, and security boundaries.
"""
import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.main import app
from backend.core.database import Base, get_db
from backend.core.deps import get_current_user, require_roles
from backend.models.user import User
from backend.models.enums import UserRole

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
# Dummy Protected Route for Testing Role-based Access Control (RBAC)
# ---------------------------------------------------------------------------
@app.get("/test/admin-only", tags=["Test"])
def admin_only_endpoint(user: User = Depends(require_roles(UserRole.ADMIN.value))):
    return {"message": f"Hello Admin {user.name}"}


# ---------------------------------------------------------------------------
# Phase 6 Authentication & Authorization Tests
# ---------------------------------------------------------------------------
def test_successful_registration(client):
    """Register a new user account, receiving JWT token and user profile without password hash."""
    r = client.post("/api/v1/auth/register", json={
        "name": "Auth Test Citizen",
        "email": "citizen.auth@test.com",
        "password": "SecurePassword123!",
        "role": "citizen",
    })
    assert r.status_code == 201
    data = r.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert "user" in data
    user_data = data["user"]
    assert user_data["email"] == "citizen.auth@test.com"
    assert user_data["role"] == "citizen"
    assert "password_hash" not in user_data
    assert "password" not in user_data


def test_duplicate_registration_fails(client):
    """Attempting to register with an already registered email returns 400 Bad Request."""
    r = client.post("/api/v1/auth/register", json={
        "name": "Duplicate User",
        "email": "citizen.auth@test.com",
        "password": "AnotherPassword123!",
    })
    assert r.status_code == 400
    assert "already exists" in r.json()["detail"]


def test_invalid_registration_password(client):
    """Registration with password < 6 characters returns 422 validation error."""
    r = client.post("/api/v1/auth/register", json={
        "name": "Short Password User",
        "email": "short.pw@test.com",
        "password": "123",
    })
    assert r.status_code == 422


def test_successful_login(client):
    """Login with valid email and password returns JWT access token."""
    r = client.post("/api/v1/auth/login", json={
        "email": "citizen.auth@test.com",
        "password": "SecurePassword123!",
    })
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "citizen.auth@test.com"


def test_login_invalid_password(client):
    """Login with correct email but wrong password returns 401 Unauthorized."""
    r = client.post("/api/v1/auth/login", json={
        "email": "citizen.auth@test.com",
        "password": "WrongPassword!",
    })
    assert r.status_code == 401
    assert "Incorrect email or password" in r.json()["detail"]


def test_login_non_existent_email(client):
    """Login with non-existent email returns 401 Unauthorized."""
    r = client.post("/api/v1/auth/login", json={
        "email": "ghost.user@test.com",
        "password": "SomePassword123!",
    })
    assert r.status_code == 401


def test_get_me_authenticated(client):
    """Accessing /api/v1/auth/me with valid Bearer token returns current user profile."""
    # Login to get token
    r_login = client.post("/api/v1/auth/login", json={
        "email": "citizen.auth@test.com",
        "password": "SecurePassword123!",
    })
    token = r_login.json()["access_token"]

    r_me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r_me.status_code == 200
    me_data = r_me.json()
    assert me_data["email"] == "citizen.auth@test.com"
    assert me_data["role"] == "citizen"
    assert "password_hash" not in me_data


def test_get_me_missing_token(client):
    """Accessing /api/v1/auth/me without Authorization header returns 401 Unauthorized."""
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401


def test_get_me_invalid_token(client):
    """Accessing /api/v1/auth/me with bogus token returns 401 Unauthorized."""
    r = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer bogus.invalid.token"})
    assert r.status_code == 401


def test_role_authorization_enforcement(client):
    """Role check allows Admin user and rejects Citizen user with 403 Forbidden."""
    # 1. Register Admin user
    r_admin_reg = client.post("/api/v1/auth/register", json={
        "name": "Auth Admin User",
        "email": "admin.auth@test.com",
        "password": "AdminPassword123!",
        "role": "admin",
    })
    assert r_admin_reg.status_code == 201
    admin_token = r_admin_reg.json()["access_token"]

    # 2. Login Citizen user
    r_cit_login = client.post("/api/v1/auth/login", json={
        "email": "citizen.auth@test.com",
        "password": "SecurePassword123!",
    })
    citizen_token = r_cit_login.json()["access_token"]

    # 3. Citizen accessing admin endpoint -> 403 Forbidden
    r_cit_access = client.get("/test/admin-only", headers={"Authorization": f"Bearer {citizen_token}"})
    assert r_cit_access.status_code == 403
    assert "lacks required permissions" in r_cit_access.json()["detail"]

    # 4. Admin accessing admin endpoint -> 200 OK
    r_admin_access = client.get("/test/admin-only", headers={"Authorization": f"Bearer {admin_token}"})
    assert r_admin_access.status_code == 200
    assert "Hello Admin Auth Admin User" in r_admin_access.json()["message"]


def test_password_hash_not_exposed(client):
    """Verify password_hash is not present in UserRead response schemas anywhere."""
    r = client.post("/api/v1/auth/login", json={
        "email": "citizen.auth@test.com",
        "password": "SecurePassword123!",
    })
    user_dict = r.json()["user"]
    assert "password_hash" not in user_dict
    assert "password" not in user_dict
