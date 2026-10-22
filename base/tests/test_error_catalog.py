"""Keeps docs/ERROR_CODES.md and base/utils/errors.py from drifting apart."""
import re
from pathlib import Path

from django.test import SimpleTestCase

from base.utils.errors import CATALOG

DOCS = Path(__file__).resolve().parents[2] / "docs" / "ERROR_CODES.md"

# Matches a table row: | `APT002` | 409 | Slot already taken | ... |
ROW = re.compile(r"^\|\s*`([A-Z]{3}\d{3})`\s*\|\s*(\d{3})\s*\|\s*([^|]+?)\s*\|", re.M)


def documented_codes():
    return {
        code: (message, int(status))
        for code, status, message in ROW.findall(DOCS.read_text(encoding="utf-8"))
    }


class ErrorCatalogDocsTests(SimpleTestCase):
    def test_docs_file_is_found(self):
        self.assertTrue(DOCS.exists(), f"{DOCS} not found")

    def test_every_code_in_the_catalog_is_documented(self):
        missing = sorted(set(CATALOG) - set(documented_codes()))
        self.assertEqual(missing, [], f"Add these codes to docs/ERROR_CODES.md: {missing}")

    def test_every_documented_code_exists_in_the_catalog(self):
        stale = sorted(set(documented_codes()) - set(CATALOG))
        self.assertEqual(stale, [], f"These documented codes no longer exist: {stale}")

    def test_documented_message_and_status_match_the_code(self):
        docs = documented_codes()
        for code, (message, status) in CATALOG.items():
            if code not in docs:
                continue  # reported by the first test
            with self.subTest(code=code):
                self.assertEqual(docs[code], (message, status))
