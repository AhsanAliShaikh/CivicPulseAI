from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, List


class NotificationRead(BaseModel):
    id: int
    user_id: int
    complaint_id: int
    notification_type: str
    title: str
    message: str
    is_read: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationUpdate(BaseModel):
    is_read: Optional[bool] = None


class NotificationListResponse(BaseModel):
    items: List[NotificationRead]
    unread_count: int
    total: int
