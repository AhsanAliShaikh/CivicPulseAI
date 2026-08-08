from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from backend.core.database import Base

def utc_now():
    return datetime.now(timezone.utc)

class ComplaintStatusHistory(Base):
    __tablename__ = "complaint_status_histories"

    id = Column(Integer, primary_key=True, index=True)
    complaint_id = Column(Integer, ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False, index=True)
    
    old_status = Column(String(50), nullable=True)
    new_status = Column(String(50), nullable=False)
    changed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    note = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    complaint = relationship("Complaint", back_populates="status_history")
    changer = relationship("User")

    def __repr__(self):
        return f"<ComplaintStatusHistory id={self.id} complaint_id={self.complaint_id} {self.old_status}->{self.new_status}>"
