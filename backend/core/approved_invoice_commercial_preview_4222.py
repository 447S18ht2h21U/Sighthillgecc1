"""Fictional approved Invoice preview with reconciled MSR commercial values.

No database access, payment assertion, customer delivery or live route.
Existing approved customer/equipment placement is retained.
"""
from io import BytesIO
from hashlib import sha256
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import simpleSplit

from .approved_invoice_equipment_preview_4221 import (
    create_equipment_invoice_preview,
)
from .invoice_msr_projection import revised_invoice_projection


# Approved Invoice is 792 x 612 points, PDF origin at bottom-left.
# Financial positions are provisional until visual acceptance.
AMOUNT_POSITIONS = {
    "subtotal": 107,
    "sales_tax": 86,
    "other_charges": 65,
    "invoice_total": 44,
}


def _printable(value, label, limit=350):
    if type(value) is not str:
        raise ValueError(f"{label} must be text.")
    if len(value) > limit or any(
        ord(c) < 32 or ord(c) > 126 for c in value
    ):
        raise ValueError(f"{label} contains unsupported text.")
    return value


def create_commercial_invoice_preview(
    directory, snapshot, project_code, invoice_number, invoice_date
):
    """Add approved financial projection to the reviewed equipment preview."""
    projection = revised_invoice_projection(snapshot)

    source = Path(directory) / "GECC Invoice ref1103.pdf"
    before = sha256(source.read_bytes()).hexdigest()

    base_pdf = create_equipment_invoice_preview(
        directory, snapshot, project_code, invoice_number, invoice_date
    )
    reader = PdfReader(BytesIO(base_pdf), strict=True)
    if len(reader.pages) != 1:
        raise ValueError("Invoice must contain exactly one page.")

    page = reader.pages[0]
    if (
        float(page.mediabox.width),
        float(page.mediabox.height)
    ) != (792.0, 612.0):
        raise ValueError("Approved Invoice geometry mismatch.")

    layer = BytesIO()
    pen = canvas.Canvas(layer, pagesize=(792, 612))

    for key, baseline in AMOUNT_POSITIONS.items():
        value = _printable(projection[key], key, limit=32)

        if not value:
            raise ValueError(f"Missing commercial field: {key}")

        pen.setFont("Helvetica", 9)
        if pen.stringWidth(value, "Helvetica", 9) > 74:
            raise ValueError(f"Commercial field exceeds space: {key}")

        # Write only inside the empty amount cell, not over its label.
        pen.setFillColorRGB(1, 1, 1)
        pen.rect(706, baseline - 3, 79, 13, stroke=0, fill=1)
        pen.setFillColorRGB(0.04, 0.18, 0.25)
        pen.drawRightString(778, baseline, value)

    notes = _printable(projection["notes"], "notes")

    if notes:
        lines = simpleSplit(notes, "Helvetica", 8, 380)

        if len(lines) > 3:
            raise ValueError(
                "Invoice notes exceed the approved three-line preview area."
            )

        pen.setFillColorRGB(0.04, 0.18, 0.25)
        pen.setFont("Helvetica", 8)

        for index, line in enumerate(lines):
            pen.drawString(23, 83 - index * 12, line)

    pen.save()

    writer = PdfWriter()
    output_page = writer.add_page(page)
    output_page.merge_page(
        PdfReader(BytesIO(layer.getvalue()), strict=True).pages[0]
    )

    writer.add_metadata({
        "/Title": "VERIDIAN fictional complete Invoice preview",
        "/Subject": "Development only; no customer invoice or payment request",
        "/VERIDIANInvoiceProjection": "MSR reconciled",
    })

    stream = BytesIO()
    writer.write(stream)
    result = stream.getvalue()

    verification = PdfReader(BytesIO(result), strict=True)
    if len(verification.pages) != 1:
        raise ValueError("Commercial preview PDF verification failed.")

    text = verification.pages[0].extract_text() or ""
    for key in AMOUNT_POSITIONS:
        if projection[key] not in text:
            raise ValueError(f"Rendered financial value missing: {key}")

    if notes and notes.split()[0] not in text:
        raise ValueError("Rendered Invoice notes missing.")

    if sha256(source.read_bytes()).hexdigest() != before:
        raise ValueError("Approved Invoice original changed.")

    return result