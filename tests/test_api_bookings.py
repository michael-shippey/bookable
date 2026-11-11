import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, time, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.main import app
from app.models.booking import Booking
from tests.test_api_availability import add_rule, availability, upcoming
from tests.test_api_businesses import create_business, create_service

BOISE = ZoneInfo("America/Boise")


@pytest.fixture()
def world(client, make_account):
    """A Boise business open Mondays 9 to 5 with a 60-minute service, an owner,
    and a customer whose profile timezone is Tokyo."""
    owner = make_account("owner@example.com")
    business = create_business(client, owner.headers)
    add_rule(client, owner.headers, business["id"], day_of_week=0, start_time="09:00", end_time="17:00")
    service = create_service(client, owner.headers, business["id"], duration=60)
    customer = make_account("customer@example.com", timezone="Asia/Tokyo")
    return SimpleNamespace(
        owner=owner,
        business=business,
        service=service,
        customer=customer,
        monday=upcoming(0),
    )


def monday_slots(client, world):
    return availability(client, world.service["id"], world.monday, "America/Boise")["slots"]


def book(client, headers, service_id, start, timezone=None):
    body = {"service_id": service_id, "start": start}
    if timezone:
        body["timezone"] = timezone
    return client.post("/bookings", json=body, headers=headers)


def boise_iso(day: date, hour: int, minute: int) -> str:
    return datetime.combine(day, time(hour, minute), tzinfo=BOISE).isoformat()


# --- Booking and availability stay in step -----------------------------------

def test_booking_a_slot_removes_it_and_overlapping_slots(client, world):
    slots = monday_slots(client, world)
    assert len(slots) == 29

    response = book(client, world.customer.headers, world.service["id"], slots[0]["start"])
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "confirmed"
    assert body["customer_timezone"] == "Asia/Tokyo"  # defaulted from the profile
    assert body["customer_id"] == world.customer.id

    after = monday_slots(client, world)
    # 9:00, 9:15, 9:30, 9:45 all overlap the 9:00-10:00 booking; 10:00 only touches it.
    assert len(after) == 25
    assert after[0]["business_local_start"].startswith(f"{world.monday}T10:00:00")


def test_the_same_slot_cannot_be_booked_twice(client, world):
    start = monday_slots(client, world)[0]["start"]
    first = book(client, world.customer.headers, world.service["id"], start)
    second = book(client, world.customer.headers, world.service["id"], start)
    assert first.status_code == 201
    assert second.status_code == 409


def test_a_partly_overlapping_start_is_rejected_too(client, world):
    slots = monday_slots(client, world)
    assert book(client, world.customer.headers, world.service["id"], slots[0]["start"]).status_code == 201  # 9:00
    overlapping = book(client, world.customer.headers, world.service["id"], slots[2]["start"])  # 9:30
    assert overlapping.status_code == 409


def test_back_to_back_bookings_are_allowed(client, world):
    slots = monday_slots(client, world)
    nine = slots[0]["start"]
    ten = slots[4]["start"]
    assert book(client, world.customer.headers, world.service["id"], nine).status_code == 201
    assert book(client, world.customer.headers, world.service["id"], ten).status_code == 201


def test_a_tokyo_customer_books_in_their_own_timezone(client, world):
    tuesday = world.monday + timedelta(days=1)
    slots = availability(client, world.service["id"], tuesday, "Asia/Tokyo")["slots"]

    response = book(client, world.customer.headers, world.service["id"], slots[0]["start"], "Asia/Tokyo")

    assert response.status_code == 201
    assert response.json()["customer_local_start"].startswith(str(tuesday))
    assert response.json()["customer_local_start"].endswith("+09:00")


# --- Things that cannot be booked --------------------------------------------

