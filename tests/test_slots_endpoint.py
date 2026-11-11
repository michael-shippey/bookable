from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_date_is_required():
    response = client.get("/services/1/availability")
    assert response.status_code == 422


def test_unknown_timezone_is_rejected():
    response = client.get(
        "/services/1/availability?date=2026-11-02&timezone=Mars/Phobos"
    )
    assert response.status_code == 422


def test_date_too_far_ahead_is_rejected():
    response = client.get("/services/1/availability?date=2100-01-01")
    assert response.status_code == 422


def test_malformed_date_is_rejected():
    response = client.get("/services/1/availability?date=next-tuesday")
    assert response.status_code == 422
