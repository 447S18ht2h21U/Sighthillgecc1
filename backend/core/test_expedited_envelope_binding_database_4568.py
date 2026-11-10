
from copy import deepcopy
from datetime import date
from unittest.mock import patch
from uuid import uuid4

from django.conf import settings
from django.db import connection
from django.test import TestCase, override_settings
from rest_framework.exceptions import PermissionDenied, ValidationError

from .documents import canonical_hash
from .models import (
    Customer, MSR, Project, ProjectEvidence, Role, User,
    ExpeditedSigningAttempt, ExpeditedEnvelopeBinding,
)
from .expedited_attempt_service_4568 import create_expedited_attempt
from .expedited_envelope_binding_service_4568 import (
    bind_unverified_sandbox_envelope,
)

ATTEMPT_SERVICE = "core.expedited_attempt_service_4568"
BIND_SERVICE = "core.expedited_envelope_binding_service_4568"


@override_settings(ENVIRONMENT="development", DEBUG=True)
class ExpeditedEnvelopeBindingDatabase4568Tests(TestCase):
    @classmethod
    def setUpClass(cls):
        name = str(settings.DATABASES["default"]["NAME"])
        if (
            connection.vendor != "sqlite"
            or not (
                name == ":memory:"
                or (
                    name.startswith("file:memorydb_")
                    and "mode=memory" in name
                )
            )
        ):
            raise RuntimeError("STOP: In-memory SQLite required.")
        super().setUpClass()

    def setUp(self):
        self.manager = User.objects.create(
            username="bind_mgr_" + uuid4().hex[:12],
            role=Role.SALES_MANAGER, initials="SM", is_active=True
        )
        self.sales = User.objects.create(
            username="bind_sales_" + uuid4().hex[:12],
            role=Role.SALES_ASSOCIATE, initials="SA", is_active=True
        )
        customer = Customer.objects.create(
            legal_name="Fictional customer",
            billing_address="Fictional address",
            created_by=self.manager,
        )
        project = Project.objects.create(
            code="BIND-" + uuid4().hex[:12],
            customer=customer,
            location="Fictional installation address",
            sales_associate=self.sales,
            reviewer=self.manager,
        )
        snapshot = {"test": uuid4().hex}
        self.msr = MSR.objects.create(
            project=project, status="APPROVED", snapshot=snapshot,
            created_by=self.manager, prepared_by=self.sales,
            approved_by=self.manager,
        )
        project.current_approved = self.msr
        project.save(update_fields=["current_approved"])
        self.plan = {
            "msr_id": str(self.msr.pk),
            "project_id": str(project.pk),
            "snapshot_sha256": canonical_hash(snapshot),
            "proposed_date": date(2026, 11, 15),
            "recipient_manifest": [
                {
                    "role": role,
                    "recipient_id": str(n),
                    "routing_order": str(n),
                    "name": "Fictional " + role,
                    "email": f"fictional{n}@example.invalid",
                }
                for n, role in enumerate(
                    ("CUSTOMER", "INSTALLATION_MANAGER", "COMPTROLLER"), 1
                )
            ],
            "source_digest": canonical_hash({
                "source": str(self.msr.pk), "test": "binding"
            }),
        }
        with patch(
            f"{ATTEMPT_SERVICE}.prepare_expedited_attempt",
            return_value=deepcopy(self.plan),
        ):
            self.attempt = create_expedited_attempt(
                actor=self.manager, project_id=str(project.pk)
            )
        self.account = str(uuid4())
        self.envelope = str(uuid4())

    def bind(self, actor=None, envelope=None):
        with patch(
            f"{BIND_SERVICE}.docusign.configuration",
            return_value={
                "account_id": self.account,
                "blockers": [],
            },
        ):
            return bind_unverified_sandbox_envelope(
                actor=actor or self.manager,
                attempt_id=self.attempt["attempt_id"],
                account_id=self.account,
                envelope_id=envelope or self.envelope,
            )

    def test_real_binding_and_immutable_project_evidence(self):
        result = self.bind()
        self.assertEqual(
            result["status"], "SANDBOX_IDENTITY_CLAIM_UNVERIFIED"
        )
        self.assertFalse(result["provider_authenticated"])
        self.assertFalse(result["installation_authorized"])
        binding = ExpeditedEnvelopeBinding.objects.get(
            pk=result["binding_id"]
        )
        self.assertEqual(
            str(binding.attempt_id), self.attempt["attempt_id"]
        )
        self.assertEqual(
            str(binding.provider_envelope_id), self.envelope
        )
        evidence = ProjectEvidence.objects.get(
            msr=self.msr, kind="EXPEDITED_ENVELOPE_BINDING"
        )
        self.assertEqual(evidence.data["binding_id"], str(binding.pk))
        self.assertEqual(evidence.digest, canonical_hash(evidence.data))
        self.assertFalse(evidence.data["send_authorized"])

    def test_duplicate_binding_rejected(self):
        self.bind()
        with self.assertRaises(ValidationError):
            self.bind(envelope=str(uuid4()))
        self.assertEqual(
            ExpeditedEnvelopeBinding.objects.count(), 1
        )

    def test_evidence_failure_rolls_back_binding(self):
        with patch(
            f"{BIND_SERVICE}.ProjectEvidence.objects.create",
            side_effect=ValidationError("Fictional evidence failure"),
        ):
            with self.assertRaises(ValidationError):
                self.bind()
        self.assertFalse(
            ExpeditedEnvelopeBinding.objects.exists()
        )

    def test_sales_associate_cannot_bind(self):
        with self.assertRaises(PermissionDenied):
            self.bind(actor=self.sales)
        self.assertFalse(
            ExpeditedEnvelopeBinding.objects.exists()
        )

    def test_wrong_sandbox_account_rejected(self):
        with patch(
            f"{BIND_SERVICE}.docusign.configuration",
            return_value={
                "account_id": str(uuid4()),
                "blockers": [],
            },
        ):
            with self.assertRaises(PermissionDenied):
                bind_unverified_sandbox_envelope(
                    actor=self.manager,
                    attempt_id=self.attempt["attempt_id"],
                    account_id=self.account,
                    envelope_id=self.envelope,
                )
        self.assertFalse(
            ExpeditedEnvelopeBinding.objects.exists()
        )

    def test_missing_attempt_evidence_rejected(self):
        with patch(
            f"{BIND_SERVICE}.ProjectEvidence.objects.filter",
            return_value=[],
        ):
            with self.assertRaises(ValidationError):
                self.bind()
        self.assertFalse(
            ExpeditedEnvelopeBinding.objects.exists()
        )

    def test_msr_revision_becomes_current_blocks_old_binding(self):
        revision = MSR.objects.create(
            project=self.msr.project, number=2,
            status="DRAFT", snapshot={"test": "revision"},
            created_by=self.manager, prepared_by=self.sales,
            source=self.msr, revision_reason="Fictional revision",
        )
        self.msr.project.current_approved = revision
        self.msr.project.save(update_fields=["current_approved"])
        with self.assertRaises(ValidationError):
            self.bind()
        self.assertFalse(
            ExpeditedEnvelopeBinding.objects.exists()
        )

    @override_settings(ENVIRONMENT="production", DEBUG=False)
    def test_production_binding_disabled(self):
        with self.assertRaises(PermissionDenied):
            self.bind()
