from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from backend.core.database import Base

def utc_now():
    return datetime.now(timezone.utc)

class AIAnalysis(Base):
    __tablename__ = "ai_analyses"

    id = Column(Integer, primary_key=True, index=True)
    complaint_id = Column(Integer, ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False, index=True)
    
    model_name = Column(String(100), nullable=False)
    model_version = Column(String(50), nullable=False)
    
    category = Column(String(100), nullable=True)
    priority = Column(String(50), nullable=True)
    confidence = Column(Float, nullable=True)
    summary = Column(Text, nullable=True)
    reasoning = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationship
    complaint = relationship("Complaint", back_populates="ai_analyses")

    def __repr__(self):
        return f"<AIAnalysis id={self.id} complaint_id={self.complaint_id} model='{self.model_name}'>"
