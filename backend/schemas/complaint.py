from pydantic import BaseModel, ConfigDict, field_validator
from datetime import datetime
from typing import Optional, List
from backend.models.enums import ComplaintStatus, ComplaintPriority
from backend.schemas.attachment import ComplaintAttachmentRead
from backend.schemas.status_history import ComplaintStatusHistoryRead
from backend.schemas.ai_analysis import AIAnalysisRead
from backend.schemas.department import DepartmentRead


class ComplaintBase(BaseModel):
    title: str
    description: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    priority: ComplaintPriority = ComplaintPriority.MEDIUM


class ComplaintCreate(ComplaintBase):
    user_id: int
    department_id: Optional[int] = None

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Title cannot be empty.")
        if len(v) < 5:
            raise ValueError("Title must be at least 5 characters.")
        return v

    @field_validator("description")
    @classmethod
    def description_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Description cannot be empty.")
        if len(v) < 10:
            raise ValueError("Description must be at least 10 characters.")
        return v


class ComplaintRead(ComplaintBase):
    id: int
    public_id: str
    user_id: int
    department_id: Optional[int] = None
    department: Optional[DepartmentRead] = None
    status: ComplaintStatus

    # AI storage fields (populated by Phase 3+)
    ai_category: Optional[str] = None
    ai_priority: Optional[str] = None
    ai_confidence: Optional[float] = None
    ai_summary: Optional[str] = None

    # Timestamps
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None

    # Nested child objects
    attachments: List[ComplaintAttachmentRead] = []
    status_history: List[ComplaintStatusHistoryRead] = []
    ai_analyses: List[AIAnalysisRead] = []

    model_config = ConfigDict(from_attributes=True)


class ComplaintSummary(BaseModel):
    """Lightweight complaint representation for list responses."""
    id: int
    public_id: str
    user_id: int
    title: str
    category: Optional[str] = None
    status: ComplaintStatus
    priority: ComplaintPriority
    department: Optional[DepartmentRead] = None
    address: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ComplaintListResponse(BaseModel):
    """Paginated complaint list response."""
    items: List[ComplaintSummary]
    page: int
    page_size: int
    total: int
    pages: int


class StatusUpdateRequest(BaseModel):
    status: ComplaintStatus
    note: Optional[str] = None
    changed_by: Optional[int] = None


class DepartmentAssignRequest(BaseModel):
    department_id: int
