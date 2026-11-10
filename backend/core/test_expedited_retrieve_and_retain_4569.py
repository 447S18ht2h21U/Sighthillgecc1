
from copy import deepcopy
from hashlib import sha256
from unittest.mock import patch
from uuid import uuid4

from django.test import TestCase, override_settings
from rest_framework.exceptions import ValidationError, PermissionDenied

from .documents import canonical_hash
from .models import (
    ExpeditedSigningAttempt, ExpeditedEnvelopeBinding,
    ExpeditedSigningDocument, ExpeditedSigningObservation,
    ProjectEvidence,
)
from .test_expedited_observation_storage_4569 import (
    ExpeditedObservationStorage4569Tests,
)
from .expedited_retrieve_and_retain_4569 import (
    retrieve_and_retain_expedited_sandbox_candidate,
)

MODULE = "core.expedited_retrieve_and_retain_4569"


@override_settings(ENVIRONMENT="development", DEBUG=True)
class ExpeditedRetrieveAndRetain4569Tests(TestCase):
    def setUp(self):
        ExpeditedObservationStorage4569Tests.setUp(self)

        attempt = ExpeditedSigningAttempt.objects.get(
            pk=self.attempt["attempt_id"]
        )
        self.offline = {
            "source_msr_id": str(self.msr.pk),
            "recipients": {
                "signers": [
                    {
                        "recipientId": item["recipient_id"],
                        "routingOrder": item["routing_order"],
                        "name": item["name"],
                        "email": item["email"],
                    }
                    for item in attempt.recipient_manifest
                ]
            },
            "documents": [
                {
                    "documentId": str(number),
                    "documentBase64": "fictional-offline-doc-" + str(number),
                }
                for number in (1, 2)
            ],
        }
        self.actual_digest = canonical_hash({
            "msr_id": str(self.msr.pk),
            "snapshot_sha256": attempt.snapshot_sha256,
            "proposed_date": attempt.proposed_date.isoformat(),
            "recipients": attempt.recipient_manifest,
            "document_hashes": {
                item["documentId"]: canonical_hash(
                    item["documentBase64"]
                )
                for item in self.offline["documents"]
            },
        })

        # The reused fixture deliberately generated an arbitrary
        # digest; create a fresh, correctly sourced attempt/binding
        # in the disposable test DB, without modifying immutable rows.
        new_attempt = ExpeditedSigningAttempt.objects.create(
            msr=self.msr,
            initiated_by=self.manager,
            snapshot_sha256=attempt.snapshot_sha256,
            proposed_date=attempt.proposed_date,
            recipient_manifest=deepcopy(attempt.recipient_manifest),
            source_digest=self.actual_digest,
        )
        original_binding = ExpeditedEnvelopeBinding.objects.get(
            pk=self.binding_id
        )
        new_binding = ExpeditedEnvelopeBinding.objects.create(
            attempt=new_attempt,
            provider_account_id=original_binding.provider_account_id,
            provider_envelope_id=uuid4(),
            bound_by=self.manager,
            binding_digest=canonical_hash({
                "test": "protected-provider-bridge",
                "source": self.actual_digest,
            }),
        )
        self.binding_id = str(new_binding.pk)
        self.envelope = str(new_binding.provider_envelope_id)
        self.candidate["envelope_id"] = self.envelope

        self.summary = {
            "envelopeId": self.envelope,
            "status": "completed",
            "lastModifiedDateTime": "2026-11-15T18:01:00Z",
            "completedDateTime": "2026-11-15T18:00:00Z",
        }
        self.candidate["envelope_stability"] = {
            field: self.summary[field]
            for field in (
                "envelopeId",
                "status",
                "lastModifiedDateTime",
                "completedDateTime",
            )
        }
        self.token = "fictional-token-never-sent"

        # New binding must carry matching immutable project evidence.
        data = {
            "attempt_id": str(new_attempt.pk),
            "msr_id": str(self.msr.pk),
            "source_digest": self.actual_digest,
            "provider_account_id": str(new_binding.provider_account_id),
            "provider_envelope_id": self.envelope,
            "state": "SANDBOX_IDENTITY_CLAIM_UNVERIFIED",
            "provider_authenticated": False,
            "installation_authorized": False,
        }
        ProjectEvidence.objects.create(
            msr=self.msr,
            kind="EXPEDITED_ENVELOPE_BINDING",
            created_by=self.manager,
            data={**data, "binding_id": self.binding_id},
            digest=canonical_hash({
                **data, "binding_id": self.binding_id
            }),
        )

    def run_integration(self, bytes_override=None, summary_override=None):
        pdfs = bytes_override or self.pdfs
        summary = summary_override or self.summary

        def get_pdf(account, envelope, document, token):
            return pdfs[document]

        with (
            patch(
                f"{MODULE}.read_unified_sandbox_candidate",
                return_value=deepcopy(self.candidate),
            ),
            patch(
                f"{MODULE}.signing_test.pdf_document",
                side_effect=get_pdf,
            ),
            patch(
                f"{MODULE}.signing_test.provider",
                return_value=summary,
            ),
        ):
            return retrieve_and_retain_expedited_sandbox_candidate(
                actor=self.manager,
                binding_id=self.binding_id,
                token=self.token,
                offline_envelope=self.offline,
            )

    def test_retrieved_bytes_persist_in_real_database(self):
        result = self.run_integration()
        self.assertEqual(
            result["status"], "UNVERIFIED_DOCUMENT_BYTES_RETAINED"
        )
        self.assertFalse(result["installation_authorized"])
        self.assertFalse(result["provider_authenticated"])
        obs = ExpeditedSigningObservation.objects.get(
            pk=result["observation_id"]
        )
        documents = ExpeditedSigningDocument.objects.filter(
            observation=obs
        )
        self.assertEqual(documents.count(), 3)
        for row in documents:
            self.assertEqual(
                bytes(row.content), self.pdfs[row.document_id]
            )

    def test_changed_download_rejected_without_retention(self):
        changed = dict(self.pdfs)
        changed["1"] = self.pdfs["2"]
        with self.assertRaises(ValidationError):
            self.run_integration(bytes_override=changed)
        self.assertFalse(
            ExpeditedSigningObservation.objects.exists()
        )

    def test_wrong_offline_msr_rejected_before_provider(self):
        self.offline["source_msr_id"] = str(uuid4())
        with self.assertRaises(ValidationError):
            self.run_integration()

    def test_modified_source_document_rejected(self):
        self.offline["documents"][0]["documentBase64"] += "-altered"
        with self.assertRaises(ValidationError):
            self.run_integration()

    def test_recipient_identity_mismatch_rejected(self):
        self.offline["recipients"]["signers"][1]["email"] = (
            "impostor@example.invalid"
        )
        with self.assertRaises(ValidationError):
            self.run_integration()

    def test_changed_final_provider_state_rejected(self):
        changed = {**self.summary, "status": "voided"}
        with self.assertRaises(ValidationError):
            self.run_integration(summary_override=changed)
        self.assertFalse(
            ExpeditedSigningObservation.objects.exists()
        )

    def test_changed_final_modification_timestamp_rejected(self):
        changed = {
            **self.summary,
            "lastModifiedDateTime": "2026-11-15T18:02:00Z",
        }
        with self.assertRaises(ValidationError):
            self.run_integration(summary_override=changed)
        self.assertFalse(
            ExpeditedSigningObservation.objects.exists()
        )

    def test_changed_final_completion_timestamp_rejected(self):
        changed = {
            **self.summary,
            "completedDateTime": "2026-11-15T18:03:00Z",
        }
        with self.assertRaises(ValidationError):
            self.run_integration(summary_override=changed)
        self.assertFalse(
            ExpeditedSigningObservation.objects.exists()
        )

    def test_missing_stability_evidence_rejected(self):
        self.candidate.pop("envelope_stability", None)
        with self.assertRaises(ValidationError):
            self.run_integration()
        self.assertFalse(
            ExpeditedSigningObservation.objects.exists()
        )

    @override_settings(ENVIRONMENT="production", DEBUG=False)
    def test_production_is_disabled(self):
        with self.assertRaises(PermissionDenied):
            self.run_integration()
