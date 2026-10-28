from datetime import datetime
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _check_timezone(value: str) -> str:
    try:
        ZoneInfo(value)
    except (KeyError, ValueError, OSError):
        raise ValueError("Unknown timezone (use a name like 'America/Boise' or 'UTC')")
    return value


class BusinessCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    timezone: str = "UTC"

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        return _check_timezone(value)


class BusinessUpdate(BaseModel):
    """Every field is optional: send only what you want to change."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    timezone: str | None = None

    @field_validator("name", "timezone")
    @classmethod
    def not_null(cls, value, info):
        # These columns are required in the database, so an explicit null is invalid.
        if value is None:
            raise ValueError(f"{info.field_name} cannot be null")
        return value

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        return _check_timezone(value)


class BusinessRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    name: str
    description: str | None
    timezone: str
    created_at: datetime
