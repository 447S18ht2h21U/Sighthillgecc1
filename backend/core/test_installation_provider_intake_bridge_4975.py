"""Focused integration of provider-shaped readback into existing intake."""
from dataclasses import replace
from hashlib import sha256
from unittest import TestCase
from unittest.mock import patch

from django.core.exceptions import ValidationError
from rest_framework.exceptions import PermissionDenied

from .test_installation_docusign_evidence_intake_4966 import (
    inputs,
)
from .test_installation_docusign_response_4964 import response
from .installation_provider_readback_4972 import (
    SandboxInspectionReadback4972,
)
from .installation_provider_intake_bridge_4975 import (
    link_unverified_inspection_readback,
)

M = "core.installation_provider_intake_bridge_4975"
ACCOUNT = "11111111-1111-4111-8111-111111111111"
ENVELOPE = "22222222-2222-4222-8222-222222222222"


def candidate(negative=()):
    values = inputs(tuple(negative))
    envelope = values["envelope"]
    signed = values["signed_pdf"]
    certificate = values["certificate_pdf"]
    recipient = envelope.request["recipients"]["signers"][0]

    readback = SandboxInspectionReadback4972(
        account_id=ACCOUNT,
        envelope_id=ENVELOPE,
        envelope_summary={
            "envelopeId": ENVELOPE,
            "status": "completed",
        },
        recipient_summary={
            "signers": [{
                "recipientId": "1",
                "name": recipient["name"],
                "email": recipient["email"],
                "status": "completed",
            }]
        },
        recipient_tabs=response(envelope, set(negative)),
        signed_pdf=signed,
        certificate_pdf=certificate,
        signed_pdf_sha256=sha256(signed).hexdigest(),
        certificate_sha256=sha256(certificate).hexdigest(),
    )
    return envelope, readback


def link(envelope, readback, **changes):
    params = dict(
        envelope=envelope,
        readback=readback,
        expected_account_id=ACCOUNT,
        expected_envelope_id=ENVELOPE,
    )
    params.update(changes)
    return link_unverified_inspection_readback(**params)


class OfflineProviderIntakeBridge4975Tests(TestCase):
    def test_readback_attaches_to_existing_unverified_bundle(self):
        envelope, readback = candidate()
        result = link(envelope, readback)
        self.assertEqual(result.account_id, ACCOUNT)
        self.assertEqual(result.envelope_id, ENVELOPE)
        self.assertEqual(len(result.evidence_bundle.inspection_findings), 5)
        self.assertFalse(result.provider_origin_authenticated)
        self.assertFalse(result.signer_identity_verified)
        self.assertFalse(result.certificate_verified)
        self.assertFalse(result.evidence_retained)
        self.assertFalse(result.completion_authorized)

    def test_negative_manager_finding_preserved(self):
        envelope, readback = candidate(("inspection_4",))
        result = link(envelope, readback)
        self.assertEqual(
            result.evidence_bundle.negative_inspection_ids,
            ("inspection_4",),
        )
        self.assertFalse(result.corrective_actions_created)

    def test_wrong_envelope_identity_rejected(self):
        envelope, readback = candidate()
        with self.assertRaises(ValidationError):
            link(envelope, readback, expected_envelope_id=ACCOUNT)

    def test_changed_recipient_rejected(self):
        envelope, readback = candidate()
        readback.recipient_summary["signers"][0]["email"] = "wrong@example.com"
        with self.assertRaises(ValidationError):
            link(envelope, readback)

    def test_missing_answer_rejected(self):
        envelope, readback = candidate()
        readback.recipient_tabs["radioGroupTabs"][0]["radios"][0][
            "selected"
        ] = "false"
        with self.assertRaises(ValidationError):
            link(envelope, readback)

    def test_duplicate_answer_rejected(self):
        envelope, readback = candidate()
        readback.recipient_tabs["radioGroupTabs"][0]["radios"][1][
            "selected"
        ] = "true"
        with self.assertRaises(ValidationError):
            link(envelope, readback)

    def test_changed_pdf_fingerprint_rejected(self):
        envelope, readback = candidate()
        tampered = replace(
            readback,
            signed_pdf_sha256="0" * 64,
        )
        with self.assertRaises(ValidationError):
            link(envelope, tampered)

    def test_unverified_readback_cannot_claim_signature_trust(self):
        envelope, readback = candidate()
        tampered = replace(
            readback, provider_signature_verified=True
        )
        with self.assertRaises(ValidationError):
            link(envelope, tampered)

    @patch(M + ".settings")
    def test_production_denied(self, settings):
        settings.ENVIRONMENT = "production"
        settings.DEBUG = False
        envelope, readback = candidate()
        with self.assertRaises(PermissionDenied):
            link(envelope, readback)
