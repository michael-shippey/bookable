"""Turn weekly opening hours into bookable time slots, across timezones.

No database and no web framework in here, only the standard library, so it
is easy to test thoroughly.

The core idea:
  * Opening hours are LOCAL wall-clock times in the business's timezone.
  * A slot is an exact moment, kept in UTC.
  * The customer asks for a day in THEIR timezone. We convert that day into a
    UTC range, convert the business's windows into UTC too, and compare.
Converting to exact UTC instants first is what makes daylight saving, half-hour
timezones and overnight windows work without special cases.

Daylight-saving rules used when a local time is odd:
  * A local time that does not exist (clocks spring forward) is read using the
    offset from BEFORE the change.
  * A local time that happens twice (clocks fall back) is read as its FIRST
    occurrence.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Iterable, NamedTuple, Protocol, Sequence
from zoneinfo import ZoneInfo

UTC = timezone.utc


class RuleLike(Protocol):
    """Anything with these attributes works: a database row or a plain Rule."""

    day_of_week: int  # 0 = Monday ... 6 = Sunday
    start_time: time | None
    end_time: time | None
    is_all_day: bool


class Rule(NamedTuple):
    day_of_week: int
    start_time: time | None
    end_time: time | None
    is_all_day: bool = False


@dataclass(frozen=True)
class Slot:
    start: datetime  # UTC
    end: datetime  # UTC


Window = tuple[datetime, datetime]  # (start, end) in UTC, end exclusive


def _local(day: date, at: time, tz: ZoneInfo) -> datetime:
    return datetime.combine(day, at, tzinfo=tz)


def rule_window_utc(rule: RuleLike, day: date, tz: ZoneInfo) -> Window:
    """The UTC window a rule produces on one specific local date.

    A window belongs to the day it starts on. If the end time is not later
    than the start time, the window ends on the following day.
    """
    if rule.is_all_day:
        start = _local(day, time.min, tz)
        end = _local(day + timedelta(days=1), time.min, tz)
    else:
        start = _local(day, rule.start_time, tz)
        end_day = day if rule.end_time > rule.start_time else day + timedelta(days=1)
        end = _local(end_day, rule.end_time, tz)
    return start.astimezone(UTC), end.astimezone(UTC)


def merge_windows(windows: Iterable[Window]) -> list[Window]:
    """Join windows that overlap or touch, so back-to-back windows (like two
    all-day rules on consecutive days) become one continuous stretch."""
    merged: list[Window] = []
    for start, end in sorted(windows):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def business_windows(
    rules: Iterable[RuleLike], tz: ZoneInfo, first_day: date, last_day: date
) -> list[Window]:
    """All of a business's opening windows that start between two local dates."""
    rules = list(rules)
    windows: list[Window] = []
    day = first_day
    while day <= last_day:
        for rule in rules:
            if rule.day_of_week == day.weekday():
                start, end = rule_window_utc(rule, day, tz)
                if end > start:  # skips a window squeezed to nothing by a clock change
                    windows.append((start, end))
        day += timedelta(days=1)
    return merge_windows(windows)


def generate_slots(
    rules: Iterable[RuleLike],
    business_tz: ZoneInfo,
    customer_tz: ZoneInfo,
    customer_date: date,
    duration_minutes: int,
    now: datetime,
    step_minutes: int = 15,
    busy: Sequence[Window] = (),
) -> list[Slot]:
    """Every bookable slot that STARTS on customer_date in the customer's timezone.

    A slot may end after the customer's midnight; only its start has to fall
    within their day. Slots start at the opening time of their window and step
    forward by step_minutes. Slots in the past, or overlapping a busy interval
    (an existing booking), are left out.
    """
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    if duration_minutes <= 0 or step_minutes <= 0:
        raise ValueError("duration_minutes and step_minutes must be positive")

    # The customer's local day, as an exact range of UTC instants. On a
    # daylight-saving day this range is 23 or 25 hours long, and that is correct.
    range_start = _local(customer_date, time.min, customer_tz).astimezone(UTC)
    range_end = _local(
        customer_date + timedelta(days=1), time.min, customer_tz
    ).astimezone(UTC)

    # Look one day back (an overnight window may spill into our range) and one
    # day past the end (a slot near the end of the range may need a window that
    # continues into the next day).
    first_day = range_start.astimezone(business_tz).date() - timedelta(days=1)
    last_day = range_end.astimezone(business_tz).date() + timedelta(days=1)
    windows = business_windows(rules, business_tz, first_day, last_day)

    step = timedelta(minutes=step_minutes)
    length = timedelta(minutes=duration_minutes)

    slots: list[Slot] = []
    for window_start, window_end in windows:
        start = window_start
        while start + length <= window_end:
            end = start + length
            if (
                range_start <= start < range_end
                and start > now
                and not any(start < b_end and b_start < end for b_start, b_end in busy)
            ):
                slots.append(Slot(start, end))
            start += step
    return slots
