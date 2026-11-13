"""In-memory draft V4 Receipt plus equipment addendum package.

This is a preparation artifact, never an issuance instruction.
The archive and both PDFs are returned as bytes, not persisted or sent.
"""

import json
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from pypdf import PdfReader

from .approved_final_receipt_reference_4756 import (
    APPROVED_SHA256,
    verify_approved_final_receipt,
)
from .documents import canonical_hash
from .final_equipment_addendum_4796 import EquipmentAddendumDraft
from .final_receipt_customer_candidate_4793 import (
    RenderedV4CustomerCandidate,
)


@dataclass(frozen=True)
class ReceiptPackageDraft:
    project_id: str
    msr_id: str
    snapshot_sha256: str
    receipt_sha256: str
    addendum_sha256: str
    archive_sha256: str
    archive: bytes
    status: str = "DRAFT_NOT_ISSUED"
    issuance_authorized: bool = False
    customer_delivery_verified: bool = False
    completion_authorized: bool = False


def _verify_pdf(content, digest, *, required, forbidden=()):
    if (
        type(content) is not bytes
        or not content.startswith(b"%PDF-")
        or len(content) > 5 * 1024 * 1024
        or sha256(content).hexdigest() != digest
    ):
        raise ValueError("Exact retained PDF bytes required.")

    reader = PdfReader(BytesIO(content), strict=True)

    if reader.is_encrypted or not reader.pages:
        raise ValueError("Unencrypted PDF required.")

    if any(
        (
            float(page.mediabox.width),
            float(page.mediabox.height),
        ) != (792.0, 612.0)
        for page in reader.pages
    ):
        raise ValueError("Approved landscape page geometry required.")

    visible = "\n".join(page.extract_text() or "" for page in reader.pages)

    if any(phrase not in visible for phrase in required):
        raise ValueError("Required PDF content missing.")

    if any(phrase in visible for phrase in forbidden):
        raise ValueError("Unexpected issuance classification in PDF.")

    return reader


def build_receipt_package_draft(*, project, receipt, addendum):
    if project is None or getattr(project, "pk", None) is None:
        raise ValueError("Persisted project required.")

    msr = getattr(project, "current_approved", None)

    if (
        msr is None
        or msr.status != "APPROVED"
        or msr.project_id != project.pk
        or project.state == "CANCELLED"
    ):
        raise ValueError("Current approved MSR required.")

    if (
        not isinstance(receipt, RenderedV4CustomerCandidate)
        or not isinstance(addendum, EquipmentAddendumDraft)
    ):
        raise ValueError("Verified draft PDF types required.")

    pid = str(project.pk)
    mid = str(msr.pk)
    digest = canonical_hash(msr.snapshot)

    if (
        receipt.project_id != pid
        or receipt.approved_msr_id != mid
        or receipt.status != "DRAFT_NOT_ISSUED"
        or addendum.project_id != pid
        or addendum.msr_id != mid
        or addendum.snapshot_sha256 != digest
        or addendum.equipment_count < 1
        or addendum.status != "DRAFT_NOT_ISSUED"
        or addendum.trusted_installation_evidence is not False
        or addendum.customer_issuance_authorized is not False
        or addendum.customer_delivery_verified is not False
        or addendum.completion_authorized is not False
    ):
        raise ValueError("Cross-project, MSR or authority mismatch.")

    reference = verify_approved_final_receipt()

    if (
        receipt.reference_sha256 != reference.sha256
        or reference.sha256.upper() != APPROVED_SHA256
    ):
        raise ValueError("Approved V4 reference mismatch.")

    receipt_reader = _verify_pdf(
        receipt.content,
        receipt.pdf_sha256,
        required=("DRAFT - NOT ISSUED", "DRAFT CUSTOMER COPY"),
        forbidden=("INTERNAL - NOT ISSUED",),
    )

    if len(receipt_reader.pages) != 1:
        raise ValueError("V4 Receipt must be exactly one page.")

    if "draft, not issued" not in str(
        receipt_reader.metadata.title or ""
    ).lower():
        raise ValueError("Receipt draft PDF metadata missing.")

    _verify_pdf(
        addendum.content,
        addendum.pdf_sha256,
        required=(
            "EQUIPMENT IDENTIFICATION ADDENDUM",
            "DRAFT - NOT ISSUED",
            "Approved MSR version: " + str(msr.number),
        ),
    )

    manifest = {
        "purpose": "DRAFT_NOT_ISSUED",
        "project_id": pid,
        "approved_msr_id": mid,
        "approved_msr_version": msr.number,
        "snapshot_sha256": digest,
        "approved_reference_sha256": reference.sha256,
        "receipt_sha256": receipt.pdf_sha256,
        "addendum_sha256": addendum.pdf_sha256,
        "equipment_count": addendum.equipment_count,
        "issuance_authorized": False,
        "customer_delivery_verified": False,
        "completion_authorized": False,
    }

    output = BytesIO()

    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("V4-Receipt-DRAFT-NOT-ISSUED.pdf", receipt.content)
        archive.writestr(
            "Equipment-Addendum-DRAFT-NOT-ISSUED.pdf",
            addendum.content,
        )
        archive.writestr(
            "draft-manifest.json",
            json.dumps(manifest, sort_keys=True, indent=2),
        )

    content = output.getvalue()

    with ZipFile(BytesIO(content), "r") as archive:
        if set(archive.namelist()) != {
            "V4-Receipt-DRAFT-NOT-ISSUED.pdf",
            "Equipment-Addendum-DRAFT-NOT-ISSUED.pdf",
            "draft-manifest.json",
        }:
            raise ValueError("Draft archive entries invalid.")

        if (
            sha256(
                archive.read("V4-Receipt-DRAFT-NOT-ISSUED.pdf")
            ).hexdigest() != receipt.pdf_sha256
            or sha256(
                archive.read("Equipment-Addendum-DRAFT-NOT-ISSUED.pdf")
            ).hexdigest() != addendum.pdf_sha256
            or json.loads(archive.read("draft-manifest.json"))
                != manifest
        ):
            raise ValueError("Draft package fingerprint mismatch.")

    return ReceiptPackageDraft(
        project_id=pid,
        msr_id=mid,
        snapshot_sha256=digest,
        receipt_sha256=receipt.pdf_sha256,
        addendum_sha256=addendum.pdf_sha256,
        archive_sha256=sha256(content).hexdigest(),
        archive=content,
    )
