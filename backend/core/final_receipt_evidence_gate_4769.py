"""Read-only Final Receipt evidence gate.

Combines financial/equipment preflight with independently reviewed
physical-unit manifest. Candidate review is never equivalent to
trusted installation evidence, customer Receipt issuance, or delivery.
No database writes or provider calls.
"""

from dataclasses import dataclass

from .final_receipt_retention_preflight_4766 import (
    assess_final_receipt_retention_preflight,
)
from .receipt_equipment_manifest_4768 import (
    build_receipt_equipment_manifest,
)


@dataclass(frozen=True)
class FinalReceiptEvidenceGate:
    project_id: str
    approved_msr_id: str
    expected_units: int
    reviewed_units: int
    verified_funds: str
    outstanding_balance: str
    blockers: tuple[str, ...]
    candidate_evidence_complete: bool
    trusted_equipment_evidence: bool = False
    retention_authorized: bool = False
    final_receipt_verified: bool = False
    customer_delivery_verified: bool = False
    completion_authorized: bool = False


def assess_final_receipt_evidence_gate(project):
    """Read existing evidence without granting any authorization.

    A future API caller must independently enforce actor permissions.
    """
    if project is None or getattr(project, "pk", None) is None:
        raise ValueError("Persisted project required.")

    preflight = assess_final_receipt_retention_preflight(project)
    manifest = build_receipt_equipment_manifest(project)

    msr = getattr(project, "current_approved", None)
    if (
        msr is None
        or getattr(msr, "status", None) != "APPROVED"
        or getattr(msr, "project_id", None) != project.pk
    ):
        raise ValueError("Current approved MSR required.")

    project_id = str(project.pk)
    msr_id = str(msr.pk)

    if (
        preflight.project_id != project_id
        or manifest.project_id != project_id
        or preflight.approved_msr_id != msr_id
        or manifest.msr_id != msr_id
        or manifest.msr_version != msr.number
    ):
        raise ValueError("Receipt evidence binding mismatch.")

    if (
        preflight.expected_physical_units != manifest.expected_units
        or manifest.expected_units < 1
        or preflight.reviewed_unit_candidates < 0
        or preflight.reviewed_unit_candidates > manifest.expected_units
        or len(manifest.reviewed_units) > manifest.expected_units
    ):
        raise ValueError("Conflicting physical-equipment counts.")

    if (
        preflight.retention_ready is not False
        or preflight.final_receipt_verified is not False
        or preflight.customer_delivery_verified is not False
        or preflight.completion_authorized is not False
        or manifest.trusted_installation_evidence is not False
        or manifest.receipt_retention_authorized is not False
        or manifest.receipt_issuance_authorized is not False
        or manifest.completion_authorized is not False
    ):
        raise ValueError("Unauthorized evidence-state promotion.")

    blockers = list(preflight.blockers)
    blockers.extend(manifest.blockers)

    reviewed_units = len(manifest.reviewed_units)
    candidates_complete = (
        manifest.all_candidates_reviewed is True
        and reviewed_units == manifest.expected_units
        and preflight.reviewed_unit_candidates == reviewed_units
    )

    if not candidates_complete:
        blockers.append(
            "Independently reviewed equipment manifest is incomplete."
        )

    # These are unconditional until distinct trusted equipment,
    # final PDF retention, and authenticated delivery workflows exist.
    blockers.extend((
        "Reviewed inspection candidates are not trusted installation evidence.",
        "The internal PDF is not an issued customer Receipt.",
        "Final Receipt retention and authenticated delivery remain blocked.",
    ))

    return FinalReceiptEvidenceGate(
        project_id=project_id,
        approved_msr_id=msr_id,
        expected_units=manifest.expected_units,
        reviewed_units=reviewed_units,
        verified_funds=preflight.verified_funds,
        outstanding_balance=preflight.outstanding_balance,
        blockers=tuple(dict.fromkeys(blockers)),
        candidate_evidence_complete=candidates_complete,
    )
