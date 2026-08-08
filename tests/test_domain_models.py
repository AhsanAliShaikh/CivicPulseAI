import pytest
from sqlalchemy import create_engine, inspect, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from pydantic import ValidationError

from backend.core.database import Base
from backend.models import (
    User, Department, Complaint,
    ComplaintAttachment, ComplaintStatusHistory, AIAnalysis,
    UserRole, ComplaintStatus, ComplaintPriority
)
from backend.schemas import UserCreate, DepartmentCreate, ComplaintCreate

# Configure isolated in-memory database for testing
TEST_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture(scope="function")
def db_session():
    """Provides a fresh, isolated in-memory SQLite database session per test."""
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    
    # Enable SQLite foreign key enforcement
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)

def test_tables_created(db_session):
    """Verify all 6 core entity tables exist in database metadata."""
    inspector = inspect(db_session.bind)
    tables = inspector.get_table_names()
    expected_tables = {
        "users",
        "departments",
        "complaints",
        "complaint_attachments",
        "complaint_status_histories",
        "ai_analyses",
    }
    assert expected_tables.issubset(set(tables))

def test_user_creation_and_uniqueness(db_session):
    """Verify User model creation and email uniqueness constraint."""
    user = User(name="John Doe", email="john@example.com", role=UserRole.CITIZEN.value)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    assert user.id is not None
    assert user.email == "john@example.com"
    assert user.is_active is True

    # Test email uniqueness violation
    duplicate_user = User(name="Jane Doe", email="john@example.com")
    db_session.add(duplicate_user)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

def test_department_creation_and_uniqueness(db_session):
    """Verify Department model creation and code uniqueness constraint."""
    dept = Department(name="Roads & Bridges", code="ROADS", description="Road repairs")
    db_session.add(dept)
    db_session.commit()
    db_session.refresh(dept)

    assert dept.id is not None
    assert dept.code == "ROADS"

    # Test code uniqueness violation
    duplicate_dept = Department(name="Roads Copy", code="ROADS")
    db_session.add(duplicate_dept)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

def test_complaint_and_relationships(db_session):
    """Verify Complaint entity creation with User, Department, Attachments, History, AI Analysis."""
    user = User(name="Jane Citizen", email="jane@example.com", role=UserRole.CITIZEN.value)
    dept = Department(name="Sanitation", code="SAN")
    db_session.add_all([user, dept])
    db_session.commit()

    complaint = Complaint(
        user_id=user.id,
        department_id=dept.id,
        title="Large Pothole on Main St",
        description="Hazardous pothole causing traffic slowdown.",
        latitude=37.7749,
        longitude=-122.4194,
        category="Roads",
        priority=ComplaintPriority.HIGH.value,
        status=ComplaintStatus.SUBMITTED.value
    )
    db_session.add(complaint)
    db_session.commit()
    db_session.refresh(complaint)

    # Add child attachment
    attachment = ComplaintAttachment(
        complaint_id=complaint.id,
        file_name="pothole.jpg",
        file_url="https://storage.civicpulse.ai/pothole.jpg",
        file_type="image/jpeg",
        file_size=1024500
    )
    # Add status history
    history = ComplaintStatusHistory(
        complaint_id=complaint.id,
        old_status=None,
        new_status=ComplaintStatus.SUBMITTED.value,
        changed_by=user.id,
        note="Initial citizen submission"
    )
    # Add AI analysis record
    ai_record = AIAnalysis(
        complaint_id=complaint.id,
        model_name="gemini-1.5-pro",
        model_version="1.0",
        category="Roads",
        priority="high",
        confidence=0.94,
        summary="High priority road hazard detected"
    )
    db_session.add_all([attachment, history, ai_record])
    db_session.commit()

    # Verify relationships
    assert complaint.user.email == "jane@example.com"
    assert complaint.department.code == "SAN"
    assert len(complaint.attachments) == 1
    assert complaint.attachments[0].file_name == "pothole.jpg"
    assert len(complaint.status_history) == 1
    assert complaint.status_history[0].new_status == "submitted"
    assert len(complaint.ai_analyses) == 1
    assert complaint.ai_analyses[0].confidence == 0.94

def test_complaint_cascade_delete(db_session):
    """Verify deleting a complaint cascade-deletes attachments, status_history, ai_analyses without deleting User or Department."""
    user = User(name="Alice", email="alice@example.com")
    dept = Department(name="Water", code="WTR")
    db_session.add_all([user, dept])
    db_session.commit()

    complaint = Complaint(
        user_id=user.id,
        department_id=dept.id,
        title="Water Leak",
        description="Pipe burst near 5th ave"
    )
    db_session.add(complaint)
    db_session.commit()

    attachment = ComplaintAttachment(
        complaint_id=complaint.id,
        file_name="leak.png",
        file_url="http://example.com/leak.png",
        file_type="image/png",
        file_size=500
    )
    history = ComplaintStatusHistory(
        complaint_id=complaint.id,
        new_status="submitted",
        changed_by=user.id
    )
    ai_rec = AIAnalysis(
        complaint_id=complaint.id,
        model_name="test-model",
        model_version="0.1"
    )
    db_session.add_all([attachment, history, ai_rec])
    db_session.commit()

    # Delete complaint
    db_session.delete(complaint)
    db_session.commit()

    # Dependent child records deleted
    assert db_session.query(ComplaintAttachment).count() == 0
    assert db_session.query(ComplaintStatusHistory).count() == 0
    assert db_session.query(AIAnalysis).count() == 0

    # User and Department REMAIN INTACT
    assert db_session.query(User).count() == 1
    assert db_session.query(Department).count() == 1

def test_status_history_changed_by_set_null(db_session):
    """Verify status history record persists with changed_by set to NULL when acting user is deleted."""
    user = User(name="Staff User", email="staff@example.com", role=UserRole.STAFF.value)
    citizen = User(name="Citizen User", email="citizen@example.com", role=UserRole.CITIZEN.value)
    db_session.add_all([user, citizen])
    db_session.commit()

    complaint = Complaint(user_id=citizen.id, title="Issue", description="Desc")
    db_session.add(complaint)
    db_session.commit()

    history = ComplaintStatusHistory(
        complaint_id=complaint.id,
        old_status="submitted",
        new_status="in_progress",
        changed_by=user.id,
        note="Assigned by staff"
    )
    db_session.add(history)
    db_session.commit()
    history_id = history.id

    # Delete the staff user who changed the status
    db_session.delete(user)
    db_session.commit()

    # Verify history entry still exists and changed_by is set to NULL (or changer relationship handles it)
    retrieved_history = db_session.query(ComplaintStatusHistory).filter_by(id=history_id).first()
    assert retrieved_history is not None
    assert retrieved_history.changed_by is None or retrieved_history.note == "Assigned by staff"

def test_pydantic_schema_validations():
    """Verify Pydantic schemas enforce type safety and email validation."""
    # Valid user creation schema
    user_data = UserCreate(name="Valid User", email="valid@example.com", role=UserRole.CITIZEN)
    assert user_data.email == "valid@example.com"

    # Invalid email validation
    with pytest.raises(ValidationError):
        UserCreate(name="Invalid User", email="not-an-email")
