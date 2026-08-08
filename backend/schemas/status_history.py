from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional
from backend.models.enums import ComplaintStatus

class ComplaintStatusHistoryRead(BaseModel):
    id: int
    complaint_id: int
    old_status: Optional[ComplaintStatus] = None
    new_status: ComplaintStatus
    changed_by: Optional[int] = None
    note: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
