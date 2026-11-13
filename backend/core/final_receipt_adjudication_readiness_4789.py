"""Read-only integration of provisional equipment adjudication and Receipt readiness.

All trust, installation, customer issuance, delivery and completion authority
remain false. No production policy is established by this assessment.
"""

from dataclasses import dataclass

from .equipment_trust_verifier_4785 import verify_equipment_trust_decisions
from .final_receipt_issuance_boundary_4781 import (
    assess_final_receipt_issuance_boundary,
)


@dataclass(frozen=True)
class FinalReceiptAdjudicationReadiness:
    project_id: str
    msr_id: str
    internal_receipt_verified: bool
    candidate_equipment_review_complete: bool
    provisional_ceo_adjudication_complete: bool
    expected_equipment_units: int
    verified_ceo_approvals: int
    blockers: tuple[str, ...]
    trusted_installation_evidence: bool = False
    installation_authorized: bool = False
    final_receipt_issuance_authorized: bool = False
    customer_delivery_verified: bool = False
    completion_authorized: bool = False


def assess_final_receipt_adjudication_readiness(project):
    """Combine the existing issuance boundary and real adjudication verifier.

    Missing candidate reviews are a blocked status. Corrupt or mismatched
    evidence is an error, not an acceptable missing-review condition.
    """
    if project is None or getattr(project, "pk", None) is None:
        raise ValueError("Persisted project required.")

    msr = getattr(project, "current_approved", None)
    if (
        msr is None
        or getattr(msr, "status", None) != "APPROVED"
        or str(getattr(msr, "project_id", "")) != str(project.pk)
    ):
        raise ValueError("Current approved MSR required.")

    boundary = assess_final_receipt_issuance_boundary(project)

    project_id = str(project.pk)
    msr_id = str(msr.pk)

    if (
        boundary.project_id != project_id
        or boundary.msr_id != msr_id
        or boundary.trusted_installation_evidence is not False
        or boundary.customer_receipt_issuance_authorized is not False
        or boundary.provider_email_authenticated is not False
        or boundary.customer_delivery_verified is not False
        or boundary.completion_authorized is not False
    ):
        raise ValueError("Receipt boundary identity or trust mismatch.")

    blockers = list(boundary.blockers)
    expected = 0
    approved = 0
    adjudicated = False

    if boundary.reviewed_equipment_candidates_complete is True:
        verified = verify_equipment_trust_decisions(project)

        if (
            verified.project_id != project_id
            or verified.msr_id != msr_id
            or verified.expected_units < 1
            or verified.approved_decisions_verified < 0
            or verified.approved_decisions_verified > verified.expected_units
            or verified.trusted_installation_evidence is not False
            or verified.installation_authorized is not False
            or verified.receipt_issuance_authorized is not False
            or verified.customer_delivery_verified is not False
            or verified.completion_authorized is not False
        ):
            raise ValueError("Equipment adjudication identity or trust mismatch.")

        expected = verified.expected_units
        approved = verified.approved_decisions_verified
        adjudicated = verified.all_approval_decisions_verified is True
        blockers.extend(verified.blockers)

        if not adjudicated:
            blockers.append(
                "Every physical unit requires a verified affirmative "
                "independent adjudication."
            )
    else:
        blockers.append(
            "Independent physical-equipment review remains incomplete."
        )

    blockers.extend((
        "CEO equipment adjudication is provisional, not a production "
        "trust authorization.",
        "Separate trusted installation evidence remains required.",
        "A FINAL customer Receipt has not been authorized for issuance.",
        "Authenticated delivery and project completion remain blocked.",
    ))

    return FinalReceiptAdjudicationReadiness(
        project_id=project_id,
        msr_id=msr_id,
        internal_receipt_verified=(
            boundary.internal_document_verified is True
        ),
        candidate_equipment_review_complete=(
            boundary.reviewed_equipment_candidates_complete is True
        ),
        provisional_ceo_adjudication_complete=adjudicated,
        expected_equipment_units=expected,
        verified_ceo_approvals=approved,
        blockers=tuple(dict.fromkeys(blockers)),
    )
