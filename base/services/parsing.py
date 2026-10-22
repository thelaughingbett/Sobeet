"""Turn raw request values into typed ones, raising coded 400s on bad input.

Called from the views, so the services themselves only deal with real datetimes and dates.
"""
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from base.utils.errors import APT010, AVL001


def parse_start_at(raw):
    """Parse an ISO 8601 timestamp that carries a UTC offset, e.g. 2026-11-03T10:00:00+03:00."""
    if raw in (None, ""):
        raise APT010(detail="start_at is required.")
    if not isinstance(raw, str):
        raise APT010(detail="start_at must be an ISO 8601 string.")
    try:
        value = parse_datetime(raw)
    except ValueError:
        value = None
    if value is None:
        raise APT010(
            detail="start_at must be an ISO 8601 timestamp, e.g. 2026-11-03T10:00:00+03:00."
        )
    if timezone.is_naive(value):
        raise APT010(
            detail="start_at must include a UTC offset, e.g. 2026-11-03T10:00:00+03:00."
        )
    return value


def parse_query_date(raw):
    """Parse a YYYY-MM-DD date from a query string."""
    if not raw:
        raise AVL001(detail="Query parameter 'date' is required (YYYY-MM-DD).")
    try:
        value = parse_date(raw)
    except ValueError:
        value = None
    if value is None:
        raise AVL001(
            detail="'date' must be a valid date in the format YYYY-MM-DD.")
    return value
