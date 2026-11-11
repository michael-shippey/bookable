from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.bookings import confirmed_busy_intervals
from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user, require_role
from app.models.availability import AvailabilityRule
from app.models.booking import Booking, BookingStatus
from app.models.business import Business
from app.models.service import Service
from app.models.user import User, UserRole
from app.permissions import ensure_can_manage, get_business_or_404
from app.schemas.booking import BookingCreate, BookingRead
from app.slots import generate_slots

router = APIRouter(tags=["bookings"])

TAKEN = "That time slot was just taken. Please choose another."
EXCLUSION_VIOLATION = "23P01"  # Postgres error code for a broken exclusion constraint


@router.post("/bookings", response_model=BookingRead, status_code=status.HTTP_201_CREATED)
def create_booking(
    payload: BookingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    customer_timezone = payload.timezone or current_user.timezone
    customer_tz = ZoneInfo(customer_timezone)
    start = payload.start.astimezone(UTC)

    service = db.get(Service, payload.service_id)
    if service is None or not service.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Service not found")

    # LAYER 2: lock the business row. Simultaneous bookings for the same
    # business now take turns, so the check below and the insert are not
    # interleaved with someone else's. (Released when this transaction ends.)
    business = get_business_or_404(db, service.business_id, lock=True)
    business_tz = ZoneInfo(business.timezone)
    rules = db.scalars(
        select(AvailabilityRule).where(AvailabilityRule.business_id == business.id)
    ).all()

    def bookable_slots(busy):
        return generate_slots(
            rules=rules,
            business_tz=business_tz,
            customer_tz=customer_tz,
            customer_date=start.astimezone(customer_tz).date(),
            duration_minutes=service.duration_minutes,
            now=datetime.now(UTC),
            busy=busy,
        )

    # LAYER 1: re-validate with the very same function the availability
    # endpoint uses, so the two can never disagree.
    if not any(slot.start == start for slot in bookable_slots(())):
        raise HTTPException(
            422,
            "That is not a bookable time: it is outside opening hours, in the past, "
            "or not on the slot grid. Use a start time from the availability endpoint.",
        )

    busy = confirmed_busy_intervals(db, business.id, start)
    if not any(slot.start == start for slot in bookable_slots(busy)):
        raise HTTPException(status.HTTP_409_CONFLICT, TAKEN)

    booking = Booking(
        business_id=business.id,
        service_id=service.id,
        customer_id=current_user.id,
        start_at=start,
        end_at=start + timedelta(minutes=service.duration_minutes),
        customer_timezone=customer_timezone,
        status=BookingStatus.CONFIRMED.value,
    )
    db.add(booking)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        # LAYER 3: if the database's exclusion constraint caught an overlap that
        # layers 1 and 2 somehow missed, it is still just "slot taken".
        if getattr(error.orig, "sqlstate", None) == EXCLUSION_VIOLATION:
            raise HTTPException(status.HTTP_409_CONFLICT, TAKEN)
        raise

    db.refresh(booking)
    return booking


# "/bookings/me" must come before "/bookings/{booking_id}", or "me" would be
# read as a booking id.
@router.get("/bookings/me", response_model=list[BookingRead])
def my_bookings(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = (
        select(Booking)
        .where(Booking.customer_id == current_user.id)
        .order_by(Booking.start_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return db.scalars(stmt).all()


def _is_manager(user: User, business: Business) -> bool:
    return user.role == UserRole.ADMIN or business.owner_id == user.id


@router.get("/bookings/{booking_id}", response_model=BookingRead)
def get_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    booking = db.get(Booking, booking_id)
    business = db.get(Business, booking.business_id) if booking else None
    # Strangers get 404, not 403, so they can't learn which ids exist.
    if booking is None or not (
        booking.customer_id == current_user.id or _is_manager(current_user, business)
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Booking not found")
    return booking


@router.post("/bookings/{booking_id}/cancel", response_model=BookingRead)
def cancel_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    booking = db.get(Booking, booking_id, with_for_update=True)
    business = db.get(Business, booking.business_id) if booking else None
    is_customer = booking is not None and booking.customer_id == current_user.id
    is_manager = booking is not None and _is_manager(current_user, business)
    if booking is None or not (is_customer or is_manager):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Booking not found")

    if booking.status == BookingStatus.CANCELLED.value:
        raise HTTPException(status.HTTP_409_CONFLICT, "This booking is already cancelled")

    now = datetime.now(UTC)
    if booking.start_at <= now:
        raise HTTPException(status.HTTP_409_CONFLICT, "This booking has already started")

    notice = timedelta(hours=settings.cancellation_notice_hours)
    if not is_manager and booking.start_at - now < notice:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Bookings must be cancelled at least {settings.cancellation_notice_hours} "
            "hours before they start. Please contact the business.",
        )

    booking.status = BookingStatus.CANCELLED.value
    booking.cancelled_at = now
    db.commit()
    db.refresh(booking)
    return booking


@router.get("/businesses/{business_id}/bookings", response_model=list[BookingRead])
def business_bookings(
    business_id: int,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_role(UserRole.BUSINESS_OWNER, UserRole.ADMIN)
    ),
):
    """The business's own calendar. Owner or admin only."""
    business = get_business_or_404(db, business_id)
    ensure_can_manage(business, current_user)
    stmt = (
        select(Booking)
        .where(Booking.business_id == business_id)
        .order_by(Booking.start_at)
        .limit(limit)
        .offset(offset)
    )
    return db.scalars(stmt).all()
