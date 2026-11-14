"""Read-only FINAL Receipt release preflight.

A draft package, provisional equipment adjudication, and paid balance
must never independently authorize FINAL issuance or delivery.
"""

from dataclasses import dataclass
from hashlib import sha256

from django.db import connections, router

from .documents import canonical_hash
from .installation_completion_evidence_4815 import (
    assess_installation_completion_evidence,
)
from .final_receipt_financial_evidence_4760 import (
    assess_final_receipt_finances,
)
from .models import ReceiptDraftPackage
from .receipt_draft_retention_4803 import (
    verify_retained_draft_package,
)


@dataclass(frozen=True)
class FinalReceiptReleasePreflight:
    project_id: str
    msr_id: str | None
    status: str
    storage_available: bool
    retained_package_count: int
    verified_package_count: int
    financial_evidence_verified: bool
    payment_fully_confirmed: bool
    overpayment_requires_review: bool
    draft_integrity_verified: bool
    blockers: tuple[str, ...]
    operational_schedule_completed: bool
    provisional_equipment_decisions_verified: bool
    physical_unit_count: int = 0
    verified_inspection_candidate_count: int = 0
    all_inspection_candidates_verified: bool = False
    installation_provenance_status: str = "UNVERIFIED"
    installation_source_integrity_verified: bool = False
    acceptance_candidate_verified: bool = False
    post_installation_acceptance_verified: bool = False
    trusted_installation_evidence: bool = False
    final_receipt_issuance_authorized: bool = False
    final_receipt_verified: bool = False
    provider_email_authenticated: bool = False
    customer_delivery_verified: bool = False
    completion_authorized: bool = False


def assess_final_receipt_release_preflight(project):
    """Independently correlate persisted evidence, never promote authority."""
    if project is None or getattr(project, "pk", None) is None:
        raise ValueError("Persisted project required.")

    pid = str(project.pk)
    msr = getattr(project, "current_approved", None)
    mid = str(msr.pk) if msr is not None else None

    blockers = [
        "Trusted installation completion evidence is not verified.",
        "FINAL customer Receipt issuance has not been authorized.",
        "Provider-authenticated delivery of the exact FINAL Receipt is absent.",
        "Verified DocuSign Completion Certificate evidence is required.",
    ]

    base = {
        "project_id": pid,
        "msr_id": mid,
        "storage_available": False,
        "retained_package_count": 0,
        "verified_package_count": 0,
        "financial_evidence_verified": False,
        "payment_fully_confirmed": False,
        "overpayment_requires_review": False,
        "draft_integrity_verified": False,
        "operational_schedule_completed": False,
        "provisional_equipment_decisions_verified": False,
    }

    if (
        msr is None
        or msr.status != "APPROVED"
        or msr.project_id != project.pk
        or getattr(project, "current_approved_id", None) != msr.pk
        or type(msr.snapshot) is not dict
        or project.state == "CANCELLED"
    ):
        blockers.append("Active project with current approved MSR required.")
        return FinalReceiptReleasePreflight(
            **base,
            status="PREREQUISITES_MISSING",
            blockers=tuple(blockers),
        )

    finances = assess_final_receipt_finances(project)

    if (
        finances.project_id != pid
        or finances.approved_msr_id != mid
        or finances.approved_msr_version != msr.number
        or finances.receipt_issuance_authorized is not False
        or finances.customer_delivery_verified is not False
        or finances.project_completion_authorized is not False
    ):
        raise ValueError("Financial evidence identity or authority mismatch.")

    installation = assess_installation_completion_evidence(project)

    if (
        installation.project_id != pid
        or installation.post_installation_acceptance_verified is not False
        or installation.trusted_installation_evidence is not False
        or installation.final_receipt_issuance_authorized is not False
        or installation.completion_authorized is not False
    ):
        raise ValueError("Installation completion asserted false authority.")

    base["operational_schedule_completed"] = (
        installation.operational_schedule_completed
    )
    base["provisional_equipment_decisions_verified"] = (
        installation.provisional_equipment_decisions_verified
    )
    base["installation_source_integrity_verified"] = (
        installation.installation_source_integrity_verified
    )
    base["installation_provenance_status"] = (
        installation.installation_provenance_status
    )
    base["acceptance_candidate_verified"] = (
        installation.acceptance_candidate_verified
    )
    base["physical_unit_count"] = installation.physical_unit_count
    base["verified_inspection_candidate_count"] = (
        installation.verified_inspection_candidate_count
    )
    base["all_inspection_candidates_verified"] = (
        installation.all_inspection_candidates_verified
    )
    blockers.extend(installation.blockers)

    base["financial_evidence_verified"] = True
    base["payment_fully_confirmed"] = (
        finances.payment_fully_confirmed is True
    )
    base["overpayment_requires_review"] = (
        finances.overpayment_requires_review is True
    )

    if not base["payment_fully_confirmed"]:
        blockers.append("Customer payment is not fully bank-confirmed.")

    if base["overpayment_requires_review"]:
        blockers.append("Financial overpayment requires independent review.")

    alias = router.db_for_read(ReceiptDraftPackage)
    connection = connections[alias]

    with connection.cursor() as cursor:
        available_tables = set(connection.introspection.table_names(cursor))

    if ReceiptDraftPackage._meta.db_table not in available_tables:
        blockers.append("Immutable draft-package storage is unavailable.")
        return FinalReceiptReleasePreflight(
            **base,
            status="SCHEMA_UNAVAILABLE",
            blockers=tuple(blockers),
        )

    base["storage_available"] = True

    records = list(
        ReceiptDraftPackage.objects.using(alias)
        .filter(project_id=project.pk, msr_id=msr.pk)
        .order_by("created_at", "pk")
    )

    base["retained_package_count"] = len(records)

    if not records:
        blockers.append("No immutable draft Receipt package is retained.")
        return FinalReceiptReleasePreflight(
            **base,
            status="NO_DRAFT_PACKAGE",
            blockers=tuple(blockers),
        )

    digest = canonical_hash(msr.snapshot)

    for record in records:
        try:
            if (
                record.snapshot_sha256 != digest
                or record.status != "DRAFT_NOT_ISSUED"
                or sha256(bytes(record.content)).hexdigest()
                    != record.archive_sha256
            ):
                raise ValueError("Stored draft identity mismatch.")

            verified = verify_retained_draft_package(
                project=project,
                record=record,
            )

            if (
                verified.integrity_verified is not True
                or verified.project_id != pid
                or verified.msr_id != mid
                or verified.status != "DRAFT_NOT_ISSUED"
                or verified.issuance_authorized is not False
                or verified.customer_delivery_verified is not False
                or verified.completion_authorized is not False
            ):
                raise ValueError("Stored draft verification mismatch.")

            base["verified_package_count"] += 1

        except (ValueError, TypeError, AttributeError, Exception) as exc:
            # Fail closed; no archive contents or private details returned.
            blockers.append("Retained draft-package integrity failed.")
            base["verified_package_count"] = 0
            return FinalReceiptReleasePreflight(
                **base,
                status="INTEGRITY_FAILED",
                blockers=tuple(dict.fromkeys(blockers)),
            )

    base["draft_integrity_verified"] = True

    blockers.append(
        "Verified draft packages are not issued FINAL customer Receipts."
    )

    return FinalReceiptReleasePreflight(
        **base,
        status="DRAFT_EVIDENCE_VERIFIED_RELEASE_BLOCKED",
        blockers=tuple(dict.fromkeys(blockers)),
    )
