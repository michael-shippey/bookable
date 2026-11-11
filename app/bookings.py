from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.booking import Booking, BookingStatus


def confirmed_busy_intervals(
    db: Session, business_id: int, around: datetime, days: int = 2
) -> list[tuple[datetime, datetime]]:
    """Confirmed bookings of a business near a moment, as (start, end) pairs.

    Used to hide taken slots. The window is generous on purpose: callers only
    need every booking that could overlap the day they care about.
    """
    window_start = around - timedelta(days=days)
    window_end = around + timedelta(days=days)
    rows = db.execute(
        select(Booking.start_at, Booking.end_at).where(
            Booking.business_id == business_id,
            Booking.status == BookingStatus.CONFIRMED.value,
            Booking.start_at < window_end,
            Booking.end_at > window_start,
        )
    ).all()
    return [(row.start_at, row.end_at) for row in rows]
