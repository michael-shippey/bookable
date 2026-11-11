from datetime import date, datetime

from pydantic import BaseModel


class SlotRead(BaseModel):
    start: datetime  # exact moment, in UTC
    end: datetime  # exact moment, in UTC
    business_local_start: datetime  # the same moment on the business's clock
    customer_local_start: datetime  # the same moment on the customer's clock


class AvailabilityResponse(BaseModel):
    service_id: int
    duration_minutes: int
    date: date  # the day that was asked about, in the CUSTOMER's timezone
    business_timezone: str
    customer_timezone: str
    slots: list[SlotRead]
