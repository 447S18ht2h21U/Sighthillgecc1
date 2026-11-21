"""Read-only inspection draft authorization status.

Development only. This does not grant signing authority, create a
provider envelope, or alter any project completion requirements.
"""
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError

from core.models import Project, ProjectEvidence, User
from core.installation_source_artifact_4826 import (
    verify_retained_installation_source,
)
from core.installation_attestation_manifest_4941 import verify_attestation_preparation
from core.installation_provider_oauth_4979 import Role, canonical_hash
from core.installation_draft_authorization_5179 import KIND


ALLOWED = (Role.CEO, Role.SALES_MANAGER, Role.COMPTROLLER)

FALSE_FLAGS = (
    "provider_draft_created",
    "provider_request_authorized",
    "send_authorized",
    "provider_signature_verified",
    "inspection_findings_verified",
    "receipt_issuance_authorized",
    "project_completion_authorized",
)


def _viewer(actor):
    if (
        settings.ENVIRONMENT != "development"
        or settings.DEBUG is not True
        or actor is None
        or not getattr(actor, "pk", None)
        or getattr(actor, "is_active", False) is not True
        or getattr(actor, "role", None) not in ALLOWED
    ):
        raise PermissionDenied("Inspection workflow status unavailable.")

    current = User.objects.filter(
        pk=actor.pk, is_active=True
    ).first()

    if current is None or current.role not in ALLOWED:
        raise PermissionDenied("Current authorized role required.")

    if current.role != actor.role:
        raise PermissionDenied("User role changed; sign in again.")

    return current



def _readiness(project, msr):
    """Read the independent source-evidence result, never create evidence."""
    try:
        verified = verify_attestation_preparation(project_id=project.pk)
    except (PermissionDenied, ValidationError):
        return False

    return (
        str(getattr(verified, "project_id", "")) == str(project.pk)
        and str(getattr(verified, "msr_id", "")) == str(msr.pk)
        and getattr(verified, "record_integrity_verified", False) is True
        and getattr(verified, "current_source_binding_verified", False)
            is True
        and getattr(verified, "provider_envelope_verified", None)
            is False
        and getattr(verified, "source_artifact_authenticated", None)
            is False
        and getattr(verified, "trusted_installation_evidence", None)
            is False
        and getattr(verified, "final_receipt_issuance_authorized", None)
            is False
        and getattr(verified, "customer_delivery_verified", None)
            is False
        and getattr(verified, "completion_authorized", None)
            is False
    )


def status(*, actor, project_id):
    _viewer(actor)

    project = Project.objects.filter(pk=project_id).first()

    if project is None:
        raise ValidationError("Project not found.")

    result = {
        "project_id": str(project.pk),
        "authorization_state": "NOT_AUTHORIZED",
        "preparation_ready": False,
        "preparation_state": "SOURCE_EVIDENCE_NOT_VERIFIED",
        "source_stage": "SOURCE_NOT_VERIFIED",
        "intent_id": None,
        "provider_draft_created": False,
        "provider_request_authorized": False,
        "send_authorized": False,
        "provider_signature_verified": False,
        "project_completion_authorized": False,
    }

    if project.state == "CANCELLED":
        result["authorization_state"] = "PROJECT_CANCELLED"
        return result

    msr = project.current_approved

    if (
        msr is None
        or msr.status != "APPROVED"
        or msr.project_id != project.pk
    ):
        result["authorization_state"] = "APPROVED_MSR_REQUIRED"
        return result

    # A retained source remains unauthenticated until provider verification.
    # This read-only check never creates or repairs evidence.
    try:
        source_verified = (
            verify_retained_installation_source(project) is True
        )
    except (ValueError, TypeError, ValidationError):
        source_verified = False

    ready = _readiness(project, msr)
    result["source_stage"] = (
        "PREPARATION_VERIFIED" if ready else
        "SOURCE_VERIFIED_PREPARATION_PENDING" if source_verified else
        "SOURCE_NOT_VERIFIED"
    )
    result["preparation_ready"] = ready
    result["preparation_state"] = (
        "VERIFIED_FOR_OFFLINE_PREPARATION"
        if ready else "SOURCE_EVIDENCE_NOT_VERIFIED"
    )

    records = ProjectEvidence.objects.filter(
        msr=msr, kind=KIND
    )

    count = records.count()

    if count == 0:
        return result

    if count != 1:
        result["authorization_state"] = "AUTHORIZATION_CONFLICT"
        return result

    intent = records.first()

    if intent is None or type(intent.data) is not dict:
        result["authorization_state"] = "AUTHORIZATION_INVALID"
        return result

    data = intent.data

    expected = (
        intent.digest == canonical_hash(data)
        and data.get("schema")
            == "GECC_IM_SANDBOX_DRAFT_INTENT_5179_V1"
        and data.get("state") == "DRAFT_INTENT_RECORDED"
        and data.get("project_id") == str(project.pk)
        and data.get("msr_id") == str(msr.pk)
        and data.get("msr_version") == str(msr.number)
        and data.get("authorized_by_id")
            == str(intent.created_by_id)
        and all(data.get(key) is False for key in FALSE_FLAGS)
    )

    if not expected:
        result["authorization_state"] = "AUTHORIZATION_INVALID"
        return result

    approver = User.objects.filter(
        pk=intent.created_by_id, is_active=True
    ).first()

    if approver is None or approver.role not in (
        Role.CEO, Role.SALES_MANAGER
    ):
        result["authorization_state"] = "AUTHORIZER_INELIGIBLE"
        return result

    result["authorization_state"] = "DRAFT_INTENT_RECORDED"
    result["intent_id"] = str(intent.pk)
    return result