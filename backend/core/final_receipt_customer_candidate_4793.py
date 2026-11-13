"""Non-issuable customer-layout V4 draft renderer."""
# Original renderer SHA256: 281ac4bc6484802e67f1388b9b5d720276574f169c8db61d72a1a0221f4289dc

"""Approved V4 Receipt PDF rendering layer.

Draft rendering only. This does not issue or retain a customer
Receipt, validate installation-stage serial evidence, send email,
or authorize administrative project completion.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from hashlib import sha256
from io import BytesIO

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import simpleSplit

from .approved_final_receipt_reference_4756 import (
    verify_approved_final_receipt,
)
from .final_receipt_adjudication_readiness_4789 import (
    FinalReceiptAdjudicationReadiness,
)
from .final_receipt_financial_evidence_4760 import (
    FinalReceiptFinancialEvidence,
)
from .approved_receipt_overlay_preview_4223 import (
    HEADER_FIELDS,
    EQUIPMENT_COLUMNS,
    AMOUNT_BASELINES,
)
from .equipment_invoice_rows import project_equipment_rows
from .invoice_msr_projection import revised_invoice_projection
from .msr_document_source import customer_document_data


@dataclass(frozen=True)
class RenderedV4CustomerCandidate:
    content: bytes
    pdf_sha256: str
    reference_sha256: str
    approved_msr_id: str
    project_id: str
    status: str = "DRAFT_NOT_ISSUED"


def _text(value, label, maximum_length=160):
    if (
        type(value) is not str
        or not value.strip()
        or len(value) > maximum_length
        or any(ord(ch) < 32 or ord(ch) > 126 for ch in value)
    ):
        raise ValueError(f"Invalid Receipt value: {label}")
    return value.strip()


def _draw_fitted(pen, text, x, y, width, size=8.5):
    while size >= 6.0:
        if pen.stringWidth(text, "Helvetica", size) <= width:
            break
        size -= 0.5
    else:
        raise ValueError("Receipt field does not fit the approved layout.")

    pen.setFillColorRGB(1, 1, 1)
    pen.rect(x - 1, y - 3, width + 1, 13, stroke=0, fill=1)
    pen.setFillColorRGB(0.04, 0.18, 0.25)
    pen.setFont("Helvetica", size)
    pen.drawString(x, y, text)


def render_v4_receipt_customer_candidate(
    *,
    snapshot,
    project_id,
    approved_msr_id,
    project_code,
    invoice_number,
    invoice_date,
    finances,
    readiness,
):
    """Render a non-issuable draft using the approved V4 layout.

    Equipment serial numbers intentionally remain blank until the
    separate installation-evidence verification is connected.
    A caller-supplied financial report cannot authorize issuance.
    """
    if not isinstance(readiness, FinalReceiptAdjudicationReadiness):
        raise ValueError("Verified equipment readiness required.")

    if (
        readiness.project_id != project_id
        or readiness.msr_id != approved_msr_id
        or readiness.candidate_equipment_review_complete is not True
        or readiness.provisional_ceo_adjudication_complete is not True
        or readiness.expected_equipment_units < 1
        or readiness.verified_ceo_approvals != readiness.expected_equipment_units
        or readiness.trusted_installation_evidence is not False
        or readiness.installation_authorized is not False
        or readiness.final_receipt_issuance_authorized is not False
        or readiness.customer_delivery_verified is not False
        or readiness.completion_authorized is not False
    ):
        raise ValueError("Equipment readiness binding invalid.")

    if type(snapshot) is not dict:
        raise ValueError("Approved MSR snapshot required.")

    if not isinstance(finances, FinalReceiptFinancialEvidence):
        raise ValueError("Final Receipt financial evidence required.")

    if (
        not isinstance(project_id, str)
        or not isinstance(approved_msr_id, str)
        or finances.project_id != project_id
        or finances.approved_msr_id != approved_msr_id
    ):
        raise ValueError("Receipt project/MSR evidence binding mismatch.")

    if not isinstance(invoice_date, date) or type(invoice_date) is not date:
        raise ValueError("Receipt date must be a calendar date.")

    if finances.contract_total != Decimal(str(snapshot.get("total_price"))):
        raise ValueError("Approved price and financial evidence disagree.")

    if finances.overpayment_requires_review:
        raise ValueError("Overpayment requires review before Receipt preparation.")

    if (
        finances.receipt_issuance_authorized
        or finances.customer_delivery_verified
        or finances.project_completion_authorized
    ):
        raise ValueError("Unverified Receipt authority is prohibited.")

    source = verify_approved_final_receipt()

    common = customer_document_data(snapshot)
    projection = revised_invoice_projection(snapshot)
    rows = project_equipment_rows(snapshot)

    if projection.get("notes"):
        raise ValueError(
            "Promotion disclosure placement requires separate approval."
        )

    if len(rows) != 8:
        raise ValueError("Expected eight Receipt equipment rows.")

    for row in rows:
        if any(row.get(key) for key in (
            "model_identification",
            "serial_number",
            "price",
        )):
            raise ValueError(
                "Unverified equipment identification or prices prohibited."
            )

    values = {
        "invoice_date": invoice_date.isoformat(),
        "invoice_number": _text(invoice_number, "invoice_number", 100),
        "project_code": _text(project_code, "project_code", 100),
        "customer_name": _text(common["customer"], "customer_name"),
        "project_address": _text(
            common["project_location"], "project_address"
        ),
        "project_city": _text(common["project_city"], "project_city"),
        "project_state": _text(common["project_state"], "project_state"),
        "project_zip": _text(common["project_zip"], "project_zip"),
        "customer_phone": _text(
            common["customer_phone"], "customer_phone"
        ),
        "customer_email": _text(
            common["customer_email"], "customer_email"
        ),
    }

    page = PdfReader(BytesIO(source.content), strict=True).pages[0]
    layer = BytesIO()
    pen = canvas.Canvas(layer, pagesize=(792, 612))

    for key, (x, y, width) in HEADER_FIELDS.items():
        _draw_fitted(
            pen,
            _text(values[key], key),
            x, y, width,
        )

    for index, row in enumerate(rows):
        top = 353.0 - index * 27.0

        for key, x, width in EQUIPMENT_COLUMNS:
            value = row[key]
            if not value:
                continue

            value = _text(value, f"equipment_{index+1}_{key}")
            size = 7.0
            wrapped = simpleSplit(
                value, "Helvetica", size, width - 3
            )

            if len(wrapped) > 2:
                size = 6.0
                wrapped = simpleSplit(
                    value, "Helvetica", size, width - 3
                )

            if not wrapped or len(wrapped) > 2:
                raise ValueError("Equipment description does not fit.")

            pen.setFillColorRGB(0.04, 0.18, 0.25)
            pen.setFont("Helvetica", size)

            for number, line in enumerate(wrapped):
                pen.drawString(x, top - 11 - number * 8, line)

    for key, y in AMOUNT_BASELINES.items():
        amount = _text(projection[key], key)

        if pen.stringWidth(amount, "Helvetica", 9) > 74:
            raise ValueError("Financial figure does not fit Receipt.")

        pen.setFillColorRGB(1, 1, 1)
        pen.rect(695, y - 3, 68, 13, stroke=0, fill=1)
        pen.setFillColorRGB(0.04, 0.18, 0.25)
        pen.setFont("Helvetica", 9)
        pen.drawRightString(746, y, amount)

    # Mandatory safeguard until installation-stage evidence,
    # immutable retention and issuance authorization are integrated.
    pen.saveState()
    pen.translate(396, 295)
    pen.rotate(32)
    pen.setFillColorRGB(0.65, 0.12, 0.12)
    pen.setFont("Helvetica-Bold", 24)
    pen.drawCentredString(0, 0, "DRAFT - NOT ISSUED")
    pen.restoreState()

    pen.setFillColorRGB(0.65, 0.12, 0.12)
    pen.setFont("Helvetica-Bold", 8)
    pen.drawCentredString(
        396, 598,
        "DRAFT CUSTOMER COPY - NOT AUTHORIZED FOR ISSUANCE"
    )
    pen.save()

    overlay = PdfReader(BytesIO(layer.getvalue()), strict=True).pages[0]
    page.merge_page(overlay)

    writer = PdfWriter()
    writer.add_page(page)
    writer.add_metadata({
        "/Title": "VERIDIAN V4 Receipt - draft, not issued",
        "/VERIDIANApprovedReferenceSHA256": source.sha256,
        "/Subject": "No customer issuance or delivery verification",
    })

    output = BytesIO()
    writer.write(output)
    content = output.getvalue()

    check = PdfReader(BytesIO(content), strict=True)

    if check.is_encrypted or len(check.pages) != 1:
        raise ValueError("Rendered Receipt PDF verification failed.")

    visible = check.pages[0].extract_text() or ""

    for required in (
        values["customer_name"],
        values["invoice_number"],
        "DRAFT - NOT ISSUED",
    ):
        if required not in visible:
            raise ValueError(
                "Required rendered Receipt content missing."
            )

    return RenderedV4CustomerCandidate(
        content=content,
        pdf_sha256=sha256(content).hexdigest(),
        reference_sha256=source.sha256,
        approved_msr_id=approved_msr_id,
        project_id=project_id,
    )
