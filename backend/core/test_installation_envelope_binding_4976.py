from dataclasses import replace
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from rest_framework.exceptions import PermissionDenied

from .models import Role, User, ProjectEvidence
from .test_installation_evidence_retention_4969 import (
    InspectionEvidenceDatabaseAcceptance4969 as Fixture,
)
from .installation_evidence_retention_4969 import (
    retain_unverified_inspection_evidence,
    _bundle_material, _digest,
)
from .installation_provider_intake_bridge_4975 import (
    OfflineInspectionReadbackBridge4975,
)
from .installation_envelope_binding_4976 import (
    bind_unverified_inspection_envelope, KIND,
)

M = "core.installation_envelope_binding_4976"
WRITER = "core.installation_evidence_retention_4969"
ACCOUNT = "11111111-1111-4111-8111-111111111111"
ENVELOPE = "22222222-2222-4222-8222-222222222222"


@override_settings(DEBUG=True, ENVIRONMENT="development")
class InspectionEnvelopeBindingDatabase4976(TestCase):
    def setUp(self):
        Fixture.setUp(self)
        changed = replace(
            self.bundle, purported_envelope_id=ENVELOPE
        )
        self.bundle = replace(
            changed,
            bundle_sha256=_digest(_bundle_material(changed)),
        )
        with patch(WRITER + ".audit"):
            self.retained, created = retain_unverified_inspection_evidence(
                actor=self.actor,
                project_id=self.project.pk,
                bundle=self.bundle,
            )
        self.assertTrue(created)
        self.bridge = OfflineInspectionReadbackBridge4975(
            account_id=ACCOUNT,
            envelope_id=ENVELOPE,
            project_id=str(self.project.pk),
            approved_msr_id=str(self.msr.pk),
            observation_sha256=self.bundle.response_observation_sha256,
            evidence_bundle_sha256=self.bundle.bundle_sha256,
            evidence_bundle=self.bundle,
        )

    def bind(self, **changes):
        values = dict(
            actor=self.actor,
            project_id=self.project.pk,
            inspection_evidence_id=self.retained.pk,
            bridge=self.bridge,
        )
        values.update(changes)
        with (
            patch(M + ".docusign.configuration",
                  return_value={"account_id": ACCOUNT, "blockers": []}),
            patch(M + ".audit"),
        ):
            return bind_unverified_inspection_envelope(**values)

    def test_actual_database_association(self):
        record, created = self.bind()
        self.assertTrue(created)
        record = ProjectEvidence.objects.get(pk=record.pk)
        self.assertEqual(record.kind, KIND)
        self.assertEqual(
            record.data["retained_inspection_id"],
            str(self.retained.pk),
        )
        self.assertFalse(record.data["provider_authenticated"])
        self.assertFalse(record.data["completion_authorized"])

    def test_identical_binding_is_idempotent(self):
        first, created = self.bind()
        second, repeated = self.bind()
        self.assertTrue(created)
        self.assertFalse(repeated)
        self.assertEqual(first.pk, second.pk)

    def test_wrong_envelope_rejected(self):
        wrong = replace(self.bridge, envelope_id=ACCOUNT)
        with self.assertRaises(ValidationError):
            self.bind(bridge=wrong)

    def test_wrong_bundle_digest_rejected(self):
        wrong = replace(
            self.bridge, evidence_bundle_sha256="0" * 64
        )
        with self.assertRaises(ValidationError):
            self.bind(bridge=wrong)

    def test_wrong_project_rejected(self):
        with self.assertRaises(ValidationError):
            self.bind(
                project_id="00000000-0000-0000-0000-000000000000"
            )

    def test_technician_denied(self):
        technician = User.objects.create_user(
            username="inspection-bind-tech-4976",
            password=None,
            role=Role.TECHNICIAN,
            initials="BT",
        )
        with self.assertRaises(PermissionDenied):
            self.bind(actor=technician)

    def test_production_gate_denied(self):
        with override_settings(
            DEBUG=False, ENVIRONMENT="production"
        ):
            with self.assertRaises(PermissionDenied):
                self.bind()

    def test_no_duplicate_or_new_evidence_on_replay(self):
        self.bind()
        self.bind()
        self.assertEqual(
            ProjectEvidence.objects.filter(kind=KIND).count(), 1
        )
