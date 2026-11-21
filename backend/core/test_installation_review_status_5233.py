from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from core.installation_manager_workspace_5211 import workspace
from core.post_installation_acceptance_4819 import (
    record_post_installation_inspection,
    review_post_installation_inspection,
)
from core.test_post_installation_acceptance_4819 import (
    PostInstallationAcceptance4819 as Fixture,
)


@override_settings(DEBUG=True, ENVIRONMENT="development")
class InspectionReviewStatus5233(TestCase):
    setUp = Fixture.setUp

    def state(self):
        request = APIRequestFactory().get("/api/im-inspection-workspace/")
        force_authenticate(request, user=self.inspector)
        response = workspace(request, self.project.pk)
        self.assertEqual(response.status_code, 200)
        data = response.data
        self.assertFalse(data["provider_signature_verified"])
        self.assertFalse(data["receipt_issuance_authorized"])
        self.assertFalse(data["project_completion_authorized"])
        return data["internal_review_state"]

    def inspect(self, passed=True):
        return record_post_installation_inspection(
            actor=self.inspector,
            project_id=self.project.pk,
            inspection_passed=passed,
            notes="Development fixture inspection findings, isolated database.",
        )

    def review(self, inspection, accepted, examined):
        return review_post_installation_inspection(
            actor=self.reviewer,
            inspection_id=inspection.pk,
            accept=accepted,
            independently_examined=examined,
            reason="Independent examination of isolated fixture evidence.",
        )

    def test_no_inspection(self):
        self.assertEqual(self.state(), "NOT_RECORDED")

    def test_recorded_inspection_awaits_review(self):
        self.inspect()
        self.assertEqual(self.state(), "AWAITING_INDEPENDENT_REVIEW")

    def test_acceptance_remains_internal_only(self):
        inspection = self.inspect()
        self.review(inspection, accepted=True, examined=True)
        self.assertEqual(self.state(), "INTERNAL_CANDIDATE_ACCEPTED")

    def test_rejected_inspection_reports_rejection(self):
        inspection = self.inspect(passed=False)
        self.review(inspection, accepted=False, examined=False)
        self.assertEqual(self.state(), "INTERNAL_CANDIDATE_REJECTED")
