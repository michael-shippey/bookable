from zoneinfo import ZoneInfo


def validate_timezone(value: str) -> str:
    """Accept only real IANA timezone names, like 'America/Boise' or 'UTC'."""
    try:
        ZoneInfo(value)
    except (KeyError, ValueError, OSError):
        raise ValueError("Unknown timezone (use a name like 'America/Boise' or 'UTC')")
    return value
