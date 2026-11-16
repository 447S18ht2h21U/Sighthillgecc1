"""Development-only server-generated inspection draft authorization.

The browser supplies only a project identifier and explicit confirmation.
The server constructs every document and signer placement. No provider I/O.
"""
import os

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError

from core.installation_docusign_contract_4959 import (
    build_unsigned_installation_docusign_contract,
)
from core.installation_inspection_form_4945 import (
    render_unsigned_inspection_form,
)
from core.installation_docusign_placement_4960 import (
    build_offline_inspection_tab_plan,
)
from core.installation_docusign_envelope_4962 import (
    build_offline_installation_envelope,
)
from core.installation_draft_authorization_5179 import (
    _gate as authorization_gate,
    record_draft_intent,
)


def _pdf_bytes(document):
    """Extract exact bytes, failing closed on an unknown document format."""
    if type(document) is bytes:
        return document

    for field in ("pdf_bytes", "unsigned_pdf", "pdf", "content"):
        value = getattr(document, field, None)
        if type(value) is bytes:
            return value

    raise ValidationError(
        "Inspection form builder did not return recognized PDF bytes."
    )


def assemble(*, actor, project_id):
    """Generate a fresh, matching inspection draft entirely server-side."""
    authorization_gate(actor)

    contract = build_unsigned_installation_docusign_contract(
        actor=actor,
        project_id=project_id,
    )

    document = render_unsigned_inspection_form(
        actor=actor,
        project_id=project_id,
    )

    unsigned_pdf = _pdf_bytes(document)

    plan = build_offline_inspection_tab_plan(
        contract=contract,
        pdf_bytes=unsigned_pdf,
    )

    envelope = build_offline_installation_envelope(
        contract=contract,
        plan=plan,
        unsigned_pdf=unsigned_pdf,
    )

    if (
        str(envelope.project_id) != str(project_id)
        or str(envelope.approved_msr_id)
           != str(contract.approved_msr_id)
        or str(envelope.approved_msr_version)
           != str(contract.approved_msr_version)
        or envelope.provider_signed is not False
        or envelope.completion_authorized is not False
        or envelope.envelope_id is not None
    ):
        raise ValidationError(
            "Generated inspection package failed binding checks."
        )

    return envelope


def authorize(*, actor, project_id, confirmed):
    """Record CEO/SM intent; never connect to DocuSign or send anything."""
    authorization_gate(actor)

    if confirmed is not True:
        raise ValidationError(
            "Explicit inspection draft authorization confirmation required."
        )

    envelope = assemble(actor=actor, project_id=project_id)

    result = record_draft_intent(
        actor=actor,
        project_id=project_id,
        envelope=envelope,
        confirmed=True,
    )

    return {
        "status": result["status"],
        "evidence_id": result["evidence_id"],
        "digest": result["digest"],
        "provider_draft_created": False,
        "provider_request_authorized": False,
        "send_authorized": False,
        "provider_signature_verified": False,
        "project_completion_authorized": False,
    }