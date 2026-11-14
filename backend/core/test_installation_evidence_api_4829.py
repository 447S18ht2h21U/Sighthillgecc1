"""Isolated operational installation evidence endpoint acceptance."""
from unittest.mock import patch

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
from .installation_source_artifact_4826 import (
    retain_installation_source,
)


@override_settings(DEBUG=True, ENVIRONMENT="development")
class OperationalInstallationEvidence4829(TestCase):
    setUp = Fixture.setUp

    def request(self, actor=None):
        factory = APIRequestFactory()
        req = factory.get(
            "/api/operational-projects/"
            f"{self.project.pk}/installation-evidence-status/"
        )
        if actor is not None:
            force_authenticate(req, user=actor)
        view = OperationalProjectViewSet.as_view({
            "get": "installation_evidence_status",
        })
        return view(req, pk=str(self.project.pk))

    def assert_blocked(self, response):
        self.assertEqual(response.status_code, 200)
        body = response.data
        self.assertTrue(body["read_only"])
        for key in (
            "installation_source_authenticated",
            "trusted_installation_evidence",
            "final_receipt_issuance_authorized",
            "provider_email_authenticated",
            "customer_delivery_verified",
            "completion_authorized",
        ):
            self.assertIs(body[key], False, key)
        self.assertNotIn("content_base64", str(body))
        self.assertNotIn("Synthetic installation inspection source", str(body))

    def test_comptroller_reads_missing_evidence_without_release(self):
        response = self.request(self.reviewer)
        self.assert_blocked(response)
        self.assertFalse(
            response.data["internal_acceptance_candidate_verified"]
        )

    def test_accepted_source_is_visible_but_untrusted(self):
        inspection = record_post_installation_inspection(
            actor=self.inspector,
            project_id=self.project.pk,
            inspection_passed=True,
            notes="Physical post-installation inspection completed.",
        )
        review_post_installation_inspection(
            actor=self.reviewer,
            inspection_id=inspection.pk,
            accept=True,
            reason="Independent examination supports candidate acceptance.",
            independently_examined=True,
        )
        retain_installation_source(
            actor=self.inspector,
            project_id=self.project.pk,
            inspection_id=inspection.pk,
            content=b"%PDF-1.4\nSynthetic source bytes\n%%EOF",
            description="Synthetic installation inspection source document.",
        )

        response = self.request(self.reviewer)
        self.assert_blocked(response)
        self.assertTrue(
            response.data["internal_acceptance_candidate_verified"]
        )
        self.assertTrue(
            response.data["installation_source_integrity_verified"]
        )
        self.assertEqual(
            response.data["installation_provenance_status"],
            "SOURCE_ARTIFACT_RETAINED_UNAUTHENTICATED",
        )

    def test_installation_manager_is_denied_administrative_evidence(self):
        response = self.request(self.inspector)
        self.assertEqual(response.status_code, 403)

    def test_unauthenticated_request_is_denied(self):
        response = self.request()
        self.assertIn(response.status_code, (401, 403))

    def test_verification_failure_returns_blocked_status(self):
        with patch(
            "core.operational_project_api."
            "OperationalProjectViewSet.installation_evidence_status",
            wraps=None,
        ) if False else patch(
            "core.installation_completion_evidence_4815."
            "assess_installation_provenance",
            side_effect=ValueError("Synthetic verification failure"),
        ):
            response = self.request(self.reviewer)

        self.assert_blocked(response)
        self.assertEqual(
            response.data["status"],
            "EVIDENCE_VERIFICATION_FAILED",
        )
