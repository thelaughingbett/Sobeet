import uuid
from datetime import timedelta
from unittest.mock import patch

from django.db import IntegrityError, transaction

from base.models import Appointment, ClinicHoliday, Doctor, TimeOff
from base.services import book_appointment, list_upcoming_appointments

from .helpers import (
    MONDAY,
    NOW,
    SUNDAY,
    TUESDAY,
    ClinicTestCase,
    at,
    make_appointment,
)


class BookAppointmentTests(ClinicTestCase):
    def test_books_a_free_slot(self):
        appointment = self.book(at(MONDAY, 10))

        self.assertEqual(appointment.state, Appointment.State.BOOKED)
        self.assertEqual(appointment.patient_id, self.patient.pk)
        self.assertEqual(appointment.doctor_id, self.doctor.pk)
        self.assertEqual(appointment.start_at, at(MONDAY, 10))
        self.assertEqual(appointment.end_at, at(MONDAY, 10, 30))
        self.assertIsNone(appointment.rescheduled_from)

    def test_booked_slot_cannot_be_booked_by_someone_else(self):
        self.book(at(MONDAY, 10))
        with self.assertError("APT002"):
            self.book(at(MONDAY, 10), patient=self.other_patient)
        self.assertEqual(Appointment.objects.count(), 1)

    def test_slot_can_be_booked_again_after_cancellation(self):
        make_appointment(
            self.patient, self.doctor, at(MONDAY, 10),
            state="cancelled", cancelled_at=NOW,
        )  # fmt: skip
        appointment = self.book(at(MONDAY, 10), patient=self.other_patient)
        self.assertEqual(appointment.state, Appointment.State.BOOKED)

    def test_adjacent_slots_do_not_conflict(self):
        self.book(at(MONDAY, 10))
        self.book(at(MONDAY, 10, 30), patient=self.other_patient)
        self.book(at(MONDAY, 9, 30), patient=self.other_patient)
        self.assertEqual(Appointment.objects.count(), 3)

    # ── Validation, one rule at a time ────────────────────────────

    def test_rejects_a_slot_in_the_past(self):
        with self.assertError("APT003"):
            self.book(at(MONDAY, 7))

    def test_rejects_a_slot_inside_the_minimum_lead_time(self):
        # now is 08:00, so 08:30 is only 30 minutes away.
        with self.assertError("APT004"):
            self.book(at(MONDAY, 8, 30))

    def test_allows_a_slot_exactly_one_hour_ahead(self):
        appointment = self.book(at(MONDAY, 9))
        self.assertEqual(appointment.start_at, at(MONDAY, 9))

    def test_rejects_a_start_time_off_the_slot_grid(self):
        with self.assertError("APT005"):
            self.book(at(MONDAY, 10, 10))

    def test_rejects_a_slot_that_ends_after_working_hours(self):
        with self.assertError("APT006"):
            self.book(at(MONDAY, 17))

    def test_rejects_a_slot_before_working_hours(self):
        with self.assertError("APT006"):
            self.book(at(MONDAY, 8), now=NOW - timedelta(days=1))

    def test_rejects_a_day_the_doctor_does_not_work(self):
        with self.assertError("APT006"):
            self.book(at(SUNDAY, 10), now=NOW - timedelta(days=7))

    def test_rejects_slots_that_overlap_lunch(self):
        with self.assertError("APT007"):
            self.book(at(MONDAY, 12, 30))
        with self.assertError("APT007"):
            self.book(at(MONDAY, 13))

    def test_slots_either_side_of_lunch_are_allowed(self):
        self.book(at(MONDAY, 12))
        self.book(at(MONDAY, 13, 30), patient=self.other_patient)

    def test_rejects_a_clinic_holiday(self):
        ClinicHoliday.objects.create(
            clinic=self.clinic, holiday_date=TUESDAY, name="Test Day"
        )
        with self.assertError("APT008"):
            self.book(at(TUESDAY, 10))

    def test_rejects_a_slot_inside_doctor_time_off(self):
        TimeOff.objects.create(
            doctor=self.doctor, start_at=at(MONDAY, 10), end_at=at(MONDAY, 11)
        )
        with self.assertError("APT009"):
            self.book(at(MONDAY, 10, 30))
        # A slot starting exactly when the time off ends is fine.
        self.book(at(MONDAY, 11))

    def test_rejects_an_inactive_doctor(self):
        self.doctor.status = Doctor.Status.INACTIVE
        self.doctor.save()
        with self.assertError("DOC002"):
            self.book(at(MONDAY, 10))

    def test_adjunct_doctor_can_be_booked(self):
        self.doctor.status = Doctor.Status.ADJUNCT
        self.doctor.save()
        self.assertEqual(self.book(at(MONDAY, 10)).state, "booked")

    def test_unknown_doctor_raises_doc001(self):
        with self.assertError("DOC001"):
            book_appointment(
                patient_id=self.patient.pk,
                doctor_id=uuid.uuid4(),
                start_at=at(MONDAY, 10),
                now=NOW,
            )

    def test_malformed_doctor_id_raises_doc001(self):
        with self.assertError("DOC001"):
            book_appointment(
                patient_id=self.patient.pk,
                doctor_id="not-a-uuid",
                start_at=at(MONDAY, 10),
                now=NOW,
            )

    def test_unknown_patient_raises_pat001(self):
        with self.assertError("PAT001"):
            book_appointment(
                patient_id=uuid.uuid4(),
                doctor_id=self.doctor.pk,
                start_at=at(MONDAY, 10),
                now=NOW,
            )

    def test_validation_failures_create_nothing(self):
        with self.assertError("APT007"):
            self.book(at(MONDAY, 12, 30))
        self.assertEqual(Appointment.objects.count(), 0)


