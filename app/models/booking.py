import enum
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BookingStatus(str, enum.Enum):
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    # A later "request" feature would add PENDING here (and to the check below).


class Booking(Base):
    """One customer's reservation of one service at an exact moment.

    start_at and end_at are exact instants (stored in UTC). Nothing here is a
    wall-clock time; customer_timezone only remembers how the customer saw it.

    The double-booking guard is NOT declared on this class: it is an exclusion
    constraint, "ex_bookings_no_overlap", created in the migration, which stops
    two confirmed bookings of one business from overlapping in time.
    """

    __tablename__ = "bookings"
    __table_args__ = (
        # (service, business) must be a real pair, so a booking can never mix
        # one business's service with another business's calendar.
        ForeignKeyConstraint(
            ["service_id", "business_id"],
            ["services.id", "services.business_id"],
            name="fk_bookings_service_business",
            ondelete="RESTRICT",
        ),
        CheckConstraint("end_at > start_at", name="ck_bookings_end_after_start"),
        CheckConstraint(
            "status IN ('confirmed', 'cancelled')", name="ck_bookings_status"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int]
    service_id: Mapped[int] = mapped_column(index=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )

    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    customer_timezone: Mapped[str] = mapped_column(String(64))

    status: Mapped[str] = mapped_column(
        String(20), default=BookingStatus.CONFIRMED.value
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
