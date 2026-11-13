"""Read-only unit-level equipment evidence for V4 Receipt preparation.

An independently accepted inspection candidate is NOT trusted
installation evidence. This module does not promote it to trusted
status, issue a Receipt, or grant installation/completion authority.
"""

from dataclasses import dataclass
from uuid import UUID

from .documents import canonical_hash
from .equipment_physical_units import physical_units_from_snapshot
from .equipment_physical_capture_pending_service import (
    KIND as PENDING_KIND,
)
from .equipment_physical_inspection_review_service import (
    REVIEW_KIND,
)
from .equipment_physical_inspection_verifier import (
    verify_physical_inspection_candidate,
)
from .models import ProjectEvidence


@dataclass(frozen=True)
class ReviewedEquipmentUnit:
    unit_id: str
    serial_number: str
    pending_evidence_id: str
    review_evidence_id: str
    pending_digest: str
    review_digest: str


@dataclass(frozen=True)
class ReceiptEquipmentManifest:
    project_id: str
    msr_id: str
    msr_version: int
    snapshot_sha256: str
    expected_units: int
    reviewed_units: tuple[ReviewedEquipmentUnit, ...]
    blockers: tuple[str, ...]
    all_candidates_reviewed: bool
    trusted_installation_evidence: bool = False
    receipt_retention_authorized: bool = False
    receipt_issuance_authorized: bool = False
    completion_authorized: bool = False


def build_receipt_equipment_manifest(project):
    """Read existing immutable evidence; never authorize customer issuance.

    Any future API caller must enforce its own project and role access.
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

    project_id = str(UUID(str(project.pk)))
    msr_id = str(UUID(str(msr.pk)))
    snapshot_digest = canonical_hash(msr.snapshot)

    units = physical_units_from_snapshot(
        msr_id=msr_id,
        snapshot=msr.snapshot,
    )

    unit_ids = [unit.unit_id for unit in units]

    if (
        not unit_ids
        or len(unit_ids) != len(set(unit_ids))
        or any(type(unit_id) is not str or not unit_id
               for unit_id in unit_ids)
    ):
        raise ValueError("Physical equipment identities are invalid.")

    pending_records = list(
        ProjectEvidence.objects.filter(msr=msr, kind=PENDING_KIND)
    )
    review_records = list(
        ProjectEvidence.objects.filter(msr=msr, kind=REVIEW_KIND)
    )

    blockers = []
    accepted = []
    seen_serials = set()

    for unit_id in unit_ids:
        captures = [
            record for record in pending_records
            if type(record.data) is dict
            and record.data.get("unit_id") == unit_id
        ]
        reviews = [
            record for record in review_records
            if type(record.data) is dict
            and record.data.get("unit_id") == unit_id
        ]

        if len(captures) != 1 or len(reviews) != 1:
            blockers.append(
                f"Unit {unit_id}: exactly one capture and review required."
            )
            continue

        pending = captures[0]
        review = reviews[0]
        p = pending.data
        r = review.data

        valid = (
            pending.digest == canonical_hash(p)
            and review.digest == canonical_hash(r)
            and p.get("purpose")
                == "PHYSICAL_INSPECTION_PENDING_VERIFICATION"
            and p.get("project_id") == project_id
            and p.get("msr_id") == msr_id
            and p.get("msr_version") == msr.number
            and p.get("snapshot_sha256") == snapshot_digest
            and p.get("unit_id") == unit_id
            and p.get("recorded_by") == str(pending.created_by_id)
            and p.get("confirmed_in_person") is True
            and p.get("independently_verified") is False
            and p.get("trusted_installation_evidence") is False
            and p.get("installation_authorized") is False
            and r.get("status") == "CANDIDATE_ACCEPTED"
            and r.get("pending_id") == str(pending.pk)
            and r.get("pending_digest") == pending.digest
            and r.get("project_id") == project_id
            and r.get("msr_id") == msr_id
            and r.get("msr_version") == msr.number
            and r.get("snapshot_sha256") == snapshot_digest
            and r.get("unit_id") == unit_id
            and r.get("recorder_id") == str(pending.created_by_id)
            and r.get("reviewer_id") == str(review.created_by_id)
            and pending.created_by_id != review.created_by_id
            and r.get("independently_examined") is True
            and r.get("trusted_installation_evidence") is False
            and r.get("installation_authorized") is False
        )

        if not valid:
            blockers.append(
                f"Unit {unit_id}: evidence integrity or independence failed."
            )
            continue

        serial = p.get("serial_number")

        if (
            type(serial) is not str
            or not serial.strip()
            or len(serial) > 120
            or serial != serial.strip().upper()
        ):
            blockers.append(
                f"Unit {unit_id}: normalized serial evidence missing."
            )
            continue

        if serial in seen_serials:
            blockers.append(
                f"Unit {unit_id}: duplicate physical serial number."
            )
            continue

        verification = verify_physical_inspection_candidate(
            project_id=project_id,
            msr_id=msr_id,
            unit_id=unit_id,
        )

        if (
            verification.msr_id != msr_id
            or verification.unit_id != unit_id
            or verification.review_candidate_verified is not True
            or verification.trusted_installation_evidence is not False
            or verification.installation_authorized is not False
            or verification.blockers
        ):
            blockers.append(
                f"Unit {unit_id}: independent verifier did not accept."
            )
            continue

        seen_serials.add(serial)

        accepted.append(
            ReviewedEquipmentUnit(
                unit_id=unit_id,
                serial_number=serial,
                pending_evidence_id=str(pending.pk),
                review_evidence_id=str(review.pk),
                pending_digest=pending.digest,
                review_digest=review.digest,
            )
        )

    for record in pending_records + review_records:
        data = record.data

        if (
            type(data) is not dict
            or data.get("unit_id") not in unit_ids
        ):
            blockers.append(
                "Malformed or unexpected equipment evidence exists."
            )

    all_reviewed = (
        not blockers and len(accepted) == len(unit_ids)
    )

    return ReceiptEquipmentManifest(
        project_id=project_id,
        msr_id=msr_id,
        msr_version=msr.number,
        snapshot_sha256=snapshot_digest,
        expected_units=len(unit_ids),
        reviewed_units=tuple(accepted),
        blockers=tuple(blockers),
        all_candidates_reviewed=all_reviewed,
    )
