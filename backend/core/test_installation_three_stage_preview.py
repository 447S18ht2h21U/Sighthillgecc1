"""Disposable-database checks for the unregistered installation preview."""
from dataclasses import FrozenInstanceError

from django.test import TestCase, override_settings
from rest_framework.exceptions import ValidationError

from .installation_eligibility import ensure_installation_eligible
from .installation_three_stage_preview import preview_pre_installation
from .test_installation_eligibility import InstallationEligibilityTests


@override_settings(DEBUG=True, ENVIRONMENT="development")
class ThreeStageInstallationPreviewTests(TestCase):
    def setUp(self):
        self.fixture = InstallationEligibilityTests()
        self.fixture.setUp()
        self.project = self.fixture.project

    def prepare(self, **kwargs):
        result = self.fixture.prepare_installation_state(**kwargs)
        self.project.refresh_from_db()
        return result

    def test_no_invoice_signature_needed_in_new_preview(self):
        self.prepare(invoice=False)
        result = preview_pre_installation(self.project)
        self.assertTrue(result.requirements_satisfied, result.blockers)
        self.assertEqual(result.blockers, ())
        self.assertFalse(result.installation_authorized)
        self.assertFalse(result.invoice_delivery_verified)

    def test_current_operational_rule_remains_unchanged(self):
        self.prepare(invoice=False)
        with self.assertRaises(ValidationError):
            ensure_installation_eligible(self.project)

    def test_missing_contract_still_blocks(self):
        self.prepare(contract=False, invoice=False)
        result = preview_pre_installation(self.project)
        self.assertFalse(result.requirements_satisfied)
        self.assertIn(
            "Verified customer Contract signature is required.",
            result.blockers,
        )

    def test_missing_cancellation_evidence_still_blocks(self):
        self.prepare(cancellation=False, invoice=False)
        result = preview_pre_installation(self.project)
        self.assertFalse(result.requirements_satisfied)
        self.assertIn(
            "Verified cancellation deadline is required.",
            result.blockers,
        )

    def test_unexpired_waiting_period_still_blocks(self):
        self.prepare(invoice=False, signed_days_ago=2)
        result = preview_pre_installation(self.project)
        self.assertFalse(result.requirements_satisfied)
        self.assertIn(
            "Five-day waiting period or cancellation deadline remains open.",
            result.blockers,
        )

    def test_later_cancellation_deadline_still_blocks(self):
        self.prepare(
            invoice=False,
            cancellation_days_after_signature=12,
        )
        result = preview_pre_installation(self.project)
        self.assertFalse(result.requirements_satisfied)
        self.assertIn(
            "Five-day waiting period or cancellation deadline remains open.",
            result.blockers,
        )

    def test_missing_deposit_still_blocks(self):
        self.prepare(invoice=False, deposit=False)
        result = preview_pre_installation(self.project)
        self.assertFalse(result.requirements_satisfied)
        self.assertTrue(
            any("Deposit required:" in reason for reason in result.blockers),
            result.blockers,
        )

    def test_cancelled_project_still_blocks(self):
        self.prepare(invoice=False)
        self.project.state = "CANCELLED"
        result = preview_pre_installation(self.project)
        self.assertFalse(result.requirements_satisfied)
        self.assertIn("Project is cancelled.", result.blockers)

    def test_result_cannot_be_mutated_or_grant_authority(self):
        self.prepare(invoice=False)
        result = preview_pre_installation(self.project)
        self.assertFalse(result.installation_authorized)
        with self.assertRaises(FrozenInstanceError):
            result.installation_authorized = True