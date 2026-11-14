"""Offline project-bound Receipt feedback observation and audit packet.

No customer authentication is inferred from an answer, a printed Receipt,
or the identity of the staff member recording an observation.
No database writes, live signing, sending, completion, or work orders.
"""
from dataclasses import dataclass
from hashlib import sha256
import json
import re

from django.core.exceptions import ValidationError

from .installation_inspection_form_4945 import INSPECTION_IDS, SURVEY_IDS
from .installation_receipt_audit_4950 import (
    compare_receipt_survey_to_inspection,
)


_ALLOWED_SOURCES = frozenset({
    "STAFF_TRANSCRIPTION_UNVERIFIED",
    "CUSTOMER_RESPONSE_UNVERIFIED",
})
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")


def _identifier(value, label):
    if (
        type(value) is not str
        or not value.strip()
        or value != value.strip()
        or len(value) > 128
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
    ):
        raise ValidationError(f"Invalid {label}.")
    return value


def _digest(value, label):
    if type(value) is not str or not _HEX_64.fullmatch(value):
        raise ValidationError(f"Invalid {label} SHA-256.")
    return value


def _answers(value, expected, label):
    if type(value) is not dict or set(value) != set(expected):
        raise ValidationError(f"Exact {label} answer keys required.")
    for key in expected:
        if value[key] is not None and (
            type(value[key]) is not str
            or value[key] not in ("YES", "NO")
        ):
            raise ValidationError(f"Invalid {label} answer.")
    return tuple((key, value[key]) for key in expected)


def _canonical_bytes(payload):
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False
    ).encode("utf-8")


@dataclass(frozen=True)
class UnverifiedReceiptFeedbackObservation:
    project_id: str
    approved_msr_id: str
    approved_msr_version: str
    receipt_evidence_id: str
    receipt_pdf_sha256: str
    recorded_by_actor_id: str
    source_kind: str
    answers: tuple[tuple[str, str | None], ...]
    observation_sha256: str
    status: str = "UNVERIFIED_RECEIPT_FEEDBACK_OBSERVATION"
    persisted: bool = False
    customer_identity_authenticated: bool = False
    customer_answers_provider_verified: bool = False
    receipt_delivery_verified: bool = False


@dataclass(frozen=True)
class UnverifiedProjectReceiptAuditPacket:
    observation: UnverifiedReceiptFeedbackObservation
    manager_findings: tuple[tuple[str, str | None], ...]
    inspection_source_evidence_id: str
    audit: object
    packet_sha256: str
    status: str = "UNVERIFIED_PROJECT_AUDIT_CANDIDATE"
    independently_verified: bool = False
    corrective_actions_persisted: bool = False
    final_receipt_issuance_authorized: bool = False
    completion_authorized: bool = False


def record_unverified_receipt_feedback(
    *,
    project_id,
    approved_msr_id,
    approved_msr_version,
    receipt_evidence_id,
    receipt_pdf_sha256,
    recorded_by_actor_id,
    source_kind,
    survey_answers,
):
    """Create an immutable in-memory observation, not a trusted record."""
    values = {
        "project_id": _identifier(project_id, "project ID"),
        "approved_msr_id": _identifier(approved_msr_id, "MSR ID"),
        "approved_msr_version": _identifier(
            approved_msr_version, "MSR version"
        ),
        "receipt_evidence_id": _identifier(
            receipt_evidence_id, "Receipt evidence ID"
        ),
        "receipt_pdf_sha256": _digest(
            receipt_pdf_sha256, "Receipt document"
        ),
        "recorded_by_actor_id": _identifier(
            recorded_by_actor_id, "recording actor ID"
        ),
    }
    if type(source_kind) is not str or source_kind not in _ALLOWED_SOURCES:
        raise ValidationError("Unrecognized unverified evidence source.")

    answers = _answers(survey_answers, SURVEY_IDS, "Receipt survey")
    payload = {
        **values,
        "source_kind": source_kind,
        "answers": answers,
        "schema": "GECC_RECEIPT_FEEDBACK_4951_V1",
    }
    return UnverifiedReceiptFeedbackObservation(
        **values,
        source_kind=source_kind,
        answers=answers,
        observation_sha256=sha256(_canonical_bytes(payload)).hexdigest(),
    )


def build_unverified_receipt_audit_packet(
    *,
    observation,
    expected_project_id,
    expected_msr_id,
    expected_msr_version,
    expected_receipt_evidence_id,
    expected_receipt_pdf_sha256,
    inspection_source_evidence_id,
    manager_findings,
):
    """Bind observed feedback to expected record identities, fail closed."""
    if type(observation) is not UnverifiedReceiptFeedbackObservation:
        raise ValidationError("Unverified feedback observation required.")

    expected = (
        ("project_id", expected_project_id),
        ("approved_msr_id", expected_msr_id),
        ("approved_msr_version", expected_msr_version),
        ("receipt_evidence_id", expected_receipt_evidence_id),
        ("receipt_pdf_sha256", expected_receipt_pdf_sha256),
    )
    for field, value in expected:
        if getattr(observation, field) != value:
            raise ValidationError(f"Receipt evidence binding mismatch: {field}")

    _identifier(inspection_source_evidence_id, "inspection evidence ID")
    _digest(expected_receipt_pdf_sha256, "expected Receipt document")
    manager = _answers(manager_findings, INSPECTION_IDS, "manager inspection")

    # Recompute the observation fingerprint. This detects in-memory
    # corruption; it is not evidence of customer authenticity.
    payload = {
        "project_id": observation.project_id,
        "approved_msr_id": observation.approved_msr_id,
        "approved_msr_version": observation.approved_msr_version,
        "receipt_evidence_id": observation.receipt_evidence_id,
        "receipt_pdf_sha256": observation.receipt_pdf_sha256,
        "recorded_by_actor_id": observation.recorded_by_actor_id,
        "source_kind": observation.source_kind,
        "answers": observation.answers,
        "schema": "GECC_RECEIPT_FEEDBACK_4951_V1",
    }
    if (
        observation.source_kind not in _ALLOWED_SOURCES
        or _answers(dict(observation.answers), SURVEY_IDS, "Receipt survey")
        != observation.answers
        or sha256(_canonical_bytes(payload)).hexdigest()
        != observation.observation_sha256
    ):
        raise ValidationError("Receipt observation integrity mismatch.")

    audit = compare_receipt_survey_to_inspection(
        manager_findings=dict(manager),
        customer_survey_candidates=dict(observation.answers),
    )
    packet = {
        "observation_sha256": observation.observation_sha256,
        "inspection_source_evidence_id": inspection_source_evidence_id,
        "manager_findings": manager,
        "receipt_reference_sha256": audit.reference_sha256,
        "audit_review_candidate_ids": audit.review_candidate_ids,
        "audit_direct_discrepancy_ids": audit.direct_discrepancy_ids,
        "schema": "GECC_PROJECT_RECEIPT_AUDIT_4951_V1",
    }
    return UnverifiedProjectReceiptAuditPacket(
        observation=observation,
        manager_findings=manager,
        inspection_source_evidence_id=inspection_source_evidence_id,
        audit=audit,
        packet_sha256=sha256(_canonical_bytes(packet)).hexdigest(),
    )
