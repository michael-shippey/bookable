from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Service(Base):
    __tablename__ = "services"

    # Rules enforced by the database itself, as a last line of defense in case
    # bad data ever reaches it by a route other than our API.
    __table_args__ = (
        UniqueConstraint("business_id", "name", name="uq_services_business_name"),
        CheckConstraint(
            "duration_minutes > 0 AND duration_minutes <= 1440",
            name="ck_services_duration_range",
        ),
        CheckConstraint("price_cents >= 0", name="ck_services_price_nonnegative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(String(500))
    duration_minutes: Mapped[int]

    # Money is stored as whole cents in an integer. Floats cannot represent
    # values like 0.10 exactly, which causes rounding bugs with money.
    price_cents: Mapped[int]

    # "Soft delete": we deactivate instead of deleting, because bookings will
    # later point at services and we don't want to erase booking history.
    is_active: Mapped[bool] = mapped_column(default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
