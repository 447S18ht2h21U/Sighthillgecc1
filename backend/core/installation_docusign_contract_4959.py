"""Offline Installation Manager DocuSign signing contract.

Specifies required provider fields and project/document bindings.
Does NOT install tabs, create/send envelopes, authenticate a signer,
or grant installation, Receipt, or completion authority.

Customer Receipt survey answers are excluded from this signing contract.
"""
from dataclasses import dataclass
from hashlib import sha256
import json
import re

from django.conf import settings
from django.core.exceptions import ValidationError
from rest_framework.exceptions import PermissionDenied

from .installation_attestation_manifest_4941 import (
    build_installation_signing_manifest,
)
from .installation_inspection_form_4945 import (
    INSPECTION_IDS,
    INSPECTION_ITEMS,
    render_unsigned_inspection_form,
)
from .installation_attestation_pdf_4942 import (
    SIGNATURE_ANCHOR,
    DATE_ANCHOR,
)


_HEX64 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class RequiredSigningField:
    field_id: str
    field_type: str
    required: bool
    signer_role: str
    choices: tuple[str, ...] = ()
    question_text: str = ""
    anchor: str | None = None


@dataclass(frozen=True)
class UnsignedInstallationSigningContract:
    project_id: str
    approved_msr_id: str
    approved_msr_version: str
    source_evidence_id: str
    source_pdf_sha256: str
    preparation_evidence_id: str
    binding_sha256: str
    signer_user_id: str
    signer_email: str
    signer_name: str
    unsigned_pdf_sha256: str
    fields: tuple[RequiredSigningField, ...]
    contract_sha256: str
    provider: str = "DOCUSIGN"
    status: str = "OFFLINE_SIGNING_CONTRACT_NOT_SENT"
    envelope_id: None = None
    provider_tabs_installed: bool = False
    signer_authenticated: bool = False
    provider_signature_verified: bool = False
    provider_dates_verified: bool = False
    inspection_findings_verified: bool = False
    customer_survey_authenticated: bool = False
    trusted_installation_evidence: bool = False
    corrective_actions_persisted: bool = False
    receipt_issuance_authorized: bool = False
    project_completion_authorized: bool = False


def _required_text(value, label):
    if (
        type(value) is not str
        or not value.strip()
        or value != value.strip()
        or len(value) > 320
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
    ):
        raise ValidationError(f"Invalid {label}.")
    return value


def _sha(value, label):
    if type(value) is not str or not _HEX64.fullmatch(value):
        raise ValidationError(f"Invalid {label} SHA-256.")
    return value


def required_installation_signing_fields():
    """Five mutually exclusive Yes/No groups plus signature and date.

    Provider group placement and returned tab authentication are future
    integration steps; this function never claims tabs are installed.
    """
    findings = tuple(
        RequiredSigningField(
            field_id=key,
            field_type="RADIO_GROUP",
            required=True,
            signer_role="INSTALLATION_MANAGER",
            choices=("YES", "NO"),
            question_text=question,
        )
        for key, question in zip(INSPECTION_IDS, INSPECTION_ITEMS)
    )
    return findings + (
        RequiredSigningField(
            field_id="installation_manager_signature",
            field_type="SIGN_HERE",
            required=True,
            signer_role="INSTALLATION_MANAGER",
            anchor=SIGNATURE_ANCHOR,
        ),
        RequiredSigningField(
            field_id="installation_manager_signed_date",
            field_type="DATE_SIGNED",
            required=True,
            signer_role="INSTALLATION_MANAGER",
            anchor=DATE_ANCHOR,
        ),
    )


def validate_five_findings(values):
    """Validate tab response structure, NOT provider authenticity."""
    if type(values) is not dict or set(values) != set(INSPECTION_IDS):
        raise ValidationError("Exactly five inspection findings required.")
    if any(type(values[key]) is not str
           or values[key] not in ("YES", "NO")
           for key in INSPECTION_IDS):
        raise ValidationError("Each inspection finding must be Yes or No.")
    return tuple((key, values[key]) for key in INSPECTION_IDS)


