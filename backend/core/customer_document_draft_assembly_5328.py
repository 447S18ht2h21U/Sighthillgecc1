"""Detached, non-issuable assembly of draft customer-document PDFs.

The first page must already be a marked draft. Financial and promotional
values come from the MSR projection. This module cannot authorize or
deliver customer documents.
"""
from hashlib import sha256
from io import BytesIO

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

from .customer_schedule_continuation_5326 import (
    render_schedule_continuation,
)
from .invoice_msr_projection import revised_invoice_projection

MARKER = "DRAFT - NOT ISSUED"


def _read_pdf(content):
    if type(content) is not bytes or not content:
        raise ValueError("Valid PDF bytes required.")
    reader = PdfReader(BytesIO(content), strict=True)
    if reader.is_encrypted or not reader.pages:
        raise ValueError("Unreadable or encrypted draft PDF.")
    return reader


def _draft_overlay(width, height):
    buffer = BytesIO()
    pen = canvas.Canvas(buffer, pagesize=(width, height))
    pen.saveState()
    pen.setFillColorRGB(0.65, 0.12, 0.12)
    pen.setFont("Helvetica-Bold", 17)
    pen.translate(width / 2, height / 2)
    pen.rotate(32)
    pen.drawCentredString(0, 0, MARKER)
    pen.restoreState()
    pen.setFillColorRGB(0.65, 0.12, 0.12)
    pen.setFont("Helvetica-Bold", 8)
    pen.drawCentredString(
        width / 2, height - 15,
        "DRAFT CUSTOMER DOCUMENT - NOT AUTHORIZED FOR ISSUANCE"
    )
    pen.save()
    return PdfReader(BytesIO(buffer.getvalue()), strict=True).pages[0]


def assemble_draft_document(
    *,
    first_page_pdf,
    snapshot,
    project_code,
    document_kind,
    equipment_start=8,
):
    """Append complete unpriced schedule to a verified draft first page.

    The approved MSR and first-page financial rendering remain separate
    authorization responsibilities. No changes to operational PDF routes.
    """
    if document_kind not in ("INVOICE", "RECEIPT", "AGREEMENT"):
        raise ValueError("Unsupported document type.")
    if type(snapshot) is not dict:
        raise ValueError("MSR snapshot required.")

    first = _read_pdf(first_page_pdf)
    if len(first.pages) != 1:
        raise ValueError("Exactly one draft first page is required.")
    first_text = first.pages[0].extract_text() or ""
    if MARKER not in first_text:
        raise ValueError("Unmarked first page is prohibited.")

    # Validate financial treatment and obtain only recorded MSR notes.
    projection = revised_invoice_projection(snapshot)
    notes = projection.get("notes") or ""

    appendix = render_schedule_continuation(
        snapshot=snapshot,
        project_code=project_code,
        document_kind=document_kind,
        equipment_start=equipment_start,
        promotion_notes=notes,
    )

    writer = PdfWriter()
    writer.add_page(first.pages[0])

    if appendix:
        extra = _read_pdf(appendix)
        for source_page in extra.pages:
            width = float(source_page.mediabox.width)
            height = float(source_page.mediabox.height)
            source_page.merge_page(_draft_overlay(width, height))
            writer.add_page(source_page)

    writer.add_metadata({
        "/Title": f"{document_kind} draft - NOT ISSUED",
        "/Subject": "Development-only customer document preview",
        "/VERIDIANIssuanceAuthorized": "false",
    })

    output = BytesIO()
    writer.write(output)
    content = output.getvalue()

    check = _read_pdf(content)
    visible = [page.extract_text() or "" for page in check.pages]
    if not all(MARKER in text for text in visible):
        raise ValueError("A draft page is missing its non-issuance mark.")
    if len(check.pages) != 1 + (
        len(_read_pdf(appendix).pages) if appendix else 0
    ):
        raise ValueError("Draft page count mismatch.")

    # Verify the final equipment and material entries survived assembly.
    if appendix:
        continuation_text = "\n".join(visible[1:])
        equipment = snapshot.get("equipment", [])
        materials = snapshot.get("materials", [])
        if len(equipment) > equipment_start:
            last_model = equipment[-1]["model_number"]
            if last_model not in continuation_text:
                raise ValueError("Last equipment entry is missing.")
        if materials:
            last_material = materials[-1]["description"]
            if last_material not in continuation_text:
                raise ValueError("Last material entry is missing.")
        if notes and notes not in continuation_text:
            # Text extraction may insert line wraps. Require all note words.
            words = notes.split()
            if not words or not all(
                word in continuation_text for word in words
            ):
                raise ValueError("Promotional disclosure is missing.")

    return {
        "content": content,
        "sha256": sha256(content).hexdigest(),
        "page_count": len(check.pages),
        "status": "DRAFT_NOT_ISSUED",
    }
