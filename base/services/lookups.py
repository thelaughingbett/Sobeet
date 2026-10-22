"""Fetch records by id, raising the matching coded 404 when they are missing."""
from django.core.exceptions import ValidationError as DjangoValidationError

from base.utils.errors import APT001, DOC001, PAT001
from base.models import Appointment, Doctor, Patient

# A malformed UUID raises ValidationError (or ValueError / TypeError) rather than DoesNotExist.
_BAD_ID = (DjangoValidationError, ValueError, TypeError)


def get_doctor(doctor_id):
    try:
        return Doctor.objects.select_related("clinic", "account").get(pk=doctor_id)
    except (Doctor.DoesNotExist, *_BAD_ID):
        raise DOC001(detail="No doctor found with that id.") from None


def get_patient(patient_id):
    try:
        return Patient.objects.select_related("account").get(pk=patient_id)
    except (Patient.DoesNotExist, *_BAD_ID):
        raise PAT001(detail="No patient found with that id.") from None


def get_appointment(appointment_id, *, for_update=False):
    """Must be called inside a transaction when for_update=True."""
    queryset = Appointment.objects.select_related(
        "doctor__clinic", "doctor__account", "patient__account"
    )
    if for_update:
        queryset = queryset.select_for_update(of=("self",))
    try:
        return queryset.get(pk=appointment_id)
    except (Appointment.DoesNotExist, *_BAD_ID):
        raise APT001(detail="No appointment found with that id.") from None
