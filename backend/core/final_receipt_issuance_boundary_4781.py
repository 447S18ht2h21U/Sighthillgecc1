"""Read-only separation of internal Receipt storage and customer issuance.

This boundary deliberately grants NO authority to issue, send, claim
provider delivery, or complete a project. It identifies independently
required evidence before a separate issuance workflow can be enabled.
"""

from dataclasses import dataclass
from hashlib import sha256

from .documents import canonical_hash
from .final_receipt_evidence_gate_4769 import (
    assess_final_receipt_evidence_gate,
)
from .final_receipt_internal_retention_4770 import (
    RENDERER_VERSION,
    validate_internal_receipt_document,
)
from .models import Document, ReceiptDispatchOutbox


@dataclass(frozen=True)
class FinalReceiptIssuanceBoundary:
    project_id: str
    msr_id: str
    internal_document_id: str | None
    internal_document_verified: bool
    reviewed_equipment_candidates_complete: bool
    existing_outbox_intents: int
    blockers: tuple[str, ...]
    trusted_installation_evidence: bool = False
    customer_receipt_issuance_authorized: bool = False
    provider_email_authenticated: bool = False
    customer_delivery_verified: bool = False
    completion_authorized: bool = False


def assess_final_receipt_issuance_boundary(project):
    """Inspect persisted data without authorizing an irreversible action."""
    if project is None or getattr(project, "pk", None) is None:
        raise ValueError("Persisted project required.")

    msr = getattr(project, "current_approved", None)

    if (
        msr is None
        or getattr(msr, "status", None) != "APPROVED"
        or str(getattr(msr, "project_id", "")) != str(project.pk)
    ):
        raise ValueError("Current approved MSR binding invalid.")

    gate = assess_final_receipt_evidence_gate(project)

    if (
        gate.project_id != str(project.pk)
        or gate.approved_msr_id != str(msr.pk)
        or gate.trusted_equipment_evidence is not False
        or gate.retention_authorized is not False
        or gate.final_receipt_verified is not False
        or gate.customer_delivery_verified is not False
        or gate.completion_authorized is not False
    ):
        raise ValueError("Upstream evidence gate asserted unauthorized trust.")

    blockers = list(gate.blockers)
    document = (
        Document.objects.filter(
            msr=msr,
            kind=Document.Kind.RECEIPT,
            renderer_version=RENDERER_VERSION,
        ).first()
    )

    document_id = None
    verified = False

    if document is None:
        blockers.append("No retained internal V4 Receipt preparation.")
    else:
        document_id = str(document.pk)

        # This must validate the *actual* immutable PDF bytes.
        # Fail closed on corrupt or wrongly classified stored records.
        validate_internal_receipt_document(
            document,
            msr=msr,
            reference_sha256=document.template_sha256,
            snapshot_sha256=canonical_hash(msr.snapshot),
        )

        if (
            type(document.values) is not dict
            or document.values.get("project_id") != str(project.pk)
            or document.values.get("reference_sha256")
                != document.template_sha256
            or document.values.get("purpose") != "INTERNAL_NOT_ISSUED"
            or sha256(bytes(document.content)).hexdigest()
                != document.pdf_sha256
        ):
            raise ValueError("Stored internal Receipt binding invalid.")

        verified = True
        blockers.append(
            "Retained PDF is an INTERNAL preparation, not an "
            "authorized customer-facing Receipt."
        )

    intent_count = ReceiptDispatchOutbox.objects.filter(
        project=project,
        msr=msr,
    ).count()

    if intent_count:
        blockers.append(
            "Existing Receipt outbox intents do not prove "
            "provider delivery."
        )

    if gate.candidate_evidence_complete is not True:
        blockers.append(
            "Independent physical equipment reviews incomplete."
        )

    blockers.extend((
        "Trusted installation evidence has not been granted.",
        "No independently authorized FINAL customer Receipt exists.",
        "Authenticated customer delivery has not been verified.",
        "Completion remains prohibited.",
    ))

    return FinalReceiptIssuanceBoundary(
        project_id=str(project.pk),
        msr_id=str(msr.pk),
        internal_document_id=document_id,
        internal_document_verified=verified,
        reviewed_equipment_candidates_complete=(
            gate.candidate_evidence_complete is True
        ),
        existing_outbox_intents=intent_count,
        blockers=tuple(dict.fromkeys(blockers)),
    )
