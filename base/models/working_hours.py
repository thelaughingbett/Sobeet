from django.db import models
from django.db.models import F, Q

from .base import BaseModel


class WorkingHours(BaseModel):
    """One block per doctor per working weekday. Weekdays run Sunday = 1 to Saturday = 7."""

    class Weekday(models.IntegerChoices):
        SUNDAY = 1, "Sunday"
        MONDAY = 2, "Monday"
        TUESDAY = 3, "Tuesday"
        WEDNESDAY = 4, "Wednesday"
        THURSDAY = 5, "Thursday"
        FRIDAY = 6, "Friday"
        SATURDAY = 7, "Saturday"

    doctor = models.ForeignKey(
        "base.Doctor",
        on_delete=models.CASCADE,
        related_name="working_hours"
    )
    weekday = models.PositiveSmallIntegerField(choices=Weekday.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        verbose_name_plural = "working hours"
        ordering = ["doctor", "weekday"]
        constraints = [
            models.CheckConstraint(
                condition=Q(weekday__gte=1, weekday__lte=7),
                name="workinghours_weekday_1_to_7",
            ),
            models.CheckConstraint(
                condition=Q(end_time__gt=F("start_time")),
                name="workinghours_end_after_start",
            ),
            models.UniqueConstraint(
                fields=["doctor", "weekday"],
                name="workinghours_one_block_per_weekday",
            ),
        ]

    @staticmethod
    def weekday_for(day):
        """Map a date to this system's weekday number (Sunday = 1)."""
        return (day.isoweekday() % 7) + 1

    def __str__(self):
        return (
            f"{self.doctor} {self.get_weekday_display()} "
            f"{self.start_time:%H:%M}-{self.end_time:%H:%M}"
        )
