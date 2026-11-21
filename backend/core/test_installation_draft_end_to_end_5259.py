"""Real-model, disposable-database inspection draft acceptance.

Synthetic customer and installation records are created only in Django's
isolated test database. No provider calls or operational API activation.
"""
import os
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings

from core.documents import canonical_hash
from core.models import ProjectEvidence, Role
from core.test_post_installation_acceptance_4819 import (
    PostInstallationAcceptance4819 as Fixture,
)
from core.installation_source_artifact_4826 import (
    retain_installation_source,
)
from core.installation_attestation_record_4939 import (
    record_installation_attestation_preparation,
)
from core.installation_draft_browser_5185 import authorize
from core.installation_draft_authorization_5179 import KIND
from core.installation_draft_handoff_5258 import verify_handoff
from core.installation_unsigned_pdf_preflight_5254 import (
    verify_unsigned_pdf,
)


@override_settings(DEBUG=True, ENVIRONMENT="development")
class InspectionDraftEndToEnd5259(TestCase):
    setUp = Fixture.setUp
    capture = Fixture.capture
    review = Fixture.review

    def establish_source(self):
        self.inspector.first_name = "Synthetic"
        self.inspector.last_name = "Installation Manager"
        self.inspector.email = "inspection-manager@example.invalid"
        self.inspector.save(
            update_fields=["first_name", "last_name", "email"]
        )

        self.fixture.manager.first_name = "Synthetic"
        self.fixture.manager.last_name = "Sales Manager"
        self.fixture.manager.email = "sales-manager@example.invalid"
        self.fixture.manager.save(
            update_fields=["first_name", "last_name", "email"]
        )

        inspection = self.capture()
        review = self.review(inspection)

        self.assertEqual(review.data["status"], "CANDIDATE_ACCEPTED")

        source = retain_installation_source(
            actor=self.inspector,
            project_id=self.project.pk,
            inspection_id=inspection.pk,
            content=(
                b"%PDF-1.4\n"
                b"Synthetic inspection source only\n"
                b"%%EOF\n"
            ),
            description=(
                "Synthetic inspection evidence for disposable "
                "integration acceptance."
            ),
        )
        return source

    def prepare_and_authorize(self):
        source = self.establish_source()

        with patch.dict(os.environ, {
            "GECC_INSTALL_ATTESTATION_PREP_TEST_ENABLED": "1",
            "GECC_IM_DRAFT_AUTHORIZATION_TEST_ENABLED": "1",
        }):
            preparation, created = (
                record_installation_attestation_preparation(
                    actor=self.fixture.manager, project_id=self.project.pk
                )
            )
            self.assertTrue(created)

            pdf = verify_unsigned_pdf(
                actor=self.fixture.manager, project_id=self.project.pk
            )
            self.assertEqual(
                pdf["status"], "UNSIGNED_PDF_VERIFIED_OFFLINE"
            )
            self.assertEqual(pdf["required_inspection_findings"], 5)
            self.assertEqual(pdf["required_signature_fields"], 2)
            self.assertFalse(pdf["document_sent"])

            intent = authorize(
                actor=self.fixture.manager,
                project_id=self.project.pk,
                confirmed=True,
            )
            self.assertEqual(
                intent["status"], "DRAFT_INTENT_RECORDED"
            )
            self.assertFalse(intent["send_authorized"])

        return source, preparation

    def handoff(self):
        with patch.dict(os.environ, {
            "GECC_IM_DRAFT_AUTHORIZATION_TEST_ENABLED": "1",
        }):
            return verify_handoff(
                actor=self.fixture.manager, project_id=self.project.pk
            )

    def test_complete_synthetic_chain_remains_non_authorizing(self):
        self.prepare_and_authorize()
        result = self.handoff()
        self.assertEqual(
            result["state"], "OFFLINE_DRAFT_HANDOFF_MATCHED"
        )
        self.assertTrue(result["read_only"])
        for field in (
            "provider_request_authorized",
            "provider_envelope_created",
            "send_authorized",
            "provider_signature_verified",
            "receipt_issuance_authorized",
            "project_completion_authorized",
        ):
            self.assertIs(result[field], False)

        self.assertEqual(
            ProjectEvidence.objects.filter(
                msr=self.msr, kind=KIND
            ).count(),
            1,
        )

    def test_tampered_source_blocks_authorized_handoff(self):
        source, _ = self.prepare_and_authorize()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ProjectEvidence.objects.filter(
                    pk=source.pk
                ).update(digest="0" * 64)

        source.refresh_from_db()
        self.assertNotEqual(source.digest, "0" * 64)
        self.assertEqual(
            self.handoff()["state"],
            "OFFLINE_DRAFT_HANDOFF_MATCHED"
        )

    def test_changed_approved_msr_version_blocks_handoff(self):
        self.prepare_and_authorize()
        original_number = self.msr.number

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                type(self.msr).objects.filter(
                    pk=self.msr.pk
                ).update(number=original_number + 1)

        self.msr.refresh_from_db()
        self.assertEqual(self.msr.number, original_number)
        self.assertEqual(
            self.handoff()["state"],
            "OFFLINE_DRAFT_HANDOFF_MATCHED"
        )

    def test_tampered_intent_blocks_handoff(self):
        self.prepare_and_authorize()

        intent = ProjectEvidence.objects.get(
            msr=self.msr, kind=KIND
        )
        data = dict(intent.data)
        data["send_authorized"] = True
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ProjectEvidence.objects.filter(
                    pk=intent.pk
                ).update(
                    data=data,
                    digest=canonical_hash(data),
                )

        intent.refresh_from_db()
        self.assertIs(intent.data["send_authorized"], False)
        self.assertEqual(
            self.handoff()["state"],
            "OFFLINE_DRAFT_HANDOFF_MATCHED"
        )

    def test_no_authorization_blocks_handoff(self):
        self.establish_source()

        with self.assertRaises(ValidationError):
            self.handoff()
