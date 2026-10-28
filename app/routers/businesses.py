from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_role
from app.models.business import Business
from app.models.user import User, UserRole
from app.schemas.business import BusinessCreate, BusinessRead, BusinessUpdate

router = APIRouter(prefix="/businesses", tags=["businesses"])


def _get_business_or_404(db: Session, business_id: int) -> Business:
    business = db.get(Business, business_id)
    if business is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Business not found")
    return business


def _ensure_can_manage(business: Business, user: User) -> None:
    """Ownership check: the role says what you may do, this says to WHAT."""
    if user.role != UserRole.ADMIN and business.owner_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not own this business")


@router.post("", response_model=BusinessRead, status_code=status.HTTP_201_CREATED)
def create_business(
    payload: BusinessCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    business = Business(owner_id=current_user.id, **payload.model_dump())
    db.add(business)

    # Creating a business is how a customer becomes a business owner. The
    # business and the promotion are saved together in one transaction.
    if current_user.role == UserRole.CUSTOMER:
        current_user.role = UserRole.BUSINESS_OWNER

    db.commit()
    db.refresh(business)
    return business


@router.get("", response_model=list[BusinessRead])
def list_businesses(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Public. Paginated so one request can never return the whole table."""
    stmt = select(Business).order_by(Business.id).limit(limit).offset(offset)
    return db.scalars(stmt).all()


@router.get("/{business_id}", response_model=BusinessRead)
def get_business(business_id: int, db: Session = Depends(get_db)):
    return _get_business_or_404(db, business_id)


@router.patch("/{business_id}", response_model=BusinessRead)
def update_business(
    business_id: int,
    payload: BusinessUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_role(UserRole.BUSINESS_OWNER, UserRole.ADMIN)
    ),
):
    business = _get_business_or_404(db, business_id)
    _ensure_can_manage(business, current_user)

    # exclude_unset: only touch fields the client actually sent.
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(business, field, value)

    db.commit()
    db.refresh(business)
    return business


@router.delete("/{business_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_business(
    business_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_role(UserRole.BUSINESS_OWNER, UserRole.ADMIN)
    ),
):
    business = _get_business_or_404(db, business_id)
    _ensure_can_manage(business, current_user)
    db.delete(business)
    db.commit()
