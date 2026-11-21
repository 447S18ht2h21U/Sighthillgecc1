"""Isolated, read-only inspection draft handoff verification.

No API route, provider I/O, envelope creation, or database mutation.
"""
import os
import re

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection

from core.models import Project, ProjectEvidence, User, Role
from core.installation_draft_authorization_5179 import (
    KIND, _fingerprint,
)
from core.installation_draft_browser_5185 import assemble
from core.installation_provider_oauth_4979 import canonical_hash


_HEX = re.compile(r"^[0-9a-f]{64}$")
_FLAG = "GECC_IM_DRAFT_AUTHORIZATION_TEST_ENABLED"


def _isolated_gate(actor):
    if (
        settings.ENVIRONMENT != "development"
        or settings.DEBUG is not True
        or os.environ.get(_FLAG) != "1"
        or connection.vendor != "sqlite"
        or not (
            connection.settings_dict.get("NAME") == ":memory:"
            or (
                type(connection.settings_dict.get("NAME")) is str
                and connection.settings_dict["NAME"].startswith(
                    "file:memorydb_"
                )
                and connection.settings_dict["NAME"].endswith(
                    "?mode=memory&cache=shared"
                )
            )
        )
    ):
        raise PermissionDenied(
            "Inspection draft handoff requires isolated in-memory testing."
        )

    if (
        actor is None
        or getattr(actor, "pk", None) is None
        or getattr(actor, "is_active", False) is not True
        or getattr(actor, "role", None)
        not in (Role.CEO, Role.SALES_MANAGER)
    ):
        raise PermissionDenied("CEO or Sales Manager required.")

    current = User.objects.filter(
        pk=actor.pk, is_active=True
    ).first()

    if (
        current is None
        or current.role != actor.role
        or current.role not in (Role.CEO, Role.SALES_MANAGER)
    ):
        raise PermissionDenied("Current authorized role required.")


def verify_handoff(*, actor, project_id):
    """Rebuild and match the exact authorized offline package."""
    _isolated_gate(actor)

    project = Project.objects.select_related(
        "current_approved"
    ).filter(pk=project_id).first()

    if project is None or project.state == "CANCELLED":
        raise ValidationError("Active project required.")

    msr = project.current_approved
    if (
        msr is None
        or msr.status != "APPROVED"
        or msr.project_id != project.pk
        or project.current_approved_id != msr.pk
    ):
        raise ValidationError("Current approved MSR required.")

    records = list(
        ProjectEvidence.objects.filter(msr=msr, kind=KIND)
    )
    if len(records) != 1:
        raise ValidationError(
            "Exactly one inspection draft authorization required."
        )

    record = records[0]
    data = record.data

    if (
        type(data) is not dict
        or record.msr_id != msr.pk
        or record.digest != canonical_hash(data)
        or data.get("schema")
        != "GECC_IM_SANDBOX_DRAFT_INTENT_5179_V1"
        or data.get("state") != "DRAFT_INTENT_RECORDED"
        or data.get("project_id") != str(project.pk)
        or data.get("msr_id") != str(msr.pk)
        or data.get("msr_version") != str(msr.number)
        or data.get("authorized_by_id")
        != str(record.created_by_id)
    ):
        raise ValidationError(
            "Inspection draft authorization integrity failed."
        )

    authorizer = User.objects.filter(
        pk=record.created_by_id, is_active=True
    ).first()
    if (
        authorizer is None
        or authorizer.role not in (Role.CEO, Role.SALES_MANAGER)
    ):
        raise ValidationError(
            "Original draft authorizer is no longer eligible."
        )

    flags = (
        "provider_draft_created",
        "provider_request_authorized",
        "send_authorized",
        "provider_signature_verified",
        "inspection_findings_verified",
        "receipt_issuance_authorized",
        "project_completion_authorized",
    )
    if any(data.get(name) is not False for name in flags):
        raise ValidationError(
            "Unexpected signing or completion authorization."
        )

    recorded_hash = data.get("draft_payload_sha256")
    if (
        type(recorded_hash) is not str
        or _HEX.fullmatch(recorded_hash) is None
    ):
        raise ValidationError("Recorded draft fingerprint invalid.")

    envelope = assemble(actor=actor, project_id=project_id)
    generated_hash = _fingerprint(envelope)

    if (
        generated_hash != recorded_hash
        or envelope.project_id != str(project.pk)
        or envelope.approved_msr_id != str(msr.pk)
        or envelope.approved_msr_version != str(msr.number)
        or envelope.envelope_id is not None
        or envelope.state != "LOCAL_DRAFT_NOT_SUBMITTED"
        or envelope.provider_signed is not False
        or envelope.completion_authorized is not False
    ):
        raise ValidationError(
            "Current unsigned inspection draft differs from authorization."
        )

    return {
        "project_id": str(project.pk),
        "authorization_id": str(record.pk),
        "state": "OFFLINE_DRAFT_HANDOFF_MATCHED",
        "draft_payload_sha256": recorded_hash,
        "read_only": True,
        "provider_request_authorized": False,
        "provider_envelope_created": False,
        "send_authorized": False,
        "provider_signature_verified": False,
        "receipt_issuance_authorized": False,
        "project_completion_authorized": False,
    }
