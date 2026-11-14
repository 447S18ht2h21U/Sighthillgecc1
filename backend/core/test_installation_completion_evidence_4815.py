"""Isolated installation-completion release boundary acceptance."""

from django.test import TestCase, override_settings
from django.utils import timezone

from . import test_receipt_draft_retention_4803 as fixture
from .installation_completion_evidence_4815 import (
    assess_installation_completion_evidence,
)
from .final_receipt_release_preflight_4812 import (
    assess_final_receipt_release_preflight,
)
from .models import InstallationSchedule


@override_settings(DEBUG=True, ENVIRONMENT="development")
class InstallationCompletionEvidence4815(TestCase):
    setUp = fixture.DraftRetentionAcceptance4803.setUp
    prepare_real_evidence = (
        fixture.DraftRetentionAcceptance4803.prepare_real_evidence
    )
    decide = fixture.DraftRetentionAcceptance4803.decide
    prepare_pair = fixture.DraftRetentionAcceptance4803.prepare_pair
    prepare_package = fixture.DraftRetentionAcceptance4803.prepare_package
    retain = fixture.DraftRetentionAcceptance4803.retain

    def create_completed_schedule(self, *, timestamp=True):
        return InstallationSchedule.objects.create(
            project=self.project,
            scheduled_date=timezone.localdate(),
            installation_manager=self.comptroller,
            scheduled_by=self.comptroller,
            status=InstallationSchedule.Status.COMPLETED,
            completed_at=timezone.now() if timestamp else None,
        )

    def assert_no_release(self, result):
        self.assertFalse(result.trusted_installation_evidence)
        self.assertFalse(result.final_receipt_issuance_authorized)
        self.assertFalse(result.customer_delivery_verified)
        self.assertFalse(result.completion_authorized)

    def test_missing_completion_record_blocks_release(self):
        evidence = assess_installation_completion_evidence(
            self.project
        )
        self.assertFalse(evidence.operational_schedule_completed)
        self.assertEqual(evidence.completed_schedule_count, 0)
        self.assert_no_release(evidence)

        result = assess_final_receipt_release_preflight(self.project)
        self.assertFalse(result.operational_schedule_completed)
        self.assert_no_release(result)

        print("PASS: Missing installation completion blocks release.")

    def test_completed_schedule_does_not_establish_trust(self):
        # Fictional data inside disposable test SQLite only.
        self.create_completed_schedule()

        evidence = assess_installation_completion_evidence(
            self.project
        )
        self.assertTrue(evidence.operational_schedule_completed)
        self.assert_no_release(evidence)

        result = assess_final_receipt_release_preflight(self.project)
        self.assertTrue(result.operational_schedule_completed)
        self.assert_no_release(result)

        print("PASS: Completed schedule does not authorize FINAL Receipt.")

    def test_inconsistent_completion_record_rejected(self):
        self.create_completed_schedule(timestamp=False)

        evidence = assess_installation_completion_evidence(
            self.project
        )
        self.assertFalse(evidence.operational_schedule_completed)
        self.assert_no_release(evidence)

        result = assess_final_receipt_release_preflight(self.project)
        self.assertFalse(result.operational_schedule_completed)
        self.assert_no_release(result)

        print("PASS: Completion timestamp mismatch fails closed.")
