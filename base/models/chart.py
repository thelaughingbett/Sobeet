from django.db import models

from .base import BaseModel


class Chart(BaseModel):
    """Medical record anchor. Kept out of the booking flow; needs its own access rules."""

    patient = models.ForeignKey(
        "base.Patient",
        on_delete=models.PROTECT,
        related_name="charts"
    )

    def __str__(self):
        return f"Chart for {self.patient}"
