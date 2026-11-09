"""Unregistered, development-only serial exception request service.

Requests are immutable and audited. They never authorize an exception,
equipment installation, or a document change. No API is registered.
"""
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from .documents import canonical_hash
from .equipment_physical_units import physical_units_from_snapshot
from .models import Project, ProjectEvidence, Role, User
from .services import audit


REQUEST_KIND = "SERIAL_EXCEPTION_REQUEST"


@transaction.atomic
def request_serial_exception(*, actor, project_id, msr_id, unit_id, reason):
    if settings.ENVIRONMENT != "development" or not settings.DEBUG:
        raise ValidationError(
            "Serial exception prototype is development-only."
        )

    if actor is None or not getattr(actor, "pk", None):
        raise PermissionDenied("An authenticated requester is required.")

    requester = User.objects.get(pk=actor.pk)
    if not requester.is_active or requester.role != Role.INSTALLATION_MANAGER:
        raise PermissionDenied(
            "Only an active Installation Manager may request this exception."
        )

    if type(reason) is not str or not 15 <= len(reason.strip()) <= 2000:
        raise ValidationError(
            "A specific written explanation is required."
        )
    if type(unit_id) is not str or not unit_id.strip():
        raise ValidationError("A specific physical unit is required.")

    project = Project.objects.select_for_update().get(pk=project_id)
    msr = project.current_approved

    if (
        project.state == "CANCELLED"
        or msr is None
        or msr.status != "APPROVED"
        or str(msr.pk) != str(msr_id)
        or msr.project_id != project.pk
    ):
        raise ValidationError(
            "Exception must reference the current approved MSR of an active project."
        )

    try:
        units = physical_units_from_snapshot(
            msr_id=str(msr.pk), snapshot=msr.snapshot
        )
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc

    if unit_id not in {unit.unit_id for unit in units}:
        raise ValidationError(
            "The physical unit does not belong to this approved MSR."
        )

    previous = ProjectEvidence.objects.filter(
        msr=msr, kind=REQUEST_KIND
    ).order_by("-created_at", "-id")

    if any(evidence.data.get("unit_id") == unit_id for evidence in previous):
        raise ValidationError(
            "A serial exception request already exists for this physical unit."
        )

    payload = {
        "status": "REQUESTED",
        "msr_id": str(msr.pk),
        "msr_version": msr.number,
        "snapshot_sha256": canonical_hash(msr.snapshot),
        "unit_id": unit_id,
        "requester_id": str(requester.pk),
        "reason": reason.strip(),
        "requested_at": timezone.now().isoformat(),
        "genuinely_not_applicable": "REQUIRES_INDEPENDENT_REVIEW",
        "comptroller_approved": False,
        "exception_effective": False,
        "installation_authorized": False,
    }
    digest = canonical_hash(payload)

    evidence = ProjectEvidence.objects.create(
        msr=msr,
        kind=REQUEST_KIND,
        created_by=requester,
        data=payload,
        digest=digest,
    )
    audit(
        requester,
        "equipment.serial_exception_requested",
        project.pk,
        {
            "evidence_id": str(evidence.pk),
            "msr_id": str(msr.pk),
            "unit_id": unit_id,
            "digest": digest,
            "exception_effective": False,
        },
    )
    return evidence

DECISION_KIND = "SERIAL_EXCEPTION_DECISION"


