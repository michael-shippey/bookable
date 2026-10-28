from datetime import datetime, timedelta, timezone

import jwt
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.security import create_access_token, decode_access_token

client = TestClient(app)


def test_token_round_trip():
    token = create_access_token(42)
    assert decode_access_token(token) == 42


def test_tampered_token_is_rejected():
    token = create_access_token(42)
    assert decode_access_token(token + "x") is None


def test_token_signed_with_wrong_key_is_rejected():
    forged = jwt.encode(
        {"sub": "42", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        "some-other-secret-key-that-is-long-enough-0123456789",
        algorithm=settings.algorithm,
    )
    assert decode_access_token(forged) is None


def test_expired_token_is_rejected():
    expired = jwt.encode(
        {"sub": "42", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        settings.secret_key,
        algorithm=settings.algorithm,
    )
    assert decode_access_token(expired) is None


def test_me_requires_a_token():
    response = client.get("/users/me")
    assert response.status_code == 401


def test_me_rejects_garbage_token():
    response = client.get("/users/me", headers={"Authorization": "Bearer not-a-token"})
    assert response.status_code == 401
