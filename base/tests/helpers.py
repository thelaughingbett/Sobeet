"""Shared helpers for the tests: a fixed clock, small factories, and a base test case."""
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.test import TestCase

from base.utils.errors import ClinicError
from base.models import Account, Appointment, Clinic, Doctor, Patient, WorkingHours
from base.services import book_appointment

NAIROBI = ZoneInfo("Africa/Nairobi")

# A fixed "now" so no test depends on the real clock: Monday 2 November 2026, 08:00.
NOW = datetime(2026, 11, 2, 8, 0, tzinfo=NAIROBI)
SUNDAY = date(2026, 11, 1)
MONDAY = date(2026, 11, 2)
TUESDAY = date(2026, 11, 3)

# Weekday numbers in this system: Sunday = 1 ... Saturday = 7.
MON_TO_FRI = (2, 3, 4, 5, 6)


def at(day, hour, minute=0):
    """A clinic-local (Nairobi) datetime on `day`."""
    return datetime.combine(day, time(hour, minute), tzinfo=NAIROBI)


def make_clinic(**overrides):
    overrides.setdefault("name", "Test Clinic")
    return Clinic.objects.create(**overrides)


def make_doctor(
    clinic,
    *,
    email="amina@example.com",
    name="Amina Otieno",
    status=Doctor.Status.ACTIVE,
    weekdays=MON_TO_FRI,
    start=time(9, 0),
    end=time(17, 0),
):
    account = Account.objects.create_user(
        email, password=None, full_name=name, role=Account.Role.DOCTOR
    )
    doctor = Doctor.objects.create(
        account=account, clinic=clinic, title="Dr.", speciality="GP", status=status
    )
    for weekday in weekdays:
        WorkingHours.objects.create(
            doctor=doctor, weekday=weekday, start_time=start, end_time=end
        )
    return doctor


def make_patient(*, email="wanjiru@example.com", name="Wanjiru Kamau"):
    account = Account.objects.create_user(
        email, password=None, full_name=name, role=Account.Role.PATIENT
    )
    return Patient.objects.create(account=account)


def make_appointment(
    patient, doctor, start_at, *, state=Appointment.State.BOOKED, minutes=30, **extra
):
    """Insert an appointment directly, bypassing the booking rules."""
    return Appointment.objects.create(
        patient=patient,
        doctor=doctor,
        start_at=start_at,
        end_at=start_at + timedelta(minutes=minutes),
        state=state,
        **extra,
    )


class ClinicTestCase(TestCase):
    """One clinic (Africa/Nairobi, 30-minute slots, lunch 12:30-13:30), one doctor
    working Mon-Fri 09:00-17:00, and two patients."""

    def setUp(self):
        self.clinic = make_clinic()
        self.doctor = make_doctor(self.clinic)
        self.patient = make_patient()
        self.other_patient = make_patient(
            email="brian@example.com", name="Brian Otieno"
        )

    def book(self, start_at, *, patient=None, doctor=None, now=NOW):
        return book_appointment(
            patient_id=(patient or self.patient).pk,
            doctor_id=(doctor or self.doctor).pk,
            start_at=start_at,
            now=now,
        )

    @contextmanager
    def assertError(self, code):
        """Assert the block raises a ClinicError with this code."""
        with self.assertRaises(ClinicError) as ctx:
            yield
        self.assertEqual(ctx.exception.code, code)
