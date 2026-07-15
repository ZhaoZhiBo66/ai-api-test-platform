from datetime import UTC, datetime


def utc_now() -> datetime:
    """Current UTC time, without a tzinfo.

    Replaces datetime.utcnow(), which is deprecated. The tzinfo is stripped on
    purpose: the DateTime columns carry no timezone, so a value read back is
    always naive. Defaulting to an aware value would make the same attribute
    aware before a flush and naive after a refresh, and comparing the two
    raises.
    """
    return datetime.now(UTC).replace(tzinfo=None)