class DoubleBookingProtectionTests(ClinicTestCase):
    """The database, not just the application, must stop double booking.

    These need the partial unique constraint on Appointment (doctor, start_at)
    where state = 'booked' (or the Postgres exclusion constraint)."""

    def test_database_rejects_two_booked_appointments_in_one_slot(self):
        make_appointment(self.patient, self.doctor, at(MONDAY, 10))
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_appointment(self.other_patient, self.doctor, at(MONDAY, 10))

    def test_database_allows_a_booking_on_a_cancelled_slot(self):
        make_appointment(
            self.patient, self.doctor, at(MONDAY, 10),
            state="cancelled", cancelled_at=NOW,
        )  # fmt: skip
        make_appointment(self.other_patient, self.doctor, at(MONDAY, 10))
        self.assertEqual(Appointment.objects.count(), 2)

    def test_lost_race_is_reported_as_slot_taken(self):
        """If validation passes but another booking lands first, the insert fails
        on the constraint and the caller still gets APT002, not a 500."""
        make_appointment(self.other_patient, self.doctor, at(MONDAY, 10))
        with patch(
            "base.services.booking.validate_slot",
            return_value=at(MONDAY, 10, 30),
        ):
            with self.assertError("APT002"):
                self.book(at(MONDAY, 10))
        self.assertEqual(Appointment.objects.count(), 1)


class UpcomingAppointmentsTests(ClinicTestCase):
    def test_lists_only_future_booked_appointments_soonest_first(self):
        afternoon = self.book(at(MONDAY, 15))
        morning = self.book(at(MONDAY, 10))
        tomorrow = self.book(at(TUESDAY, 9))
        # None of these should appear:
        make_appointment(
            self.patient, self.doctor, at(MONDAY, 11),
            state="cancelled", cancelled_at=NOW,
        )  # fmt: skip
        make_appointment(self.patient, self.doctor, at(MONDAY, 7))  # in the past
        self.book(at(MONDAY, 14), patient=self.other_patient)  # someone else's

        result = list(
            list_upcoming_appointments(patient_id=self.patient.pk, now=NOW)
        )
        self.assertEqual(
            [a.pk for a in result], [morning.pk, afternoon.pk, tomorrow.pk]
        )

    def test_unknown_patient_raises_pat001(self):
        with self.assertError("PAT001"):
            list_upcoming_appointments(patient_id=uuid.uuid4(), now=NOW)
