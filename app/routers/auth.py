from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.auth import Token
from app.security import DUMMY_HASH, create_access_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(
    form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    # The OAuth2 standard calls the login field "username"; we use it for the email.
    user = db.scalar(select(User).where(User.email == form.username.lower()))

    # Always verify a hash, even for unknown emails, so timing doesn't leak
    # which emails exist.
    password_ok = verify_password(
        form.password, user.hashed_password if user else DUMMY_HASH
    )

    # One vague message for every failure, so attackers learn nothing.
    if user is None or not password_ok or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return Token(access_token=create_access_token(user.id))
