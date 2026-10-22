from django.db import models

from .base import BaseModel


class Doctor(BaseModel):
    """Clinical profile attached to an Account."""

    class Status(models.TextChoices):
        INACTIVE = "inactive", "Inactive"
        ACTIVE = "active", "Active"
        ADJUNCT = "adjunct", "Adjunct"

    BOOKABLE_STATUSES = (Status.ACTIVE, Status.ADJUNCT)

    account = models.OneToOneField(
        "base.Account",
        on_delete=models.PROTECT,
        related_name="doctor"
    )
    clinic = models.ForeignKey(
        "base.Clinic",
        on_delete=models.PROTECT,
        related_name="doctors"
    )
    title = models.CharField(max_length=50, blank=True)
    speciality = models.CharField(max_length=150, blank=True)
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.ACTIVE
    )

    @property
    def is_bookable(self):
        return self.status in self.BOOKABLE_STATUSES

    def __str__(self):
        return f"{self.title} {self.account.full_name}".strip()
