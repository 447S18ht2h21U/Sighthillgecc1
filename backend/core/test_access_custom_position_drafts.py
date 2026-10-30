"""Isolated tests for non-executable custom position proposals."""

from django.test import SimpleTestCase

from .access_custom_position_drafts import (
    draft_grants_access,
    validate_position_draft,
)
from .access_permission_catalog import PERMISSION_BY_CODE
from .access_position_templates import POSITION_TEMPLATES


DESCRIPTION = "Handles customer support and service coordination."


class CustomPositionDraftTests(SimpleTestCase):

    def test_custom_position_with_no_permissions(self):
        draft = validate_position_draft(
            "Customer Service Manager", DESCRIPTION, []
        )
        self.assertEqual(draft.title, "Customer Service Manager")
        self.assertEqual(draft.permission_codes, ())
        self.assertFalse(draft.requires_independent_approval)

    def test_known_permissions_are_recorded_but_not_granted(self):
        draft = validate_position_draft(
            "Customer Service Manager",
            DESCRIPTION,
            ["dashboard.view", "customers.view"],
        )
        self.assertEqual(
            draft.permission_codes,
            ("dashboard.view", "customers.view"),
        )
        self.assertFalse(draft_grants_access(draft, "customers.view"))

    def test_sensitive_independent_approval_is_flagged(self):
        draft = validate_position_draft(
            "Customer Service Manager",
            DESCRIPTION,
            ["financials.balance_sheet.view"],
        )
        self.assertTrue(draft.requires_independent_approval)
        self.assertFalse(draft_grants_access(draft, "financials.balance_sheet.view"))

    def test_unknown_permission_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_position_draft(
                "Customer Service Manager", DESCRIPTION, ["system.superuser"]
            )

    def test_duplicate_permission_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_position_draft(
                "Customer Service Manager",
                DESCRIPTION,
                ["customers.view", "customers.view"],
            )

    def test_invalid_titles_are_rejected(self):
        for title in ("", "AB", "<script>", "X" * 101):
            with self.subTest(title=title):
                with self.assertRaises(ValueError):
                    validate_position_draft(title, DESCRIPTION, [])

    def test_standard_position_names_are_reserved(self):
        for position in POSITION_TEMPLATES:
            for title in (position.code, position.label):
                with self.subTest(title=title):
                    with self.assertRaises(ValueError):
                        validate_position_draft(title, DESCRIPTION, [])

    def test_reserved_names_are_case_insensitive(self):
        for title in ("ceo", "comptroller", "sales manager"):
            with self.subTest(title=title):
                with self.assertRaises(ValueError):
                    validate_position_draft(title, DESCRIPTION, [])

    def test_distinct_custom_position_is_permitted(self):
        draft = validate_position_draft(
            "Customer Service Coordinator", DESCRIPTION, []
        )
        self.assertEqual(draft.title, "Customer Service Coordinator")
        self.assertFalse(draft_grants_access(draft, "customers.view"))

    def test_missing_description_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_position_draft("Customer Service Manager", "", [])

    def test_invalid_permission_collection_is_rejected(self):
        for codes in (None, "customers.view", [None]):
            with self.subTest(codes=codes):
                with self.assertRaises(ValueError):
                    validate_position_draft(
                        "Customer Service Manager", DESCRIPTION, codes
                    )

    def test_every_catalog_permission_stays_non_executable(self):
        for code in PERMISSION_BY_CODE:
            with self.subTest(permission=code):
                draft = validate_position_draft(
                    "Customer Service Manager", DESCRIPTION, [code]
                )
                self.assertFalse(draft_grants_access(draft, code))