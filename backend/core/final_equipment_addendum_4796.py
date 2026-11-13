"""Read-only equipment identification addendum candidate.

Uses the exact current approved MSR physical-unit inventory,
independently reviewed serial captures, and provisional CEO decisions.

Never creates a FINAL document or authorizes customer distribution.
"""

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO

from pypdf import PdfReader
from reportlab.pdfgen import canvas

from .documents import canonical_hash
from .equipment_physical_units import physical_units_from_snapshot
from .equipment_trust_verifier_4785 import (
    verify_equipment_trust_decisions,
)
from .receipt_equipment_manifest_4768 import (
    build_receipt_equipment_manifest,
)


@dataclass(frozen=True)
class EquipmentAddendumDraft:
    project_id: str
    msr_id: str
    snapshot_sha256: str
    equipment_count: int
    content: bytes
    pdf_sha256: str
    status: str = "DRAFT_NOT_ISSUED"
    trusted_installation_evidence: bool = False
    customer_issuance_authorized: bool = False
    customer_delivery_verified: bool = False
    completion_authorized: bool = False


def _safe(value, label, limit=72):
    if (
        type(value) is not str
        or not value.strip()
        or len(value) > limit
        or any(ord(ch) < 32 or ord(ch) > 126 for ch in value)
    ):
        raise ValueError("Invalid addendum value: " + label)
    return value.strip()


def render_equipment_addendum_draft(project):
    """Render an in-memory PDF with no storage or external side effects."""
    if project is None or getattr(project, "pk", None) is None:
        raise ValueError("Persisted project required.")

    msr = getattr(project, "current_approved", None)

    if (
        msr is None
        or msr.status != "APPROVED"
        or msr.project_id != project.pk
        or getattr(project, "state", None) == "CANCELLED"
    ):
        raise ValueError("Current approved project/MSR required.")

    pid = str(project.pk)
    mid = str(msr.pk)
    digest = canonical_hash(msr.snapshot)

    expected = physical_units_from_snapshot(
        msr_id=mid,
        snapshot=msr.snapshot,
    )
    manifest = build_receipt_equipment_manifest(project)
    decisions = verify_equipment_trust_decisions(project)

    if (
        not expected
        or manifest.project_id != pid
        or manifest.msr_id != mid
        or manifest.msr_version != msr.number
        or manifest.snapshot_sha256 != digest
        or manifest.expected_units != len(expected)
        or manifest.all_candidates_reviewed is not True
        or manifest.blockers
        or len(manifest.reviewed_units) != len(expected)
        or manifest.trusted_installation_evidence is not False
        or manifest.receipt_retention_authorized is not False
        or manifest.receipt_issuance_authorized is not False
        or manifest.completion_authorized is not False
        or decisions.project_id != pid
        or decisions.msr_id != mid
        or decisions.expected_units != len(expected)
        or decisions.approved_decisions_verified != len(expected)
        or decisions.rejected_decisions_verified != 0
        or decisions.all_approval_decisions_verified is not True
        or decisions.blockers
        or decisions.trusted_installation_evidence is not False
        or decisions.installation_authorized is not False
        or decisions.receipt_issuance_authorized is not False
        or decisions.customer_delivery_verified is not False
        or decisions.completion_authorized is not False
    ):
        raise ValueError("Equipment evidence is not ready for draft addendum.")

    reviewed = {unit.unit_id: unit for unit in manifest.reviewed_units}

    if len(reviewed) != len(expected):
        raise ValueError("Duplicate equipment-unit identities.")

    rows = []
    serials = set()

    for unit in expected:
        record = reviewed.get(unit.unit_id)

        if record is None:
            raise ValueError("Approved equipment unit missing review.")

        unit_id = _safe(unit.unit_id, "unit ID", 35)
        brand = _safe(unit.brand, "brand", 50)
        serial = _safe(record.serial_number, "serial number", 60)

        if serial.casefold() in serials:
            raise ValueError("Duplicate serial number.")

        serials.add(serial.casefold())
        rows.append((unit_id, brand, serial))

    output = BytesIO()
    pen = canvas.Canvas(output, pagesize=(792, 612))
    pen.setTitle("VERIDIAN Equipment Addendum - DRAFT NOT ISSUED")
    pen.setSubject("Unissued equipment identification candidate")

    code = _safe(str(project.code), "project code", 65)

    for page_start in range(0, len(rows), 10):
        page_rows = rows[page_start:page_start + 10]

        pen.setFont("Helvetica-Bold", 17)
        pen.drawString(45, 556, "EQUIPMENT IDENTIFICATION ADDENDUM")

        pen.setFont("Helvetica", 10)
        pen.drawString(45, 533, "Project: " + code)
        pen.drawString(45, 516, "Approved MSR version: " + str(msr.number))

        pen.setFont("Helvetica-Bold", 10)
        pen.drawString(45, 477, "Physical unit")
        pen.drawString(265, 477, "Brand")
        pen.drawString(395, 477, "Verified review serial")
        pen.line(45, 470, 750, 470)

        for index, row in enumerate(page_rows):
            y = 445 - (index * 33)

            pen.setFont("Helvetica", 9)
            pen.drawString(45, y, row[0])
            pen.drawString(265, y, row[1])
            pen.drawString(395, y, row[2])
            pen.line(45, y - 11, 750, y - 11)

        pen.saveState()
        pen.translate(396, 290)
        pen.rotate(28)
        pen.setFillColorRGB(0.65, 0.12, 0.12)
        pen.setFont("Helvetica-Bold", 27)
        pen.drawCentredString(0, 0, "DRAFT - NOT ISSUED")
        pen.restoreState()

        pen.setFont("Helvetica", 8)
        pen.drawString(
            45, 42,
            "Provisional adjudication only. Not proof of installation "
            "authorization or customer delivery."
        )
        pen.showPage()

    pen.save()
    content = output.getvalue()

    reader = PdfReader(BytesIO(content), strict=True)

    if (
        reader.is_encrypted
        or len(reader.pages) != (len(rows) + 9) // 10
        or any(
            (
                float(page.mediabox.width),
                float(page.mediabox.height),
            ) != (792.0, 612.0)
            for page in reader.pages
        )
    ):
        raise ValueError("Addendum PDF geometry or integrity invalid.")

    visible = "\n".join(
        page.extract_text() or "" for page in reader.pages
    )

    for row in rows:
        if any(value not in visible for value in row):
            raise ValueError("Equipment identification absent from PDF.")

    if visible.count("DRAFT - NOT ISSUED") != len(reader.pages):
        raise ValueError("Non-issuance watermark missing.")

    return EquipmentAddendumDraft(
        project_id=pid,
        msr_id=mid,
        snapshot_sha256=digest,
        equipment_count=len(rows),
        content=content,
        pdf_sha256=sha256(content).hexdigest(),
    )
