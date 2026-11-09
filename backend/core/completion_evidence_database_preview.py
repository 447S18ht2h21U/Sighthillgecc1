"""Unregistered read-only project/MSR-bound completion evidence inventory.

A preparation PDF is not a delivered Receipt. A retained DocuSign
document is not alone proof of completed provider verification.
No operational project-completion permissions are granted.
"""
from dataclasses import dataclass
import hashlib
from uuid import UUID

from .models import (
    Project,
    Document,
    CompletionSignatureVerification,
)


@dataclass(frozen=True)
class CompletionDatabaseEvidence:
    project_id: str
    msr_id: str | None
    receipt_document_candidates: int
    certificate_document_candidates: int
    receipt_retention_verified: bool
    receipt_email_verified: bool
    completed_docusign_received_verified: bool
    completed_docusign_retained_verified: bool
    survey_required: bool
    blockers: tuple[str, ...]
    project_completion_authorized: bool = False
    project_completed: bool = False


def inspect_completion_database_evidence(*, project_id):
    try:
        project_key = str(UUID(str(project_id)))
    except (TypeError, AttributeError, ValueError):
        raise ValueError("Valid project UUID required.") from None

    blockers = []
    project = (
        Project.objects.select_related("current_approved")
        .filter(pk=project_key).first()
    )

    def denied(msr_key=None, receipts=0, certificates=0):
        return CompletionDatabaseEvidence(
            project_id=project_key,
            msr_id=msr_key,
            receipt_document_candidates=receipts,
            certificate_document_candidates=certificates,
            receipt_retention_verified=False,
            receipt_email_verified=False,
            completed_docusign_received_verified=False,
            completed_docusign_retained_verified=False,
            survey_required=False,
            blockers=tuple(blockers),
        )

    if project is None:
        blockers.append("Project does not exist.")
        return denied()

    if project.state == "CANCELLED":
        blockers.append("Cancelled project cannot be completed.")

    msr = project.current_approved
    if (
        msr is None
        or msr.status != "APPROVED"
        or msr.project_id != project.pk
    ):
        blockers.append("Correct current approved MSR is required.")
        return denied()

    msr_key = str(msr.pk)

    # Historical internal kind is retained for compatibility.
    # Only a valid PDF is counted as a *candidate* for the Receipt;
    # there is no assumption of issuance or email delivery.
    receipts = 0
    for document in Document.objects.filter(
        msr_id=msr.pk, kind=Document.Kind.INVOICE
    ):
        content = bytes(document.content)
        if (
            content.startswith(b"%PDF-")
            and hashlib.sha256(content).hexdigest()
                == str(document.pdf_sha256).lower()
        ):
            receipts += 1

    if not receipts:
        blockers.append("No matching retained Receipt PDF candidate.")
    else:
        blockers.append(
            "Retained historical document is not yet a verified final Receipt."
        )

    # The provider verification and retained PDF must both be tied to
    # a release package for the CURRENT approved MSR.
    certificates = 0
    verifications = CompletionSignatureVerification.objects.filter(
        release_package__plan__msr_id=msr.pk
    )

    expected_kind = (
        "COMPLETION_FINANCED"
        if msr.snapshot.get("financing_type") == "FINANCED"
        else "COMPLETION_NON_FINANCED"
        if msr.snapshot.get("financing_type") == "NON_FINANCED"
        else None
    )

    if expected_kind is None:
        blockers.append("Approved MSR financing classification is invalid.")

    for verification in verifications:
        if not (
            verification.provider_account_id
            and verification.provider_envelope_id
            and verification.digest
            and expected_kind
        ):
            continue

        for document in verification.retained_documents.all():
            content = bytes(document.content)
            if (
                document.kind == expected_kind
                and content.startswith(b"%PDF-")
                and hashlib.sha256(content).hexdigest()
                    == str(document.pdf_sha256).lower()
            ):
                certificates += 1

    if certificates:
        blockers.append(
            "DocuSign PDF candidate found, but completion receipt "
            "and trusted provider evidence are not yet independently verified."
        )
    else:
        blockers.append(
            "No matching retained completed-certificate PDF candidate."
        )

    blockers.extend((
        "The exact final Receipt must be independently retained and verified.",
        "Successful email sending of that exact Receipt must be verified.",
        "GECC receipt of the completed DocuSign certificate must be verified.",
        "Trusted completion authorization is not operationally implemented.",
    ))

    return denied(msr_key, receipts, certificates)