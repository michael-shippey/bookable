from datetime import time

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.availability import segments_overlap, weekly_segments, window_length
from app.main import app
from app.schemas.availability import RuleCreate

client = TestClient(app)

MON, FRI, SAT, SUN = 0, 4, 5, 6


# --- window_length -----------------------------------------------------------

def test_length_of_normal_window():
    assert window_length(time(9, 0), time(17, 0), False) == 480


def test_length_of_overnight_window():
    assert window_length(time(20, 0), time(2, 0), False) == 360


def test_end_at_midnight_means_end_of_day():
    assert window_length(time(9, 0), time(0, 0), False) == 900


def test_length_of_all_day_window():
    assert window_length(None, None, True) == 1440


# --- weekly_segments ---------------------------------------------------------

def test_simple_segment():
    assert weekly_segments(MON, time(9, 0), time(17, 0), False) == [(540, 1020)]


def test_overnight_segment_stays_in_week():
    # Friday 20:00 - Saturday 02:00
    start = FRI * 1440 + 20 * 60
    assert weekly_segments(FRI, time(20, 0), time(2, 0), False) == [(start, start + 360)]


def test_sunday_overnight_wraps_to_monday():
    segments = weekly_segments(SUN, time(20, 0), time(2, 0), False)
    assert segments == [(SUN * 1440 + 1200, 7 * 1440), (0, 120)]


# --- segments_overlap --------------------------------------------------------

def _seg(day, start, end, all_day=False):
    return weekly_segments(day, start, end, all_day)


def test_overlapping_windows_detected():
    a = _seg(MON, time(9, 0), time(17, 0))
    b = _seg(MON, time(12, 0), time(18, 0))
    assert segments_overlap(a, b)


def test_touching_windows_do_not_overlap():
    a = _seg(MON, time(9, 0), time(12, 0))
    b = _seg(MON, time(12, 0), time(17, 0))
    assert not segments_overlap(a, b)


def test_different_days_do_not_overlap():
    a = _seg(MON, time(9, 0), time(17, 0))
    b = _seg(1, time(9, 0), time(17, 0))
    assert not segments_overlap(a, b)


def test_friday_overnight_overlaps_early_saturday():
    friday = _seg(FRI, time(20, 0), time(2, 0))
    saturday = _seg(SAT, time(1, 0), time(5, 0))
    assert segments_overlap(friday, saturday)


def test_friday_overnight_does_not_overlap_later_saturday():
    friday = _seg(FRI, time(20, 0), time(2, 0))
    saturday = _seg(SAT, time(3, 0), time(5, 0))
    assert not segments_overlap(friday, saturday)


def test_sunday_overnight_overlaps_early_monday():
    sunday = _seg(SUN, time(20, 0), time(2, 0))
    monday = _seg(MON, time(1, 0), time(3, 0))
    assert segments_overlap(sunday, monday)


def test_all_day_overlaps_anything_that_day():
    all_day = _seg(MON, None, None, True)
    assert segments_overlap(all_day, _seg(MON, time(9, 0), time(10, 0)))


# --- RuleCreate validation ---------------------------------------------------

def test_normal_rule_accepted():
    rule = RuleCreate(day_of_week=0, start_time="09:00", end_time="17:00")
    assert rule.start_time == time(9, 0)


def test_overnight_rule_accepted():
    RuleCreate(day_of_week=4, start_time="20:00", end_time="02:00")


def test_all_day_rule_accepted():
    RuleCreate(day_of_week=5, is_all_day=True)


def test_all_day_rule_with_times_rejected():
    with pytest.raises(ValidationError):
        RuleCreate(day_of_week=5, is_all_day=True, start_time="09:00", end_time="17:00")


def test_missing_times_rejected():
    with pytest.raises(ValidationError):
        RuleCreate(day_of_week=0)


def test_equal_times_rejected():
    with pytest.raises(ValidationError):
        RuleCreate(day_of_week=0, start_time="09:00", end_time="09:00")


def test_seconds_rejected():
    with pytest.raises(ValidationError):
        RuleCreate(day_of_week=0, start_time="09:00:30", end_time="17:00")


def test_timezone_in_time_rejected():
    with pytest.raises(ValidationError):
        RuleCreate(day_of_week=0, start_time="09:00+02:00", end_time="17:00")


def test_bad_day_rejected():
    with pytest.raises(ValidationError):
        RuleCreate(day_of_week=7, start_time="09:00", end_time="17:00")


# --- Endpoints need a login --------------------------------------------------

def test_create_rule_requires_auth():
    response = client.post(
        "/businesses/1/availability/rules",
        json={"day_of_week": 0, "start_time": "09:00", "end_time": "17:00"},
    )
    assert response.status_code == 401


def test_delete_rule_requires_auth():
    response = client.delete("/businesses/1/availability/rules/1")
    assert response.status_code == 401
