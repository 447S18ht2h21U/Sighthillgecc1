"""Real isolated-database installation source integration tests."""
from unittest.mock import patch

from django.test import TestCase, override_settings

from .test_post_installation_acceptance_4819 import (
    PostInstallationAcceptance4819 as Fixture,
)
from .installation_source_artifact_4826 import (
    retain_installation_source,
)
from .installation_provenance_gate_4825 import (
    assess_installation_provenance,
)
from .post_installation_acceptance_verifier_4820 import (
    verify_post_installation_acceptance,
)
from .installation_completion_evidence_4815 import (
    assess_installation_completion_evidence,
)
from .final_receipt_release_preflight_4812 import (
    assess_final_receipt_release_preflight,
)
from .models import AuditEvent, ProjectEvidence


@override_settings(DEBUG=True, ENVIRONMENT="development")
class InstallationSourceIntegration4827(TestCase):
    setUp = Fixture.setUp
    capture = Fixture.capture
    review = Fixture.review

    def prepare(self, with_source):
        inspection = self.capture()
        self.review(inspection)
        if with_source:
            retain_installation_source(
                actor=self.inspector,
                project_id=self.project.pk,
                inspection_id=inspection.pk,
                content=b"%PDF-1.4\nTest inspection document\n%%EOF",
                description="Synthetic installation inspection source.",
            )

    def assess(self):
        acceptance = verify_post_installation_acceptance(self.project)
        return assess_installation_provenance(
            project=self.project, acceptance=acceptance
        )

    def assert_no_release(self, result):
        self.assertFalse(result.trusted_installation_evidence)
        self.assertFalse(result.final_receipt_issuance_authorized)
        self.assertFalse(result.completion_authorized)

    def test_accepted_without_source_is_missing(self):
        self.prepare(False)
        result = self.assess()
        self.assertEqual(
            result.status, "AWAITING_AUTHENTICATED_INSTALLATION_PROOF"
        )
        self.assertFalse(result.source_artifact_integrity_verified)
        self.assertFalse(result.source_artifact_authenticated)
        self.assert_no_release(result)

    def test_exact_source_retention_does_not_grant_trust(self):
        self.prepare(True)
        before = (
            ProjectEvidence.objects.count(),
            AuditEvent.objects.count(),
        )

        gate = self.assess()
        installation = assess_installation_completion_evidence(self.project)
        receipt = assess_final_receipt_release_preflight(self.project)

        self.assertEqual(
            gate.status, "SOURCE_ARTIFACT_RETAINED_UNAUTHENTICATED"
        )
        self.assertTrue(gate.source_artifact_integrity_verified)
        self.assertTrue(gate.source_artifact_retained_verified)
        self.assertFalse(gate.source_artifact_authenticated)

        self.assertEqual(
            installation.installation_provenance_status, gate.status
        )
        self.assertTrue(
            installation.installation_source_integrity_verified
        )
        self.assertEqual(
            receipt.installation_provenance_status, gate.status
        )
        self.assertTrue(receipt.installation_source_integrity_verified)

        for result in (gate, installation, receipt):
            self.assert_no_release(result)

        self.assertFalse(receipt.customer_delivery_verified)
        self.assertEqual(before, (
            ProjectEvidence.objects.count(),
            AuditEvent.objects.count(),
        ))

    def test_source_verification_failure_fails_closed(self):
        self.prepare(True)
        with patch(
            "core.installation_provenance_gate_4825."
            "verify_retained_installation_source",
            return_value=False,
        ):
            gate = self.assess()
            receipt = assess_final_receipt_release_preflight(self.project)

        self.assertFalse(gate.source_artifact_integrity_verified)
        self.assertFalse(receipt.installation_source_integrity_verified)
        self.assert_no_release(gate)
        self.assert_no_release(receipt)

    def test_source_verifier_exception_fails_closed(self):
        self.prepare(True)
        with patch(
            "core.installation_provenance_gate_4825."
            "verify_retained_installation_source",
            side_effect=ValueError("Synthetic integrity failure"),
        ):
            result = self.assess()

        self.assertFalse(result.source_artifact_integrity_verified)
        self.assert_no_release(result)