def build_unsigned_installation_docusign_contract(*, actor, project_id):
    if settings.ENVIRONMENT != "development" or settings.DEBUG is not True:
        raise PermissionDenied("Offline signing contract is disabled.")

    manifest = build_installation_signing_manifest(
        actor=actor, project_id=project_id
    )
    document = render_unsigned_inspection_form(
        actor=actor, project_id=project_id
    )

    project = _required_text(str(manifest.project_id), "project ID")
    msr = _required_text(str(manifest.approved_msr_id), "MSR ID")
    version = _required_text(
        str(manifest.approved_msr_version), "MSR version"
    )
    source_id = _required_text(
        str(manifest.source_evidence_id), "source evidence ID"
    )
    prep_id = _required_text(
        str(manifest.preparation_evidence_id),
        "attestation preparation evidence ID",
    )
    signer_id = _required_text(
        str(manifest.signer_user_id), "signer user ID"
    )
    signer_email = _required_text(
        manifest.signer_email, "signer email"
    )
    signer_name = _required_text(
        manifest.signer_name, "signer name"
    )

    if "@" not in signer_email or signer_email.startswith("@"):
        raise ValidationError("Signer email required.")

    source_sha = _sha(
        manifest.source_pdf_sha256, "source PDF"
    )
    binding_sha = _sha(
        manifest.attestation_binding_sha256, "attestation binding"
    )
    pdf_sha = _sha(document.pdf_sha256, "unsigned document")

    if (
        type(document.pdf) is not bytes
        or not document.pdf.startswith(b"%PDF-")
        or sha256(document.pdf).hexdigest() != pdf_sha
        or str(document.project_id) != project
        or str(document.approved_msr_id) != msr
        or document.provider_authenticated is not False
        or document.docusign_tabs_configured is not False
        or document.completion_authorized is not False
    ):
        raise ValidationError("Unsigned inspection PDF binding invalid.")

    if (
        SIGNATURE_ANCHOR.encode() not in document.pdf
        or DATE_ANCHOR.encode() not in document.pdf
    ):
        raise ValidationError("Required signing anchors absent.")

    fields = required_installation_signing_fields()
    if (
        len(fields) != 7
        or tuple(field.field_id for field in fields[:5])
        != tuple(INSPECTION_IDS)
        or any(not field.required for field in fields)
        or any(field.signer_role != "INSTALLATION_MANAGER"
               for field in fields)
        or any(field.choices != ("YES", "NO")
               for field in fields[:5])
    ):
        raise ValidationError("Signing field contract invalid.")

    payload = {
        "schema": "GECC_INTERNAL_INSPECTION_SIGNING_4959_V1",
        "project_id": project,
        "approved_msr_id": msr,
        "approved_msr_version": version,
        "source_evidence_id": source_id,
        "source_pdf_sha256": source_sha,
        "preparation_evidence_id": prep_id,
        "binding_sha256": binding_sha,
        "signer_user_id": signer_id,
        "signer_email": signer_email,
        "signer_name": signer_name,
        "unsigned_pdf_sha256": pdf_sha,
        "fields": [
            {
                "field_id": field.field_id,
                "type": field.field_type,
                "required": field.required,
                "role": field.signer_role,
                "choices": field.choices,
                "question": field.question_text,
                "anchor": field.anchor,
            }
            for field in fields
        ],
        "provider": "DOCUSIGN",
        "status": "OFFLINE_SIGNING_CONTRACT_NOT_SENT",
    }
    digest = sha256(
        json.dumps(
            payload, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()

    return UnsignedInstallationSigningContract(
        project_id=project,
        approved_msr_id=msr,
        approved_msr_version=version,
        source_evidence_id=source_id,
        source_pdf_sha256=source_sha,
        preparation_evidence_id=prep_id,
        binding_sha256=binding_sha,
        signer_user_id=signer_id,
        signer_email=signer_email,
        signer_name=signer_name,
        unsigned_pdf_sha256=pdf_sha,
        fields=fields,
        contract_sha256=digest,
    )
