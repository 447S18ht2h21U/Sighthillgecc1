"""Integrated offline inspection signing acceptance.

Real PDF, contract, placement, envelope, authorization DB and audit.
Only the upstream independent evidence-to-manifest boundary is replaced
with a controlled, internally consistent synthetic manifest.

No provider network requests or production database use.
"""
import os
from hashlib import sha256
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from core.models import (
    AuditEvent,
    AuditHead,
    Customer,
    MSR,
    Project,
    ProjectEvidence,
    Role,
    User,
)
from core.installation_provider_oauth_4979 import canonical_hash
from core.installation_attestation_manifest_4941 import (
    InstallationSigningManifest,
)
from core.installation_draft_browser_5185 import (
    assemble,
    authorize,
)
from core.installation_draft_authorization_5179 import KIND
from core.test_installation_draft_persistence_5194 import (
    disposable_customer_fields,
)


FLAG = "GECC_IM_DRAFT_AUTHORIZATION_TEST_ENABLED"


@override_settings(ENVIRONMENT="development", DEBUG=True)
class IntegratedInspectionSigning5197Tests(TestCase):

    def setUp(self):
        flag = patch.dict(os.environ, {FLAG: "1"})
        flag.start()
        self.addCleanup(flag.stop)

        self.ceo = User.objects.create_user(
            username="inspection_5197_ceo",
            role=Role.CEO,
            initials="IC",
        )

        self.sales = User.objects.create_user(
            username="inspection_5197_sales",
            role=Role.SALES_ASSOCIATE,
            initials="IS",
        )

        self.manager = User.objects.create_user(
            username="inspection_5197_im",
            role=Role.INSTALLATION_MANAGER,
            initials="IM",
            email="inspection5197@example.invalid",
            first_name="Inspection",
            last_name="Manager",
        )

        customer = Customer.objects.create(
            **disposable_customer_fields(created_by=self.ceo)
        )

        self.project = Project.objects.create(
            code="INSPECTION-5197",
            customer=customer,
            location="Disposable integration test",
            sales_associate=self.sales,
            reviewer=self.ceo,
            state="DRAFT",
        )

        self.msr = MSR.objects.create(
            project=self.project,
            number=1,
            status="APPROVED",
            snapshot={},
            created_by=self.sales,
            prepared_by=self.sales,
            approved_by=self.ceo,
        )

        self.project.current_approved = self.msr
        self.project.save(update_fields=["current_approved"])

        AuditHead.objects.get_or_create(pk=1)

        self.manifest = self.make_manifest()

        # Replace ONLY the upstream independent source verifier
        # boundary. Every downstream builder remains real.
        self.form_patch = patch(
            "core.installation_inspection_form_4945."
            "build_installation_signing_manifest",
            return_value=self.manifest,
        )
        self.contract_patch = patch(
            "core.installation_docusign_contract_4959."
            "build_installation_signing_manifest",
            return_value=self.manifest,
        )

        self.form_patch.start()
        self.contract_patch.start()
        self.addCleanup(self.form_patch.stop)
        self.addCleanup(self.contract_patch.stop)

    def make_manifest(self):
        source_pdf = (
            b"%PDF-1.4\n"
            b"Disposable installation source acceptance fixture\n"
            b"%%EOF\n"
        )

        source_id = str(uuid4())
        preparation_id = str(uuid4())
        binding_digest = "b" * 64

        identity = {
            "purpose": "DOCUSIGN_INSTALLATION_SIGNING_MANIFEST_4941",
            "project_id": str(self.project.pk),
            "approved_msr_id": str(self.msr.pk),
            "approved_msr_version": 1,
            "preparation_evidence_id": preparation_id,
            "source_evidence_id": source_id,
            "source_pdf_sha256": sha256(source_pdf).hexdigest(),
            "signer_user_id": str(self.manager.pk),
            "signer_email": self.manager.email,
            "signer_name": self.manager.get_full_name(),
            "attestation_binding_sha256": binding_digest,
            "source_document_role": "SUPPORTING_SOURCE_NOT_SIGNED",
        }

        return InstallationSigningManifest(
            project_id=identity["project_id"],
            approved_msr_id=identity["approved_msr_id"],
            approved_msr_version=1,
            preparation_evidence_id=preparation_id,
            source_evidence_id=source_id,
            source_pdf_sha256=identity["source_pdf_sha256"],
            source_pdf=source_pdf,
            signer_user_id=identity["signer_user_id"],
            signer_email=identity["signer_email"],
            signer_name=identity["signer_name"],
            attestation_binding_sha256=binding_digest,
            manifest_sha256=canonical_hash(identity),
        )

    def test_missing_independent_source_blocks_browser_readiness(self):
        from core.installation_draft_status_5186 import _readiness

        self.assertFalse(
            _readiness(self.project, self.msr)
        )
        self.assertFalse(
            ProjectEvidence.objects.filter(
                msr=self.msr, kind=KIND
            ).exists()
        )

    def test_real_builders_generate_bound_unsent_envelope(self):
        envelope = assemble(
            actor=self.ceo,
            project_id=self.project.pk,
        )

        self.assertEqual(
            envelope.project_id,
            str(self.project.pk),
        )
        self.assertEqual(
            envelope.approved_msr_id,
            str(self.msr.pk),
        )
        self.assertEqual(
            str(envelope.approved_msr_version),
            "1",
        )
        self.assertEqual(
            envelope.signer_user_id,
            str(self.manager.pk),
        )

        self.assertIsNone(envelope.envelope_id)
        self.assertFalse(envelope.provider_signed)
        self.assertFalse(envelope.completion_authorized)

        request = envelope.request
        self.assertEqual(request["status"], "created")
        self.assertTrue(
            isinstance(
                envelope.envelope_package_sha256, str
            )
        )
        self.assertEqual(
            len(envelope.envelope_package_sha256), 64
        )

        self.assertFalse(
            ProjectEvidence.objects.filter(
                msr=self.msr, kind=KIND
            ).exists()
        )

    def test_real_package_authorization_persists_and_audits(self):
        before_audit = AuditEvent.objects.count()

        result = authorize(
            actor=self.ceo,
            project_id=self.project.pk,
            confirmed=True,
        )

        self.assertEqual(
            result["status"],
            "DRAFT_INTENT_RECORDED",
        )
        self.assertFalse(
            result["provider_request_authorized"]
        )
        self.assertFalse(result["send_authorized"])

        evidence = ProjectEvidence.objects.get(
            pk=result["evidence_id"],
            msr=self.msr,
            kind=KIND,
        )

        self.assertEqual(
            evidence.digest,
            canonical_hash(evidence.data),
        )
        self.assertEqual(
            evidence.created_by_id,
            self.ceo.pk,
        )
        self.assertEqual(
            evidence.data["project_id"],
            str(self.project.pk),
        )
        self.assertEqual(
            evidence.data["msr_id"],
            str(self.msr.pk),
        )

        fingerprint = evidence.data[
            "draft_payload_sha256"
        ]
        self.assertEqual(len(fingerprint), 64)

        for key in (
            "provider_draft_created",
            "provider_request_authorized",
            "send_authorized",
            "provider_signature_verified",
            "inspection_findings_verified",
            "receipt_issuance_authorized",
            "project_completion_authorized",
        ):
            self.assertIs(
                evidence.data[key], False
            )

        self.assertEqual(
            AuditEvent.objects.count(),
            before_audit + 1,
        )

        event = AuditEvent.objects.latest("sequence")
        self.assertEqual(event.actor_id, self.ceo.pk)
        self.assertEqual(
            event.entity_id, self.project.pk
        )
        self.assertEqual(
            event.action,
            "installation.inspection_sandbox_draft_intent_recorded",
        )
        self.assertEqual(
            event.payload["evidence_id"],
            str(evidence.pk),
        )

    def test_duplicate_real_package_authorization_rejected(self):
        authorize(
            actor=self.ceo,
            project_id=self.project.pk,
            confirmed=True,
        )

        before_audit = AuditEvent.objects.count()

        with self.assertRaises(ValidationError):
            authorize(
                actor=self.ceo,
                project_id=self.project.pk,
                confirmed=True,
            )

        self.assertEqual(
            ProjectEvidence.objects.filter(
                msr=self.msr, kind=KIND
            ).count(),
            1,
        )
        self.assertEqual(
            AuditEvent.objects.count(),
            before_audit,
        )