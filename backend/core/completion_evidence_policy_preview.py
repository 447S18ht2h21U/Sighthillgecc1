"""Unregistered, read-only, fail-closed project-completion policy.

Inputs are candidate assertions only. Independent durable evidence
verification and authorized transactional completion remain mandatory.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class CompletionEvidencePreview:
    candidate_requirements_satisfied: bool
    blockers: tuple[str, ...]
    survey_received: bool
    evidence_trusted: bool = False
    project_completion_authorized: bool = False
    project_completed: bool = False


def preview_project_completion_evidence(
    *,
    physical_work_verified=False,
    required_inspections_verified=False,
    receipt_pdf_retained=False,
    receipt_email_delivery_verified=False,
    completed_docusign_certificate_received=False,
    completed_docusign_certificate_retained=False,
    customer_satisfaction_survey_received=False,
):
    checks = (
        ("Verified physical installation completion is required.",
         physical_work_verified),
        ("Required inspection evidence is missing.",
         required_inspections_verified),
        ("Exact final Receipt PDF must be retained.",
         receipt_pdf_retained),
        ("Verified email-sending evidence for the same Receipt is required.",
         receipt_email_delivery_verified),
        ("GECC must receive the verified completed DocuSign Completion Certificate.",
         completed_docusign_certificate_received),
        ("The completed DocuSign Completion Certificate must be retained.",
         completed_docusign_certificate_retained),
    )
    flags = [flag for _, flag in checks]
    if any(type(flag) is not bool for flag in flags):
        raise ValueError("Completion evidence flags must be booleans.")
    if type(customer_satisfaction_survey_received) is not bool:
        raise ValueError("Survey status must be boolean.")

    blockers = [message for message, flag in checks if not flag]
    blockers.append(
        "Independent project/MSR/document evidence verification and "
        "operational completion authorization are not implemented."
    )
    return CompletionEvidencePreview(
        candidate_requirements_satisfied=all(flags),
        blockers=tuple(blockers),
        survey_received=customer_satisfaction_survey_received,
    )
