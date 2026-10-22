import uuid
from unittest.mock import patch

from django.urls import reverse
from rest_framework.test import APITestCase

from base.models import Appointment
from base.tests.helpers import (
    MONDAY,
    NOW,
    TUESDAY,
    at,
    make_appointment,
    make_clinic,
    make_doctor,
    make_patient,
)


class EndpointTestCase(APITestCase):
    def setUp(self):
        # Freeze the clock at Monday 2 Nov 2026, 08:00 Nairobi.
        patcher = patch("django.utils.timezone.now", return_value=NOW)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.clinic = make_clinic()
        self.doctor = make_doctor(self.clinic)
        self.patient = make_patient()
        self.other_patient = make_patient(
            email="brian@example.com", name="Brian Otieno"
        )

    def payload(self, start, **overrides):
        body = {
            "patient_id": str(self.patient.pk),
            "doctor_id": str(self.doctor.pk),
            "start_at": start.isoformat(),
        }
        body.update(overrides)
        return body

    def post_booking(self, body):
        return self.client.post(reverse("appointment-create"), body, format="json")

    def cancel(self, appointment_id, body):
        url = reverse("appointment-cancel", args=[appointment_id])
        return self.client.patch(url, body, format="json")

    def reschedule(self, appointment_id, body):
        url = reverse("appointment-reschedule", args=[appointment_id])
        return self.client.patch(url, body, format="json")

    def assertErrorResponse(self, response, status, code):
        self.assertEqual(response.status_code, status, response.data)
        self.assertEqual(response.data["code"], code)
        self.assertIn(f"(Ref: {code})", response.data["error"])
        self.assertTrue(response.data["message"])


class BookingEndpointTests(EndpointTestCase):
    def test_booking_returns_201_and_the_appointment(self):
        response = self.post_booking(self.payload(at(MONDAY, 10)))

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["state"], "booked")
        self.assertEqual(response.data["start_at"],
                         "2026-11-02T10:00:00+03:00")
        self.assertEqual(response.data["end_at"], "2026-11-02T10:30:00+03:00")
        self.assertEqual(response.data["patient_id"], str(self.patient.pk))
        self.assertEqual(response.data["doctor_name"], "Dr. Amina Otieno")
        self.assertEqual(Appointment.objects.count(), 1)

    def test_taken_slot_returns_409(self):
        self.post_booking(self.payload(at(MONDAY, 10)))
        response = self.post_booking(
            self.payload(at(MONDAY, 10), patient_id=str(self.other_patient.pk))
        )
        self.assertErrorResponse(response, 409, "APT002")

    def test_business_rule_failures_return_422(self):
        cases = {
            "APT003": at(MONDAY, 7),  # past
            "APT004": at(MONDAY, 8, 30),  # inside the 1 hour lead time
            "APT005": at(MONDAY, 10, 10),  # off the slot grid
            "APT006": at(MONDAY, 17),  # outside working hours
            "APT007": at(MONDAY, 12, 30),  # lunch
        }
        for code, start_at in cases.items():
            with self.subTest(code=code):
                response = self.post_booking(self.payload(start_at))
                self.assertErrorResponse(response, 422, code)
        self.assertEqual(Appointment.objects.count(), 0)

    def test_missing_ids_return_400(self):
        body = self.payload(at(MONDAY, 10))
        del body["patient_id"]
        response = self.post_booking(body)
        self.assertErrorResponse(response, 400, "GEN004")
        self.assertIn("patient_id", response.data["detail"])

    def test_missing_or_invalid_start_at_returns_400(self):
        for value in (None, "tomorrow", "2026-11-03T10:00:00"):
            with self.subTest(value=value):
                response = self.post_booking(
                    self.payload(at(MONDAY, 10), start_at=value)
                )
                self.assertErrorResponse(response, 400, "APT010")

    def test_unknown_doctor_and_patient_return_404(self):
        response = self.post_booking(
            self.payload(at(MONDAY, 10), doctor_id=str(uuid.uuid4()))
        )
        self.assertErrorResponse(response, 404, "DOC001")

        response = self.post_booking(
            self.payload(at(MONDAY, 10), patient_id=str(uuid.uuid4()))
        )
        self.assertErrorResponse(response, 404, "PAT001")

    def test_malformed_json_returns_400(self):
        response = self.client.generic(
            "POST",
            reverse("appointment-create"),
            "{not json",
            content_type="application/json",
        )
        self.assertErrorResponse(response, 400, "GEN001")

    def test_body_must_be_a_json_object(self):
        response = self.client.post(
            reverse("appointment-create"), ["a", "list"], format="json"
        )
        self.assertErrorResponse(response, 400, "GEN001")


