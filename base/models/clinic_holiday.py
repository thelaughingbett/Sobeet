from django.db import models

from .base import BaseModel


class ClinicHoliday(BaseModel):
    """A clinic-wide closed day. Yearly holidays match on month and day only."""

    clinic = models.ForeignKey(
        "base.Clinic",
        on_delete=models.CASCADE,
        related_name="holidays"
    )
    holiday_date = models.DateField()
    name = models.CharField(max_length=150)
    is_yearly = models.BooleanField(
        default=False,
        help_text="If true, match on month and day only."
    )

    class Meta:
        ordering = ["holiday_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["clinic", "holiday_date"],
                name="clinicholiday_unique_clinic_date",
            ),
        ]

    def occurs_on(self, day):
        """True if this holiday closes the clinic on the given date."""
        if self.is_yearly:
            return (self.holiday_date.month, self.holiday_date.day) == (
                day.month,
                day.day,
            )
        return self.holiday_date == day

    def __str__(self):
        return f"{self.name} ({self.holiday_date})"
