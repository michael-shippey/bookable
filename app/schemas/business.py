from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.common import validate_timezone


class BusinessCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    timezone: str = "UTC"

    @field_validator("timezone")
    @classmethod
    def check_timezone(cls, value: str) -> str:
        return validate_timezone(value)


class BusinessUpdate(BaseModel):
    """Every field is optional: send only what you want to change."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    timezone: str | None = None

    @field_validator("name")
    @classmethod
    def name_not_null(cls, value):
        # This column is required in the database, so an explicit null is invalid.
        if value is None:
            raise ValueError("name cannot be null")
        return value

    @field_validator("timezone")
    @classmethod
    def check_timezone(cls, value):
        if value is None:
            raise ValueError("timezone cannot be null")
        return validate_timezone(value)


class BusinessRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    name: str
    description: str | None
    timezone: str
    created_at: datetime
