from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

from app.config import settings

# recommended() gives us Argon2, a modern algorithm designed to be slow and
# memory-hungry on purpose, which makes stolen password hashes hard to crack.
_password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return _password_hash.verify(plain_password, hashed_password)


# Used at login when the email doesn't exist, so we still spend the same time
# hashing. Otherwise response time would reveal which emails are registered.
DUMMY_HASH = hash_password("dummy-password-for-timing")


def create_access_token(user_id: int) -> str:
    """Create a signed JWT. 'sub' (subject) identifies the user; 'exp' is expiry."""
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> int | None:
    """Return the user id if the token is valid and unexpired, otherwise None."""
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
