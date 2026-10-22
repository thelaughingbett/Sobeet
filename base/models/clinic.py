import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q

from .base import BaseModel


def validate_timezone(value):
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValidationError(f"'{value}' is not a valid IANA timezone name.")


class Clinic(BaseModel):
    """The location. Holds clinic-wide scheduling rules."""

    name = models.CharField(max_length=150)
    timezone = models.CharField(
        max_length=64,
        default="Africa/Nairobi",
        validators=[validate_timezone],
        help_text="IANA name, e.g. Africa/Nairobi",
    )
    slot_minutes = models.PositiveSmallIntegerField(default=30)
    lunch_start = models.TimeField(default=datetime.time(12, 30))
    lunch_end = models.TimeField(default=datetime.time(13, 30))

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(slot_minutes__gt=0),
                name="clinic_slot_minutes_positive",
            ),
            models.CheckConstraint(
                condition=Q(lunch_end__gt=F("lunch_start")),
                name="clinic_lunch_end_after_start",
            ),
        ]

    def __str__(self):
        return self.name
