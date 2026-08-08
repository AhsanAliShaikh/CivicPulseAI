from pydantic import BaseModel, EmailStr, ConfigDict
from datetime import datetime
from typing import Optional
from backend.models.enums import UserRole

class UserBase(BaseModel):
    name: str
    email: EmailStr
    role: UserRole = UserRole.CITIZEN

class UserCreate(UserBase):
    pass

class UserRead(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
