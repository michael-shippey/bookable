from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.user import UserRole
from app.schemas.common import validate_timezone


class UserCreate(BaseModel):
    """What a client must send to register. Note: no 'role' field on purpose."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=100)
    timezone: str = "UTC"

    @field_validator("timezone")
    @classmethod
    def check_timezone(cls, value: str) -> str:
        return validate_timezone(value)


class UserUpdate(BaseModel):
    """Fields a user may change about themselves. Role and email are not here."""

    full_name: str | None = Field(default=None, min_length=1, max_length=100)
    timezone: str | None = None

    @field_validator("full_name")
    @classmethod
    def full_name_not_null(cls, value):
        if value is None:
            raise ValueError("full_name cannot be null")
        return value

    @field_validator("timezone")
    @classmethod
    def check_timezone(cls, value):
        if value is None:
            raise ValueError("timezone cannot be null")
        return validate_timezone(value)


class UserRead(BaseModel):
    """What we send back. Note: no password or hash, ever."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool
    timezone: str
    created_at: datetime
