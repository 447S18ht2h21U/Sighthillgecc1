"""Read-only, offline inspection PDF verification.

No documents are saved, downloaded, transmitted, or marked signed.
Only a verified source and preparation record can reach the PDF builder.
"""
from django.core.exceptions import PermissionDenied, ValidationError

from core.models import Role
from core.installation_draft_status_5186 import status as inspect_status
from core.installation_docusign_contract_4959 import (
    build_unsigned_installation_docusign_contract,
)


def verify_unsigned_pdf(*, actor, project_id):
    if (
        actor is None
        or getattr(actor, "role", None)
        not in (Role.CEO, Role.SALES_MANAGER)
    ):
        raise PermissionDenied("CEO or Sales Manager required.")

    current = inspect_status(actor=actor, project_id=project_id)

    if (
        current.get("project_id") != str(project_id)
        or current.get("preparation_ready") is not True
        or current.get("source_stage") != "PREPARATION_VERIFIED"
        or current.get("authorization_state")
        not in ("NOT_AUTHORIZED", "DRAFT_INTENT_RECORDED")
        or any(
            current.get(field) is not False
            for field in (
                "provider_draft_created",
                "provider_request_authorized",
                "send_authorized",
                "provider_signature_verified",
                "project_completion_authorized",
            )
        )
    ):
        raise ValidationError(
            "Verified inspection source and draft preparation are required."
        )

    contract = build_unsigned_installation_docusign_contract(
        actor=actor,
        project_id=project_id,
    )

    fields = getattr(contract, "fields", ())
    expected_ids = tuple(
        f"inspection_{index}" for index in range(1, 6)
    ) + (
        "installation_manager_signature",
        "installation_manager_signed_date",
    )

    if (
        contract.project_id != str(project_id)
        or contract.approved_msr_id is None
        or contract.approved_msr_version is None
        or contract.source_evidence_id is None
        or contract.preparation_evidence_id is None
        or type(contract.unsigned_pdf_sha256) is not str
        or len(contract.unsigned_pdf_sha256) != 64
        or any(
            c not in "0123456789abcdef"
            for c in contract.unsigned_pdf_sha256
        )
        or tuple(field.field_id for field in fields) != expected_ids
        or any(
            field.required is not True
            or field.signer_role != "INSTALLATION_MANAGER"
            for field in fields
        )
        or contract.envelope_id is not None
        or contract.provider_signature_verified is not False
        or contract.inspection_findings_verified is not False
        or contract.trusted_installation_evidence is not False
        or contract.receipt_issuance_authorized is not False
        or contract.project_completion_authorized is not False
    ):
        raise ValidationError("Unsigned inspection document failed checks.")

    return {
        "project_id": str(project_id),
        "status": "UNSIGNED_PDF_VERIFIED_OFFLINE",
        "unsigned_pdf_sha256": contract.unsigned_pdf_sha256,
        "required_inspection_findings": 5,
        "required_signature_fields": 2,
        "read_only": True,
        "document_saved": False,
        "provider_envelope_created": False,
        "document_sent": False,
        "provider_signature_verified": False,
        "receipt_issuance_authorized": False,
        "project_completion_authorized": False,
    }