class AvailabilityEndpointTests(EndpointTestCase):
    def url(self, doctor_id=None):
        return reverse("doctor-availability", args=[doctor_id or self.doctor.pk])

    def test_returns_free_slots_for_the_day(self):
        response = self.client.get(self.url(), {"date": "2026-11-02"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["date"], "2026-11-02")
        self.assertEqual(response.data["timezone"], "Africa/Nairobi")
        self.assertEqual(len(response.data["slots"]), 14)
        self.assertEqual(
            response.data["slots"][0],
            {
                "start_at": "2026-11-02T09:00:00+03:00",
                "end_at": "2026-11-02T09:30:00+03:00",
            },
        )

    def test_booked_slot_disappears(self):
        self.post_booking(self.payload(at(MONDAY, 10)))
        response = self.client.get(self.url(), {"date": "2026-11-02"})
        starts = [slot["start_at"] for slot in response.data["slots"]]
        self.assertNotIn("2026-11-02T10:00:00+03:00", starts)
        self.assertEqual(len(starts), 13)

    def test_missing_or_invalid_date_returns_400(self):
        for params in ({}, {"date": "nope"}, {"date": "2026-13-01"}):
            with self.subTest(params=params):
                response = self.client.get(self.url(), params)
                self.assertErrorResponse(response, 400, "AVL001")

    def test_unknown_doctor_returns_404(self):
        response = self.client.get(self.url(uuid.uuid4()), {
                                   "date": "2026-11-02"})
        self.assertErrorResponse(response, 404, "DOC001")

    def test_malformed_doctor_id_returns_a_coded_404(self):
        url = reverse("doctor-availability", args=["abc"])
        response = self.client.get(url, {"date": "2026-11-02"})
        self.assertErrorResponse(response, 404, "DOC001")


class CancelEndpointTests(EndpointTestCase):
    def setUp(self):
        super().setUp()
        self.appointment = make_appointment(
            self.patient, self.doctor, at(MONDAY, 10))

    def test_cancel_returns_200_and_frees_the_slot(self):
        response = self.cancel(self.appointment.pk, {
                               "reason": "Feeling better"})

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["state"], "cancelled")
        self.assertEqual(response.data["cancel_reason"], "Feeling better")
        self.assertIsNotNone(response.data["cancelled_at"])

        rebook = self.post_booking(
            self.payload(at(MONDAY, 10), patient_id=str(self.other_patient.pk))
        )
        self.assertEqual(rebook.status_code, 201)

    def test_cancelling_twice_returns_409(self):
        self.cancel(self.appointment.pk, {"reason": "Feeling better"})
        response = self.cancel(self.appointment.pk, {"reason": "Again"})
        self.assertErrorResponse(response, 409, "APT011")

    def test_missing_reason_returns_400(self):
        for body in ({}, {"reason": ""}, {"reason": "   "}):
            with self.subTest(body=body):
                response = self.cancel(self.appointment.pk, body)
                self.assertErrorResponse(response, 400, "APT013")

    def test_non_string_reason_returns_400(self):
        response = self.cancel(self.appointment.pk, {"reason": 123})
        self.assertErrorResponse(response, 400, "GEN004")

    def test_unknown_appointment_returns_404(self):
        response = self.cancel(uuid.uuid4(), {"reason": "Nope"})
        self.assertErrorResponse(response, 404, "APT001")


