import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.dependencies import require_role
from app.main import app
from app.models.user import User, UserRole
from app.schemas.business import BusinessCreate, BusinessUpdate

client = TestClient(app)


# --- Schema validation -------------------------------------------------------

def test_valid_timezone_accepted():
    business = BusinessCreate(name="Test Salon", timezone="America/Boise")
    assert business.timezone == "America/Boise"


def test_unknown_timezone_rejected():
    with pytest.raises(ValidationError):
        BusinessCreate(name="Test Salon", timezone="Mars/Phobos")


def test_empty_name_rejected():
    with pytest.raises(ValidationError):
        BusinessCreate(name="")


def test_update_rejects_explicit_null_name():
    with pytest.raises(ValidationError):
        BusinessUpdate(name=None)


def test_update_allows_partial_fields():
    update = BusinessUpdate(description="New description")
    assert update.model_dump(exclude_unset=True) == {"description": "New description"}


# --- Role checking -----------------------------------------------------------

def test_require_role_blocks_wrong_role():
    checker = require_role(UserRole.BUSINESS_OWNER, UserRole.ADMIN)
    customer = User(role=UserRole.CUSTOMER)
    with pytest.raises(HTTPException) as error:
        checker(current_user=customer)
    assert error.value.status_code == 403


def test_require_role_allows_right_role():
    checker = require_role(UserRole.BUSINESS_OWNER, UserRole.ADMIN)
    owner = User(role=UserRole.BUSINESS_OWNER)
    assert checker(current_user=owner) is owner


# --- Endpoints need a login --------------------------------------------------

def test_create_business_requires_auth():
    response = client.post("/businesses", json={"name": "No Token Salon"})
    assert response.status_code == 401


def test_update_business_requires_auth():
    response = client.patch("/businesses/1", json={"name": "Nope"})
    assert response.status_code == 401


def test_delete_business_requires_auth():
    response = client.delete("/businesses/1")
    assert response.status_code == 401
