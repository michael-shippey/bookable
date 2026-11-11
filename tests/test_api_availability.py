import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.main import app
from tests.test_api_businesses import create_business, create_service


def add_rule(client, headers, business_id, **body):
    return client.post(
        f"/businesses/{business_id}/availability/rules", json=body, headers=headers
    )


def upcoming(weekday: int, min_days_ahead: int = 3) -> date:
    """The next date (Monday = 0) at least a few days away, so slots aren't 'past'."""
    day = date.today() + timedelta(days=min_days_ahead)
    while day.weekday() != weekday:
        day += timedelta(days=1)
    return day


def availability(client, service_id, day, timezone):
    response = client.get(
        f"/services/{service_id}/availability?date={day}&timezone={timezone}"
    )
    assert response.status_code == 200, response.text
    return response.json()


# --- Weekly rules -------------------------------------------------------------

def test_rules_can_be_created_listed_publicly_and_deleted(client, make_account):
    owner = make_account("owner@example.com")
    business = create_business(client, owner.headers)
    bid = business["id"]

    monday = add_rule(client, owner.headers, bid, day_of_week=0, start_time="09:00", end_time="17:00")
    overnight = add_rule(client, owner.headers, bid, day_of_week=4, start_time="20:00", end_time="02:00")
    all_day = add_rule(client, owner.headers, bid, day_of_week=2, is_all_day=True)

    assert monday.status_code == overnight.status_code == all_day.status_code == 201
    assert overnight.json()["crosses_midnight"] is True
    assert all_day.json()["start_time"] is None

    public = client.get(f"/businesses/{bid}/availability/rules")  # no login
    assert [r["day_of_week"] for r in public.json()] == [0, 2, 4]

    deleted = client.delete(
        f"/businesses/{bid}/availability/rules/{monday.json()['id']}", headers=owner.headers
    )
    assert deleted.status_code == 204
    assert len(client.get(f"/businesses/{bid}/availability/rules").json()) == 2


def test_overlapping_rules_are_rejected_but_touching_ones_are_fine(client, make_account):
    owner = make_account("owner@example.com")
    bid = create_business(client, owner.headers)["id"]

    assert add_rule(client, owner.headers, bid, day_of_week=0, start_time="09:00", end_time="17:00").status_code == 201
    assert add_rule(client, owner.headers, bid, day_of_week=0, start_time="12:00", end_time="18:00").status_code == 409
    assert add_rule(client, owner.headers, bid, day_of_week=0, start_time="17:00", end_time="20:00").status_code == 201  # touches only

    # Friday night runs into Saturday morning, so it blocks early-Saturday rules.
    assert add_rule(client, owner.headers, bid, day_of_week=4, start_time="20:00", end_time="02:00").status_code == 201
    assert add_rule(client, owner.headers, bid, day_of_week=5, is_all_day=True).status_code == 409
    assert add_rule(client, owner.headers, bid, day_of_week=5, start_time="01:00", end_time="05:00").status_code == 409
    assert add_rule(client, owner.headers, bid, day_of_week=5, start_time="03:00", end_time="05:00").status_code == 201


def test_sunday_night_wraps_around_into_monday_morning(client, make_account):
    owner = make_account("owner@example.com")
    bid = create_business(client, owner.headers)["id"]

    assert add_rule(client, owner.headers, bid, day_of_week=6, start_time="20:00", end_time="02:00").status_code == 201
    assert add_rule(client, owner.headers, bid, day_of_week=0, start_time="01:00", end_time="03:00").status_code == 409


def test_rules_belong_to_their_own_business(client, make_account):
    owner = make_account("owner@example.com")
    rival = make_account("rival@example.com")
    first = create_business(client, owner.headers)["id"]
    second = create_business(client, owner.headers, name="Second Shop")["id"]
    create_business(client, rival.headers, name="Rival Shop")

    rule = add_rule(client, owner.headers, first, day_of_week=0, start_time="09:00", end_time="17:00").json()

    # A rival owner cannot touch it.
    blocked = add_rule(client, rival.headers, first, day_of_week=1, start_time="09:00", end_time="17:00")
    assert blocked.status_code == 403

    # Deleting it through the wrong business finds nothing.
    wrong_business = client.delete(
        f"/businesses/{second}/availability/rules/{rule['id']}", headers=owner.headers
    )
    assert wrong_business.status_code == 404


