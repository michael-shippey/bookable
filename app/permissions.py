"""Shared permission helpers, used by several routers."""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.business import Business
from app.models.user import User, UserRole


def get_business_or_404(db: Session, business_id: int) -> Business:
    business = db.get(Business, business_id)
    if business is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Business not found")
    return business


def ensure_can_manage(business: Business, user: User) -> None:
    """Ownership check: the role says what you may do, this says to WHAT."""
    if user.role != UserRole.ADMIN and business.owner_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not own this business")
