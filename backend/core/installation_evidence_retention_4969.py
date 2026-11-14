"""Development-only immutable retention of UNVERIFIED inspection PDFs.

No claim of provider authentication or completed signing.
No envelope creation, sending, or installation-completion authority.
"""
from hashlib import sha256
import json
import os
import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from rest_framework.exceptions import PermissionDenied

from .models import (
    Project,
    User,
    Role,
    InstallationInspectionEvidence4969,
)
from .installation_docusign_evidence_intake_4966 import (
    UnverifiedInspectionEvidenceBundle,
)
from .services import audit


_HEX = re.compile(r"^[0-9a-f]{64}$")


def _digest(value):
    return sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True
    ).encode("utf-8")).hexdigest()


def _bundle_material(bundle):
    return {
        "schema": "GECC_UNVERIFIED_IM_EVIDENCE_INTAKE_4966_V1",
        "project_id": bundle.project_id,
        "msr_id": bundle.approved_msr_id,
        "msr_version": bundle.approved_msr_version,
        "signer_user_id": bundle.signer_user_id,
        "purported_envelope_id": bundle.purported_envelope_id,
        "envelope_package_sha256": bundle.envelope_package_sha256,
        "observation_sha256": bundle.response_observation_sha256,
        "signed_pdf_sha256": bundle.signed_pdf_sha256,
        "certificate_sha256": bundle.certificate_sha256,
        "inspection_findings": bundle.inspection_findings,
        "negative_inspection_ids": bundle.negative_inspection_ids,
    }


