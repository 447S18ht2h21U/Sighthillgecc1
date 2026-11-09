"""Database-backed Stage 1 candidate tests; no operational permissions."""
from django.test import TestCase, override_settings
from . import test_installation_eligibility as eligibility_fixture
from .installation_three_stage_preview import preview_pre_installation
from .installation_stage_one_scheduling_adapter import (
    assess_stage_one_scheduling_candidate,
)


@override_settings(DEBUG=True, ENVIRONMENT="development")
class StageOneSchedulingIntegrationTests(TestCase):
    def setUp(self):
        fixture = eligibility_fixture.InstallationEligibilityTests()
        fixture.setUp()
        self.fixture = fixture
        self.project = fixture.project

    def check_candidate(self, expected, **kwargs):
        self.fixture.prepare_installation_state(**kwargs)
        self.project.refresh_from_db()
        preview = preview_pre_installation(self.project)
        assessment = assess_stage_one_scheduling_candidate(preview)
        self.assertEqual(assessment.candidate_ready, expected, assessment.blockers)
        self.assertFalse(assessment.scheduling_authorized)
        self.assertFalse(assessment.installation_authorized)
        self.assertFalse(preview.installation_authorized)
        return assessment

    def test_contract_without_invoice_is_candidate(self):
        self.check_candidate(True, invoice=False)

    def test_missing_contract_blocks(self):
        self.check_candidate(False, contract=False, invoice=False)

    def test_missing_cancellation_evidence_blocks(self):
        self.check_candidate(False, cancellation=False, invoice=False)

    def test_five_day_wait_blocks(self):
        self.check_candidate(False, signed_days_ago=2, invoice=False)

    def test_future_cancellation_deadline_blocks(self):
        self.check_candidate(
            False, cancellation_days_after_signature=12, invoice=False
        )

    def test_missing_deposit_blocks(self):
        self.check_candidate(False, deposit=False, invoice=False)

    def test_cancelled_project_blocks(self):
        self.fixture.prepare_installation_state(invoice=False)
        self.project.refresh_from_db()
        self.project.state = "CANCELLED"
        preview = preview_pre_installation(self.project)
        assessment = assess_stage_one_scheduling_candidate(preview)
        self.assertFalse(assessment.candidate_ready)
        self.assertFalse(assessment.scheduling_authorized)
        self.assertFalse(assessment.installation_authorized)
