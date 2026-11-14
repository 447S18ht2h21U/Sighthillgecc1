"""Real isolated-database installation provenance boundary tests."""
from dataclasses import replace

from django.test import TestCase, override_settings

from .test_post_installation_acceptance_4819 import (
    PostInstallationAcceptance4819 as Fixture,
)
from .post_installation_acceptance_verifier_4820 import (
    verify_post_installation_acceptance,
)
from .installation_provenance_gate_4825 import (
    assess_installation_provenance,
)
from .installation_completion_evidence_4815 import (
    assess_installation_completion_evidence,
)
from .final_receipt_release_preflight_4812 import (
    assess_final_receipt_release_preflight,
)


@override_settings(DEBUG=True, ENVIRONMENT="development")
class InstallationProvenance4825(TestCase):
    setUp = Fixture.setUp
    capture = Fixture.capture
    review = Fixture.review

    def assert_blocked(self, result):
        self.assertFalse(result.trusted_installation_evidence)
        self.assertFalse(result.final_receipt_issuance_authorized)
        self.assertFalse(result.completion_authorized)

    def test_missing_acceptance_has_distinct_provenance_status(self):
        acceptance = verify_post_installation_acceptance(self.project)
        gate = assess_installation_provenance(
            project=self.project, acceptance=acceptance
        )
        self.assertEqual(
            gate.status, "INTERNAL_ACCEPTANCE_CANDIDATE_MISSING"
        )
        self.assertFalse(gate.source_artifact_authenticated)
        self.assert_blocked(gate)

        installation = assess_installation_completion_evidence(
            self.project
        )
        self.assertEqual(
            installation.installation_provenance_status, gate.status
        )
        self.assert_blocked(installation)

    def test_accepted_internal_review_never_authenticates_source(self):
        inspection = self.capture()
        self.review(inspection)

        acceptance = verify_post_installation_acceptance(self.project)
        self.assertTrue(acceptance.acceptance_candidate_verified)

        gate = assess_installation_provenance(
            project=self.project, acceptance=acceptance
        )
        self.assertEqual(
            gate.status, "AWAITING_AUTHENTICATED_INSTALLATION_PROOF"
        )
        self.assertTrue(gate.internal_acceptance_candidate_verified)
        self.assertFalse(gate.source_artifact_authenticated)
        self.assertFalse(gate.source_artifact_integrity_verified)
        self.assertTrue(gate.required_proof)
        self.assert_blocked(gate)

        installation = assess_installation_completion_evidence(
            self.project
        )
        receipt = assess_final_receipt_release_preflight(
            self.project
        )
        self.assertEqual(
            installation.installation_provenance_status, gate.status
        )
        self.assertEqual(
            receipt.installation_provenance_status, gate.status
        )
        self.assertTrue(receipt.acceptance_candidate_verified)
        self.assert_blocked(installation)
        self.assert_blocked(receipt)
        self.assertFalse(receipt.customer_delivery_verified)

    def test_forged_acceptance_authority_is_rejected(self):
        acceptance = verify_post_installation_acceptance(self.project)
        forged = replace(
            acceptance,
            trusted_installation_evidence=True,
        )
        with self.assertRaises(ValueError):
            assess_installation_provenance(
                project=self.project, acceptance=forged
            )

    def test_wrong_msr_identity_is_rejected(self):
        acceptance = verify_post_installation_acceptance(self.project)
        forged = replace(acceptance, msr_id="wrong-msr")
        with self.assertRaises(ValueError):
            assess_installation_provenance(
                project=self.project, acceptance=forged
            )