def retain_unverified_inspection_evidence(*, actor, project_id, bundle):
    if (
        settings.ENVIRONMENT != "development"
        or settings.DEBUG is not True
        or os.environ.get("GECC_IM_EVIDENCE_RETENTION_TEST_ENABLED") != "1"
    ):
        raise PermissionDenied("Inspection retention disabled.")

    if actor is None or not getattr(actor, "pk", None):
        raise PermissionDenied("Authenticated reviewer required.")

    reviewer = User.objects.filter(
        pk=actor.pk, is_active=True
    ).first()
    if reviewer is None or reviewer.role not in (
        Role.CEO, Role.COMPTROLLER
    ):
        raise PermissionDenied("Authorized reviewer required.")

    if type(bundle) is not UnverifiedInspectionEvidenceBundle:
        raise ValidationError("Unverified evidence bundle required.")

    forbidden = (
        bundle.authenticated_provider_readback,
        bundle.envelope_binding_verified,
        bundle.signer_identity_verified,
        bundle.provider_signature_verified,
        bundle.provider_date_verified,
        bundle.provider_certificate_verified,
        bundle.stored_in_durable_evidence,
        bundle.corrective_actions_created,
        bundle.receipt_issuance_authorized,
        bundle.completion_authorized,
    )
    if (
        bundle.status != "EVIDENCE_INTAKE_UNAUTHENTICATED"
        or any(value is not False for value in forbidden)
    ):
        raise ValidationError("Provider authority cannot be inferred.")

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
        or bundle.project_id != str(project.pk)
        or bundle.approved_msr_id != str(msr.pk)
        or bundle.approved_msr_version != str(msr.number)
    ):
        raise ValidationError("Approved project/MSR binding failed.")

    manager = User.objects.filter(
        pk=bundle.signer_user_id,
        is_active=True,
        role=Role.INSTALLATION_MANAGER,
    ).first()
    if manager is None:
        raise ValidationError("Intended Installation Manager not found.")

    if (
        type(bundle.purported_envelope_id) is not str
        or not 1 <= len(bundle.purported_envelope_id) <= 128
        or bundle.purported_envelope_id.strip()
        != bundle.purported_envelope_id
        or type(bundle.signed_pdf) is not bytes
        or type(bundle.certificate_pdf) is not bytes
        or not 100 <= len(bundle.signed_pdf) <= 5_000_000
        or not 100 <= len(bundle.certificate_pdf) <= 5_000_000
        or not bundle.signed_pdf.startswith(b"%PDF-")
        or not bundle.certificate_pdf.startswith(b"%PDF-")
        or not bundle.signed_pdf.rstrip().endswith(b"%%EOF")
        or not bundle.certificate_pdf.rstrip().endswith(b"%%EOF")
        or sha256(bundle.signed_pdf).hexdigest()
        != bundle.signed_pdf_sha256
        or sha256(bundle.certificate_pdf).hexdigest()
        != bundle.certificate_sha256
        or not _HEX.fullmatch(bundle.bundle_sha256)
        or bundle.bundle_sha256 != _digest(_bundle_material(bundle))
    ):
        raise ValidationError("Inspection evidence integrity failed.")

    answers = bundle.inspection_findings
    if (
        type(answers) is not tuple
        or len(answers) != 5
        or tuple(key for key, _ in answers)
        != tuple(f"inspection_{i}" for i in range(1, 6))
        or any(value not in ("YES", "NO") for _, value in answers)
        or bundle.negative_inspection_ids != tuple(
            key for key, value in answers if value == "NO"
        )
    ):
        raise ValidationError("Inspection findings inconsistent.")

    metadata = {
        "state": "UNVERIFIED_RETAINED",
        "provider_authenticated": False,
        "signatures_verified": False,
        "dates_verified": False,
        "completion_authorized": False,
        "project_id": str(project.pk),
        "msr_id": str(msr.pk),
        "msr_version": str(msr.number),
        "intended_manager_id": str(manager.pk),
        "envelope_package_sha256": bundle.envelope_package_sha256,
        "response_observation_sha256": bundle.response_observation_sha256,
        "inspection_findings": list(answers),
        "negative_inspection_ids": list(bundle.negative_inspection_ids),
        "bundle_digest": bundle.bundle_sha256,
        "signed_pdf_sha256": bundle.signed_pdf_sha256,
        "certificate_sha256": bundle.certificate_sha256,
    }

    with transaction.atomic():
        existing = list(
            InstallationInspectionEvidence4969.objects
            .select_for_update()
            .filter(
                msr=msr,
                purported_envelope_id=bundle.purported_envelope_id,
            )
        )
        if existing:
            record = existing[0]
            if (
                len(existing) != 1
                or record.bundle_digest != bundle.bundle_sha256
                or record.source_digest != _digest(record.source_data)
                or record.source_digest != _digest(metadata)
                or _digest(record.source_data) != _digest(metadata)
                or record.signed_pdf_sha256 != bundle.signed_pdf_sha256
                or record.certificate_sha256 != bundle.certificate_sha256
                or bytes(record.signed_pdf) != bundle.signed_pdf
                or bytes(record.certificate_pdf) != bundle.certificate_pdf
            ):
                raise ValidationError(
                    "Conflicting inspection envelope evidence."
                )
            return record, False

        record = InstallationInspectionEvidence4969.objects.create(
            msr=msr,
            created_by=reviewer,
            purported_envelope_id=bundle.purported_envelope_id,
            bundle_digest=bundle.bundle_sha256,
            source_digest=_digest(metadata),
            source_data=metadata,
            signed_pdf=bundle.signed_pdf,
            signed_pdf_sha256=bundle.signed_pdf_sha256,
            certificate_pdf=bundle.certificate_pdf,
            certificate_sha256=bundle.certificate_sha256,
        )
        audit(
            reviewer,
            "installation.inspection_unverified_evidence_retained",
            project.pk,
            {
                "retention_id": str(record.pk),
                "msr_id": str(msr.pk),
                "bundle_sha256": bundle.bundle_sha256,
                "state": "UNVERIFIED_RETAINED",
            },
        )
        return record, True


def verify_retained_inspection_bytes(record):
    """Read-back integrity only; cannot authenticate DocuSign origin."""
    if record.source_digest != _digest(record.source_data):
        raise ValidationError("Stored metadata digest mismatch.")
    if record.bundle_digest != record.source_data.get("bundle_digest"):
        raise ValidationError("Stored bundle binding mismatch.")
    if (
        sha256(bytes(record.signed_pdf)).hexdigest()
        != record.signed_pdf_sha256
        or sha256(bytes(record.certificate_pdf)).hexdigest()
        != record.certificate_sha256
        or record.source_data.get("signed_pdf_sha256")
        != record.signed_pdf_sha256
        or record.source_data.get("certificate_sha256")
        != record.certificate_sha256
    ):
        raise ValidationError("Retained document fingerprint mismatch.")
    return {
        "retention_id": str(record.pk),
        "integrity_verified": True,
        "provider_authenticated": False,
        "signatures_verified": False,
        "completion_authorized": False,
    }
