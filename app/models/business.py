from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Business(Base):
    __tablename__ = "businesses"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Foreign key: every business belongs to exactly one user. The database
    # itself refuses a business whose owner doesn't exist. Indexed because we
    # will often query "all businesses owned by user X".
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(String(1000))  # optional

    # Availability only makes sense in the business's local time, so we store
    # its IANA timezone (like "America/Boise") now.
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