def test_times_outside_the_schedule_are_rejected(client, world):
    sid = world.service["id"]
    headers = world.customer.headers
    assert book(client, headers, sid, boise_iso(world.monday, 8, 0)).status_code == 422   # before opening
    assert book(client, headers, sid, boise_iso(world.monday, 17, 0)).status_code == 422  # at closing
    assert book(client, headers, sid, boise_iso(world.monday, 9, 7)).status_code == 422    # off the slot grid
    tuesday = world.monday + timedelta(days=1)
    assert book(client, headers, sid, boise_iso(tuesday, 10, 0)).status_code == 422        # closed day


def test_a_start_without_an_offset_is_rejected(client, world):
    response = book(client, world.customer.headers, world.service["id"], f"{world.monday}T09:00:00")
    assert response.status_code == 422


def test_past_times_are_rejected(client, world):
    past_monday = date.today() - timedelta(days=7)
    while past_monday.weekday() != 0:
        past_monday += timedelta(days=1)
    response = book(client, world.customer.headers, world.service["id"], boise_iso(past_monday, 9, 0))
    assert response.status_code == 422


def test_booking_requires_a_login(client, world):
    start = monday_slots(client, world)[0]["start"]
    response = client.post("/bookings", json={"service_id": world.service["id"], "start": start})
    assert response.status_code == 401


def test_an_inactive_service_cannot_be_booked(client, world):
    start = monday_slots(client, world)[0]["start"]
    client.patch(f"/services/{world.service['id']}", json={"is_active": False}, headers=world.owner.headers)
    response = book(client, world.customer.headers, world.service["id"], start)
    assert response.status_code == 404


# --- Cancelling ---------------------------------------------------------------

def make_booking(client, world, index=0):
    start = monday_slots(client, world)[index]["start"]
    response = book(client, world.customer.headers, world.service["id"], start)
    assert response.status_code == 201, response.text
    return response.json()


def test_cancelling_frees_the_slot_for_someone_else(client, world, make_account):
    booking = make_booking(client, world)
    start = booking["start_at"]

    cancelled = client.post(f"/bookings/{booking['id']}/cancel", headers=world.customer.headers)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert cancelled.json()["cancelled_at"] is not None

    assert len(monday_slots(client, world)) == 29
    other = make_account("other@example.com")
    assert book(client, other.headers, world.service["id"], start).status_code == 201


def test_cancellation_rules(client, world, make_account):
    booking = make_booking(client, world)
    url = f"/bookings/{booking['id']}/cancel"
    stranger = make_account("stranger@example.com")

    assert client.post(url, headers=stranger.headers).status_code == 404  # not their booking
    assert client.post(url, headers=world.customer.headers).status_code == 200
    assert client.post(url, headers=world.customer.headers).status_code == 409  # already cancelled


def test_the_business_owner_can_cancel_a_customers_booking(client, world):
    booking = make_booking(client, world)
    response = client.post(f"/bookings/{booking['id']}/cancel", headers=world.owner.headers)
    assert response.status_code == 200


def test_customers_cannot_cancel_inside_the_notice_period(client, engine, world):
    soon = datetime.now(UTC) + timedelta(hours=2)
    with Session(engine) as session:
        row = Booking(
            business_id=world.business["id"],
            service_id=world.service["id"],
            customer_id=world.customer.id,
            start_at=soon,
            end_at=soon + timedelta(hours=1),
            customer_timezone="UTC",
            status="confirmed",
        )
        session.add(row)
        session.commit()
        booking_id = row.id

    url = f"/bookings/{booking_id}/cancel"
    assert client.post(url, headers=world.customer.headers).status_code == 409
    assert client.post(url, headers=world.owner.headers).status_code == 200  # owners are exempt


# --- Viewing bookings ---------------------------------------------------------

