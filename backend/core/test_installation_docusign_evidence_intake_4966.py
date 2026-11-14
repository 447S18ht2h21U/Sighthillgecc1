"""One focused test suite for evidence-intake integration."""
from dataclasses import replace
from unittest import TestCase
from unittest.mock import patch

from django.core.exceptions import ValidationError
from rest_framework.exceptions import PermissionDenied

from .test_installation_docusign_response_4964 import (
    setup, response, parse,
)
from .installation_docusign_evidence_intake_4966 import (
    assemble_unverified_inspection_evidence,
)

M = "core.installation_docusign_evidence_intake_4966"


def pdf(label):
    return (
        b"%PDF-1.4\n"
        + label.encode("ascii")
        + b" " * 160
        + b"\n%%EOF"
    )


def inputs(negative=()):
    envelope = setup()
    observation = parse(
        envelope, response(envelope, set(negative))
    )
    return dict(
        envelope=envelope,
        observation=observation,
        claimed_envelope_status="completed",
        claimed_recipient_id="1",
        signed_pdf=pdf("synthetic-signed-document"),
        certificate_pdf=pdf("synthetic-certificate"),
    )


class InspectionEvidenceIntake4966Tests(TestCase):
    def test_completed_candidate_is_not_authenticated(self):
        result = assemble_unverified_inspection_evidence(**inputs())
        self.assertEqual(len(result.inspection_findings), 5)
        self.assertEqual(result.negative_inspection_ids, ())
        self.assertEqual(result.status, "EVIDENCE_INTAKE_UNAUTHENTICATED")
        self.assertFalse(result.authenticated_provider_readback)
        self.assertFalse(result.provider_signature_verified)
        self.assertFalse(result.provider_date_verified)
        self.assertFalse(result.stored_in_durable_evidence)
        self.assertFalse(result.completion_authorized)

    def test_negative_findings_stay_candidates(self):
        result = assemble_unverified_inspection_evidence(
            **inputs(("inspection_2", "inspection_5"))
        )
        self.assertEqual(
            result.negative_inspection_ids,
            ("inspection_2", "inspection_5"),
        )
        self.assertFalse(result.corrective_actions_created)

    def test_noncompleted_claim_rejected(self):
        values = inputs()
        values["claimed_envelope_status"] = "sent"
        with self.assertRaises(ValidationError):
            assemble_unverified_inspection_evidence(**values)

    def test_wrong_recipient_rejected(self):
        values = inputs()
        values["claimed_recipient_id"] = "2"
        with self.assertRaises(ValidationError):
            assemble_unverified_inspection_evidence(**values)

    def test_source_package_mismatch_rejected(self):
        values = inputs()
        values["observation"] = replace(
            values["observation"],
            envelope_package_sha256="0" * 64,
        )
        with self.assertRaises(ValidationError):
            assemble_unverified_inspection_evidence(**values)

    def test_untrusted_observation_cannot_claim_provider_auth(self):
        values = inputs()
        values["observation"] = replace(
            values["observation"],
            live_provider_retrieval_verified=True,
        )
        with self.assertRaises(ValidationError):
            assemble_unverified_inspection_evidence(**values)

    def test_unsigned_pdf_cannot_pass_as_signed_pdf(self):
        import base64
        values = inputs()
        values["signed_pdf"] = base64.b64decode(
            values["envelope"].request["documents"][0]["documentBase64"]
        )
        with self.assertRaises(ValidationError):
            assemble_unverified_inspection_evidence(**values)

    def test_identical_document_and_certificate_rejected(self):
        values = inputs()
        values["certificate_pdf"] = values["signed_pdf"]
        with self.assertRaises(ValidationError):
            assemble_unverified_inspection_evidence(**values)

    def test_deterministic_bundle_fingerprint(self):
        values = inputs()
        first = assemble_unverified_inspection_evidence(**values)
        second = assemble_unverified_inspection_evidence(**values)
        self.assertEqual(first.bundle_sha256, second.bundle_sha256)
        self.assertNotEqual(
            first.signed_pdf_sha256, first.certificate_sha256
        )

    @patch(M + ".settings")
    def test_production_denied(self, settings):
        settings.ENVIRONMENT = "production"
        settings.DEBUG = False
        with self.assertRaises(PermissionDenied):
            assemble_unverified_inspection_evidence(**inputs())
