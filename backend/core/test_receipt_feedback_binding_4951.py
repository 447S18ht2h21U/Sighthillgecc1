from dataclasses import replace
from unittest import TestCase
from unittest.mock import patch

from django.core.exceptions import ValidationError

from .installation_inspection_form_4945 import INSPECTION_IDS, SURVEY_IDS
from .receipt_feedback_binding_4951 import (
    record_unverified_receipt_feedback,
    build_unverified_receipt_audit_packet,
)

AUDIT = "core.installation_receipt_audit_4950.verify_approved_final_receipt"


def source_answers():
    return {key: None for key in SURVEY_IDS}


def create_observation(**changes):
    arguments = {
        "project_id": "P-4951",
        "approved_msr_id": "MSR-4951",
        "approved_msr_version": "2",
        "receipt_evidence_id": "RECEIPT-EV-4951",
        "receipt_pdf_sha256": "a" * 64,
        "recorded_by_actor_id": "STAFF-4951",
        "source_kind": "STAFF_TRANSCRIPTION_UNVERIFIED",
        "survey_answers": source_answers(),
    }
    arguments.update(changes)
    return record_unverified_receipt_feedback(**arguments)


def packet_args(observation):
    return {
        "observation": observation,
        "expected_project_id": "P-4951",
        "expected_msr_id": "MSR-4951",
        "expected_msr_version": "2",
        "expected_receipt_evidence_id": "RECEIPT-EV-4951",
        "expected_receipt_pdf_sha256": "a" * 64,
        "inspection_source_evidence_id": "INSPECTION-EV-4951",
        "manager_findings": {
            key: "YES" for key in INSPECTION_IDS
        },
    }


class ReceiptFeedbackBindingTests(TestCase):
    def test_observation_is_unverified(self):
        item = create_observation()
        self.assertFalse(item.persisted)
        self.assertFalse(item.customer_identity_authenticated)
        self.assertFalse(item.customer_answers_provider_verified)

    def test_answers_are_immutable_snapshot(self):
        answers = source_answers()
        item = create_observation(survey_answers=answers)
        answers["survey_1"] = "NO"
        self.assertIsNone(dict(item.answers)["survey_1"])

    def test_source_required(self):
        with self.assertRaises(ValidationError):
            create_observation(source_kind="CUSTOMER_VERIFIED")

    def test_unrecognized_survey_key_denied(self):
        answers = source_answers()
        answers["survey_4"] = "YES"
        with self.assertRaises(ValidationError):
            create_observation(survey_answers=answers)

    def test_unrecognized_answer_denied(self):
        answers = source_answers()
        answers["survey_1"] = "TRUE"
        with self.assertRaises(ValidationError):
            create_observation(survey_answers=answers)

    def test_invalid_receipt_digest_denied(self):
        with self.assertRaises(ValidationError):
            create_observation(receipt_pdf_sha256="unverified")

    def test_missing_actor_denied(self):
        with self.assertRaises(ValidationError):
            create_observation(recorded_by_actor_id="")

    @patch(AUDIT)
    def test_optional_unanswered_survey_no_action(self, reference):
        reference.return_value.sha256 = "b" * 64
        observation = create_observation()
        packet = build_unverified_receipt_audit_packet(
            **packet_args(observation)
        )
        self.assertEqual(packet.audit.review_candidate_ids, ())
        self.assertFalse(packet.independently_verified)
        self.assertFalse(packet.completion_authorized)

    @patch(AUDIT)
    def test_negative_cleanup_creates_review_candidate(self, reference):
        reference.return_value.sha256 = "b" * 64
        answers = source_answers()
        answers["survey_1"] = "NO"
        observation = create_observation(survey_answers=answers)
        packet = build_unverified_receipt_audit_packet(
            **packet_args(observation)
        )
        self.assertEqual(
            packet.audit.direct_discrepancy_ids, ("survey_1",)
        )
        self.assertEqual(
            packet.audit.review_candidate_ids, ("inspection_4",)
        )
        self.assertFalse(packet.corrective_actions_persisted)

    def test_cross_project_binding_denied(self):
        observation = create_observation()
        values = packet_args(observation)
        values["expected_project_id"] = "OTHER-PROJECT"
        with self.assertRaises(ValidationError):
            build_unverified_receipt_audit_packet(**values)

    def test_msr_version_mismatch_denied(self):
        observation = create_observation()
        values = packet_args(observation)
        values["expected_msr_version"] = "3"
        with self.assertRaises(ValidationError):
            build_unverified_receipt_audit_packet(**values)

    def test_observation_tampering_denied(self):
        observation = replace(
            create_observation(),
            receipt_evidence_id="OTHER-RECEIPT",
        )
        values = packet_args(observation)
        values["expected_receipt_evidence_id"] = "OTHER-RECEIPT"
        with self.assertRaises(ValidationError):
            build_unverified_receipt_audit_packet(**values)
