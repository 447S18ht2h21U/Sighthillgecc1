"""Development-only, immutable UNVERIFIED inspection envelope association.

A recorded account/envelope ID does NOT prove DocuSign provenance.
This module cannot send envelopes, authenticate signatures, or authorize
project completion. Its JSON evidence has no new database migration.
Concurrent uniqueness must be enforced before live activation.
"""
import os
from uuid import UUID

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from rest_framework.exceptions import PermissionDenied

from . import docusign
from .documents import canonical_hash
from .models import (
    Project,
    ProjectEvidence,
    InstallationInspectionEvidence4969,
    User,
    Role,
)
from .services import audit
from .installation_evidence_retention_4969 import (
    verify_retained_inspection_bytes,
)
from .installation_provider_intake_bridge_4975 import (
    OfflineInspectionReadbackBridge4975,
)

KIND = "IM_BIND_UNVERIFIED_4976"


def _uuid(value):
    if type(value) is not str:
        raise ValidationError("Canonical provider UUID required.")
    try:
        if str(UUID(value)) != value:
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise ValidationError(
            "Canonical provider UUID required."
        ) from None
    return value


def bind_unverified_inspection_envelope(
    *, actor, project_id, inspection_evidence_id, bridge
):
    if (
        settings.ENVIRONMENT != "development"
        or settings.DEBUG is not True
        or os.environ.get("GECC_IM_BINDING_TEST_ENABLED") != "1"
    ):
        raise PermissionDenied("Inspection envelope binding disabled.")

    reviewer = User.objects.filter(
        pk=getattr(actor, "pk", None), is_active=True
    ).first()
    if reviewer is None or reviewer.role not in (
        Role.CEO, Role.COMPTROLLER
    ):
        raise PermissionDenied("Authorized reviewer required.")

    if type(bridge) is not OfflineInspectionReadbackBridge4975:
        raise ValidationError("Unverified readback bridge required.")

    account = _uuid(bridge.account_id)
    envelope_id = _uuid(bridge.envelope_id)
    configuration = docusign.configuration()
    if (
        type(configuration) is not dict
        or configuration.get("blockers")
        or configuration.get("account_id") != account
        or docusign.BASE_URI != "https://demo.docusign.net"
    ):
        raise PermissionDenied("Configured sandbox account mismatch.")

    if (
        bridge.status != "READBACK_LINKED_PROVENANCE_UNVERIFIED"
        or bridge.provider_origin_authenticated is not False
        or bridge.envelope_binding_authenticated is not False
        or bridge.signature_verified is not False
        or bridge.evidence_retained is not False
        or bridge.completion_authorized is not False
    ):
        raise ValidationError("Bridge cannot assert provider authority.")

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
        or bridge.project_id != str(project.pk)
        or bridge.approved_msr_id != str(msr.pk)
    ):
        raise ValidationError("Current approved MSR mismatch.")

    retained = InstallationInspectionEvidence4969.objects.filter(
        pk=inspection_evidence_id, msr=msr
    ).first()
    if retained is None:
        raise ValidationError("Retained inspection record missing.")

    integrity = verify_retained_inspection_bytes(retained)
    metadata = retained.source_data
    if (
        integrity.get("integrity_verified") is not True
        or integrity.get("provider_authenticated") is not False
        or integrity.get("completion_authorized") is not False
        or type(metadata) is not dict
        or metadata.get("state") != "UNVERIFIED_RETAINED"
        or metadata.get("provider_authenticated") is not False
        or metadata.get("completion_authorized") is not False
        or metadata.get("project_id") != str(project.pk)
        or metadata.get("msr_id") != str(msr.pk)
        or retained.purported_envelope_id != envelope_id
        or retained.bundle_digest != bridge.evidence_bundle_sha256
        or bridge.evidence_bundle.bundle_sha256 != retained.bundle_digest
        or bridge.evidence_bundle.purported_envelope_id != envelope_id
        or bridge.evidence_bundle.signed_pdf_sha256
        != retained.signed_pdf_sha256
        or bridge.evidence_bundle.certificate_sha256
        != retained.certificate_sha256
    ):
        raise ValidationError("Retained evidence/bridge mismatch.")

    payload = {
        "schema": "GECC_UNVERIFIED_IM_ENVELOPE_BINDING_4976_V1",
        "state": "ENVELOPE_ASSOCIATION_UNVERIFIED",
        "project_id": str(project.pk),
        "msr_id": str(msr.pk),
        "msr_version": str(msr.number),
        "retained_inspection_id": str(retained.pk),
        "retained_bundle_sha256": retained.bundle_digest,
        "signed_pdf_sha256": retained.signed_pdf_sha256,
        "certificate_sha256": retained.certificate_sha256,
        "provider_account_id": account,
        "provider_envelope_id": envelope_id,
        "provider_authenticated": False,
        "signer_verified": False,
        "signed_date_verified": False,
        "completion_authorized": False,
    }
    digest = canonical_hash(payload)

    with transaction.atomic():
        # This is a test-only immutable association. The database does
        # not yet have a uniqueness constraint for concurrent writers.
        prior = list(
            ProjectEvidence.objects.select_for_update().filter(
                msr=msr,
                kind=KIND,
                data__provider_envelope_id=envelope_id,
            )
        )
        if prior:
            if (
                len(prior) != 1
                or prior[0].digest != digest
                or canonical_hash(prior[0].data) != digest
            ):
                raise ValidationError("Conflicting envelope association.")
            return prior[0], False

        record = ProjectEvidence.objects.create(
            msr=msr,
            kind=KIND,
            created_by=reviewer,
            data=payload,
            digest=digest,
        )
        audit(
            reviewer,
            "installation.inspection_envelope_associated_unverified",
            project.pk,
            {
                "binding_id": str(record.pk),
                "inspection_evidence_id": str(retained.pk),
                "state": "ENVELOPE_ASSOCIATION_UNVERIFIED",
            },
        )
        return record, True
