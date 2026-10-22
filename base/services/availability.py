"""Availability service. Read-only: computes free slots, never writes.

Slots are never stored. For a doctor and a date we start from the doctor's working
hours and remove everything that blocks them (see README section 5).
"""
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.db.models import Q
from django.utils import timezone

from base.models import Appointment, ClinicHoliday, TimeOff, WorkingHours

from .lookups import get_doctor
from .timeutils import clinic_tz, day_bounds, local_dt, min_lead_time, overlaps


@dataclass(frozen=True)
class Slot:
    start_at: datetime
    end_at: datetime

    def to_dict(self):
        return {
            "start_at": self.start_at.isoformat(),
            "end_at": self.end_at.isoformat(),
        }


def is_clinic_holiday(clinic, day):
    """True if `day` is a holiday for the clinic (exact date, or month and day if yearly)."""
    return (
        ClinicHoliday.objects.filter(clinic=clinic)
        .filter(
            Q(holiday_date=day)
            | Q(is_yearly=True, holiday_date__month=day.month, holiday_date__day=day.day)
        )
        .exists()
    )


def get_working_block(doctor, day):
    """The doctor's working hours row for the weekday of `day`, or None."""
    return WorkingHours.objects.filter(
        doctor=doctor,
        weekday=WorkingHours.weekday_for(day)
    ).first()


def get_free_slots(doctor, day, *, now=None):
    """All free slots for `doctor` on the clinic-local date `day`, in time order."""
    now = now or timezone.now()

    # 1. Doctor must be bookable (active or adjunct).
    if not doctor.is_bookable:
        return []

    clinic = doctor.clinic

    # 2. Clinic holiday.
    if is_clinic_holiday(clinic, day):
        return []

    # 3. Working hours for that weekday, cut into slot_minutes pieces.
    block = get_working_block(doctor, day)
    if block is None:
        return []

    tz = clinic_tz(clinic)
    step = timedelta(minutes=clinic.slot_minutes)
    block_start = local_dt(day, block.start_time, tz)
    block_end = local_dt(day, block.end_time, tz)
    lunch_start = local_dt(day, clinic.lunch_start, tz)
    lunch_end = local_dt(day, clinic.lunch_end, tz)

    # Fetch what can block slots on this day in two queries, not one per slot.
    day_start, day_end = day_bounds(day, tz)
    time_off = list(
        TimeOff.objects.filter(
            doctor=doctor, start_at__lt=day_end, end_at__gt=day_start
        ).values_list("start_at", "end_at")
    )
    booked = list(
        Appointment.objects.filter(
            doctor=doctor,
            state=Appointment.State.BOOKED,
            start_at__lt=day_end,
            end_at__gt=day_start,
        ).values_list("start_at", "end_at")
    )

    # 7. Slots must start at or after now + the minimum lead time (this also removes the past).
    earliest = now + min_lead_time()

    slots = []
    cursor = block_start
    while cursor + step <= block_end:
        start, end = cursor, cursor + step
        cursor = end

        if start < earliest:
            continue
        # 4. Lunch.
        if overlaps(start, end, lunch_start, lunch_end):
            continue
        # 5. Time off.
        if any(overlaps(start, end, off_start, off_end) for off_start, off_end in time_off):
            continue
        # 6. Already booked.
        if any(overlaps(start, end, b_start, b_end) for b_start, b_end in booked):
            continue

        slots.append(Slot(start_at=start, end_at=end))

    return slots


def get_free_slots_for_doctor(doctor_id, day, *, now=None):
    """Same as get_free_slots, but takes a doctor id and raises DOC001 if it doesn't exist."""
    return get_free_slots(get_doctor(doctor_id), day, now=now)
