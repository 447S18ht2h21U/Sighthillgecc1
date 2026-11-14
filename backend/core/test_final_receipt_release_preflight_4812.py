"""Focused release preflight checks using real isolated evidence."""

from unittest.mock import patch

from django.test import TestCase, override_settings

from . import test_receipt_draft_retention_4803 as fixture
from .final_receipt_release_preflight_4812 import (
    assess_final_receipt_release_preflight,
)
from .models import ReceiptDraftPackage


@override_settings(DEBUG=True, ENVIRONMENT="development")
class FinalReceiptReleasePreflight4812(TestCase):
    setUp = fixture.DraftRetentionAcceptance4803.setUp
    prepare_real_evidence = (
        fixture.DraftRetentionAcceptance4803.prepare_real_evidence
    )
    decide = fixture.DraftRetentionAcceptance4803.decide
    prepare_pair = fixture.DraftRetentionAcceptance4803.prepare_pair
    prepare_package = fixture.DraftRetentionAcceptance4803.prepare_package
    retain = fixture.DraftRetentionAcceptance4803.retain

    def assert_release_blocked(self, result):
        self.assertFalse(result.trusted_installation_evidence)
        self.assertFalse(result.final_receipt_issuance_authorized)
        self.assertFalse(result.final_receipt_verified)
        self.assertFalse(result.provider_email_authenticated)
        self.assertFalse(result.customer_delivery_verified)
        self.assertFalse(result.completion_authorized)

    def test_real_retained_package_and_finances(self):
        package = self.prepare_package()
        record, created = self.retain(package)
        self.assertTrue(created)

        result = assess_final_receipt_release_preflight(self.project)

        self.assertEqual(
            result.status,
            "DRAFT_EVIDENCE_VERIFIED_RELEASE_BLOCKED",
        )
        self.assertEqual(result.retained_package_count, 1)
        self.assertEqual(result.verified_package_count, 1)
        self.assertTrue(result.financial_evidence_verified)
        self.assertTrue(result.draft_integrity_verified)
        self.assertEqual(record.msr_id, self.msr.pk)
        self.assert_release_blocked(result)

        print("PASS: Real financial and draft evidence correlated.")
        print("PASS: FINAL issuance and delivery remain blocked.")

    def test_missing_draft_is_not_release_ready(self):
        result = assess_final_receipt_release_preflight(self.project)

        self.assertEqual(result.status, "NO_DRAFT_PACKAGE")
        self.assertFalse(result.draft_integrity_verified)
        self.assertEqual(result.verified_package_count, 0)
        self.assert_release_blocked(result)

        print("PASS: No retained draft cannot authorize issuance.")

    def test_independent_verifier_failure_blocks_release(self):
        package = self.prepare_package()
        self.retain(package)

        with patch(
            "core.final_receipt_release_preflight_4812."
            "verify_retained_draft_package",
            side_effect=ValueError("FICTIONAL CORRUPTION"),
        ):
            result = assess_final_receipt_release_preflight(
                self.project
            )

        self.assertEqual(result.status, "INTEGRITY_FAILED")
        self.assertFalse(result.draft_integrity_verified)
        self.assertEqual(result.verified_package_count, 0)
        self.assert_release_blocked(result)
        self.assertEqual(ReceiptDraftPackage.objects.count(), 1)

        print("PASS: Corrupted evidence fails closed without writes.")
