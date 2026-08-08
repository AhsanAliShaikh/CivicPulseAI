import uuid
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from backend.core.database import Base
from backend.models.enums import ComplaintStatus, ComplaintPriority

def utc_now():
    return datetime.now(timezone.utc)

def generate_uuid():
    return str(uuid.uuid4())

class Complaint(Base):
    __tablename__ = "complaints"

    id = Column(Integer, primary_key=True, index=True)
    public_id = Column(String(36), unique=True, index=True, default=generate_uuid, nullable=False)
    
    # Foreign Keys (No cascade deletion of Users or Departments)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    department_id = Column(Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True)

    # Core Complaint Information
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)

    # Location Information
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    address = Column(String(512), nullable=True)

    # Categorization & Workflow
    category = Column(String(100), nullable=True)
    subcategory = Column(String(100), nullable=True)
    priority = Column(String(50), default=ComplaintPriority.MEDIUM.value, nullable=False)
    status = Column(String(50), default=ComplaintStatus.SUBMITTED.value, nullable=False)

    # Future AI Storage Fields
    ai_category = Column(String(100), nullable=True)
    ai_priority = Column(String(50), nullable=True)
    ai_confidence = Column(Float, nullable=True)
    ai_summary = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", back_populates="complaints")
    department = relationship("Department", back_populates="complaints")
    
    # Cascading deletions targeting dependent complaint records ONLY
    attachments = relationship(
        "ComplaintAttachment",
        back_populates="complaint",
        cascade="all, delete-orphan"
    )
    status_history = relationship(
        "ComplaintStatusHistory",
        back_populates="complaint",
        cascade="all, delete-orphan"
    )
    ai_analyses = relationship(
        "AIAnalysis",
        back_populates="complaint",
        cascade="all, delete-orphan"
    )
    notifications = relationship(
        "Notification",
        back_populates="complaint",
        cascade="all, delete-orphan"
    )


    def __repr__(self):
        return f"<Complaint id={self.id} public_id='{self.public_id}' title='{self.title[:20]}' status='{self.status}'>"
