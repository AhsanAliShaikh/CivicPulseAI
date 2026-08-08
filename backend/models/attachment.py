from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from backend.core.database import Base

def utc_now():
    return datetime.now(timezone.utc)

class ComplaintAttachment(Base):
    __tablename__ = "complaint_attachments"

    id = Column(Integer, primary_key=True, index=True)
    complaint_id = Column(Integer, ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False, index=True)
    
    file_name = Column(String(255), nullable=False)
    file_url = Column(String(1024), nullable=False)
    file_type = Column(String(100), nullable=False)
    file_size = Column(Integer, nullable=False)  # size in bytes
    
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationship
    complaint = relationship("Complaint", back_populates="attachments")

    def __repr__(self):
        return f"<ComplaintAttachment id={self.id} complaint_id={self.complaint_id} file_name='{self.file_name}'>"
