import warnings
from datetime import UTC, datetime, timedelta

from app.models.interface import ApiInterface
from app.utils.time_utils import utc_now


def test_utc_now_is_naive():
    """The DateTime columns carry no timezone, so a value read back is naive.

    An aware default would make the same attribute aware before a flush and
    naive after a refresh, and comparing those two raises TypeError.
    """
    assert utc_now().tzinfo is None


def test_utc_now_is_utc_not_local_time():
    assert abs(utc_now() - datetime.now(UTC).replace(tzinfo=None)) < timedelta(seconds=5)


def test_utc_now_raises_no_deprecation_warning():
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        utc_now()


def test_timestamps_are_set_on_insert(db_session):
    before = utc_now()
    item = ApiInterface(name="n", url="https://api.example.com/x", method="GET", headers={}, body={})
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)

    assert before <= item.created_at <= utc_now()
    assert item.updated_at is not None


def test_stored_timestamp_stays_comparable_after_refresh(db_session):
    """The regression an aware default would cause: naive on the way back."""
    item = ApiInterface(name="n", url="https://api.example.com/x", method="GET", headers={}, body={})
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)

    assert item.created_at.tzinfo is None
    assert item.created_at < utc_now() + timedelta(seconds=1)
