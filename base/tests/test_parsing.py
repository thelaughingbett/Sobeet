from datetime import date

from django.test import SimpleTestCase
from django.utils import timezone

from base.utils.errors import ClinicError
from base.services import parse_query_date, parse_start_at

from .helpers import TUESDAY, at


class ParseStartAtTests(SimpleTestCase):
    def assertCode(self, code, value):
        with self.assertRaises(ClinicError) as ctx:
            parse_start_at(value)
        self.assertEqual(ctx.exception.code, code)

    def test_accepts_an_iso_timestamp_with_an_offset(self):
        value = parse_start_at("2026-11-03T10:00:00+03:00")
        self.assertTrue(timezone.is_aware(value))
        self.assertEqual(value, at(TUESDAY, 10))

    def test_accepts_utc(self):
        self.assertEqual(parse_start_at(
            "2026-11-03T07:00:00Z"), at(TUESDAY, 10))

    def test_rejects_a_timestamp_without_an_offset(self):
        self.assertCode("APT010", "2026-11-03T10:00:00")

    def test_rejects_garbage_missing_and_non_string_values(self):
        for value in ("tomorrow", "", None, 12345, ["2026-11-03T10:00:00+03:00"]):
            with self.subTest(value=value):
                self.assertCode("APT010", value)


class ParseQueryDateTests(SimpleTestCase):
    def assertCode(self, code, value):
        with self.assertRaises(ClinicError) as ctx:
            parse_query_date(value)
        self.assertEqual(ctx.exception.code, code)

    def test_accepts_a_valid_date(self):
        self.assertEqual(parse_query_date("2026-11-03"), date(2026, 11, 3))

    def test_rejects_missing_and_invalid_dates(self):
        for value in (None, "", "not-a-date", "2026-13-45", "03/11/2026"):
            with self.subTest(value=value):
                self.assertCode("AVL001", value)
