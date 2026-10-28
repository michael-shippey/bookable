from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_rejects_invalid_email():
    response = client.post(
        "/users",
        json={"email": "not-an-email", "password": "longenough1", "full_name": "Test"},
    )
    assert response.status_code == 422


def test_rejects_short_password():
    response = client.post(
        "/users",
        json={"email": "a@example.com", "password": "short", "full_name": "Test"},
    )
    assert response.status_code == 422
