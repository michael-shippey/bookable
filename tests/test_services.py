import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.models.business import Business
from app.models.user import User, UserRole
from app.permissions import ensure_can_manage
from app.schemas.service import ServiceCreate, ServiceUpdate

client = TestClient(app)


# --- Schema validation -------------------------------------------------------

def test_valid_service_accepted():
    service = ServiceCreate(name="Haircut", duration_minutes=30, price_cents=2500)
    assert service.price_cents == 2500


def test_free_service_allowed():
    service = ServiceCreate(name="Consultation", duration_minutes=15, price_cents=0)
    assert service.price_cents == 0


def test_zero_duration_rejected():
    with pytest.raises(ValidationError):
        ServiceCreate(name="Haircut", duration_minutes=0, price_cents=2500)


def test_duration_over_a_day_rejected():
    with pytest.raises(ValidationError):
        ServiceCreate(name="Haircut", duration_minutes=1441, price_cents=2500)


def test_negative_price_rejected():
    with pytest.raises(ValidationError):
        ServiceCreate(name="Haircut", duration_minutes=30, price_cents=-1)


def test_update_rejects_explicit_null_duration():
    with pytest.raises(ValidationError):
        ServiceUpdate(duration_minutes=None)


def test_update_can_deactivate():
    update = ServiceUpdate(is_active=False)
    assert update.model_dump(exclude_unset=True) == {"is_active": False}


# --- Ownership check ---------------------------------------------------------

def test_owner_can_manage_own_business():
    business = Business(owner_id=1)
    owner = User(id=1, role=UserRole.BUSINESS_OWNER)
    ensure_can_manage(business, owner)  # no exception


def test_admin_can_manage_any_business():
    business = Business(owner_id=1)
    admin = User(id=99, role=UserRole.ADMIN)
    ensure_can_manage(business, admin)  # no exception


def test_other_owner_cannot_manage():
    business = Business(owner_id=1)
    other = User(id=2, role=UserRole.BUSINESS_OWNER)
    with pytest.raises(HTTPException) as error:
        ensure_can_manage(business, other)
    assert error.value.status_code == 403


# --- Endpoints need a login --------------------------------------------------

def test_create_service_requires_auth():
    response = client.post(
        "/businesses/1/services",
        json={"name": "Haircut", "duration_minutes": 30, "price_cents": 2500},
    )
    assert response.status_code == 401


def test_update_service_requires_auth():
    response = client.patch("/services/1", json={"is_active": False})
    assert response.status_code == 401
