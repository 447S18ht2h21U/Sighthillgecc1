"""Offline comparison of five inspection findings with three Receipt answers.

The approved V4 Receipt has only three survey questions and zero PDF
form fields. This module never attributes printed answers to a customer
or authenticates them. It does not read or write project records.
"""

from dataclasses import dataclass

from django.core.exceptions import ValidationError

from .approved_final_receipt_reference_4756 import (
    REQUIRED_SURVEY_TEXT,
    verify_approved_final_receipt,
)
from .installation_inspection_form_4945 import (
    INSPECTION_IDS,
    INSPECTION_ITEMS,
    SURVEY_IDS,
    SURVEY_ITEMS,
    assess_inspection_answers,
)


# The only direct question-level comparison.
DIRECT_MAPPING = {
    "survey_1": "inspection_4",
}

# Related questions provide review context, NOT matching answers.
CONTEXT_MAPPING = {
    "survey_2": ("inspection_2", "inspection_3"),
    "survey_3": ("inspection_5",),
}


@dataclass(frozen=True)
class ReceiptFeedbackFinding:
    survey_id: str
    question: str
    customer_answer_candidate: str | None
    related_inspection_ids: tuple[str, ...]
    relationship: str
    assessment: str
    review_required: bool


@dataclass(frozen=True)
class InstallationReceiptAudit:
    findings: tuple[ReceiptFeedbackFinding, ...]
    manager_negative_ids: tuple[str, ...]
    manager_unanswered_ids: tuple[str, ...]
    customer_negative_ids: tuple[str, ...]
    direct_discrepancy_ids: tuple[str, ...]
    review_candidate_ids: tuple[str, ...]
    customer_survey_answered_count: int
    reference_sha256: str
    status: str = "OFFLINE_CANDIDATES_NOT_CUSTOMER_AUTHENTICATED"
    customer_provenance_verified: bool = False
    manager_signature_verified: bool = False
    corrective_actions_persisted: bool = False
    customer_survey_required_for_completion: bool = False
    completion_authorized: bool = False


def compare_receipt_survey_to_inspection(
    *, manager_findings, customer_survey_candidates
):
    """Compare the real question sets without invented Receipt fields."""
    if (
        type(manager_findings) is not dict
        or set(manager_findings) != set(INSPECTION_IDS)
        or type(customer_survey_candidates) is not dict
        or set(customer_survey_candidates) != set(SURVEY_IDS)
    ):
        raise ValidationError("Exact five/three question sets required.")

    for values in (manager_findings, customer_survey_candidates):
        for answer in values.values():
            if answer is not None and (
                type(answer) is not str or answer not in ("YES", "NO")
            ):
                raise ValidationError("Only YES, NO or unanswered allowed.")

    reference = verify_approved_final_receipt()
    if tuple(REQUIRED_SURVEY_TEXT) != tuple(SURVEY_ITEMS):
        raise ValidationError("Receipt survey wording differs from approved form.")

    inspection = assess_inspection_answers(
        inspection=manager_findings,
        survey=customer_survey_candidates,
    )

    findings = []
    customer_negatives = []
    direct_discrepancies = []
    review_ids = set(inspection.corrective_action_items)
    review_ids.update(inspection.unanswered_inspection_items)

    for survey_id, question in zip(SURVEY_IDS, SURVEY_ITEMS):
        answer = customer_survey_candidates[survey_id]

        if survey_id in DIRECT_MAPPING:
            inspection_id = DIRECT_MAPPING[survey_id]
            related = (inspection_id,)
            manager = manager_findings[inspection_id]
            relationship = "DIRECT_CLEANUP_CHECK"

            if answer is None:
                assessment = "CUSTOMER_UNANSWERED"
            elif manager is None:
                assessment = "MANAGER_UNANSWERED"
            elif manager == answer:
                assessment = "AGREEMENT"
            else:
                assessment = "DIRECT_DISCREPANCY"
                direct_discrepancies.append(survey_id)
                review_ids.add(inspection_id)
        else:
            related = CONTEXT_MAPPING[survey_id]
            relationship = "CONTEXT_ONLY"
            assessment = (
                "CUSTOMER_UNANSWERED"
                if answer is None
                else "RELATED_FEEDBACK_NO_DIRECT_COMPARISON"
            )

        if answer == "NO":
            customer_negatives.append(survey_id)
            review_ids.update(related)

        findings.append(
            ReceiptFeedbackFinding(
                survey_id=survey_id,
                question=question,
                customer_answer_candidate=answer,
                related_inspection_ids=related,
                relationship=relationship,
                assessment=assessment,
                review_required=(
                    answer == "NO"
                    or assessment == "DIRECT_DISCREPANCY"
                ),
            )
        )

    return InstallationReceiptAudit(
        findings=tuple(findings),
        manager_negative_ids=inspection.corrective_action_items,
        manager_unanswered_ids=inspection.unanswered_inspection_items,
        customer_negative_ids=tuple(customer_negatives),
        direct_discrepancy_ids=tuple(direct_discrepancies),
        review_candidate_ids=tuple(
            key for key in INSPECTION_IDS if key in review_ids
        ),
        customer_survey_answered_count=inspection.survey_answered_count,
        reference_sha256=reference.sha256,
    )
