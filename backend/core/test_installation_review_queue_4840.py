"""Isolated acceptance for independent inspection review discovery."""
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from .test_post_installation_acceptance_4819 import (
    PostInstallationAcceptance4819 as Fixture,
)
from .operational_project_api import OperationalProjectViewSet
from .post_installation_acceptance_4819 import (
    record_post_installation_inspection,
    review_post_installation_inspection,
)


@override_settings(DEBUG=True, ENVIRONMENT="development")
class InspectionReviewQueue4840(TestCase):
    setUp = Fixture.setUp

    def get_queue(self, actor):
        request = APIRequestFactory().get(
            f"/api/operational-projects/{self.project.pk}/"
            "installation-inspection-review-queue/"
        )
        if actor is not None:
            force_authenticate(request, user=actor)
        view = OperationalProjectViewSet.as_view({
            "get": "installation_inspection_review_queue",
        })
        return view(request, pk=str(self.project.pk))

    def record(self):
        return record_post_installation_inspection(
            actor=self.inspector,
            project_id=self.project.pk,
            inspection_passed=True,
            notes="Actual physical inspection candidate was recorded.",
        )

    def assert_blocked(self, response):
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIs(response.data["read_only"], True)
        for field in (
            "trusted_installation_evidence",
            "final_receipt_issuance_authorized",
            "customer_delivery_verified",
            "completion_authorized",
        ):
            self.assertIs(response.data[field], False)

    def test_no_inspection_reports_missing(self):
        result = self.get_queue(self.reviewer)
        self.assert_blocked(result)
        self.assertEqual(result.data["status"], "NO_INSPECTION")
        self.assertIsNone(result.data["pending_inspection_id"])

    def test_valid_inspection_returns_exact_pending_id(self):
        inspection = self.record()
        result = self.get_queue(self.reviewer)
        self.assert_blocked(result)
        self.assertEqual(
            result.data["status"], "PENDING_INDEPENDENT_REVIEW"
        )
        self.assertEqual(
            result.data["pending_inspection_id"],
            str(inspection.pk),
        )
        self.assertIs(result.data["inspection_passed"], True)
        self.assertEqual(
            result.data["inspection_notes"],
            "Actual physical inspection candidate was recorded.",
        )
        self.assertTrue(result.data["inspection_recorded_at"])
        self.assertNotIn("content_base64", str(result.data))
        self.assertNotIn("content_base64", str(result.data))

    def test_review_consumes_pending_inspection(self):
        inspection = self.record()
        review_post_installation_inspection(
            actor=self.reviewer,
            inspection_id=inspection.pk,
            accept=True,
            reason="Independent inspection candidate reviewed and accepted.",
            independently_examined=True,
        )
        result = self.get_queue(self.reviewer)
        self.assert_blocked(result)
        self.assertEqual(
            result.data["status"], "REVIEW_RECORDED_UNVERIFIED"
        )
        self.assertIsNone(result.data["pending_inspection_id"])
        self.assertIs(result.data["independent_review_recorded"], True)
        self.assertEqual(
            result.data["review_decision"],
            "INTERNAL_CANDIDATE_ACCEPTED",
        )

    def test_rejected_inspection_displays_explicit_decision(self):
        inspection = self.record()
        review_post_installation_inspection(
            actor=self.reviewer,
            inspection_id=inspection.pk,
            accept=False,
            reason=(
                "Simulation only; no actual physical inspection "
                "or independent site evidence was examined."
            ),
            independently_examined=False,
        )
        response = self.get_queue(self.reviewer)
        self.assert_blocked(response)
        self.assertEqual(
            response.data["status"], "REVIEW_RECORDED_UNVERIFIED"
        )
        self.assertEqual(
            response.data["review_decision"], "REJECTED"
        )
        self.assertIsNone(response.data["pending_inspection_id"])

    def test_installation_manager_cannot_read_comptroller_queue(self):
        result = self.get_queue(self.inspector)
        self.assertEqual(result.status_code, 403)

    def test_anonymous_request_cannot_read_review_queue(self):
        result = self.get_queue(None)
        self.assertIn(result.status_code, (401, 403))
