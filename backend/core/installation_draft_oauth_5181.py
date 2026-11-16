"""Controlled inspection-draft OAuth context, without provider creation.

The CEO or Sales Manager authorizes an exact offline package.
The Comptroller may authenticate the sandbox connection.
Neither action creates or sends an envelope in this phase.
"""
import os
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError

from core import docusign
from core.models import ProjectEvidence, User
from core.installation_provider_oauth_4979 import Role, audit, canonical_hash
from core.installation_draft_authorization_5179 import (
    KIND, _fingerprint,
)

OPERATION = "SANDBOX_IM_DRAFT_CONTEXT_5181"
FLAG = "GECC_IM_DRAFT_OAUTH_TEST_ENABLED"


def _gate(actor):
    if (
        settings.ENVIRONMENT != "development"
        or settings.DEBUG is not True
        or os.environ.get(FLAG) != "1"
    ):
        raise PermissionDenied("Inspection draft OAuth integration disabled.")

    if (
        actor is None
        or not getattr(actor, "pk", None)
        or getattr(actor, "is_active", False) is not True
        or getattr(actor, "role", None) != Role.COMPTROLLER
    ):
        raise PermissionDenied("Active Comptroller required.")

    reviewer = User.objects.filter(
        pk=actor.pk, is_active=True, role=Role.COMPTROLLER
    ).first()

    if reviewer is None:
        raise PermissionDenied("Current Comptroller identity required.")

    return reviewer


def _authorization(intent_id, envelope):
    evidence = ProjectEvidence.objects.select_related(
        "msr__project"
    ).filter(pk=intent_id, kind=KIND).first()

    if evidence is None or type(evidence.data) is not dict:
        raise ValidationError("Inspection draft intent not found.")

    data = evidence.data
    msr = evidence.msr
    project = msr.project

    if (
        evidence.digest != canonical_hash(data)
        or data.get("schema") != "GECC_IM_SANDBOX_DRAFT_INTENT_5179_V1"
        or data.get("state") != "DRAFT_INTENT_RECORDED"
        or project.state == "CANCELLED"
        or project.current_approved_id != msr.pk
        or msr.status != "APPROVED"
        or data.get("project_id") != str(project.pk)
        or data.get("msr_id") != str(msr.pk)
        or data.get("msr_version") != str(msr.number)
        or data.get("authorized_by_id") != str(evidence.created_by_id)
        or data.get("draft_payload_sha256") != _fingerprint(envelope)
        or envelope.project_id != str(project.pk)
        or envelope.approved_msr_id != str(msr.pk)
        or envelope.approved_msr_version != str(msr.number)
    ):
        raise ValidationError("Inspection authorization binding invalid.")

    for key in (
        "provider_draft_created",
        "provider_request_authorized",
        "send_authorized",
        "provider_signature_verified",
        "inspection_findings_verified",
        "receipt_issuance_authorized",
        "project_completion_authorized",
    ):
        if data.get(key) is not False:
            raise ValidationError("Inspection authorization trust mismatch.")

    approver = User.objects.filter(
        pk=evidence.created_by_id, is_active=True
    ).first()

    if approver is None or approver.role not in (
        Role.CEO, Role.SALES_MANAGER
    ):
        raise PermissionDenied("Original draft authorizer no longer eligible.")

    return evidence, project


def begin(*, actor, session_key, intent_id, envelope, confirmed):
    reviewer = _gate(actor)

    if confirmed is not True:
        raise ValidationError("Explicit sandbox context confirmation required.")

    if not isinstance(session_key, str) or not session_key:
        raise PermissionDenied("Authenticated browser session required.")

    intent, project = _authorization(intent_id, envelope)

    result = docusign.begin(
        reviewer,
        session_key,
        context={
            "operation": OPERATION,
            "intent_id": str(intent.pk),
            "intent_digest": intent.digest,
            "project_id": str(project.pk),
            "draft_payload_sha256": intent.data["draft_payload_sha256"],
            "provider_request_authorized": False,
            "send_authorized": False,
        },
    )

    audit(
        reviewer,
        "installation.inspection_draft_oauth_started",
        project.pk,
        {
            "intent_id": str(intent.pk),
            "intent_digest": intent.digest,
            "provider_request_authorized": False,
            "send_authorized": False,
        },
    )

    return {
        **result,
        "operation": OPERATION,
        "provider_request_authorized": False,
        "send_authorized": False,
        "project_completion_authorized": False,
    }


