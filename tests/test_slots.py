from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

from app.slots import Rule, generate_slots

UTC = timezone.utc
BOISE = ZoneInfo("America/Boise")      # UTC-6 in summer, UTC-7 in winter
TOKYO = ZoneInfo("Asia/Tokyo")         # UTC+9, no daylight saving
KOLKATA = ZoneInfo("Asia/Kolkata")     # UTC+5:30, a half-hour offset
LONG_AGO = datetime(2026, 1, 1, tzinfo=UTC)  # so nothing counts as "in the past"

# Calendar facts used below (2026): Mon Nov 2, Fri Nov 6, Sat Oct 31, Sun Nov 1.
# US clocks fall back on Sun Nov 1 and spring forward on Sun Mar 8.


def utc(year, month, day, hour=0, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


def slots(rules, business_tz, customer_tz, day, duration=60, step=60,
          now=LONG_AGO, busy=()):
    return generate_slots(
        rules=rules,
        business_tz=business_tz,
        customer_tz=customer_tz,
        customer_date=day,
        duration_minutes=duration,
        now=now,
        step_minutes=step,
        busy=busy,
    )


MON_9_TO_5 = [Rule(0, time(9), time(17))]


# --- Same timezone ------------------------------------------------------------

def test_simple_day_same_timezone():
    result = slots(MON_9_TO_5, BOISE, BOISE, date(2026, 11, 2))
    assert len(result) == 8  # starts at 9,10,...,16 local
    assert result[0].start == utc(2026, 11, 2, 16)   # 9:00 MST
    assert result[-1].start == utc(2026, 11, 2, 23)  # 16:00 MST
    assert result[-1].end == utc(2026, 11, 3, 0)     # 17:00 MST, closing time


def test_long_service_must_fit_before_closing():
    # 90-minute service, every 30 minutes: last start is 15:30
    result = slots(MON_9_TO_5, BOISE, BOISE, date(2026, 11, 2), duration=90, step=30)
    assert len(result) == 14
    assert result[-1].end == utc(2026, 11, 3, 0)


def test_day_with_no_rule_has_no_slots():
    assert slots(MON_9_TO_5, BOISE, BOISE, date(2026, 11, 3)) == []


# --- Different timezones ------------------------------------------------------

def test_tokyo_customer_sees_the_business_day_on_their_next_day():
    # Boise Mon 9-5 (MST) is Tue 01:00-09:00 in Tokyo.
    tuesday = slots(MON_9_TO_5, BOISE, TOKYO, date(2026, 11, 3))
    assert len(tuesday) == 8
    assert tuesday[0].start.astimezone(TOKYO).hour == 1
    assert tuesday[0].start.astimezone(TOKYO).day == 3
    # The same business hours do NOT show up on Tokyo's Monday.
    assert slots(MON_9_TO_5, BOISE, TOKYO, date(2026, 11, 2)) == []


def test_half_hour_timezone():
    rules = [Rule(0, time(9), time(17))]
    result = slots(rules, KOLKATA, UTC, date(2026, 11, 2))
    assert len(result) == 8
    assert result[0].start == utc(2026, 11, 2, 3, 30)  # 9:00 IST


def test_slots_are_identical_instants_for_every_customer():
    boise = slots(MON_9_TO_5, BOISE, BOISE, date(2026, 11, 2))
    tokyo = slots(MON_9_TO_5, BOISE, TOKYO, date(2026, 11, 3))
    assert [s.start for s in boise] == [s.start for s in tokyo]


# --- Overnight windows --------------------------------------------------------

FRI_NIGHT = [Rule(4, time(20), time(2))]  # Friday 20:00 to Saturday 02:00


def test_overnight_window_on_its_own_day():
    result = slots(FRI_NIGHT, BOISE, BOISE, date(2026, 11, 6))  # Friday
    assert len(result) == 4  # 20, 21, 22, 23


def test_overnight_window_spills_into_next_day_without_a_rule_for_it():
    result = slots(FRI_NIGHT, BOISE, BOISE, date(2026, 11, 7))  # Saturday
    assert len(result) == 2  # 00:00 and 01:00 (the last one ends at 02:00)


def test_overnight_slot_can_end_after_customer_midnight():
    result = slots(FRI_NIGHT, BOISE, BOISE, date(2026, 11, 6))
    last = result[-1]  # starts 23:00 Friday, ends 00:00 Saturday
    assert last.start.astimezone(BOISE).day == 6
    assert last.end.astimezone(BOISE).day == 7


# --- Merging windows (24-hour businesses) -------------------------------------

def test_all_day_rules_on_consecutive_days_join_up():
    rules = [Rule(0, None, None, True), Rule(1, None, None, True)]
    result = slots(rules, BOISE, BOISE, date(2026, 11, 2), duration=60, step=30)
    # 23:30 on Monday fits because Tuesday continues straight on.
    assert len(result) == 48
    assert result[-1].start.astimezone(BOISE).strftime("%H:%M") == "23:30"


def test_single_all_day_rule_stops_at_midnight():
    rules = [Rule(0, None, None, True)]
    result = slots(rules, BOISE, BOISE, date(2026, 11, 2), duration=60, step=30)
    assert len(result) == 47  # 23:30 would run past the end of Monday's window


# --- Daylight saving ----------------------------------------------------------

def test_all_day_on_fall_back_day_has_25_hours():
    rules = [Rule(6, None, None, True)]  # Sunday
    result = slots(rules, BOISE, BOISE, date(2026, 11, 1))
    assert len(result) == 25


def test_all_day_on_spring_forward_day_has_23_hours():
    rules = [Rule(6, None, None, True)]
    result = slots(rules, BOISE, BOISE, date(2026, 3, 8))
    assert len(result) == 23


def test_overnight_window_is_7_real_hours_on_fall_back_night():
    rules = [Rule(5, time(20), time(2))]  # Saturday 20:00 to Sunday 02:00
    result = slots(rules, BOISE, UTC, date(2026, 11, 1))
    assert len(result) == 7


def test_overnight_window_is_6_real_hours_on_spring_forward_night():
    rules = [Rule(5, time(20), time(2))]
    result = slots(rules, BOISE, UTC, date(2026, 3, 8))
    assert len(result) == 6


def test_wall_clock_hours_stay_put_across_a_daylight_saving_change():
    # Business opens at 09:00 local both before and after the clocks change,
    # which means different UTC instants.
    before = slots(MON_9_TO_5, BOISE, BOISE, date(2026, 10, 26))[0]
    after = slots(MON_9_TO_5, BOISE, BOISE, date(2026, 11, 2))[0]
    assert before.start.astimezone(BOISE).hour == 9
    assert after.start.astimezone(BOISE).hour == 9
    assert before.start.hour == 15 and after.start.hour == 16  # UTC differs


# --- Past slots and existing bookings -----------------------------------------

def test_past_slots_are_dropped():
    now = utc(2026, 11, 2, 19)  # 12:00 MST
    result = slots(MON_9_TO_5, BOISE, BOISE, date(2026, 11, 2), now=now)
    assert len(result) == 4  # 13, 14, 15, 16; a slot starting exactly now is gone


def test_busy_interval_blocks_only_overlapping_slots():
    busy = [(utc(2026, 11, 2, 17), utc(2026, 11, 2, 18))]  # 10:00-11:00 MST
    result = slots(MON_9_TO_5, BOISE, BOISE, date(2026, 11, 2), busy=busy)
    starts = [s.start.astimezone(BOISE).hour for s in result]
    assert starts == [9, 11, 12, 13, 14, 15, 16]


# --- Bad input ----------------------------------------------------------------

def test_naive_now_is_rejected():
    try:
        slots(MON_9_TO_5, BOISE, BOISE, date(2026, 11, 2), now=datetime(2026, 1, 1))
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_zero_duration_is_rejected():
    try:
        slots(MON_9_TO_5, BOISE, BOISE, date(2026, 11, 2), duration=0)
    except ValueError:
        return
    raise AssertionError("expected ValueError")
