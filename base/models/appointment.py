from django.db import models
from django.db.models import F, Func, Q

from .base import BaseModel


class Appointment(BaseModel):
    """A claim on a doctor's time. Only `booked` appointments hold a slot."""

    class State(models.TextChoices):
        BOOKED = "booked", "Booked"
        CANCELLED = "cancelled", "Cancelled"
        RESCHEDULED = "rescheduled", "Rescheduled"
        EXECUTED = "executed", "Executed"
        NO_SHOW = "no_show", "No show"

    patient = models.ForeignKey(
        "base.Patient",
        on_delete=models.PROTECT,
        related_name="appointments"
    )
    doctor = models.ForeignKey(
        "base.Doctor",
        on_delete=models.PROTECT,
        related_name="appointments"
    )
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    state = models.CharField(
        max_length=12,
        choices=State.choices,
        default=State.BOOKED
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancel_reason = models.CharField(max_length=255, blank=True)
    rescheduled_from = models.OneToOneField(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="rescheduled_to",
    )

    class Meta:
        ordering = ["start_at"]
        indexes = [
            models.Index(
                fields=["doctor", "start_at"],
                name="appt_doctor_start_idx"
            ),
            models.Index(
                fields=["patient", "start_at"],
                name="appt_patient_start_idx"
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(end_at__gt=F("start_at")),
                name="appointment_end_after_start",
            ),

            models.CheckConstraint(
                condition=~Q(state="cancelled") | Q(
                    cancelled_at__isnull=False),
                name="appointment_cancelled_has_timestamp",
            ),
            # No two booked appointments for the same doctor may start at the same time.
            # cancelled / rescheduled rows are excluded so they free the slot.
            models.UniqueConstraint(
                fields=["doctor", "start_at"],
                condition=Q(state="booked"),
                name="appointment_unique_booked_slot",
            ),

        ]

    @property
    def holds_slot(self):
        return self.state == self.State.BOOKED

    def __str__(self):
        return f"{self.patient} with {self.doctor} at {self.start_at:%Y-%m-%d %H:%M} [{self.state}]"
