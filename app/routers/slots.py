from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.availability import AvailabilityRule
from app.models.service import Service
from app.permissions import get_business_or_404
from app.schemas.common import validate_timezone
from app.schemas.slots import AvailabilityResponse, SlotRead
from app.slots import generate_slots

router = APIRouter(tags=["availability"])


@router.get("/services/{service_id}/availability", response_model=AvailabilityResponse)
def get_availability(
    service_id: int,
    on_date: date = Query(
        ..., alias="date", description="The day to check, in the CUSTOMER's timezone"
    ),
    customer_timezone: str = Query(
        "UTC", alias="timezone", description="Customer's IANA timezone, e.g. Asia/Tokyo"
    ),
    db: Session = Depends(get_db),
):
    """Public. Open slots for a service on one day, as seen by the customer.

    Advisory only: another customer may take a slot before you book it. The
    booking step is what actually guarantees there are no double bookings.
    """
    # Cheap input checks first, before touching the database.
    try:
        customer_tz = ZoneInfo(validate_timezone(customer_timezone))
    except ValueError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error))

    # Customers can be up to a day ahead of or behind UTC, hence the extra day.
    today = datetime.now(UTC).date()
    if on_date < today - timedelta(days=1) or on_date > today + timedelta(days=366):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "date must be within the next year",
        )

    service = db.get(Service, service_id)
    if service is None or not service.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Service not found")

    business = get_business_or_404(db, service.business_id)
    business_tz = ZoneInfo(business.timezone)
    rules = db.scalars(
        select(AvailabilityRule).where(AvailabilityRule.business_id == business.id)
    ).all()

    slots = generate_slots(
        rules=rules,
        business_tz=business_tz,
        customer_tz=customer_tz,
        customer_date=on_date,
        duration_minutes=service.duration_minutes,
        now=datetime.now(UTC),
    )

    return AvailabilityResponse(
        service_id=service.id,
        duration_minutes=service.duration_minutes,
        date=on_date,
        business_timezone=business.timezone,
        customer_timezone=customer_timezone,
        slots=[
            SlotRead(
                start=slot.start,
                end=slot.end,
                business_local_start=slot.start.astimezone(business_tz),
                customer_local_start=slot.start.astimezone(customer_tz),
            )
            for slot in slots
        ],
    )
