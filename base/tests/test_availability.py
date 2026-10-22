import uuid
from datetime import date

from base.models import ClinicHoliday, Doctor, TimeOff
from base.services import get_free_slots, get_free_slots_for_doctor

from .helpers import (
    MONDAY,
    NOW,
    SUNDAY,
    ClinicTestCase,
    at,
    make_appointment,
)

FULL_DAY = [
    "09:00", "09:30", "10:00", "10:30", "11:00", "11:30", "12:00",
    "13:30", "14:00", "14:30", "15:00", "15:30", "16:00", "16:30",
]  # fmt: skip


class FreeSlotsTests(ClinicTestCase):
    def starts(self, day=MONDAY, now=NOW):
        slots = get_free_slots(self.doctor, day, now=now)
        return [slot.start_at.strftime("%H:%M") for slot in slots]

    def test_full_working_day_skips_the_lunch_break(self):
        starts = self.starts()
        self.assertEqual(starts, FULL_DAY)
        self.assertNotIn("12:30", starts)
        self.assertNotIn("13:00", starts)

    def test_slot_serialises_with_the_clinic_offset(self):
        slot = get_free_slots(self.doctor, MONDAY, now=NOW)[0]
        self.assertEqual(
            slot.to_dict(),
            {
                "start_at": "2026-11-02T09:00:00+03:00",
                "end_at": "2026-11-02T09:30:00+03:00",
            },
        )

    def test_booked_slot_is_removed(self):
        make_appointment(self.patient, self.doctor, at(MONDAY, 10))
        starts = self.starts()
        self.assertNotIn("10:00", starts)
        self.assertIn("09:30", starts)
        self.assertIn("10:30", starts)

    def test_cancelled_and_rescheduled_slots_are_available_again(self):
        make_appointment(
            self.patient, self.doctor, at(MONDAY, 10),
            state="cancelled", cancelled_at=NOW,
        )  # fmt: skip
        make_appointment(
            self.patient, self.doctor, at(MONDAY, 11), state="rescheduled"
        )
        starts = self.starts()
        self.assertIn("10:00", starts)
        self.assertIn("11:00", starts)

    def test_time_off_removes_overlapping_slots(self):
        TimeOff.objects.create(
            doctor=self.doctor, start_at=at(MONDAY, 10), end_at=at(MONDAY, 11)
        )
        starts = self.starts()
        self.assertNotIn("10:00", starts)
        self.assertNotIn("10:30", starts)
        self.assertIn("09:30", starts)
        # The interval is half-open, so a slot starting when the time off ends stays.
        self.assertIn("11:00", starts)

    def test_partial_time_off_removes_every_slot_it_touches(self):
        TimeOff.objects.create(
            doctor=self.doctor, start_at=at(MONDAY, 10, 15), end_at=at(MONDAY, 10, 45)
        )
        starts = self.starts()
        self.assertNotIn("10:00", starts)
        self.assertNotIn("10:30", starts)

    def test_clinic_holiday_removes_the_whole_day(self):
        ClinicHoliday.objects.create(
            clinic=self.clinic, holiday_date=MONDAY, name="Test Day"
        )
        self.assertEqual(self.starts(), [])

    def test_yearly_holiday_matches_on_month_and_day(self):
        ClinicHoliday.objects.create(
            clinic=self.clinic,
            holiday_date=date(2020, 11, 2),
            name="Yearly",
            is_yearly=True,
        )
        self.assertEqual(self.starts(), [])

    def test_one_off_holiday_in_another_year_does_not_apply(self):
        ClinicHoliday.objects.create(
            clinic=self.clinic, holiday_date=date(2020, 11, 2), name="Old"
        )
        self.assertEqual(self.starts(), FULL_DAY)

    def test_day_without_working_hours_has_no_slots(self):
        self.assertEqual(self.starts(SUNDAY), [])

    def test_inactive_doctor_has_no_slots(self):
        self.doctor.status = Doctor.Status.INACTIVE
        self.doctor.save()
        self.assertEqual(self.starts(), [])

    def test_adjunct_doctor_is_bookable(self):
        self.doctor.status = Doctor.Status.ADJUNCT
        self.doctor.save()
        self.assertEqual(self.starts(), FULL_DAY)

    def test_slots_before_the_minimum_lead_time_are_hidden(self):
        # At 10:00 the earliest bookable start is 11:00.
        self.assertEqual(self.starts(now=at(MONDAY, 10))[0], "11:00")

    def test_slot_exactly_at_the_lead_time_is_shown(self):
        self.assertEqual(self.starts(now=at(MONDAY, 8))[0], "09:00")

    def test_past_date_has_no_slots(self):
        self.assertEqual(self.starts(date(2026, 10, 26)), [])

    def test_unknown_doctor_raises_doc001(self):
        with self.assertError("DOC001"):
            get_free_slots_for_doctor(uuid.uuid4(), MONDAY, now=NOW)
