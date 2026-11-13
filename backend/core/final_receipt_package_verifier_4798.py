"""Independent retrieval-time verification of a draft Receipt ZIP.

Verifies archived bytes against the approved MSR and persisted physical
inspection/adjudication evidence. Never authorizes or sends documents.
"""

import json
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from zipfile import ZipFile, BadZipFile

from pypdf import PdfReader

from .approved_final_receipt_reference_4756 import (
    verify_approved_final_receipt,
)
from .documents import canonical_hash
from .equipment_trust_verifier_4785 import (
    verify_equipment_trust_decisions,
)
from .final_receipt_package_4797 import ReceiptPackageDraft
from .receipt_equipment_manifest_4768 import (
    build_receipt_equipment_manifest,
)


RECEIPT_NAME = "V4-Receipt-DRAFT-NOT-ISSUED.pdf"
ADDENDUM_NAME = "Equipment-Addendum-DRAFT-NOT-ISSUED.pdf"
MANIFEST_NAME = "draft-manifest.json"
EXPECTED_NAMES = {RECEIPT_NAME, ADDENDUM_NAME, MANIFEST_NAME}


@dataclass(frozen=True)
class VerifiedDraftPackage:
    project_id: str
    msr_id: str
    receipt_sha256: str
    addendum_sha256: str
    equipment_count: int
    integrity_verified: bool
    status: str = "DRAFT_NOT_ISSUED"
    issuance_authorized: bool = False
    customer_delivery_verified: bool = False
    completion_authorized: bool = False


def _pdf(content, required, pages=None):
    if (
        type(content) is not bytes
        or len(content) < 8
        or len(content) > 5 * 1024 * 1024
        or not content.startswith(b"%PDF-")
    ):
        raise ValueError("Invalid draft PDF bytes.")

    reader = PdfReader(BytesIO(content), strict=True)

    if (
        reader.is_encrypted
        or not reader.pages
        or (pages is not None and len(reader.pages) != pages)
        or any(
            (
                float(page.mediabox.width),
                float(page.mediabox.height),
            ) != (792.0, 612.0)
            for page in reader.pages
        )
    ):
        raise ValueError("Draft PDF page integrity failed.")

    visible = "\n".join(
        page.extract_text() or "" for page in reader.pages
    )

    if (
        any(phrase not in visible for phrase in required)
        or "DRAFT - NOT ISSUED" not in visible
        or "INTERNAL - NOT ISSUED" in visible
    ):
        raise ValueError("Draft PDF contents or classification invalid.")

    return reader, visible


def verify_receipt_package_draft(*, project, package):
    if not isinstance(package, ReceiptPackageDraft):
        raise ValueError("ReceiptPackageDraft required.")

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

    pid = str(project.pk)
    mid = str(msr.pk)
    snapshot_digest = canonical_hash(msr.snapshot)

    if (
        package.project_id != pid
        or package.msr_id != mid
        or package.snapshot_sha256 != snapshot_digest
        or package.status != "DRAFT_NOT_ISSUED"
        or package.issuance_authorized is not False
        or package.customer_delivery_verified is not False
        or package.completion_authorized is not False
        or type(package.archive) is not bytes
        or len(package.archive) > 12 * 1024 * 1024
        or sha256(package.archive).hexdigest()
           != package.archive_sha256
    ):
        raise ValueError("Archive identity, integrity or authority mismatch.")

    try:
        with ZipFile(BytesIO(package.archive), "r") as archive:
            infos = archive.infolist()

            if (
                len(infos) != 3
                or {info.filename for info in infos} != EXPECTED_NAMES
                or any(
                    info.is_dir()
                    or info.flag_bits & 1
                    or info.file_size > 5 * 1024 * 1024
                    for info in infos
                )
            ):
                raise ValueError("Unexpected ZIP entry or size.")

            receipt = archive.read(RECEIPT_NAME)
            addendum = archive.read(ADDENDUM_NAME)
            raw_manifest = archive.read(MANIFEST_NAME)

    except (BadZipFile, EOFError, OSError, RuntimeError) as exc:
        raise ValueError("Stored draft ZIP is invalid.") from exc

    if len(raw_manifest) > 32768:
        raise ValueError("Manifest exceeds size limit.")

    try:
        manifest = json.loads(raw_manifest)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("Stored manifest invalid.") from exc

    if type(manifest) is not dict:
        raise ValueError("Manifest object required.")

    reference = verify_approved_final_receipt()

    expected_manifest = {
        "purpose": "DRAFT_NOT_ISSUED",
        "project_id": pid,
        "approved_msr_id": mid,
        "approved_msr_version": msr.number,
        "snapshot_sha256": snapshot_digest,
        "approved_reference_sha256": reference.sha256,
        "receipt_sha256": sha256(receipt).hexdigest(),
        "addendum_sha256": sha256(addendum).hexdigest(),
        "equipment_count": manifest.get("equipment_count"),
        "issuance_authorized": False,
        "customer_delivery_verified": False,
        "completion_authorized": False,
    }

    if (
        manifest != expected_manifest
        or manifest["receipt_sha256"] != package.receipt_sha256
        or manifest["addendum_sha256"] != package.addendum_sha256
    ):
        raise ValueError("Draft manifest does not match archived documents.")

    receipt_reader, receipt_text = _pdf(
        receipt,
        ("DRAFT CUSTOMER COPY",),
        pages=1,
    )

    if "draft, not issued" not in str(
        receipt_reader.metadata.title or ""
    ).lower():
        raise ValueError("Receipt metadata must identify draft status.")

    _, addendum_text = _pdf(
        addendum,
        (
            "EQUIPMENT IDENTIFICATION ADDENDUM",
            "Approved MSR version: " + str(msr.number),
        ),
    )

    equipment = build_receipt_equipment_manifest(project)
    decisions = verify_equipment_trust_decisions(project)

    if (
        equipment.project_id != pid
        or equipment.msr_id != mid
        or equipment.snapshot_sha256 != snapshot_digest
        or equipment.all_candidates_reviewed is not True
        or equipment.blockers
        or equipment.expected_units < 1
        or len(equipment.reviewed_units) != equipment.expected_units
        or equipment.trusted_installation_evidence is not False
        or equipment.receipt_issuance_authorized is not False
        or decisions.project_id != pid
        or decisions.msr_id != mid
        or decisions.all_approval_decisions_verified is not True
        or decisions.approved_decisions_verified
           != equipment.expected_units
        or decisions.trusted_installation_evidence is not False
        or decisions.installation_authorized is not False
        or decisions.receipt_issuance_authorized is not False
        or decisions.customer_delivery_verified is not False
        or decisions.completion_authorized is not False
        or manifest["equipment_count"] != equipment.expected_units
    ):
        raise ValueError("Current equipment evidence not sufficient.")

    for unit in equipment.reviewed_units:
        if (
            unit.unit_id not in addendum_text
            or unit.serial_number not in addendum_text
        ):
            raise ValueError("Reviewed equipment absent from addendum.")

    return VerifiedDraftPackage(
        project_id=pid,
        msr_id=mid,
        receipt_sha256=package.receipt_sha256,
        addendum_sha256=package.addendum_sha256,
        equipment_count=equipment.expected_units,
        integrity_verified=True,
    )
