"""
CivicPulse AI Data Schemas Package
"""
from backend.schemas.user import UserBase, UserCreate, UserRead
from backend.schemas.department import DepartmentBase, DepartmentCreate, DepartmentRead
from backend.schemas.complaint import (
    ComplaintBase,
    ComplaintCreate,
    ComplaintRead,
    ComplaintSummary,
    ComplaintListResponse,
    StatusUpdateRequest,
    DepartmentAssignRequest,
)
from backend.schemas.attachment import ComplaintAttachmentRead, ComplaintAttachmentCreate
from backend.schemas.status_history import ComplaintStatusHistoryRead
from backend.schemas.ai_analysis import AIAnalysisRead, AIAnalysisCreate
from backend.schemas.notification import NotificationRead, NotificationUpdate, NotificationListResponse
from backend.schemas.auth import UserRegister, UserLogin, TokenResponse

__all__ = [
    "UserBase",
    "UserCreate",
    "UserRead",
    "DepartmentBase",
    "DepartmentCreate",
    "DepartmentRead",
    "ComplaintBase",
    "ComplaintCreate",
    "ComplaintRead",
    "ComplaintSummary",
    "ComplaintListResponse",
    "StatusUpdateRequest",
    "DepartmentAssignRequest",
    "ComplaintAttachmentRead",
    "ComplaintAttachmentCreate",
    "ComplaintStatusHistoryRead",
    "AIAnalysisRead",
    "AIAnalysisCreate",
    "NotificationRead",
    "NotificationUpdate",
    "NotificationListResponse",
    "UserRegister",
    "UserLogin",
    "TokenResponse",
]