def test_listing_and_viewing_bookings(client, world, make_account):
    first = make_booking(client, world, index=0)   # 9:00
    second = make_booking(client, world, index=4)  # 11:00 (the slot list now starts at 10:00)
    stranger = make_account("stranger@example.com")

    mine = client.get("/bookings/me", headers=world.customer.headers).json()
    assert [b["id"] for b in mine] == [second["id"], first["id"]]  # latest first

    calendar = client.get(f"/businesses/{world.business['id']}/bookings", headers=world.owner.headers)
    assert [b["id"] for b in calendar.json()] == [first["id"], second["id"]]  # in time order
    assert client.get(f"/businesses/{world.business['id']}/bookings", headers=world.customer.headers).status_code == 403

    assert client.get(f"/bookings/{first['id']}", headers=world.customer.headers).status_code == 200
    assert client.get(f"/bookings/{first['id']}", headers=world.owner.headers).status_code == 200
    assert client.get(f"/bookings/{first['id']}", headers=stranger.headers).status_code == 404


def test_a_business_with_bookings_cannot_be_deleted(client, world):
    make_booking(client, world)
    response = client.delete(f"/businesses/{world.business['id']}", headers=world.owner.headers)
    assert response.status_code == 409


# --- The race: many requests at once -----------------------------------------

def test_simultaneous_requests_for_one_slot_only_one_wins(client, world):
    start = monday_slots(client, world)[0]["start"]
    attempts = 8
    barrier = threading.Barrier(attempts)

    def attempt(_):
        own_client = TestClient(app)
        barrier.wait()  # release every request at the same moment
        return book(own_client, world.customer.headers, world.service["id"], start).status_code

    with ThreadPoolExecutor(max_workers=attempts) as pool:
        results = sorted(pool.map(attempt, range(attempts)))

    assert results == [201] + [409] * (attempts - 1)
    assert len(client.get("/bookings/me", headers=world.customer.headers).json()) == 1


def test_simultaneous_requests_for_overlapping_slots_only_one_wins(client, world):
    slots = monday_slots(client, world)
    starts = [slots[0]["start"], slots[2]["start"]]  # 9:00 and 9:30 overlap each other
    barrier = threading.Barrier(2)

    def attempt(start):
        own_client = TestClient(app)
        barrier.wait()
        return book(own_client, world.customer.headers, world.service["id"], start).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = sorted(pool.map(attempt, starts))

    assert results == [201, 409]


# --- LAYER 3 on its own: the database refuses, no matter what our code does --

def test_the_database_itself_refuses_overlapping_bookings(client, engine, world):
    second_business = create_business(client, world.owner.headers, name="Second Shop")
    second_service = create_service(client, world.owner.headers, second_business["id"])
    base = datetime(2030, 1, 7, 16, 0, tzinfo=UTC)
    hour = timedelta(hours=1)

    def row(start, end, *, business=world.business, service=world.service, status="confirmed"):
        return Booking(
            business_id=business["id"],
            service_id=service["id"],
            customer_id=world.customer.id,
            start_at=start,
            end_at=end,
            customer_timezone="UTC",
            status=status,
        )

    with Session(engine) as session:
        session.add(row(base, base + hour))
        session.commit()

    # An overlapping confirmed booking of the same business: refused by Postgres.
    with Session(engine) as session:
        session.add(row(base + timedelta(minutes=30), base + timedelta(minutes=90)))
        with pytest.raises(IntegrityError) as error:
            session.commit()
        assert error.value.orig.sqlstate == "23P01"  # exclusion_violation

    # Allowed: back to back, a cancelled booking, and another business at the same time.
    with Session(engine) as session:
        session.add(row(base + hour, base + 2 * hour))
        session.add(row(base, base + hour, status="cancelled"))
        session.add(row(base, base + hour, business=second_business, service=second_service))
        session.commit()


def test_a_booking_cannot_mix_one_business_with_anothers_service(client, engine, world):
    second_business = create_business(client, world.owner.headers, name="Second Shop")
    start = datetime(2030, 1, 7, 16, 0, tzinfo=UTC)

    with Session(engine) as session:
        session.add(
            Booking(
                business_id=second_business["id"],     # one business...
                service_id=world.service["id"],        # ...another business's service
                customer_id=world.customer.id,
                start_at=start,
                end_at=start + timedelta(hours=1),
                customer_timezone="UTC",
                status="confirmed",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
