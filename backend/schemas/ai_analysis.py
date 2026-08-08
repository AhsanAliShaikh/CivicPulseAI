from pydantic import BaseModel, ConfigDict, field_validator
from datetime import datetime
from typing import Optional


class AIAnalysisCreate(BaseModel):
    """
    Payload submitted by an AI classification pipeline.
    The caller (Phase 3+ AI worker) POSTs this after analysing a complaint.
    """
    model_name: str
    model_version: str
    category: Optional[str] = None
    priority: Optional[str] = None
    confidence: Optional[float] = None
    summary: Optional[str] = None
    reasoning: Optional[str] = None
    # Optional: if provided, auto-assign this department when complaint has none
    suggested_department_id: Optional[int] = None

    @field_validator("confidence")
    @classmethod
    def confidence_range(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (0.0 <= v <= 1.0):
            raise ValueError("confidence must be between 0.0 and 1.0")
        return v

    @field_validator("model_name")
    @classmethod
    def model_name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("model_name cannot be empty")
        return v


class AIAnalysisRead(BaseModel):
    id: int
    complaint_id: int
    model_name: str
    model_version: str
    category: Optional[str] = None
    priority: Optional[str] = None
    confidence: Optional[float] = None
    summary: Optional[str] = None
    reasoning: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

