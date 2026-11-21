"""Step 5249: isolated capability contract, no persistent writes."""
from unittest.mock import patch
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from core.operational_project_api import OperationalProjectViewSet
from core.test_post_installation_acceptance_4819 import (
    PostInstallationAcceptance4819 as Fixture,
)
from core.post_installation_acceptance_4819 import (
    record_post_installation_inspection,
)


@override_settings(DEBUG=True, ENVIRONMENT="development")
class ComptrollerReviewCapability5249(TestCase):
    setUp = Fixture.setUp

    def queue(self):
        request = APIRequestFactory().get(
            "/api/operational-projects/review-queue/"
        )
        force_authenticate(request, user=self.reviewer)
        view = OperationalProjectViewSet.as_view({
            "get": "installation_inspection_review_queue",
        })
        response = view(request, pk=str(self.project.pk))
        self.assertEqual(response.status_code, 200)
        self.assertIs(response.data["read_only"], True)
        self.assertIs(response.data["completion_authorized"], False)
        return response.data

    def record(self):
        return record_post_installation_inspection(
            actor=self.inspector,
            project_id=self.project.pk,
            inspection_passed=True,
            notes="Isolated fixture inspection notes for review readiness.",
        )

    def test_no_candidate_is_not_submittable(self):
        result = self.queue()
        self.assertEqual(result["status"], "NO_INSPECTION")
        self.assertIs(result["review_submission_available"], False)

    def test_pending_candidate_without_gate_is_read_only(self):
        self.record()
        with patch.dict("os.environ", {
            "GECC_INSTALLATION_EVIDENCE_BROWSER_ENABLED": "0",
        }):
            result = self.queue()
        self.assertEqual(result["status"], "PENDING_INDEPENDENT_REVIEW")
        self.assertIs(result["review_submission_available"], False)

    def test_isolated_test_database_gate_is_explicit(self):
        self.record()
        with patch.dict("os.environ", {
            "GECC_INSTALLATION_EVIDENCE_BROWSER_ENABLED": "1",
        }):
            result = self.queue()
        self.assertEqual(result["status"], "PENDING_INDEPENDENT_REVIEW")
        self.assertIs(result["review_submission_available"], True)
        self.assertIs(result["trusted_installation_evidence"], False)
        self.assertIs(result["final_receipt_issuance_authorized"], False)
