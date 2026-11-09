"""Read-only provenance audit for future administrative project completion.

This service inspects persisted records rather than trusting caller claims.
It never authenticates a provider, sends email, changes project state, or
authorizes completion. Synthetic observations are always untrusted.
"""
from dataclasses import dataclass
from uuid import UUID
import hashlib

from .models import (
    Project,
    Document,
    ProjectEvidence,
    CompletionEnvelopeAttempt,
    CompletionSignatureVerification,
)


@dataclass(frozen=True)
class CompletionProvenanceReport:
    project_id: str
    approved_msr_id: str | None
    receipt_pdf_candidates: int
    synthetic_email_observations: int
    envelope_bound_certificate_candidates: int
    trusted_receipt_email: bool
    trusted_completed_docusign: bool
    survey_required: bool
    blockers: tuple[str, ...]
    completion_authorized: bool = False


def _canonical_uuid(value):
    try:
        candidate = str(UUID(str(value)))
        return candidate if str(value) == candidate else None
    except (ValueError, TypeError, AttributeError):
        return None


def _valid_pdf(content, digest):
    if not isinstance(digest, str) or len(digest) != 64:
        return False
    try:
        bytes_value = bytes(content)
    except (TypeError, ValueError):
        return False
    return (
        bytes_value.startswith(b"%PDF-")
        and hashlib.sha256(bytes_value).hexdigest() == digest.lower()
    )


def inspect_completion_provenance(*, project_id):
    key = _canonical_uuid(project_id)
    if key is None:
        raise ValueError("Canonical project UUID required.")

    reasons = []
    project = (
        Project.objects.select_related("current_approved")
        .filter(pk=key)
        .first()
    )

    def report(msr=None, receipts=0, synthetic=0, certificates=0):
        return CompletionProvenanceReport(
            project_id=key,
            approved_msr_id=str(msr.pk) if msr is not None else None,
            receipt_pdf_candidates=receipts,
            synthetic_email_observations=synthetic,
            envelope_bound_certificate_candidates=certificates,
            trusted_receipt_email=False,
            trusted_completed_docusign=False,
            survey_required=False,
            blockers=tuple(reasons),
        )

    if project is None:
        reasons.append("Project not found.")
        return report()

    if project.state == "CANCELLED":
        reasons.append("Cancelled projects cannot be completed.")

    msr = project.current_approved
    if (
        msr is None
        or msr.status != "APPROVED"
        or str(msr.project_id) != str(project.pk)
    ):
        reasons.append("Matching current approved MSR required.")
        return report()

    receipt_count = 0
    for document in Document.objects.filter(
        msr=msr, kind=Document.Kind.INVOICE
    ):
        if _valid_pdf(document.content, document.pdf_sha256):
            receipt_count += 1

    if receipt_count:
        reasons.append(
            "Historical Invoice PDFs are preparation candidates, "
            "not independently verified final Receipts."
        )
    else:
        reasons.append("No valid retained Receipt PDF candidate.")

    synthetic_count = ProjectEvidence.objects.filter(
        msr=msr, kind="INVOICE_DELIVERY_OBSERVATION"
    ).count()
    if synthetic_count:
        reasons.append(
            "Synthetic delivery observations are untrusted and "
            "cannot prove the customer was emailed a Receipt."
        )

    reasons.append(
        "Trusted email-provider sending evidence for the exact "
        "retained final Receipt is not yet available."
    )

    bound_certificate_count = 0
    verifications = (
        CompletionSignatureVerification.objects
        .filter(release_package__plan__msr=msr)
        .select_related("release_package__plan")
    )

    for verification in verifications:
        package = verification.release_package

        if package.plan.group not in (
            "COMPLETION_FINANCED",
            "COMPLETION_NON_FINANCED",
        ):
            continue

        account_id = _canonical_uuid(verification.provider_account_id)
        envelope_id = _canonical_uuid(verification.provider_envelope_id)
        if account_id is None or envelope_id is None:
            continue

        attempts = list(
            CompletionEnvelopeAttempt.objects.filter(
                release_package=package
            )[:2]
        )
        if len(attempts) != 1:
            continue
        attempt = attempts[0]

        if (
            _canonical_uuid(attempt.provider_account_id) != account_id
            or _canonical_uuid(attempt.provider_envelope_id) != envelope_id
            or not attempt.first_send_started_at
        ):
            continue

        for document in verification.retained_documents.all():
            if (
                document.kind == package.plan.group
                and _valid_pdf(document.content, document.pdf_sha256)
            ):
                bound_certificate_count += 1

    if bound_certificate_count:
        reasons.append(
            "A retained certificate matches a local envelope attempt, "
            "but matching local records do not authenticate DocuSign."
        )
    else:
        reasons.append(
            "No retained completion certificate matches an existing "
            "project-bound envelope attempt and verification record."
        )

    reasons.append(
        "Independent provider confirmation of completed signatures "
        "and GECC receipt of the certificate is required."
    )
    reasons.append(
        "Operational authorized project-completion transaction "
        "has not been implemented."
    )

    return report(
        msr=msr,
        receipts=receipt_count,
        synthetic=synthetic_count,
        certificates=bound_certificate_count,
    )