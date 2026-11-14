"""Offline inspection/Receipt comparison.

Inputs are unverified candidates until separately bound to actual
retained, authenticated records. No database writes, DocuSign trust,
work orders, Receipt issuance, or project-completion authority.
"""

from dataclasses import dataclass

from django.core.exceptions import ValidationError

from .installation_inspection_form_4945 import (
    INSPECTION_IDS,
    SURVEY_IDS,
    INSPECTION_ITEMS,
    SURVEY_ITEMS,
    assess_inspection_answers,
)


STATUSES = (
    "AGREEMENT_YES",
    "AGREEMENT_NO",
    "DISCREPANCY",
    "CUSTOMER_UNANSWERED",
    "MANAGER_UNANSWERED",
    "BOTH_UNANSWERED",
)

REVIEW_REASONS = (
    "MANAGER_NEGATIVE",
    "CUSTOMER_NEGATIVE",
    "RESPONSES_DISAGREE",
    "MANAGER_UNANSWERED",
)


@dataclass(frozen=True)
class QuestionComparison:
    question_id: str
    question: str
    manager_answer: str | None
    customer_answer: str | None
    status: str
    review_reasons: tuple[str, ...]


@dataclass(frozen=True)
class InstallationReceiptCrosscheck:
    comparisons: tuple[QuestionComparison, ...]
    review_candidate_ids: tuple[str, ...]
    discrepancy_ids: tuple[str, ...]
    manager_negative_ids: tuple[str, ...]
    customer_negative_ids: tuple[str, ...]
    unanswered_customer_ids: tuple[str, ...]
    survey_answers: tuple[tuple[str, str | None], ...]
    survey_answered_count: int
    status: str = "OFFLINE_COMPARISON_UNVERIFIED"
    receipt_customer_provenance_verified: bool = False
    installation_signature_verified: bool = False
    action_items_persisted: bool = False
    completion_authorized: bool = False


def _validate_answers(values, expected, label):
    if type(values) is not dict or set(values) != set(expected):
        raise ValidationError(f"Exact {label} question keys required.")

    for key in expected:
        value = values[key]
        if value is not None and (
            type(value) is not str or value not in ("YES", "NO")
        ):
            raise ValidationError(f"Invalid {label} answer: {key}")


def compare_installation_to_receipt(
    *,
    manager_findings,
    receipt_inspection_answers,
    receipt_survey_answers,
):
    """Compare corresponding questions without assuming customer authenticity.

    receipt_inspection_answers must refer to the same five inspection
    questions. Receipt field extraction and customer attribution are
    deliberately NOT implemented here.
    """
    _validate_answers(
        manager_findings, INSPECTION_IDS, "manager inspection"
    )
    _validate_answers(
        receipt_inspection_answers, INSPECTION_IDS, "Receipt inspection"
    )
    _validate_answers(
        receipt_survey_answers, SURVEY_IDS, "Receipt survey"
    )

    # The inspection analysis evaluates manager negatives and missing
    # findings. The Receipt survey is never an installation pass gate.
    assessment = assess_inspection_answers(
        inspection=manager_findings,
        survey=receipt_survey_answers,
    )

    comparisons = []
    review_ids = []
    discrepancy_ids = []
    customer_negative_ids = []
    customer_unanswered_ids = []

    for question_id, question in zip(
        INSPECTION_IDS, INSPECTION_ITEMS
    ):
        manager = manager_findings[question_id]
        customer = receipt_inspection_answers[question_id]
        reasons = []

        if manager is None and customer is None:
            status = "BOTH_UNANSWERED"
        elif manager is None:
            status = "MANAGER_UNANSWERED"
        elif customer is None:
            status = "CUSTOMER_UNANSWERED"
        elif manager == customer:
            status = (
                "AGREEMENT_YES" if manager == "YES"
                else "AGREEMENT_NO"
            )
        else:
            status = "DISCREPANCY"
            discrepancy_ids.append(question_id)
            reasons.append("RESPONSES_DISAGREE")

        if manager == "NO":
            reasons.append("MANAGER_NEGATIVE")
        if customer == "NO":
            reasons.append("CUSTOMER_NEGATIVE")
            customer_negative_ids.append(question_id)
        if manager is None:
            reasons.append("MANAGER_UNANSWERED")
        if customer is None:
            customer_unanswered_ids.append(question_id)

        reasons = tuple(dict.fromkeys(reasons))
        if reasons:
            review_ids.append(question_id)

        comparisons.append(
            QuestionComparison(
                question_id=question_id,
                question=question,
                manager_answer=manager,
                customer_answer=customer,
                status=status,
                review_reasons=reasons,
            )
        )

    if tuple(
        question_id for question_id in INSPECTION_IDS
        if manager_findings[question_id] == "NO"
    ) != assessment.corrective_action_items:
        raise ValidationError("Inspection corrective-action mismatch.")

    return InstallationReceiptCrosscheck(
        comparisons=tuple(comparisons),
        review_candidate_ids=tuple(review_ids),
        discrepancy_ids=tuple(discrepancy_ids),
        manager_negative_ids=assessment.corrective_action_items,
        customer_negative_ids=tuple(customer_negative_ids),
        unanswered_customer_ids=tuple(customer_unanswered_ids),
        survey_answers=tuple(
            (key, receipt_survey_answers[key]) for key in SURVEY_IDS
        ),
        survey_answered_count=assessment.survey_answered_count,
    )
