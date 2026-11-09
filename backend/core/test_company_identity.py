"""Verify approved corporate identity and its safe defaults."""
from dataclasses import FrozenInstanceError
from unittest import TestCase

from .company_identity import APPROVED_COMPANY_IDENTITY


class CompanyIdentityTests(TestCase):
    def test_approved_legal_name(self):
        self.assertEqual(
            APPROVED_COMPANY_IDENTITY.legal_name,
            "Green Energy Contracting Corporation",
        )

    def test_approved_email(self):
        self.assertEqual(
            APPROVED_COMPANY_IDENTITY.email,
            "care@gecc.cloud",
        )

    def test_website_remains_unconfirmed(self):
        self.assertIsNone(APPROVED_COMPANY_IDENTITY.website)

    def test_company_identity_cannot_be_mutated_in_place(self):
        with self.assertRaises(FrozenInstanceError):
            APPROVED_COMPANY_IDENTITY.email = "unapproved@example.com"

    def test_no_invented_website(self):
        self.assertFalse(APPROVED_COMPANY_IDENTITY.website)

    def test_email_is_normalized(self):
        value = APPROVED_COMPANY_IDENTITY.email
        self.assertEqual(value, value.strip().lower())
