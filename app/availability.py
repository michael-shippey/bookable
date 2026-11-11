"""Pure scheduling helpers: no database, no web framework, easy to test.

Everything here works in whole minutes. A week is 7 * 1440 = 10080 minutes,
counted from Monday 00:00 (local time). Because the week repeats, a window
that runs past Sunday midnight wraps around to the start of Monday.
"""

from datetime import time

MINUTES_PER_DAY = 1440
WEEK_MINUTES = 7 * MINUTES_PER_DAY

Segment = tuple[int, int]  # (start_minute, end_minute), end exclusive


def _minute_of_day(value: time) -> int:
    return value.hour * 60 + value.minute


def window_length(start_time: time | None, end_time: time | None, is_all_day: bool) -> int:
    """How many minutes the window lasts. End <= start means it passes midnight."""
    if is_all_day:
        return MINUTES_PER_DAY
    start, end = _minute_of_day(start_time), _minute_of_day(end_time)
    return end - start if end > start else end + MINUTES_PER_DAY - start


def weekly_segments(
    day_of_week: int, start_time: time | None, end_time: time | None, is_all_day: bool
) -> list[Segment]:
    """Place a window on the weekly timeline.

    Returns one segment normally, or two when the window wraps from the end
    of Sunday back to the start of Monday.
    """
    first_minute = 0 if is_all_day else _minute_of_day(start_time)
    start = day_of_week * MINUTES_PER_DAY + first_minute
    end = start + window_length(start_time, end_time, is_all_day)

    if end <= WEEK_MINUTES:
        return [(start, end)]
    return [(start, WEEK_MINUTES), (0, end - WEEK_MINUTES)]


def segments_overlap(a: list[Segment], b: list[Segment]) -> bool:
    """True if any piece of a shares time with any piece of b.

    Windows that only touch (one ends exactly when the other starts) do not
    overlap.
    """
    return any(a0 < b1 and b0 < a1 for a0, a1 in a for b0, b1 in b)
