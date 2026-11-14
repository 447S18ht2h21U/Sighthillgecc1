"""Installation-specific authenticated-provenance boundary.

Internal inspection/review records are not authenticated source proof.
No installation-specific provider verification has been implemented.
This read-only gate must fail closed until that separate workflow exists.
"""
from dataclasses import dataclass

from .installation_source_artifact_4826 import (
    verify_retained_installation_source,
)


REQUIRED_PROOF = (
    "Authenticated installation-specific source evidence.",
    "Exact retained source artifact with independently checked digest.",
    "Verified project, approved MSR, and completed schedule binding.",
    "Verified source identity, inspection outcome, and chronology.",
    "Independent acceptance and immutable audit evidence.",
)


@dataclass(frozen=True)
class InstallationProvenanceGate:
    project_id: str
    msr_id: str
    status: str
    internal_acceptance_candidate_verified: bool
    required_proof: tuple[str, ...]
    blockers: tuple[str, ...]
    source_artifact_authenticated: bool = False
    source_artifact_integrity_verified: bool = False
    source_artifact_retained_verified: bool = False
    trusted_installation_evidence: bool = False
    final_receipt_issuance_authorized: bool = False
    customer_delivery_verified: bool = False
    completion_authorized: bool = False


def assess_installation_provenance(*, project, acceptance):
    if project is None or getattr(project, "pk", None) is None:
        raise ValueError("Persisted project required.")

    msr = getattr(project, "current_approved", None)
    if (
        msr is None
        or msr.status != "APPROVED"
        or msr.project_id != project.pk
        or project.current_approved_id != msr.pk
        or project.state == "CANCELLED"
    ):
        raise ValueError("Current approved MSR required.")

    if (
        acceptance.project_id != str(project.pk)
        or acceptance.msr_id != str(msr.pk)
        or type(acceptance.acceptance_candidate_verified) is not bool
        or acceptance.post_installation_acceptance_verified is not False
        or acceptance.trusted_installation_evidence is not False
        or acceptance.final_receipt_issuance_authorized is not False
        or acceptance.customer_delivery_verified is not False
        or acceptance.completion_authorized is not False
    ):
        raise ValueError("Acceptance identity or authority mismatch.")

    candidate = acceptance.acceptance_candidate_verified
    status = (
        "AWAITING_AUTHENTICATED_INSTALLATION_PROOF"
        if candidate
        else "INTERNAL_ACCEPTANCE_CANDIDATE_MISSING"
    )

    retained = False
    if candidate:
        try:
            retained = (
                verify_retained_installation_source(project) is True
            )
        except Exception:
            # Storage and verification failures always deny trust.
            retained = False

    if candidate and retained:
        status = 'SOURCE_ARTIFACT_RETAINED_UNAUTHENTICATED'

    blockers = []
    if candidate and not retained:
        blockers.append(
            'Exact retained installation source artifact is missing '
            'or failed integrity verification.'
        )
    if not candidate:
        blockers.append(
            "Valid independent post-installation acceptance is missing."
        )

    blockers.append(
        "Installation-specific source authentication and exact retained "
        "artifact verification are not implemented."
    )

    return InstallationProvenanceGate(
        project_id=str(project.pk),
        msr_id=str(msr.pk),
        status=status,
        internal_acceptance_candidate_verified=candidate,
        required_proof=REQUIRED_PROOF,
        source_artifact_integrity_verified=retained,
        source_artifact_retained_verified=retained,
        blockers=tuple(blockers),
    )
