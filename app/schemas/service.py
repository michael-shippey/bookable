from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ServiceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    duration_minutes: int = Field(gt=0, le=1440)  # up to 24 hours
    price_cents: int = Field(ge=0, le=10_000_000)  # 0 = free


class ServiceUpdate(BaseModel):
    """Every field is optional: send only what you want to change."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    duration_minutes: int | None = Field(default=None, gt=0, le=1440)
    price_cents: int | None = Field(default=None, ge=0, le=10_000_000)
    is_active: bool | None = None

    @field_validator("name", "duration_minutes", "price_cents", "is_active")
    @classmethod
    def not_null(cls, value, info):
        # These columns are required in the database, so an explicit null is invalid.
        if value is None:
            raise ValueError(f"{info.field_name} cannot be null")
        return value


class ServiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    business_id: int
    name: str
    description: str | None
    duration_minutes: int
    price_cents: int
    is_active: bool
    created_at: datetime
