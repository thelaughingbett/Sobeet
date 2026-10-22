import uuid

from base.models import Appointment
from base.services import (
    cancel_appointment,
    get_free_slots,
    reschedule_appointment,
)

from .helpers import MONDAY, NOW, ClinicTestCase, at, make_appointment


def free_starts(doctor):
    slots = get_free_slots(doctor, MONDAY, now=NOW)
    return [slot.start_at.strftime("%H:%M") for slot in slots]


class CancelAppointmentTests(ClinicTestCase):
    def cancel(self, appointment, reason="Feeling better"):
        return cancel_appointment(
            appointment_id=appointment.pk, reason=reason, now=NOW
        )

    def test_cancel_records_state_reason_and_time(self):
        appointment = self.book(at(MONDAY, 10))
        result = self.cancel(appointment, "  Feeling better  ")

        appointment.refresh_from_db()
        self.assertEqual(result.pk, appointment.pk)
        self.assertEqual(appointment.state, Appointment.State.CANCELLED)
        self.assertEqual(appointment.cancel_reason, "Feeling better")
        self.assertEqual(appointment.cancelled_at, NOW)

    def test_cancelled_slot_becomes_bookable_again(self):
        appointment = self.book(at(MONDAY, 10))
        self.assertNotIn("10:00", free_starts(self.doctor))

        self.cancel(appointment)

        self.assertIn("10:00", free_starts(self.doctor))
        rebooked = self.book(at(MONDAY, 10), patient=self.other_patient)
        self.assertEqual(rebooked.state, Appointment.State.BOOKED)

    def test_cancelling_twice_raises_apt011(self):
        appointment = self.book(at(MONDAY, 10))
        self.cancel(appointment)
        with self.assertError("APT011"):
            self.cancel(appointment)

    def test_reason_is_required(self):
        appointment = self.book(at(MONDAY, 10))
        for reason in (None, "", "   "):
            with self.subTest(reason=reason):
                with self.assertError("APT013"):
                    self.cancel(appointment, reason)
        appointment.refresh_from_db()
        self.assertEqual(appointment.state, Appointment.State.BOOKED)

    def test_only_booked_appointments_can_be_cancelled(self):
        for state in ("executed", "no_show", "rescheduled"):
            with self.subTest(state=state):
                appointment = make_appointment(
                    self.patient, self.doctor, at(MONDAY, 7), state=state
                )
                with self.assertError("APT012"):
                    self.cancel(appointment)
                appointment.delete()

    def test_unknown_appointment_raises_apt001(self):
        with self.assertError("APT001"):
            cancel_appointment(
                appointment_id=uuid.uuid4(), reason="Nope", now=NOW
            )

    def test_malformed_appointment_id_raises_apt001(self):
        with self.assertError("APT001"):
            cancel_appointment(appointment_id="abc", reason="Nope", now=NOW)


class RescheduleAppointmentTests(ClinicTestCase):
    def reschedule(self, appointment, start_at):
        return reschedule_appointment(
            appointment_id=appointment.pk, start_at=start_at, now=NOW
        )

    def test_moves_the_appointment_to_the_new_slot(self):
        old = self.book(at(MONDAY, 10))
        new = self.reschedule(old, at(MONDAY, 11))

        old.refresh_from_db()
        self.assertEqual(old.state, Appointment.State.RESCHEDULED)
        self.assertEqual(new.state, Appointment.State.BOOKED)
        self.assertEqual(new.start_at, at(MONDAY, 11))
        self.assertEqual(new.end_at, at(MONDAY, 11, 30))
        self.assertEqual(new.rescheduled_from_id, old.pk)
        self.assertEqual(new.patient_id, old.patient_id)
        self.assertEqual(new.doctor_id, old.doctor_id)

    def test_original_slot_becomes_available_and_new_slot_is_taken(self):
        old = self.book(at(MONDAY, 10))
        self.reschedule(old, at(MONDAY, 11))

        starts = free_starts(self.doctor)
        self.assertIn("10:00", starts)
        self.assertNotIn("11:00", starts)

    def test_original_slot_can_be_booked_by_someone_else(self):
        old = self.book(at(MONDAY, 10))
        self.reschedule(old, at(MONDAY, 11))
        self.book(at(MONDAY, 10), patient=self.other_patient)

    def test_new_slot_that_is_taken_fails_and_keeps_the_original(self):
        old = self.book(at(MONDAY, 10))
        self.book(at(MONDAY, 11), patient=self.other_patient)

        with self.assertError("APT002"):
            self.reschedule(old, at(MONDAY, 11))

        old.refresh_from_db()
        self.assertEqual(old.state, Appointment.State.BOOKED)
        self.assertEqual(Appointment.objects.count(), 2)

    def test_new_slot_is_validated_like_a_fresh_booking(self):
        old = self.book(at(MONDAY, 10))
        cases = {
            "APT003": at(MONDAY, 7),  # past
            "APT005": at(MONDAY, 10, 10),  # off the grid
            "APT006": at(MONDAY, 17),  # after hours
            "APT007": at(MONDAY, 12, 30),  # lunch
        }
        for code, start_at in cases.items():
            with self.subTest(code=code):
                with self.assertError(code):
                    self.reschedule(old, start_at)
                old.refresh_from_db()
                self.assertEqual(old.state, Appointment.State.BOOKED)
        self.assertEqual(Appointment.objects.count(), 1)

    def test_cancelled_appointment_cannot_be_rescheduled(self):
        old = self.book(at(MONDAY, 10))
        cancel_appointment(appointment_id=old.pk, reason="Changed plans", now=NOW)
        with self.assertError("APT011"):
            self.reschedule(old, at(MONDAY, 11))

    def test_already_rescheduled_appointment_cannot_be_rescheduled_again(self):
        old = self.book(at(MONDAY, 10))
        self.reschedule(old, at(MONDAY, 11))
        with self.assertError("APT012"):
            self.reschedule(old, at(MONDAY, 14))

    def test_rescheduling_to_the_same_slot_raises_apt014(self):
        old = self.book(at(MONDAY, 10))
        with self.assertError("APT014"):
            self.reschedule(old, at(MONDAY, 10))

    def test_the_new_appointment_can_itself_be_rescheduled(self):
        first = self.book(at(MONDAY, 10))
        second = self.reschedule(first, at(MONDAY, 11))
        third = self.reschedule(second, at(MONDAY, 14))
        self.assertEqual(third.rescheduled_from_id, second.pk)

    def test_unknown_appointment_raises_apt001(self):
        with self.assertError("APT001"):
            reschedule_appointment(
                appointment_id=uuid.uuid4(), start_at=at(MONDAY, 11), now=NOW
            )
