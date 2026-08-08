from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from backend.core.database import Base
from backend.models.enums import UserRole

def utc_now():
    return datetime.now(timezone.utc)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    role = Column(String(50), default=UserRole.CITIZEN.value, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    password_hash = Column(String(255), nullable=True)

    
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    complaints = relationship("Complaint", back_populates="user")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")


    def __repr__(self):
        return f"<User id={self.id} email='{self.email}' role='{self.role}'>"