def test_simultaneous_overlapping_rules_only_one_wins(client, make_account):
    """Two requests arrive at the same moment with overlapping windows.
    Without the row lock both could pass the overlap check and both be saved."""
    owner = make_account("owner@example.com")
    bid = create_business(client, owner.headers)["id"]
    url = f"/businesses/{bid}/availability/rules"
    body = {"day_of_week": 0, "start_time": "09:00", "end_time": "17:00"}
    barrier = threading.Barrier(2)

    def attempt(_):
        own_client = TestClient(app)
        barrier.wait()  # release both requests together
        return own_client.post(url, json=body, headers=owner.headers).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = sorted(pool.map(attempt, range(2)))

    assert results == [201, 409]
    assert len(client.get(url).json()) == 1


# --- Slots endpoint -----------------------------------------------------------

def bookable_service(client, make_account, duration=60):
    """A Boise business open Mondays 9 to 5, with one service."""
    owner = make_account("owner@example.com")
    business = create_business(client, owner.headers)
    add_rule(client, owner.headers, business["id"], day_of_week=0, start_time="09:00", end_time="17:00")
    service = create_service(client, owner.headers, business["id"], duration=duration)
    return owner, business, service


def test_boise_customer_sees_the_business_day(client, make_account):
    _, _, service = bookable_service(client, make_account)
    monday = upcoming(0)

    result = availability(client, service["id"], monday, "America/Boise")

    assert len(result["slots"]) == 29  # 9:00 to 16:00, every 15 minutes
    assert result["slots"][0]["business_local_start"].startswith(f"{monday}T09:00:00")


def test_tokyo_customer_sees_the_same_instants_on_their_own_day(client, make_account):
    _, _, service = bookable_service(client, make_account)
    monday = upcoming(0)

    boise = availability(client, service["id"], monday, "America/Boise")
    tokyo_tuesday = availability(client, service["id"], monday + timedelta(days=1), "Asia/Tokyo")
    tokyo_monday = availability(client, service["id"], monday, "Asia/Tokyo")

    assert [s["start"] for s in tokyo_tuesday["slots"]] == [s["start"] for s in boise["slots"]]
    assert tokyo_monday["slots"] == []


def test_overnight_window_shows_up_on_the_next_day(client, make_account):
    owner = make_account("owner@example.com")
    business = create_business(client, owner.headers)
    add_rule(client, owner.headers, business["id"], day_of_week=4, start_time="20:00", end_time="02:00")
    service = create_service(client, owner.headers, business["id"], duration=60)
    friday = upcoming(4)

    friday_slots = availability(client, service["id"], friday, "America/Boise")["slots"]
    saturday_slots = availability(client, service["id"], friday + timedelta(days=1), "America/Boise")["slots"]

    assert len(friday_slots) == 16    # 20:00 to 23:45
    assert len(saturday_slots) == 5   # 00:00 to 01:00, though Saturday has no rule


def test_service_longer_than_the_window_has_no_slots(client, make_account):
    _, _, service = bookable_service(client, make_account, duration=600)  # 10 hours
    result = availability(client, service["id"], upcoming(0), "America/Boise")
    assert result["slots"] == []


def test_inactive_and_unknown_services_are_not_available(client, make_account):
    owner, _, service = bookable_service(client, make_account)
    monday = upcoming(0)

    client.patch(f"/services/{service['id']}", json={"is_active": False}, headers=owner.headers)
    assert client.get(f"/services/{service['id']}/availability?date={monday}").status_code == 404
    assert client.get(f"/services/999/availability?date={monday}").status_code == 404
