from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_role
from app.models.service import Service
from app.models.user import User, UserRole
from app.permissions import ensure_can_manage, get_business_or_404
from app.schemas.service import ServiceCreate, ServiceRead, ServiceUpdate

router = APIRouter(tags=["services"])

DUPLICATE_NAME = "This business already has a service with that name"


# A service only exists inside a business, so creating and listing use a
# "nested" URL: /businesses/{id}/services.
@router.post(
    "/businesses/{business_id}/services",
    response_model=ServiceRead,
    status_code=status.HTTP_201_CREATED,
)
def create_service(
    business_id: int,
    payload: ServiceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_role(UserRole.BUSINESS_OWNER, UserRole.ADMIN)
    ),
):
    business = get_business_or_404(db, business_id)
    ensure_can_manage(business, current_user)

    service = Service(business_id=business.id, **payload.model_dump())
    db.add(service)
    try:
        db.commit()
    except IntegrityError:
        # The unique constraint (business_id, name) rejected a duplicate.
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, DUPLICATE_NAME)

    db.refresh(service)
    return service


@router.get("/businesses/{business_id}/services", response_model=list[ServiceRead])
def list_services(business_id: int, db: Session = Depends(get_db)):
    """Public. Shows only active services (deactivated ones are hidden)."""
    get_business_or_404(db, business_id)
    stmt = (
        select(Service)
        .where(Service.business_id == business_id, Service.is_active.is_(True))
        .order_by(Service.id)
    )
    return db.scalars(stmt).all()


# Once you have a service's own id, it has its own top-level URL.
@router.get("/services/{service_id}", response_model=ServiceRead)
def get_service(service_id: int, db: Session = Depends(get_db)):
    service = db.get(Service, service_id)
    if service is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Service not found")
    return service


@router.patch("/services/{service_id}", response_model=ServiceRead)
def update_service(
    service_id: int,
    payload: ServiceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_role(UserRole.BUSINESS_OWNER, UserRole.ADMIN)
    ),
):
    """Also how you 'delete' a service: send {"is_active": false}."""
    service = db.get(Service, service_id)
    if service is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Service not found")

    # Ownership comes from the service's business, not from the service itself.
    business = get_business_or_404(db, service.business_id)
    ensure_can_manage(business, current_user)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(service, field, value)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, DUPLICATE_NAME)

    db.refresh(service)
    return service