@transaction.atomic
def decide_serial_exception(
    *, actor, request_id, approve, decision_reason,
    genuinely_not_applicable
):
    """Record a synthetic decision, never make an exception effective."""
    if settings.ENVIRONMENT != "development" or not settings.DEBUG:
        raise ValidationError("Serial exception decisions are development-only.")

    if actor is None or not getattr(actor, "pk", None):
        raise PermissionDenied("An authenticated Comptroller is required.")

    reviewer = User.objects.get(pk=actor.pk)
    if not reviewer.is_active or reviewer.role != Role.COMPTROLLER:
        raise PermissionDenied("Only an active Comptroller may decide.")

    if type(approve) is not bool:
        raise ValidationError("An explicit approval or rejection is required.")
    if type(decision_reason) is not str or not 15 <= len(decision_reason.strip()) <= 2000:
        raise ValidationError("A specific decision reason is required.")
    if approve and genuinely_not_applicable is not True:
        raise ValidationError("Serial non-applicability must be confirmed.")
    if type(genuinely_not_applicable) is not bool:
        raise ValidationError("Explicit applicability review is required.")

    reference = ProjectEvidence.objects.get(pk=request_id)
    if reference.kind != REQUEST_KIND:
        raise ValidationError("This is not a serial exception request.")

    project = Project.objects.select_for_update().get(pk=reference.msr.project_id)
    request = ProjectEvidence.objects.get(pk=reference.pk)
    msr = project.current_approved

    if (
        project.state == "CANCELLED"
        or msr is None
        or msr.status != "APPROVED"
        or msr.pk != request.msr_id
        or msr.project_id != project.pk
    ):
        raise ValidationError("The request is not for the current approved MSR.")

    data = request.data
    if (
        request.digest != canonical_hash(data)
        or data.get("status") != "REQUESTED"
        or data.get("msr_id") != str(msr.pk)
        or data.get("msr_version") != msr.number
        or data.get("snapshot_sha256") != canonical_hash(msr.snapshot)
        or data.get("requester_id") != str(request.created_by_id)
        or data.get("exception_effective") is not False
        or data.get("comptroller_approved") is not False
    ):
        raise ValidationError("Request evidence failed integrity checks.")

    if request.created_by_id == reviewer.pk:
        raise PermissionDenied("A requester cannot decide their own request.")

    try:
        valid_units = {
            item.unit_id for item in physical_units_from_snapshot(
                msr_id=str(msr.pk), snapshot=msr.snapshot
            )
        }
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc

    unit_id = data.get("unit_id")
    if unit_id not in valid_units:
        raise ValidationError("The request references an invalid physical unit.")

    for existing in ProjectEvidence.objects.filter(
        msr=msr, kind=DECISION_KIND
    ):
        if existing.data.get("request_id") == str(request.pk):
            raise ValidationError("This request has already been decided.")

    payload = {
        "status": "APPROVED" if approve else "REJECTED",
        "request_id": str(request.pk),
        "request_digest": request.digest,
        "msr_id": str(msr.pk),
        "msr_version": msr.number,
        "snapshot_sha256": canonical_hash(msr.snapshot),
        "unit_id": unit_id,
        "requester_id": str(request.created_by_id),
        "comptroller_id": str(reviewer.pk),
        "decision_reason": decision_reason.strip(),
        "genuinely_not_applicable": genuinely_not_applicable,
        "decided_at": timezone.now().isoformat(),
        "comptroller_approved": approve,
        "exception_effective": False,
        "installation_authorized": False,
    }

    digest = canonical_hash(payload)
    evidence = ProjectEvidence.objects.create(
        msr=msr,
        kind=DECISION_KIND,
        created_by=reviewer,
        data=payload,
        digest=digest,
    )
    audit(
        reviewer,
        "equipment.serial_exception_decided",
        project.pk,
        {
            "evidence_id": str(evidence.pk),
            "request_id": str(request.pk),
            "msr_id": str(msr.pk),
            "unit_id": unit_id,
            "approved": approve,
            "exception_effective": False,
            "digest": digest,
        },
    )
    return evidence

REVOCATION_KIND = "SERIAL_EXCEPTION_REVOCATION"


