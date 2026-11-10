
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from django.test import TestCase, override_settings
from rest_framework.exceptions import PermissionDenied, ValidationError

from .documents import canonical_hash
from .models import (
    ExpeditedSigningObservation, ExpeditedSigningDocument,
    ProjectEvidence,
)
from .test_expedited_envelope_binding_database_4568 import (
    ExpeditedEnvelopeBindingDatabase4568Tests,
)
from .expedited_observation_storage_4569 import (
    retain_unverified_expedited_observation,
)

MODULE = "core.expedited_observation_storage_4569"


@override_settings(ENVIRONMENT="development", DEBUG=True)
class ExpeditedObservationStorage4569Tests(TestCase):
    def setUp(self):
        # Reuse the real, already-tested approved-MSR fixture.
        ExpeditedEnvelopeBindingDatabase4568Tests.setUp(self)
        binding = ExpeditedEnvelopeBindingDatabase4568Tests.bind(self)
        self.binding_id = binding["binding_id"]

        root = (
            Path(__file__).resolve().parents[2]
            / "docs/reference/GECC-20261107-final-seven"
        )
        self.pdfs = {
            "1": (
                root / "GECC Project Scope of Work 20261107v2.pdf"
            ).read_bytes(),
            "2": (
                root / "GECC Expedite Service Request 20261107v2.pdf"
            ).read_bytes(),
        }
        # Fictional test fixture, NOT a DocuSign completion certificate.
        self.pdfs["certificate"] = self.pdfs["2"]

        self.candidate = {
            "status": "SANDBOX_READ_STRUCTURAL_CANDIDATE_ONLY",
            "envelope_id": self.envelope,
            "source_msr_id": str(self.msr.pk),
            "provider_origin_bound_to_msr": False,
            "provider_authenticated": False,
            "installation_authorized": False,
            "send_authorized": False,
            "document_hashes": {
                key: sha256(value).hexdigest()
                for key, value in self.pdfs.items()
            },
        }

    def retain(self):
        return retain_unverified_expedited_observation(
            actor=self.manager,
            binding_id=self.binding_id,
            candidate=self.candidate,
            pdf_bytes=self.pdfs,
        )

    def test_three_documents_saved_with_exact_bytes(self):
        result = self.retain()
        self.assertEqual(
            result["status"], "UNVERIFIED_DOCUMENT_BYTES_RETAINED"
        )
        observation = ExpeditedSigningObservation.objects.get(
            pk=result["observation_id"]
        )
        self.assertEqual(
            observation.digest, canonical_hash(observation.evidence)
        )
        retained = list(ExpeditedSigningDocument.objects.filter(
            observation=observation
        ))
        self.assertEqual(len(retained), 3)
        for record in retained:
            self.assertEqual(
                bytes(record.content), self.pdfs[record.document_id]
            )
            self.assertEqual(
                record.pdf_sha256,
                sha256(bytes(record.content)).hexdigest(),
            )
        evidence = ProjectEvidence.objects.get(
            msr=self.msr, kind="EXPEDITED_DOCUMENT_RETENTION"
        )
        self.assertEqual(
            evidence.data["observation_id"], str(observation.pk)
        )
        self.assertFalse(result["provider_authenticated"])
        self.assertFalse(result["installation_authorized"])

    def test_duplicate_retention_rejected(self):
        self.retain()
        with self.assertRaises(ValidationError):
            self.retain()
        self.assertEqual(ExpeditedSigningObservation.objects.count(), 1)
        self.assertEqual(ExpeditedSigningDocument.objects.count(), 3)

    def test_changed_pdf_rejected_before_write(self):
        self.pdfs["1"] = self.pdfs["2"]
        with self.assertRaises(ValidationError):
            self.retain()
        self.assertFalse(ExpeditedSigningObservation.objects.exists())

    def test_missing_certificate_rejected(self):
        del self.pdfs["certificate"]
        with self.assertRaises(ValidationError):
            self.retain()
        self.assertFalse(ExpeditedSigningObservation.objects.exists())

    def test_cross_project_candidate_rejected(self):
        self.candidate["source_msr_id"] = str(uuid4())
        with self.assertRaises(ValidationError):
            self.retain()
        self.assertFalse(ExpeditedSigningObservation.objects.exists())

    def test_document_write_failure_rolls_back_all_records(self):
        with patch(
            f"{MODULE}.ExpeditedSigningDocument.objects.create",
            side_effect=ValidationError("Fictional storage failure"),
        ):
            with self.assertRaises(ValidationError):
                self.retain()
        self.assertFalse(ExpeditedSigningObservation.objects.exists())
        self.assertFalse(ExpeditedSigningDocument.objects.exists())

    def test_evidence_write_failure_rolls_back_all_records(self):
        with patch(
            f"{MODULE}.ProjectEvidence.objects.create",
            side_effect=ValidationError("Fictional audit failure"),
        ):
            with self.assertRaises(ValidationError):
                self.retain()
        self.assertFalse(ExpeditedSigningObservation.objects.exists())
        self.assertFalse(ExpeditedSigningDocument.objects.exists())

    @override_settings(ENVIRONMENT="production", DEBUG=False)
    def test_production_disabled(self):
        with self.assertRaises(PermissionDenied):
            self.retain()
