from datetime import time

from sqlalchemy import CheckConstraint, ForeignKey, SmallInteger, Time
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AvailabilityRule(Base):
    """One recurring weekly window when a business takes bookings.

    Times are LOCAL wall-clock times in the business's own timezone.
    A window belongs to the day it STARTS on. If end_time is earlier than
    start_time, the window runs past midnight into the next day.
    """

    __tablename__ = "availability_rules"
    __table_args__ = (
        CheckConstraint(
            "day_of_week BETWEEN 0 AND 6", name="ck_availability_rules_day_range"
        ),
        # Either an all-day rule with no times, or a normal rule with two
        # different times (equal times would be ambiguous).
        CheckConstraint(
            "(is_all_day AND start_time IS NULL AND end_time IS NULL) OR "
            "(NOT is_all_day AND start_time IS NOT NULL AND end_time IS NOT NULL "
            "AND start_time <> end_time)",
            name="ck_availability_rules_shape",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), index=True
    )
    day_of_week: Mapped[int] = mapped_column(SmallInteger)  # 0 = Monday ... 6 = Sunday
    start_time: Mapped[time | None] = mapped_column(Time)
    end_time: Mapped[time | None] = mapped_column(Time)
    is_all_day: Mapped[bool] = mapped_column(default=False)
