"""Read-only DocuSign completion package security checks."""
import base64
import hashlib
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.test import SimpleTestCase
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import Role
from .completion_send_manifest_4619 import (
    prepare_completion_send_manifest,
)


class CompletionSendManifestTests(SimpleTestCase):
    def setUp(self):
        self.actor = SimpleNamespace(
            pk=uuid4(),
            is_authenticated=True,
            is_active=True,
            role=Role.SALES_MANAGER,
        )
        self.initiator = SimpleNamespace(
            pk=uuid4(),
            is_active=True,
            role=Role.COMPTROLLER,
        )
        msr_id = uuid4()
        project_id = uuid4()

        self.project = SimpleNamespace(
            pk=project_id,
            current_approved_id=msr_id,
            state="ACTIVE",
        )
        self.msr = SimpleNamespace(
            pk=msr_id,
            project_id=project_id,
            project=self.project,
            status="APPROVED",
            snapshot={"financing_type": "FINANCED"},
        )

        customer = {
            "name": "Synthetic Customer",
            "email": "customer@example.test",
        }
        gecc = {
            "name": "Synthetic GECC Signer",
            "email": "gecc@example.test",
        }

        self.pdf = b"%PDF-1.4\\nfictional approved certificate"
        self.digest = hashlib.sha256(self.pdf).hexdigest()

        def signer(recipient_id, routing_order, identity, prefix):
            tabs = {}
            for kind, label in (
                ("signHereTabs", prefix + "_signature"),
                ("dateSignedTabs", prefix + "_signed_date"),
                (
                    "fullNameTabs",
                    "customer_printed_name"
                    if prefix == "customer"
                    else "gecc_representative_name",
                ),
            ):
                entry = {
                    "documentId": "1",
                    "recipientId": recipient_id,
                    "tabLabel": label,
                }
                if kind == "signHereTabs":
                    entry["optional"] = "false"
                tabs[kind] = [entry]

            return {
                "recipientId": recipient_id,
                "routingOrder": routing_order,
                "name": identity["name"],
                "email": identity["email"],
                "tabs": tabs,
            }

        self.plan = SimpleNamespace(
            msr=self.msr,
            msr_id=msr_id,
            group="COMPLETION_FINANCED",
            review={
                "customer": customer,
                "gecc": gecc,
                "documents": [
                    {"kind": "COMPLETION_FINANCED"}
                ],
                "envelope_preview": {
                    "status": "created",
                    "documents": [{
                        "documentId": "1",
                        "name": "Certificate.pdf",
                        "fileExtension": "pdf",
                        "transformPdfFields": "false",
                    }],
                    "recipients": {
                        "signers": [
                            signer("1", "2", customer, "customer"),
                            signer("2", "1", gecc, "gecc"),
                        ]
                    },
                },
            },
        )

        package_id = uuid4()
        self.package = SimpleNamespace(
            pk=package_id,
            plan=self.plan,
            payload={
                "purpose": "UNSIGNED_RELEASE_REVIEW",
                "documents": [{
                    "kind": "COMPLETION_FINANCED",
                    "documentBase64": base64.b64encode(
                        self.pdf
                    ).decode("ascii"),
                    "pdf_sha256": self.digest,
                }],
            },
        )

        self.attempt = SimpleNamespace(
            pk=uuid4(),
            release_package_id=package_id,
            release_package=self.package,
            initiated_by=self.initiator,
            provider_account_id=str(uuid4()),
            provider_envelope_id="",
            state="AUTH_PENDING",
            first_send_started_at=None,
        )

    def assess(self):
        with patch(
            "core.release.validate_package"
        ), patch(
            "core.release.status",
            return_value={"status": "APPROVED"},
        ):
            return prepare_completion_send_manifest(
                actor=self.actor, attempt=self.attempt
            )

    def test_approved_manifest_is_never_a_send_authorization(self):
        result = self.assess()
        self.assertEqual(result.document_sha256, (self.digest,))
        self.assertTrue(result.signature_tabs_checked)
        self.assertTrue(result.signed_date_tabs_checked)
        self.assertFalse(result.ready_for_live_send)
        self.assertFalse(result.envelope_sent)
        self.assertFalse(result.completion_authorized)

    def test_ceo_is_authorized_for_manifest_review(self):
        self.actor.role = Role.CEO
        self.assertEqual(self.assess().recipient_ids, ("1", "2"))

    def test_comptroller_cannot_authorize_send_manifest(self):
        self.actor.role = Role.COMPTROLLER
        with self.assertRaises(PermissionDenied):
            self.assess()

    def test_sales_associate_cannot_authorize_send_manifest(self):
        self.actor.role = Role.SALES_ASSOCIATE
        with self.assertRaises(PermissionDenied):
            self.assess()

    def test_pdf_fingerprint_mismatch_rejected(self):
        self.package.payload["documents"][0]["pdf_sha256"] = "0" * 64
        with self.assertRaises(ValidationError):
            self.assess()

    def test_missing_release_pdf_rejected(self):
        self.package.payload["documents"][0]["documentBase64"] = ""
        with self.assertRaises(ValidationError):
            self.assess()

    def test_swapped_routing_order_rejected(self):
        self.plan.review["envelope_preview"]["recipients"][
            "signers"
        ][0]["routingOrder"] = "1"
        with self.assertRaises(ValidationError):
            self.assess()

    def test_missing_provider_date_signed_tab_rejected(self):
        self.plan.review["envelope_preview"]["recipients"][
            "signers"
        ][0]["tabs"]["dateSignedTabs"] = []
        with self.assertRaises(ValidationError):
            self.assess()

    def test_optional_signature_rejected(self):
        self.plan.review["envelope_preview"]["recipients"][
            "signers"
        ][0]["tabs"]["signHereTabs"][0]["optional"] = "true"
        with self.assertRaises(ValidationError):
            self.assess()

    def test_changed_customer_email_rejected(self):
        self.plan.review["envelope_preview"]["recipients"][
            "signers"
        ][0]["email"] = "other@example.test"
        with self.assertRaises(ValidationError):
            self.assess()

    def test_sent_status_cannot_be_reused(self):
        self.plan.review["envelope_preview"]["status"] = "sent"
        with self.assertRaises(ValidationError):
            self.assess()

    def test_wrong_financing_certificate_rejected(self):
        self.package.payload["documents"][0]["kind"] = (
            "COMPLETION_NON_FINANCED"
        )
        with self.assertRaises(ValidationError):
            self.assess()
