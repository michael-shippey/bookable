import pytest
from pydantic import ValidationError

from app.schemas.user import UserCreate, UserUpdate


def test_registration_defaults_to_utc():
    user = UserCreate(email="a@example.com", password="longenough1", full_name="A")
    assert user.timezone == "UTC"


def test_registration_accepts_real_timezone():
    user = UserCreate(
        email="a@example.com",
        password="longenough1",
        full_name="A",
        timezone="Asia/Tokyo",
    )
    assert user.timezone == "Asia/Tokyo"


def test_registration_rejects_unknown_timezone():
    with pytest.raises(ValidationError):
        UserCreate(
            email="a@example.com",
            password="longenough1",
            full_name="A",
            timezone="Mars/Phobos",
        )


def test_update_rejects_null_timezone():
    with pytest.raises(ValidationError):
        UserUpdate(timezone=None)


def test_update_allows_partial_fields():
    update = UserUpdate(timezone="America/Boise")
    assert update.model_dump(exclude_unset=True) == {"timezone": "America/Boise"}
