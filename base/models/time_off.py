from django.db import models
from django.db.models import F, Q

from .base import BaseModel


class TimeOff(BaseModel):
    """A per-doctor absence over the half-open interval [start_at, end_at)."""

    class Reason(models.TextChoices):
        LEAVE = "leave", "Leave"
        SICK = "sick", "Sick"
        CONFERENCE = "conference", "Conference"
        OTHER = "other", "Other"

    doctor = models.ForeignKey(
        "base.Doctor",
        on_delete=models.CASCADE,
        related_name="time_off"
    )
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    reason = models.CharField(
        max_length=12,
        choices=Reason.choices,
        default=Reason.LEAVE
    )
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name_plural = "time off"
        ordering = ["start_at"]
        indexes = [
            models.Index(
                fields=["doctor", "start_at", "end_at"], name="timeoff_doc_range_idx"
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(end_at__gt=F("start_at")),
                name="timeoff_end_after_start",
            ),
        ]

    def __str__(self):
        return f"{self.doctor} off {self.start_at:%Y-%m-%d %H:%M} to {self.end_at:%Y-%m-%d %H:%M}"