class RescheduleEndpointTests(EndpointTestCase):
    def setUp(self):
        super().setUp()
        self.appointment = make_appointment(
            self.patient, self.doctor, at(MONDAY, 10))

    def test_reschedule_returns_the_new_appointment(self):
        response = self.reschedule(
            self.appointment.pk, {"start_at": at(MONDAY, 11).isoformat()}
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["state"], "booked")
        self.assertEqual(response.data["start_at"],
                         "2026-11-02T11:00:00+03:00")
        self.assertEqual(
            response.data["rescheduled_from_id"], str(self.appointment.pk)
        )
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.state, "rescheduled")

    def test_original_slot_is_free_again(self):
        self.reschedule(self.appointment.pk, {
                        "start_at": at(MONDAY, 11).isoformat()})
        rebook = self.post_booking(
            self.payload(at(MONDAY, 10), patient_id=str(self.other_patient.pk))
        )
        self.assertEqual(rebook.status_code, 201)

    def test_new_slot_is_validated_like_a_fresh_booking(self):
        taken = self.post_booking(
            self.payload(at(MONDAY, 11), patient_id=str(self.other_patient.pk))
        )
        self.assertEqual(taken.status_code, 201)

        response = self.reschedule(
            self.appointment.pk, {"start_at": at(MONDAY, 11).isoformat()}
        )
        self.assertErrorResponse(response, 409, "APT002")

        response = self.reschedule(
            self.appointment.pk, {"start_at": at(MONDAY, 12, 30).isoformat()}
        )
        self.assertErrorResponse(response, 422, "APT007")

        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.state, "booked")

    def test_cancelled_appointment_returns_409(self):
        self.cancel(self.appointment.pk, {"reason": "Changed plans"})
        response = self.reschedule(
            self.appointment.pk, {"start_at": at(MONDAY, 11).isoformat()}
        )
        self.assertErrorResponse(response, 409, "APT011")

    def test_same_slot_returns_422(self):
        response = self.reschedule(
            self.appointment.pk, {"start_at": at(MONDAY, 10).isoformat()}
        )
        self.assertErrorResponse(response, 422, "APT014")

    def test_missing_start_at_returns_400(self):
        response = self.reschedule(self.appointment.pk, {})
        self.assertErrorResponse(response, 400, "APT010")

    def test_unknown_appointment_returns_404(self):
        response = self.reschedule(
            uuid.uuid4(), {"start_at": at(MONDAY, 11).isoformat()}
        )
        self.assertErrorResponse(response, 404, "APT001")


class PatientAppointmentsEndpointTests(EndpointTestCase):
    def url(self, patient_id=None):
        return reverse("patient-appointments", args=[patient_id or self.patient.pk])

    def test_lists_upcoming_booked_appointments_soonest_first(self):
        make_appointment(self.patient, self.doctor, at(TUESDAY, 9))
        make_appointment(self.patient, self.doctor, at(MONDAY, 15))
        make_appointment(self.patient, self.doctor, at(MONDAY, 10))
        make_appointment(
            self.patient, self.doctor, at(MONDAY, 11),
            state="cancelled", cancelled_at=NOW,
        )  # fmt: skip
        make_appointment(self.other_patient, self.doctor, at(MONDAY, 14))

        response = self.client.get(self.url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["start_at"] for item in response.data],
            [
                "2026-11-02T10:00:00+03:00",
                "2026-11-02T15:00:00+03:00",
                "2026-11-03T09:00:00+03:00",
            ],
        )

    def test_patient_with_no_appointments_gets_an_empty_list(self):
        response = self.client.get(self.url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.data), [])

    def test_unknown_patient_returns_404(self):
        response = self.client.get(self.url(uuid.uuid4()))
        self.assertErrorResponse(response, 404, "PAT001")