def finish(actor, challenge, config, token):
    """Validate the callback context. Never use the token for provider I/O."""
    reviewer = _gate(actor)
    context = getattr(challenge, "context", None)

    if (
        type(context) is not dict
        or context.get("operation") != OPERATION
        or context.get("provider_request_authorized") is not False
        or context.get("send_authorized") is not False
        or getattr(challenge, "actor_id", None) != reviewer.pk
        or type(config) is not dict
        or config.get("blockers")
        or config.get("account_id") != docusign.configuration().get("account_id")
        or type(token) is not str
        or not token
    ):
        raise PermissionDenied("Inspection draft OAuth context invalid.")

    intent = ProjectEvidence.objects.filter(
        pk=context.get("intent_id"), kind=KIND
    ).first()

    if (
        intent is None
        or type(intent.data) is not dict
        or intent.digest != canonical_hash(intent.data)
        or context.get("intent_digest") != intent.digest
        or context.get("project_id") != intent.data.get("project_id")
        or context.get("draft_payload_sha256")
           != intent.data.get("draft_payload_sha256")
    ):
        raise PermissionDenied("Inspection draft authorization changed.")

    # The approval must still be valid at callback time. A legitimate
    # OAuth token cannot revive a cancelled project, superseded MSR,
    # inactive approver, or changed signing authority.
    msr = intent.msr
    project = msr.project

    if (
        project.state == "CANCELLED"
        or project.current_approved_id != msr.pk
        or msr.project_id != project.pk
        or msr.status != "APPROVED"
        or intent.created_by_id is None
        or intent.data.get("schema")
           != "GECC_IM_SANDBOX_DRAFT_INTENT_5179_V1"
        or intent.data.get("state") != "DRAFT_INTENT_RECORDED"
        or intent.data.get("project_id") != str(project.pk)
        or intent.data.get("msr_id") != str(msr.pk)
        or intent.data.get("msr_version") != str(msr.number)
        or intent.data.get("authorized_by_id")
           != str(intent.created_by_id)
    ):
        raise PermissionDenied("Inspection authorization is no longer current.")

    for field in (
        "provider_draft_created",
        "provider_request_authorized",
        "send_authorized",
        "provider_signature_verified",
        "inspection_findings_verified",
        "receipt_issuance_authorized",
        "project_completion_authorized",
    ):
        if intent.data.get(field) is not False:
            raise PermissionDenied("Inspection authorization safety flags changed.")

    approver = User.objects.filter(
        pk=intent.created_by_id, is_active=True
    ).first()

    if approver is None or approver.role not in (
        Role.CEO, Role.SALES_MANAGER
    ):
        raise PermissionDenied("Inspection authorizer is no longer eligible.")

    # No provider calls. No draft creation. No signing permissions.
    audit(
        reviewer,
        "installation.inspection_draft_oauth_context_checked",
        context["project_id"],
        {
            "intent_id": str(intent.pk),
            "intent_digest": intent.digest,
            "provider_request_authorized": False,
            "send_authorized": False,
        },
    )

    return {
        "status": "SANDBOX_IM_DRAFT_CONTEXT_CHECKED",
        "operation": OPERATION,
        "intent_id": str(intent.pk),
        "provider_draft_created": False,
        "provider_request_authorized": False,
        "send_authorized": False,
        "provider_signature_verified": False,
        "project_completion_authorized": False,
        "tokens_retained": False,
    }