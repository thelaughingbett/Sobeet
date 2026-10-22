"""Small time helpers shared by the availability and booking services."""
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings


def clinic_tz(clinic):
    return ZoneInfo(clinic.timezone)


def local_dt(day, wall_time, tz):
    """A clinic-local wall-clock time on `day`, as an aware datetime."""
    return datetime.combine(day, wall_time).replace(tzinfo=tz)


def day_bounds(day, tz):
    """[local midnight, next local midnight) for `day`."""
    return (
        local_dt(day, time.min, tz),
        local_dt(day + timedelta(days=1), time.min, tz),
    )


def overlaps(a_start, a_end, b_start, b_end):
    """Overlap test for half-open intervals [start, end)."""
    return a_start < b_end and a_end > b_start


def min_lead_time():
    """How far ahead a booking must be. Configurable via settings.MIN_LEAD_MINUTES."""
    return timedelta(minutes=getattr(settings, "MIN_LEAD_MINUTES", 60))
