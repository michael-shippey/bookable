from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.availability import segments_overlap, weekly_segments
from app.database import get_db
from app.dependencies import require_role
from app.models.availability import AvailabilityRule
from app.models.user import User, UserRole
from app.permissions import ensure_can_manage, get_business_or_404
from app.schemas.availability import RuleCreate, RuleRead

router = APIRouter(tags=["availability"])


def _segments_for(rule) -> list[tuple[int, int]]:
    return weekly_segments(
        rule.day_of_week, rule.start_time, rule.end_time, rule.is_all_day
    )


@router.post(
    "/businesses/{business_id}/availability/rules",
    response_model=RuleRead,
    status_code=status.HTTP_201_CREATED,
)
def create_rule(
    business_id: int,
    payload: RuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_role(UserRole.BUSINESS_OWNER, UserRole.ADMIN)
    ),
):
    # lock=True: two requests adding rules to the same business now take turns,
    # so they can't both pass the overlap check below and then both save.
    business = get_business_or_404(db, business_id, lock=True)
    ensure_can_manage(business, current_user)

    new_segments = weekly_segments(
        payload.day_of_week, payload.start_time, payload.end_time, payload.is_all_day
    )
    existing = db.scalars(
        select(AvailabilityRule).where(AvailabilityRule.business_id == business_id)
    ).all()
    for rule in existing:
        if segments_overlap(new_segments, _segments_for(rule)):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"This window overlaps with existing rule {rule.id}",
            )

    rule = AvailabilityRule(business_id=business_id, **payload.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.get(
    "/businesses/{business_id}/availability/rules", response_model=list[RuleRead]
)
def list_rules(business_id: int, db: Session = Depends(get_db)):
    """Public: customers can see when a business is open."""
    get_business_or_404(db, business_id)
    stmt = (
        select(AvailabilityRule)
        .where(AvailabilityRule.business_id == business_id)
        .order_by(AvailabilityRule.day_of_week, AvailabilityRule.start_time)
    )
    return db.scalars(stmt).all()


@router.delete(
    "/businesses/{business_id}/availability/rules/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_rule(
    business_id: int,
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_role(UserRole.BUSINESS_OWNER, UserRole.ADMIN)
    ),
):
    """Rules have no PATCH: to change one, delete it and add a new one."""
    business = get_business_or_404(db, business_id)
    ensure_can_manage(business, current_user)

    rule = db.get(AvailabilityRule, rule_id)
    if rule is None or rule.business_id != business_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Rule not found")

    db.delete(rule)
    db.commit()
