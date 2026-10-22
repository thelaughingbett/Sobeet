from django.db import models

from .base import BaseModel


class Patient(BaseModel):
    """Patient profile attached to an Account."""

    account = models.OneToOneField(
        "base.Account",
        on_delete=models.PROTECT,
        related_name="patient"
    )

    def __str__(self):
        return self.account.full_name
