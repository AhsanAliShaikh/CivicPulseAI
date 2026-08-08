"""
CivicPulse AI Domain Models Package
"""
from backend.core.database import Base
from backend.models.enums import UserRole, ComplaintStatus, ComplaintPriority, NotificationType
from backend.models.user import User
from backend.models.department import Department
from backend.models.complaint import Complaint
from backend.models.attachment import ComplaintAttachment
from backend.models.status_history import ComplaintStatusHistory
from backend.models.ai_analysis import AIAnalysis
from backend.models.notification import Notification

__all__ = [
    "Base",
    "UserRole",
    "ComplaintStatus",
    "ComplaintPriority",
    "NotificationType",
    "User",
    "Department",
    "Complaint",
    "ComplaintAttachment",
    "ComplaintStatusHistory",
    "AIAnalysis",
    "Notification",
]

