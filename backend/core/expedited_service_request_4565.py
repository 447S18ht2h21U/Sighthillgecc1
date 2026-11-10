"""Development-only audited expedited request capture.

This is a claim, not verified customer consent, approval or start authority.
"""
from datetime import date

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from .documents import canonical_hash
from .installation_schedule_services import (
    _authorized_installation_actor, _require_project_access,
)
from .models import Project, ProjectEvidence
from .services import audit
from .rules import EASTERN

KIND = "EXPEDITED_SERVICE_REQUEST"


@transaction.atomic
def record_expedited_service_request(
    *, actor, project_id, proposed_date, reason, document_reference
):
    if settings.ENVIRONMENT != "development" or not settings.DEBUG:
        raise PermissionDenied("Expedited requests are not live-enabled.")

    manager, delegation = _authorized_installation_actor(actor)
    _require_project_access(manager, project_id)

    if type(proposed_date) is not date:
        raise ValidationError("A valid proposed installation date is required.")
    if proposed_date < timezone.now().astimezone(EASTERN).date():
        raise ValidationError("The proposed installation date is in the past.")

    if type(reason) is not str or not 15 <= len(reason.strip()) <= 2000:
        raise ValidationError("A specific documented reason is required.")
    if type(document_reference) is not str or not 5 <= len(document_reference.strip()) <= 250:
        raise ValidationError("A supporting document reference is required.")

    project = Project.objects.select_for_update().filter(pk=project_id).first()
    if project is None or project.state == "CANCELLED":
        raise ValidationError("An active project is required.")

    msr = project.current_approved
    if msr is None or msr.status != "APPROVED" or msr.project_id != project.pk:
        raise ValidationError("Current approved MSR is required.")

    if ProjectEvidence.objects.filter(msr=msr, kind=KIND).exists():
        raise ValidationError("An expedited request already exists for this MSR.")

    payload = {
        "status": "PENDING_INDEPENDENT_VERIFICATION",
        "project_id": str(project.pk),
        "msr_id": str(msr.pk),
        "msr_version": msr.number,
        "snapshot_sha256": canonical_hash(msr.snapshot),
        "proposed_date": proposed_date.isoformat(),
        "reason": reason.strip(),
        "document_reference_claim": document_reference.strip(),
        "requested_by": str(manager.pk),
        "requested_at": timezone.now().isoformat(),
        "customer_initials_verified": False,
        "document_signature_verified": False,
        "manager_approval_verified": False,
        "cancellation_protections_verified": False,
        "expedited_authorized": False,
        "installation_authorized": False,
    }

    digest = canonical_hash(payload)
    evidence = ProjectEvidence.objects.create(
        msr=msr, kind=KIND, created_by=manager,
        data=payload, digest=digest,
    )

    details = {
        "msr_id": str(msr.pk),
        "evidence_id": str(evidence.pk),
        "digest": digest,
        "expedited_authorized": False,
    }
    if delegation is not None:
        details["temporary_duty_authorization_id"] = str(delegation.pk)

    audit(manager, "installation.expedited_service_requested", project.pk, details)
    return evidence
