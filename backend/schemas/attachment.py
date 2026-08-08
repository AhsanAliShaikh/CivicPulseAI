from pydantic import BaseModel, ConfigDict, field_validator
from datetime import datetime


class ComplaintAttachmentCreate(BaseModel):
    file_name: str
    file_url: str
    file_type: str
    file_size: int

    @field_validator("file_name", "file_url", "file_type")
    @classmethod
    def not_empty_string(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Field cannot be empty or whitespace.")
        return v

    @field_validator("file_size")
    @classmethod
    def size_must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("file_size must be greater than 0 bytes.")
        return v


class ComplaintAttachmentRead(BaseModel):
    id: int
    complaint_id: int
    file_name: str
    file_url: str
    file_type: str
    file_size: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

