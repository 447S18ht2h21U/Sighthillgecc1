
from copy import deepcopy
from datetime import date
from unittest.mock import patch
from uuid import uuid4

from django.conf import settings
from django.db import connection
from django.test import TestCase, override_settings
from rest_framework.exceptions import ValidationError

from .documents import canonical_hash
from .models import (
    Customer, ExpeditedSigningAttempt, MSR, Project,
    ProjectEvidence, Role, User,
)
from .expedited_attempt_service_4568 import create_expedited_attempt

SERVICE = "core.expedited_attempt_service_4568"


@override_settings(ENVIRONMENT="development", DEBUG=True)
class ExpeditedAttemptDatabase4568Tests(TestCase):
    databases = {"default"}

    @classmethod
    def setUpClass(cls):
        configured = str(settings.DATABASES["default"].get("NAME", ""))
        connected = str(connection.settings_dict.get("NAME", ""))
        allowed = lambda name: (
            name == ":memory:"
            or (
                name.startswith("file:memorydb_")
                and "mode=memory" in name
            )
        )
        if (
            connection.vendor != "sqlite"
            or not allowed(configured)
            or not allowed(connected)
        ):
            raise RuntimeError("STOP: Disposable SQLite memory DB required.")
        super().setUpClass()

    def setUp(self):
        self.manager = User.objects.create(
            username="exp_manager_" + uuid4().hex[:12],
            role=Role.SALES_MANAGER,
            initials="SM",
            is_active=True,
        )
        self.sales = User.objects.create(
            username="exp_sales_" + uuid4().hex[:12],
            role=Role.SALES_ASSOCIATE,
            initials="SA",
            is_active=True,
        )
        customer = Customer.objects.create(
            legal_name="Fictional Expedited Customer",
            billing_address="Fictional test billing address",
            created_by=self.manager,
        )
        self.project = Project.objects.create(
            code="EXP-TEST-" + uuid4().hex[:12],
            customer=customer,
            location="Fictional test installation address",
            sales_associate=self.sales,
            reviewer=self.manager,
        )
        self.snapshot = {
            "scope": "Fictional equipment installation",
            "test_identifier": uuid4().hex,
        }
        self.msr = MSR.objects.create(
            project=self.project,
            number=1,
            status="APPROVED",
            snapshot=self.snapshot,
            created_by=self.manager,
            prepared_by=self.sales,
            approved_by=self.manager,
        )
        self.project.current_approved = self.msr
        self.project.save(update_fields=["current_approved"])

        self.plan = {
            "msr_id": str(self.msr.pk),
            "project_id": str(self.project.pk),
            "snapshot_sha256": canonical_hash(self.snapshot),
            "proposed_date": date(2026, 11, 15),
            "recipient_manifest": [
                {
                    "role": role,
                    "recipient_id": str(number),
                    "routing_order": str(number),
                    "name": "Fictional " + role,
                    "email": "fictional%d@example.invalid" % number,
                }
                for number, role in enumerate(
                    ("CUSTOMER", "INSTALLATION_MANAGER", "COMPTROLLER"),
                    start=1,
                )
            ],
            "source_digest": canonical_hash({
                "msr_id": str(self.msr.pk),
                "fictional_source": "expedited-request",
            }),
            "send_authorized": False,
            "installation_authorized": False,
        }

    def create_attempt(self):
        with patch(
            f"{SERVICE}.prepare_expedited_attempt",
            return_value=deepcopy(self.plan),
        ) as prepare:
            result = create_expedited_attempt(
                actor=self.manager,
                project_id=str(self.project.pk),
            )
            prepare.assert_called_once()
            return result

    def test_real_atomic_attempt_and_evidence_creation(self):
        result = self.create_attempt()
        self.assertEqual(result["status"], "PREPARED_NOT_SENT")
        self.assertIsNone(result["provider_envelope_id"])
        self.assertFalse(result["send_authorized"])
        self.assertFalse(result["installation_authorized"])

        attempt = ExpeditedSigningAttempt.objects.get(
            pk=result["attempt_id"]
        )
        self.assertEqual(attempt.msr_id, self.msr.pk)
        self.assertEqual(attempt.initiated_by_id, self.manager.pk)
        self.assertEqual(
            attempt.snapshot_sha256, canonical_hash(self.snapshot)
        )
        self.assertEqual(
            attempt.source_digest, self.plan["source_digest"]
        )
        self.assertEqual(len(attempt.recipient_manifest), 3)

        evidence = ProjectEvidence.objects.get(
            msr=self.msr, kind="EXPEDITED_SIGNING_ATTEMPT"
        )
        self.assertEqual(evidence.created_by_id, self.manager.pk)
        self.assertEqual(
            evidence.data["attempt_id"], str(attempt.pk)
        )
        self.assertEqual(evidence.data["state"], "PREPARED_NOT_SENT")
        self.assertIsNone(evidence.data["provider_envelope_id"])
        self.assertEqual(
            evidence.digest, canonical_hash(evidence.data)
        )
        self.assertFalse(evidence.data["installation_authorized"])

    def test_duplicate_attempt_rejected_without_extra_records(self):
        self.create_attempt()
        with self.assertRaises(ValidationError):
            self.create_attempt()

        self.assertEqual(
            ExpeditedSigningAttempt.objects.filter(
                msr=self.msr
            ).count(), 1
        )
        self.assertEqual(
            ProjectEvidence.objects.filter(
                msr=self.msr, kind="EXPEDITED_SIGNING_ATTEMPT"
            ).count(), 1
        )

    def test_failed_evidence_write_rolls_back_attempt(self):
        with patch(
            f"{SERVICE}.ProjectEvidence.objects.create",
            side_effect=ValidationError(
                "Fictional evidence write failure"
            ),
        ):
            with self.assertRaises(ValidationError):
                self.create_attempt()

        self.assertFalse(
            ExpeditedSigningAttempt.objects.filter(
                msr=self.msr
            ).exists()
        )
        self.assertFalse(
            ProjectEvidence.objects.filter(
                msr=self.msr, kind="EXPEDITED_SIGNING_ATTEMPT"
            ).exists()
        )

    def test_draft_msr_rejected_without_writes(self):
        # Create a separate draft revision. Never alter an approved MSR.
        draft = MSR.objects.create(
            project=self.project,
            number=2,
            status="DRAFT",
            snapshot=deepcopy(self.snapshot),
            created_by=self.manager,
            prepared_by=self.sales,
            source=self.msr,
            revision_reason="Fictional draft revision",
        )
        self.plan["msr_id"] = str(draft.pk)
        self.plan["snapshot_sha256"] = canonical_hash(draft.snapshot)

        with self.assertRaises(ValidationError):
            self.create_attempt()

        self.assertFalse(
            ExpeditedSigningAttempt.objects.filter(
                msr=draft
            ).exists()
        )
        self.assertFalse(
            ProjectEvidence.objects.filter(
                msr=draft, kind="EXPEDITED_SIGNING_ATTEMPT"
            ).exists()
        )
        self.msr.refresh_from_db()
        self.assertEqual(self.msr.status, "APPROVED")

    def test_changed_snapshot_fingerprint_rejected(self):
        self.plan["snapshot_sha256"] = "0" * 64
        with self.assertRaises(ValidationError):
            self.create_attempt()
        self.assertFalse(
            ExpeditedSigningAttempt.objects.filter(
                msr=self.msr
            ).exists()
        )

    def test_cross_project_reference_rejected(self):
        self.plan["project_id"] = str(uuid4())
        with self.assertRaises(ValidationError):
            self.create_attempt()
        self.assertFalse(
            ExpeditedSigningAttempt.objects.filter(
                msr=self.msr
            ).exists()
        )
