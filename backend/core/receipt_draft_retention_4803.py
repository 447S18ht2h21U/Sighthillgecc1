"""Development-only retention of independently verified draft packages.

No public endpoint, customer issuance, delivery, or completion authority.
"""

import os
from hashlib import sha256

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from .approved_final_receipt_reference_4756 import (
    verify_approved_final_receipt,
)
from .documents import canonical_hash
from .final_receipt_package_4797 import ReceiptPackageDraft
from .final_receipt_package_verifier_4798 import (
    verify_receipt_package_draft,
)
from .models import Project, ReceiptDraftPackage, Role, User
from .services import audit


def verify_retained_draft_package(*, project, record):
    """Reconstruct and reverify the exact retained archive on reading."""
    msr = project.current_approved

    if (
        msr is None
        or record.project_id != project.pk
        or record.msr_id != msr.pk
        or record.status != "DRAFT_NOT_ISSUED"
        or record.snapshot_sha256 != canonical_hash(msr.snapshot)
        or record.approved_reference_sha256.lower()
            != verify_approved_final_receipt().sha256.lower()
    ):
        raise ValidationError("Retained package identity mismatch.")

    content = bytes(record.content)

    if (
        len(content) > 12 * 1024 * 1024
        or sha256(content).hexdigest() != record.archive_sha256
    ):
        raise ValidationError("Retained archive fingerprint mismatch.")

    package = ReceiptPackageDraft(
        project_id=str(project.pk),
        msr_id=str(msr.pk),
        snapshot_sha256=record.snapshot_sha256,
        receipt_sha256=record.receipt_sha256,
        addendum_sha256=record.addendum_sha256,
        archive_sha256=record.archive_sha256,
        archive=content,
    )

    try:
        verified = verify_receipt_package_draft(
            project=project, package=package,
        )
    except (ValueError, TypeError) as exc:
        raise ValidationError(
            "Retained draft package failed independent verification."
        ) from exc

    if (
        verified.integrity_verified is not True
        or verified.equipment_count != record.equipment_count
        or verified.status != "DRAFT_NOT_ISSUED"
        or verified.issuance_authorized is not False
        or verified.customer_delivery_verified is not False
        or verified.completion_authorized is not False
    ):
        raise ValidationError("Retained verification claims invalid.")

    return verified


@transaction.atomic
def retain_receipt_draft_package(*, actor, project_id, package):
    """Insert exactly one verified draft package and chained audit event."""
    if (
        settings.ENVIRONMENT != "development"
        or settings.DEBUG is not True
        or os.environ.get(
            "GECC_RECEIPT_DRAFT_RETENTION_TEST_ENABLED"
        ) != "1"
    ):
        raise PermissionDenied("Draft retention is disabled.")

    if actor is None or getattr(actor, "pk", None) is None:
        raise PermissionDenied("Authenticated Comptroller required.")

    reviewer = User.objects.filter(pk=actor.pk).first()

    if (
        reviewer is None
        or reviewer.is_active is not True
        or reviewer.role != Role.COMPTROLLER
    ):
        raise PermissionDenied("Active Comptroller required.")

    if not isinstance(package, ReceiptPackageDraft):
        raise ValidationError("A verified draft package is required.")

    project = (
        Project.objects.select_for_update()
        .select_related("current_approved")
        .filter(pk=project_id)
        .first()
    )

    if project is None or project.state == "CANCELLED":
        raise ValidationError("Active project required.")

    msr = project.current_approved

    if (
        msr is None
        or msr.status != "APPROVED"
        or msr.project_id != project.pk
        or project.current_approved_id != msr.pk
        or type(msr.snapshot) is not dict
    ):
        raise ValidationError("Current approved MSR required.")

    try:
        verified = verify_receipt_package_draft(
            project=project, package=package,
        )
    except (ValueError, TypeError) as exc:
        raise ValidationError(
            "Draft package independent verification failed."
        ) from exc

    if (
        verified.integrity_verified is not True
        or verified.project_id != str(project.pk)
        or verified.msr_id != str(msr.pk)
        or verified.status != "DRAFT_NOT_ISSUED"
        or verified.issuance_authorized is not False
        or verified.customer_delivery_verified is not False
        or verified.completion_authorized is not False
    ):
        raise ValidationError("Draft package authority mismatch.")

    reference = verify_approved_final_receipt()

    identity = {
        "msr": msr,
        "archive_sha256": package.archive_sha256,
    }

    existing = ReceiptDraftPackage.objects.filter(**identity).first()

    if existing is not None:
        stored = verify_retained_draft_package(
            project=project, record=existing,
        )

        if (
            bytes(existing.content) != package.archive
            or existing.receipt_sha256 != package.receipt_sha256
            or existing.addendum_sha256 != package.addendum_sha256
            or stored.equipment_count != verified.equipment_count
        ):
            raise ValidationError(
                "Existing draft package differs from request."
            )

        return existing, False

    record = ReceiptDraftPackage.objects.create(
        project=project,
        msr=msr,
        created_by=reviewer,
        snapshot_sha256=package.snapshot_sha256,
        approved_reference_sha256=reference.sha256.lower(),
        receipt_sha256=package.receipt_sha256,
        addendum_sha256=package.addendum_sha256,
        archive_sha256=package.archive_sha256,
        equipment_count=verified.equipment_count,
        content=package.archive,
        status="DRAFT_NOT_ISSUED",
    )

    verify_retained_draft_package(project=project, record=record)

    audit(
        reviewer,
        "receipt.draft_package_retained",
        project.pk,
        {
            "package_id": str(record.pk),
            "msr_id": str(msr.pk),
            "archive_sha256": record.archive_sha256,
            "receipt_sha256": record.receipt_sha256,
            "addendum_sha256": record.addendum_sha256,
            "equipment_count": record.equipment_count,
            "draft_only": True,
            "issuance_authorized": False,
            "customer_delivery_verified": False,
            "completion_authorized": False,
        },
    )

    return record, True
