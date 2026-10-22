"""Validate a requested slot with a specific coded error for each rule.

Shared by booking and rescheduling, so a new slot is always validated like a fresh
booking. Checks run in the order documented in docs/ERROR_CODES.md.
"""
from datetime import time, timedelta

from django.utils import timezone

from base.utils.errors import (
    APT002,
    APT003,
    APT004,
    APT005,
    APT006,
    APT007,
    APT008,
    APT009,
    APT015,
    APT016,
    DOC002,
)
from base.models import Appointment, TimeOff

from .availability import get_working_block, is_clinic_holiday
from .timeutils import clinic_tz, local_dt, min_lead_time, overlaps


def _fmt(local_dt_value):
    return local_dt_value.strftime("%Y-%m-%d %H:%M")


def validate_slot(doctor, start_at, *, patient=None, now=None, exclude_appointment_id=None):
    """
    Raise a coded ClinicError if `start_at` is not a bookable slot. Returns the slot's end_at.

    `exclude_appointment_id` lets a reschedule ignore the appointment being moved.
    The final "already taken" check here gives a friendly error; the database
    constraint is what actually guarantees no double booking under concurrency.

    `patient` is the person the slot is for; it enables the patient-side checks.
    `exclude_appointment_id` lets a reschedule ignore the appointment being moved.
    """
    now = now or timezone.now()
    clinic = doctor.clinic
    tz = clinic_tz(clinic)
    step = timedelta(minutes=clinic.slot_minutes)

    # Doctor must be bookable.
    if not doctor.is_bookable:
        raise DOC002(detail=f"{doctor} is not accepting appointments.")

    local_start = start_at.astimezone(tz)
    local_end = local_start + step
    day = local_start.date()
    block = get_working_block(doctor, day)

    # Slot boundary. The grid is anchored at the start of the working block
    # (or local midnight if there is none), matching how availability cuts slots.
    anchor = local_dt(day, block.start_time if block else time.min, tz)
    if (local_start - anchor) % step != timedelta(0):
        raise APT005(
            detail=f"{_fmt(local_start)} does not line up with {clinic.slot_minutes}-minute slots."
        )

    # Past, then minimum lead time.
    if start_at < now:
        raise APT003(detail=f"{_fmt(local_start)} is in the past.")
    if start_at < now + min_lead_time():
        minutes = int(min_lead_time().total_seconds() // 60)
        raise APT004(
            detail=f"Appointments must be booked at least {minutes} minutes in advance."
        )

    # Working hours.
    if (
        block is None
        or local_start < local_dt(day, block.start_time, tz)
        or local_end > local_dt(day, block.end_time, tz)
    ):
        raise APT006(
            detail=f"{doctor} does not work at {_fmt(local_start)}."
        )

    # Lunch.
    if overlaps(
        local_start,
        local_end,
        local_dt(day, clinic.lunch_start, tz),
        local_dt(day, clinic.lunch_end, tz),
    ):
        raise APT007(
            detail=(
                f"The clinic is closed for lunch from {clinic.lunch_start:%H:%M} "
                f"to {clinic.lunch_end:%H:%M}."
            )
        )

    # Clinic holiday.
    if is_clinic_holiday(clinic, day):
        raise APT008(detail=f"The clinic is closed on {day.isoformat()}.")

    end_at = start_at + step

    # Doctor time off.
    if TimeOff.objects.filter(
        doctor=doctor, start_at__lt=end_at, end_at__gt=start_at
    ).exists():
        raise APT009(detail=f"{doctor} is unavailable at {_fmt(local_start)}.")

    # Slot already taken. If the patient holds it themselves, say so.
    taken = Appointment.objects.filter(
        doctor=doctor,
        state=Appointment.State.BOOKED,
        start_at__lt=end_at,
        end_at__gt=start_at,
    )
    if exclude_appointment_id is not None:
        taken = taken.exclude(pk=exclude_appointment_id)

    if taken.exists():
        if patient is not None and taken.filter(patient=patient).exists():
            raise APT015(detail="You are already booked for this session.")
        raise APT002(
            detail=f"{doctor} is already booked at {_fmt(local_start)}. Please pick another slot."
        )

    # The patient can't be in two places at once.
    if patient is not None:
        clash = Appointment.objects.filter(
            patient=patient,
            state=Appointment.State.BOOKED,
            start_at__lt=end_at,
            end_at__gt=start_at,
        ).select_related("doctor__account")
        if exclude_appointment_id is not None:
            clash = clash.exclude(pk=exclude_appointment_id)

        other = clash.first()
        if other is not None:
            raise APT016(
                detail=(
                    f"You already have an appointment with {other.doctor} "
                    f"at {_fmt(other.start_at.astimezone(tz))}."
                )
            )

    return end_at
