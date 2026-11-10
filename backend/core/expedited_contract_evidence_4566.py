"""Read-only assessment of retained generated contract records.

Generated PDF integrity and customer-signature existence are different
facts. Neither establishes customer initials or expedited authorization.
"""
from dataclasses import dataclass
from hashlib import sha256

from .documents import canonical_hash
from .models import CustomerSignatureEvidence, Document


@dataclass(frozen=True)
class ContractEvidenceAssessment:
    customer_contract_signature_recorded: bool = False
    generated_contract_integrity_verified: bool = False
    customer_initials_verified: bool = False
    signed_expedited_document_verified: bool = False
    installation_authorized: bool = False


def assess_contract_evidence(project):
    msr = getattr(project, "current_approved", None)
    if (
        msr is None
        or msr.status != "APPROVED"
        or msr.project_id != project.pk
    ):
        return ContractEvidenceAssessment()

    signature_recorded = CustomerSignatureEvidence.objects.filter(
        msr=msr,
        document_kind=CustomerSignatureEvidence.DocumentKind.CONTRACT,
        signer_role=CustomerSignatureEvidence.SignerRole.CUSTOMER,
    ).exists()

    generated = Document.objects.filter(
        msr=msr,
        kind=Document.Kind.CONTRACT,
    ).order_by("-created_at", "-id").first()

    intact = False
    if generated is not None:
        content = bytes(generated.content)
        intact = (
            bool(content)
            and content.startswith(b"%PDF-")
            and generated.snapshot_sha256 == canonical_hash(msr.snapshot)
            and generated.pdf_sha256 == sha256(content).hexdigest()
        )

    return ContractEvidenceAssessment(
        customer_contract_signature_recorded=bool(signature_recorded),
        generated_contract_integrity_verified=bool(intact),
    )
