import datetime

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction

from base.models import Account, Clinic, Doctor, WorkingHours
from base.utils.errors import GEN002, GEN004


def _get_clinic(clinic_id):
    try:
        return Clinic.objects.get(pk=clinic_id)
    except (Clinic.DoesNotExist, ValueError, DjangoValidationError):
        raise GEN002(detail="The clinic does not exist.")


def _parse_working_hours(items):
    """Validate the optional working_hours list. Returns a list of (weekday, start, end)."""
    if not isinstance(items, list):
        raise GEN004(detail="working_hours must be a list.")

    parsed, seen = [], set()
    for item in items:
        if not isinstance(item, dict):
            raise GEN004(detail="Each working_hours entry must be an object.")
        weekday = item.get("weekday")
        if (
            isinstance(weekday, bool)
            or not isinstance(weekday, int)
            or weekday not in WorkingHours.Weekday.values
        ):
            raise GEN004(
                detail="weekday must be an integer from 1 (Sunday) to 7 (Saturday).")
        if weekday in seen:
            raise GEN004(
                detail=f"Duplicate working_hours entry for weekday {weekday}.")
        seen.add(weekday)

        try:
            start = datetime.time.fromisoformat(item.get("start_time"))
            end = datetime.time.fromisoformat(item.get("end_time"))
        except (TypeError, ValueError):
            raise GEN004(
                detail="start_time and end_time must be HH:MM strings.")
        if end <= start:
            raise GEN004(detail="end_time must be after start_time.")
        parsed.append((weekday, start, end))
    return parsed


@transaction.atomic
def create_doctor(*, email, full_name, clinic_id, phone_no="", title="",
                  speciality="", status=Doctor.Status.ACTIVE, working_hours=()):
    email = email.strip().lower()
    if status not in Doctor.Status.values:
        raise GEN004(detail="status must be one of: " +
                     ", ".join(Doctor.Status.values) + ".")

    clinic = _get_clinic(clinic_id)
    hours = _parse_working_hours(list(working_hours))

    if Account.objects.filter(email=email).exists():
        raise GEN004(detail="An account with this email already exists.")

    account = Account.objects.create_user(
        email=email,
        password=None,
        full_name=full_name,
        phone_no=phone_no,
        role=Account.Role.DOCTOR,
    )
    doctor = Doctor.objects.create(
        account=account,
        clinic=clinic,
        title=title,
        speciality=speciality,
        status=status,
    )
    WorkingHours.objects.bulk_create(
        WorkingHours(doctor=doctor, weekday=w, start_time=s, end_time=e)
        for w, s, e in hours
    )
    return doctor


def list_doctors(*, clinic_id=None, status=None):
    doctors = (
        Doctor.objects.select_related("account")
        .prefetch_related("working_hours")
        .order_by("account__full_name")
    )
    if status:
        if status not in Doctor.Status.values:
            raise GEN004(detail="status must be one of: " +
                         ", ".join(Doctor.Status.values) + ".")
        doctors = doctors.filter(status=status)
    if clinic_id:
        _get_clinic(clinic_id)  # coded 404 for a bad or unknown clinic
        doctors = doctors.filter(clinic_id=clinic_id)
    return doctors