@transaction.atomic
def revoke_serial_exception(*, actor, decision_id, reason):
    """Append an audited synthetic revocation; never mutate the approval."""
    if settings.ENVIRONMENT != "development" or not settings.DEBUG:
        raise ValidationError("Serial exception revocation is development-only.")

    if actor is None or not getattr(actor, "pk", None):
        raise PermissionDenied("An active Comptroller is required.")

    reviewer = User.objects.get(pk=actor.pk)
    if not reviewer.is_active or reviewer.role != Role.COMPTROLLER:
        raise PermissionDenied("Only an active Comptroller may revoke.")

    if type(reason) is not str or not 15 <= len(reason.strip()) <= 2000:
        raise ValidationError("A specific written revocation reason is required.")

    decision = ProjectEvidence.objects.get(pk=decision_id)
    if decision.kind != DECISION_KIND:
        raise ValidationError("Only a serial exception decision can be revoked.")

    project = Project.objects.select_for_update().get(pk=decision.msr.project_id)
    msr = project.current_approved
    if (
        project.state == "CANCELLED"
        or msr is None
        or msr.status != "APPROVED"
        or msr.pk != decision.msr_id
        or msr.project_id != project.pk
    ):
        raise ValidationError("The decision must belong to the current approved MSR.")

    data = decision.data
    if (
        decision.digest != canonical_hash(data)
        or data.get("status") != "APPROVED"
        or data.get("comptroller_approved") is not True
        or data.get("genuinely_not_applicable") is not True
        or data.get("msr_id") != str(msr.pk)
        or data.get("msr_version") != msr.number
        or data.get("snapshot_sha256") != canonical_hash(msr.snapshot)
        or data.get("comptroller_id") != str(decision.created_by_id)
        or data.get("exception_effective") is not False
        or data.get("installation_authorized") is not False
    ):
        raise ValidationError("Approval integrity verification failed.")

    request_id = data.get("request_id")
    try:
        request = ProjectEvidence.objects.get(
            pk=request_id, msr=msr, kind=REQUEST_KIND
        )
    except (ProjectEvidence.DoesNotExist, ValueError, TypeError):
        raise ValidationError("Original request evidence is missing.") from None

    if (
        request.digest != canonical_hash(request.data)
        or data.get("request_digest") != request.digest
        or request.data.get("status") != "REQUESTED"
        or request.data.get("unit_id") != data.get("unit_id")
        or request.data.get("msr_id") != str(msr.pk)
        or request.data.get("snapshot_sha256") != canonical_hash(msr.snapshot)
        or request.data.get("requester_id") != str(request.created_by_id)
        or request.created_by_id == decision.created_by_id
    ):
        raise ValidationError("Original request and decision do not match.")

    try:
        valid_units = {
            unit.unit_id for unit in physical_units_from_snapshot(
                msr_id=str(msr.pk), snapshot=msr.snapshot
            )
        }
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc

    if data.get("unit_id") not in valid_units:
        raise ValidationError("Decision references an unknown physical unit.")

    existing = ProjectEvidence.objects.filter(msr=msr, kind=REVOCATION_KIND)
    if any(
        item.data.get("decision_id") == str(decision.pk)
        for item in existing
    ):
        raise ValidationError("The approval has already been revoked.")

    payload = {
        "status": "REVOKED",
        "decision_id": str(decision.pk),
        "decision_digest": decision.digest,
        "request_id": str(request.pk),
        "msr_id": str(msr.pk),
        "msr_version": msr.number,
        "snapshot_sha256": canonical_hash(msr.snapshot),
        "unit_id": data["unit_id"],
        "revoked_by": str(reviewer.pk),
        "reason": reason.strip(),
        "revoked_at": timezone.now().isoformat(),
        "exception_effective": False,
        "installation_authorized": False,
    }

    digest = canonical_hash(payload)
    revocation = ProjectEvidence.objects.create(
        msr=msr, kind=REVOCATION_KIND,
        created_by=reviewer, data=payload, digest=digest,
    )
    audit(
        reviewer,
        "equipment.serial_exception_revoked",
        project.pk,
        {
            "evidence_id": str(revocation.pk),
            "decision_id": str(decision.pk),
            "msr_id": str(msr.pk),
            "unit_id": data["unit_id"],
            "digest": digest,
            "exception_effective": False,
        },
    )
    return revocation