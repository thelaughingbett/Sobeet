"""Booking service. Creates, cancels, and reschedules appointments.

Validation lives in slot_validation. The database exclusion constraint on
booked appointments is what finally guarantees no double booking, so an
IntegrityError on insert is reported as APT002 ("slot already taken").
"""
from django.db import IntegrityError, transaction
from django.utils import timezone

from base.utils.errors import APT002, APT011, APT012, APT013, APT014
from base.models import Appointment, Patient

from .lookups import get_appointment, get_doctor, get_patient
from .slot_validation import validate_slot


def _create_booked(*, patient, doctor, start_at, end_at, rescheduled_from=None):
    """Insert a booked appointment, turning a constraint violation into APT002."""
    try:
        # Savepoint, so a failed insert doesn't poison an enclosing transaction.
        with transaction.atomic():
            return Appointment.objects.create(
                patient=patient,
                doctor=doctor,
                start_at=start_at,
                end_at=end_at,
                state=Appointment.State.BOOKED,
                rescheduled_from=rescheduled_from,
            )
    except IntegrityError as exc:
        raise APT002(
            detail="That slot was just taken by someone else. Please pick another slot."
        ) from exc


def _require_booked(appointment):
    if appointment.state == Appointment.State.CANCELLED:
        raise APT011(detail="This appointment has already been cancelled.")
    if appointment.state != Appointment.State.BOOKED:
        raise APT012(
            detail=f"Only booked appointments can be changed; this one is {appointment.state}."
        )


def book_appointment(*, patient_id, doctor_id, start_at, now=None):
    """Book a slot. `start_at` must be an aware datetime (see parsing.parse_start_at)."""
    doctor = get_doctor(doctor_id)
    # however you already load it (PAT001 if missing)
    patient = get_patient(patient_id)
    end_at = validate_slot(doctor, start_at, patient=patient, now=now)

    return _create_booked(
        patient=patient,
        doctor=doctor,
        start_at=start_at,
        end_at=end_at
    )


@transaction.atomic
def cancel_appointment(*, appointment_id, reason, now=None):
    """Cancel a booked appointment. The slot becomes bookable again."""
    reason = (reason or "").strip()
    if not reason:
        raise APT013(detail="Please provide a reason for cancelling.")

    appointment = get_appointment(appointment_id, for_update=True)
    _require_booked(appointment)

    appointment.state = Appointment.State.CANCELLED
    appointment.cancelled_at = now or timezone.now()
    appointment.cancel_reason = reason
    appointment.save(
        update_fields=["state", "cancelled_at", "cancel_reason", "updated_at"]
    )
    return appointment


@transaction.atomic
def reschedule_appointment(*, appointment_id, start_at, now=None):
    """Move a booked appointment to a new slot with the same doctor.

    The old appointment becomes `rescheduled` (releasing its slot) and a new
    `booked` appointment points back to it. Any failure rolls back both steps,
    so the original stays booked.
    """
    appointment = get_appointment(appointment_id, for_update=True)
    _require_booked(appointment)

    if start_at == appointment.start_at:
        raise APT014(detail="The new slot is the same as the current one.")

    # The new slot is validated exactly like a fresh booking.
    Patient.objects.select_for_update().get(pk=appointment.patient_id)

    end_at = validate_slot(
        appointment.doctor,
        start_at,
        patient=appointment.patient,
        now=now,
        exclude_appointment_id=appointment.pk,
    )

    appointment.state = Appointment.State.RESCHEDULED
    appointment.save(update_fields=["state", "updated_at"])

    return _create_booked(
        patient=appointment.patient,
        doctor=appointment.doctor,
        start_at=start_at,
        end_at=end_at,
        rescheduled_from=appointment,
    )


def list_upcoming_appointments(*, patient_id, now=None):
    """A patient's upcoming booked appointments, soonest first."""
    patient = get_patient(patient_id)
    now = now or timezone.now()
    return (
        Appointment.objects.filter(
            patient=patient,
            state=Appointment.State.BOOKED,
            start_at__gte=now,
        )
        .select_related("doctor__account")
        .order_by("start_at")
    )
