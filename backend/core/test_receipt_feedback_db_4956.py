"""Real ORM acceptance for unverified Receipt feedback.

Uses only Django's disposable SQLite test database.
Never authorizes Receipt issuance, signing, or project completion.
"""

from dataclasses import replace
from unittest.mock import patch
import os

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from rest_framework.exceptions import PermissionDenied

from .models import (
    User, Role, ProjectEvidence,
)
from .receipt_feedback_binding_4951 import (
    record_unverified_receipt_feedback,
)
from .receipt_feedback_record_4954 import (
    KIND,
    retain_unverified_receipt_feedback,
    verify_unverified_receipt_feedback,
)
from .test_receipt_observation_recording_4124 import previous


@override_settings(DEBUG=True, ENVIRONMENT="development")
class ReceiptFeedbackDatabaseAcceptance4956(TestCase):
    """An actual persisted project/MSR fixture, not mocked ORM calls."""

    def setUp(self):
        from django.conf import settings
        if settings.DEBUG is not True or settings.ENVIRONMENT != "development":
            raise RuntimeError("SAFETY STOP: Isolated test settings unavailable.")
        fixture = previous.ReceiptSendingObservationTests()
        fixture.setUp()

        self.project = fixture.msr.project
        self.msr = fixture.msr
        self.actor = User.objects.get(pk=fixture.actor.pk)

        # Changes to the test actor occur ONLY in Django's disposable
        # test database, never in either protected database.
        self.actor.role = Role.COMPTROLLER
        self.actor.is_active = True
        self.actor.save(update_fields=["role", "is_active"])

        self.assertEqual(self.msr.status, "APPROVED")
        self.project.refresh_from_db()
        self.assertEqual(
            self.project.current_approved_id, self.msr.pk
        )
        self.assertNotEqual(self.project.state, "CANCELLED")

        gate = patch.dict(
            os.environ,
            {"GECC_RECEIPT_FEEDBACK_TEST_ENABLED": "1"},
        )
        gate.start()
        self.addCleanup(gate.stop)

        self.observation = record_unverified_receipt_feedback(
            project_id=str(self.project.pk),
            approved_msr_id=str(self.msr.pk),
            approved_msr_version=str(self.msr.number),
            receipt_evidence_id="SYNTHETIC-RCPT-4956",
            receipt_pdf_sha256="a" * 64,
            recorded_by_actor_id=str(self.actor.pk),
            source_kind="STAFF_TRANSCRIPTION_UNVERIFIED",
            survey_answers={
                "survey_1": "NO",
                "survey_2": "YES",
                "survey_3": None,
            },
        )

    def retain(self, observation=None, actor=None):
        return retain_unverified_receipt_feedback(
            actor=self.actor if actor is None else actor,
            project_id=self.project.pk,
            observation=(
                self.observation
                if observation is None
                else observation
            ),
        )

    def records(self):
        return ProjectEvidence.objects.filter(
            msr=self.msr,
            kind=KIND,
        )

    def test_actual_insert_and_independent_readback(self):
        record, created = self.retain()

        self.assertTrue(created)
        self.assertEqual(self.records().count(), 1)

        reread = ProjectEvidence.objects.get(pk=record.pk)

        verified = verify_unverified_receipt_feedback(
            record=reread,
            expected_project_id=str(self.project.pk),
            expected_msr_id=str(self.msr.pk),
        )

        self.assertEqual(
            verified.observation_sha256,
            self.observation.observation_sha256,
        )
        self.assertEqual(
            dict(verified.answers)["survey_1"], "NO"
        )
        self.assertFalse(reread.data["customer_authenticated"])
        self.assertFalse(reread.data["provider_authenticated"])
        self.assertFalse(reread.data["completion_authorized"])

    def test_idempotency_uses_same_actual_record(self):
        first, first_created = self.retain()
        second, second_created = self.retain()

        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(self.records().count(), 1)

    def test_conflicting_answers_cannot_overwrite(self):
        first, _ = self.retain()

        changed = record_unverified_receipt_feedback(
            project_id=str(self.project.pk),
            approved_msr_id=str(self.msr.pk),
            approved_msr_version=str(self.msr.number),
            receipt_evidence_id="SYNTHETIC-RCPT-4956",
            receipt_pdf_sha256="a" * 64,
            recorded_by_actor_id=str(self.actor.pk),
            source_kind="STAFF_TRANSCRIPTION_UNVERIFIED",
            survey_answers={
                "survey_1": "YES",
                "survey_2": "YES",
                "survey_3": None,
            },
        )

        with self.assertRaises(ValidationError):
            self.retain(observation=changed)

        self.assertEqual(self.records().count(), 1)
        reread = self.records().get()
        self.assertEqual(reread.pk, first.pk)
        self.assertEqual(
            reread.data["observation_sha256"],
            self.observation.observation_sha256,
        )

    def test_cross_project_claim_rejected(self):
        wrong = replace(
            self.observation,
            project_id="OTHER-PROJECT-4956",
        )

        with self.assertRaises(ValidationError):
            self.retain(observation=wrong)

        self.assertFalse(self.records().exists())

    def test_unauthorized_actor_rejected(self):
        other = User.objects.create_user(
            username="receipt-feedback-unauthorized-4956",
            password=None,
            role=Role.TECHNICIAN,
            initials="RF",
        )

        with self.assertRaises(PermissionDenied):
            self.retain(actor=other)

        self.assertFalse(self.records().exists())

    def test_audit_failure_rolls_back_actual_insert(self):
        with patch(
            "core.receipt_feedback_record_4954.audit",
            side_effect=RuntimeError(
                "Synthetic audit failure 4956"
            ),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "Synthetic audit failure 4956",
            ):
                self.retain()

        self.assertFalse(self.records().exists())
