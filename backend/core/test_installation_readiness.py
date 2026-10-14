from django.test import TestCase

from .installation_readiness import installation_readiness
from .test_installation_eligibility import InstallationEligibilityTests


class InstallationReadinessTests(TestCase):

    def setUp(self):
        fixture = InstallationEligibilityTests()
        fixture.setUp()

        self.project = fixture.project
        self.fixture = fixture

    def test_ready_project_reports_ready(self):
        self.fixture.prepare_installation_state()

        result = installation_readiness(self.project)

        self.assertTrue(result["eligible"])


    def test_missing_contract_reports_blocker(self):
        self.fixture.prepare_installation_state(
            contract=False,
        )

        result = installation_readiness(self.project)

        self.assertFalse(result["eligible"])
        self.assertIn(
            "Verified contract signature evidence is required.",
            result["blocking_reasons"],
        )


    def test_financed_project_without_deposit_reports_blocker(self):
        self.fixture.prepare_installation_state(
            financed=True,
            deposit=False,
        )

        result = installation_readiness(self.project)

        self.assertFalse(result["eligible"])
        self.assertIn(
            "Verified 50% deposit is required before installation.",
            result["blocking_reasons"],
        )


    def test_non_financed_project_without_deposit_reports_ready(self):
        self.fixture.prepare_installation_state(
            financed=False,
            deposit=False,
        )

        result = installation_readiness(self.project)

        self.assertTrue(result["eligible"])
