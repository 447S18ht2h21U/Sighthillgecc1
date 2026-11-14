from copy import deepcopy
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch

from django.core.exceptions import ValidationError
from rest_framework.exceptions import PermissionDenied

from .documents import canonical_hash
from .models import Role
from .receipt_feedback_binding_4951 import (
    record_unverified_receipt_feedback,
)
from .receipt_feedback_record_4954 import (
    KIND,
    _payload,
    retain_unverified_receipt_feedback,
    verify_unverified_receipt_feedback,
)


MODULE = "core.receipt_feedback_record_4954"


def observation(**changes):
    args = {
        "project_id": "P-4954",
        "approved_msr_id": "MSR-4954",
        "approved_msr_version": "2",
        "receipt_evidence_id": "RECEIPT-4954",
        "receipt_pdf_sha256": "a" * 64,
        "recorded_by_actor_id": "CEO-4954",
        "source_kind": "STAFF_TRANSCRIPTION_UNVERIFIED",
        "survey_answers": {
            "survey_1": "NO",
            "survey_2": "YES",
            "survey_3": None,
        },
    }
    args.update(changes)
    return record_unverified_receipt_feedback(**args)


def stored_record(item=None):
    item = item or observation()
    data = _payload(item)
    return SimpleNamespace(
        pk="EVIDENCE-4954",
        kind=KIND,
        msr_id="MSR-4954",
        created_by_id="CEO-4954",
        data=data,
        digest=canonical_hash(data),
    )


class ReceiptFeedbackRecordTests(TestCase):
    def test_kind_fits_model_field(self):
        self.assertLessEqual(len(KIND), 32)

    def test_stored_payload_explicitly_unverified(self):
        data = _payload(observation())
        self.assertFalse(data["customer_authenticated"])
        self.assertFalse(data["receipt_delivery_verified"])
        self.assertFalse(data["provider_authenticated"])
        self.assertFalse(data["completion_authorized"])

    def test_readback_verifies_valid_record(self):
        item = verify_unverified_receipt_feedback(
            record=stored_record(),
            expected_project_id="P-4954",
            expected_msr_id="MSR-4954",
        )
        self.assertEqual(dict(item.answers)["survey_1"], "NO")

    def test_cross_project_readback_denied(self):
        with self.assertRaises(ValidationError):
            verify_unverified_receipt_feedback(
                record=stored_record(),
                expected_project_id="DIFFERENT",
                expected_msr_id="MSR-4954",
            )

    def test_tampered_answer_denied(self):
        record = stored_record()
        record.data = deepcopy(record.data)
        record.data["answers"][0][1] = "YES"
        with self.assertRaises(ValidationError):
            verify_unverified_receipt_feedback(
                record=record,
                expected_project_id="P-4954",
                expected_msr_id="MSR-4954",
            )

    def test_forged_authorization_denied(self):
        record = stored_record()
        record.data = deepcopy(record.data)
        record.data["customer_authenticated"] = True
        record.digest = canonical_hash(record.data)
        with self.assertRaises(ValidationError):
            verify_unverified_receipt_feedback(
                record=record,
                expected_project_id="P-4954",
                expected_msr_id="MSR-4954",
            )

    def test_wrong_recorder_denied(self):
        record = stored_record()
        record.created_by_id = "OTHER-ACTOR"
        with self.assertRaises(ValidationError):
            verify_unverified_receipt_feedback(
                record=record,
                expected_project_id="P-4954",
                expected_msr_id="MSR-4954",
            )

    def test_modified_source_digest_denied(self):
        from dataclasses import replace
        item = replace(
            observation(), observation_sha256="0" * 64
        )
        with self.assertRaises(ValidationError):
            _payload(item)

    @patch(MODULE + ".settings")
    def test_writer_disabled_without_gate(self, settings):
        settings.ENVIRONMENT = "production"
        settings.DEBUG = False
        with self.assertRaises(PermissionDenied):
            retain_unverified_receipt_feedback(
                actor=None,
                project_id="P-4954",
                observation=observation(),
            )

    @patch(MODULE + ".audit")
    @patch(MODULE + ".ProjectEvidence")
    @patch(MODULE + ".Project")
    @patch(MODULE + ".User")
    @patch(MODULE + "._gate")
    def test_writer_insert_and_idempotency(
        self, gate, users, projects, evidence, audit
    ):
        recorder = SimpleNamespace(
            pk="CEO-4954", role=Role.CEO
        )
        users.objects.filter.return_value.first.return_value = recorder

        msr = SimpleNamespace(
            pk="MSR-4954",
            number=2,
            status="APPROVED",
            project_id="P-4954",
            snapshot={},
        )
        project = SimpleNamespace(
            pk="P-4954",
            state="ACTIVE",
            current_approved=msr,
            current_approved_id=msr.pk,
        )
        projects.objects.select_for_update.return_value \
            .select_related.return_value.filter.return_value \
            .first.return_value = project

        evidence.objects.filter.return_value = []
        saved = stored_record()
        evidence.objects.create.return_value = saved

        args = {
            "actor": SimpleNamespace(pk="CEO-4954"),
            "project_id": "P-4954",
            "observation": observation(),
        }
        first, created = retain_unverified_receipt_feedback(**args)
        self.assertTrue(created)
        self.assertIs(first, saved)
        evidence.objects.create.assert_called_once()
        audit.assert_called_once()

        evidence.objects.filter.return_value = [saved]
        second, created = retain_unverified_receipt_feedback(**args)
        self.assertFalse(created)
        self.assertIs(second, saved)
        evidence.objects.create.assert_called_once()
        audit.assert_called_once()

    @patch(MODULE + ".audit")
    @patch(MODULE + ".ProjectEvidence")
    @patch(MODULE + ".Project")
    @patch(MODULE + ".User")
    @patch(MODULE + "._gate")
    def test_unauthorized_role_denied(
        self, gate, users, projects, evidence, audit
    ):
        users.objects.filter.return_value.first.return_value = (
            SimpleNamespace(pk="CEO-4954", role=Role.TECHNICIAN)
        )
        with self.assertRaises(PermissionDenied):
            retain_unverified_receipt_feedback(
                actor=SimpleNamespace(pk="CEO-4954"),
                project_id="P-4954",
                observation=observation(),
            )
        evidence.objects.create.assert_not_called()
        audit.assert_not_called()

    @patch(MODULE + ".audit")
    @patch(MODULE + ".ProjectEvidence")
    @patch(MODULE + ".Project")
    @patch(MODULE + ".User")
    @patch(MODULE + "._gate")
    def test_cross_project_write_denied(
        self, gate, users, projects, evidence, audit
    ):
        users.objects.filter.return_value.first.return_value = (
            SimpleNamespace(pk="CEO-4954", role=Role.CEO)
        )
        msr = SimpleNamespace(
            pk="MSR-OTHER", number=2, status="APPROVED",
            project_id="P-OTHER", snapshot={},
        )
        projects.objects.select_for_update.return_value \
            .select_related.return_value.filter.return_value \
            .first.return_value = SimpleNamespace(
                pk="P-OTHER", state="ACTIVE",
                current_approved=msr,
                current_approved_id=msr.pk,
            )
        with self.assertRaises(ValidationError):
            retain_unverified_receipt_feedback(
                actor=SimpleNamespace(pk="CEO-4954"),
                project_id="P-OTHER",
                observation=observation(),
            )
        evidence.objects.create.assert_not_called()
        audit.assert_not_called()
