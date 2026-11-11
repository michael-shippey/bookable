from datetime import datetime
from zoneinfo import ZoneInfo

from pydantic import (
    BaseModel,
    ConfigDict,
    computed_field,
    field_validator,
)

from app.models.booking import BookingStatus
from app.schemas.common import validate_timezone


class BookingCreate(BaseModel):
    """Book a slot. Copy `start` exactly from the availability endpoint."""

    service_id: int
    start: datetime  # must include a UTC offset
    timezone: str | None = None  # customer's timezone; defaults to their profile

    @field_validator("start")
    @classmethod
    def start_must_have_an_offset(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(
                "start must include a UTC offset, like 2026-11-16T09:00:00-07:00 "
                "or 2026-11-16T16:00:00Z (a bare local time is ambiguous)"
            )
        return value

    @field_validator("timezone")
    @classmethod
    def check_timezone(cls, value):
        return None if value is None else validate_timezone(value)


class BookingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    business_id: int
    service_id: int
    customer_id: int
    start_at: datetime  # exact moments, UTC
    end_at: datetime
    customer_timezone: str
    status: BookingStatus
    created_at: datetime
    cancelled_at: datetime | None

    @computed_field
    @property
    def customer_local_start(self) -> datetime:
        return self.start_at.astimezone(ZoneInfo(self.customer_timezone))

    @computed_field
    @property
    def customer_local_end(self) -> datetime:
        return self.end_at.astimezone(ZoneInfo(self.customer_timezone))
