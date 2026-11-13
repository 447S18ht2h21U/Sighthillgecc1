"""Validated completion provider payload; no network access."""
import copy
from unittest.mock import patch
from uuid import uuid4

from django.test import SimpleTestCase
from rest_framework.exceptions import PermissionDenied, ValidationError

from . import test_completion_send_manifest_4619 as fixtures
from .models import Role
from .completion_provider_payload_4626 import (
    build_completion_envelope,
)


class CompletionProviderPayloadTests(SimpleTestCase):
    setUp = fixtures.CompletionSendManifestTests.setUp

    def build(self):
        with patch(
            "core.release.validate_package"
        ), patch(
            "core.release.status",
            return_value={"status": "APPROVED"},
        ):
            return build_completion_envelope(
                actor=self.actor,
                attempt=self.attempt,
            )

    def test_exact_pdf_and_reviewed_routing_preserved(self):
        before = copy.deepcopy(self.plan.review["envelope_preview"])
        result = self.build()

        self.assertEqual(result.document_sha256, (self.digest,))
        self.assertEqual(result.payload["status"], "created")
        self.assertEqual(
            result.payload["transactionId"],
            str(self.attempt.pk),
        )
        self.assertEqual(
            result.payload["recipients"],
            before["recipients"],
        )
        self.assertEqual(
            result.payload["documents"][0]["documentBase64"],
            self.package.payload["documents"][0]["documentBase64"],
        )
        self.assertEqual(
            self.plan.review["envelope_preview"],
            before,
        )
        self.assertFalse(result.send_available)
        self.assertFalse(result.provider_authenticated)
        self.assertFalse(result.envelope_sent)

    def test_required_signatures_and_dates_remain_provider_managed(self):
        result = self.build()
        signers = result.payload["recipients"]["signers"]

        self.assertEqual(
            {s["recipientId"]: s["routingOrder"] for s in signers},
            {"1": "2", "2": "1"},
        )

        for signer in signers:
            tabs = signer["tabs"]
            self.assertEqual(len(tabs["signHereTabs"]), 1)
            self.assertEqual(len(tabs["dateSignedTabs"]), 1)

            for tab in (
                tabs["signHereTabs"] + tabs["dateSignedTabs"]
            ):
                self.assertNotIn("value", tab)
                self.assertNotIn("signedDate", tab)

    def test_ceo_may_prepare_the_request(self):
        self.actor.role = Role.CEO
        self.assertEqual(self.build().payload["status"], "created")

    def test_comptroller_cannot_prepare_send_request(self):
        self.actor.role = Role.COMPTROLLER
        with self.assertRaises(PermissionDenied):
            self.build()

    def test_changed_certificate_bytes_rejected(self):
        self.package.payload["documents"][0]["documentBase64"] = (
            "JVBERi0xLjQKYWx0ZXJlZA=="
        )
        with self.assertRaises(ValidationError):
            self.build()

    def test_missing_date_tab_rejected(self):
        self.plan.review["envelope_preview"]["recipients"][
            "signers"
        ][1]["tabs"]["dateSignedTabs"] = []
        with self.assertRaises(ValidationError):
            self.build()

    def test_sent_attempt_cannot_rebuild_request(self):
        self.attempt.state = "SENT_UNCHECKED"
        self.attempt.provider_envelope_id = str(uuid4())
        self.attempt.first_send_started_at = object()
        with self.assertRaises(ValidationError):
            self.build()

    def test_changed_signer_routing_rejected(self):
        self.plan.review["envelope_preview"]["recipients"][
            "signers"
        ][0]["routingOrder"] = "1"
        with self.assertRaises(ValidationError):
            self.build()
