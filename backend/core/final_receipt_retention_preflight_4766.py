"""Read-only preflight for V4 Final Receipt retention.

No issuance authority is derived from financial readiness, inspection
review, or a locally rendered PDF. This service never writes records.
"""

from dataclasses import dataclass

from .final_receipt_financial_evidence_4760 import (
    assess_final_receipt_finances,
)
from .equipment_physical_inspection_verifier import (
    physical_units_from_snapshot,
    verify_physical_inspection_candidate,
)


@dataclass(frozen=True)
class FinalReceiptRetentionPreflight:
    project_id: str
    approved_msr_id: str
    expected_physical_units: int
    reviewed_unit_candidates: int
    trusted_units: int
    verified_funds: str
    outstanding_balance: str
    blockers: tuple[str, ...]
    retention_ready: bool = False
    final_receipt_verified: bool = False
    customer_delivery_verified: bool = False
    completion_authorized: bool = False


def assess_final_receipt_retention_preflight(project):
    """Assess existing evidence without granting final Receipt authority.

    Access control must be enforced by any future API caller.
    """

    if project is None or getattr(project, "pk", None) is None:
        raise ValueError("Persisted project required.")

    msr = getattr(project, "current_approved", None)

    if (
        getattr(project, "state", None) == "CANCELLED"
        or msr is None
        or getattr(msr, "status", None) != "APPROVED"
        or getattr(msr, "project_id", None) != project.pk
        or type(getattr(msr, "snapshot", None)) is not dict
    ):
        raise ValueError("Current approved MSR required.")

    finances = assess_final_receipt_finances(project)

    if (
        finances.project_id != str(project.pk)
        or finances.approved_msr_id != str(msr.pk)
        or finances.approved_msr_version != msr.number
    ):
        raise ValueError("Financial evidence belongs to another MSR.")

    units = physical_units_from_snapshot(
        msr_id=str(msr.pk),
        snapshot=msr.snapshot,
    )

    if not isinstance(units, (tuple, list)) or not units:
        raise ValueError("Approved physical-unit inventory required.")

    identifiers = [unit.unit_id for unit in units]

    if (
        any(type(value) is not str or not value for value in identifiers)
        or len(identifiers) != len(set(identifiers))
    ):
        raise ValueError("Approved physical-unit identities are invalid.")

    blockers = []
    reviewed = 0
    trusted = 0

    for unit_id in identifiers:
        result = verify_physical_inspection_candidate(
            project_id=str(project.pk),
            msr_id=str(msr.pk),
            unit_id=unit_id,
        )

        if (
            result.msr_id != str(msr.pk)
            or result.unit_id != unit_id
        ):
            raise ValueError("Equipment review binding mismatch.")

        if result.review_candidate_verified is True:
            reviewed += 1
        else:
            blockers.append(
                f"Unit {unit_id}: independently accepted inspection "
                "candidate missing."
            )

        if result.trusted_installation_evidence is True:
            trusted += 1
        else:
            blockers.append(
                f"Unit {unit_id}: trusted physical installation "
                "evidence is not established."
            )

        if result.installation_authorized is True:
            raise ValueError(
                "Receipt preflight cannot accept installation authority "
                "from this candidate review."
            )

        for explanation in result.blockers:
            if type(explanation) is str and explanation.strip():
                blockers.append(f"Unit {unit_id}: {explanation.strip()}")

    if finances.overpayment_requires_review:
        blockers.append("Customer overpayment requires independent review.")

    blockers.extend((
        "Internal NOT ISSUED PDF is not a final customer Receipt.",
        "Exact final Receipt retention is not yet authorized.",
        "Authenticated customer email delivery has not been proven.",
    ))

    return FinalReceiptRetentionPreflight(
        project_id=str(project.pk),
        approved_msr_id=str(msr.pk),
        expected_physical_units=len(identifiers),
        reviewed_unit_candidates=reviewed,
        trusted_units=trusted,
        verified_funds=str(finances.verified_customer_funds),
        outstanding_balance=str(finances.outstanding_balance),
        blockers=tuple(blockers),
    )
