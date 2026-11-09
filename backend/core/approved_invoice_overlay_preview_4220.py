"""Fictional development-only Invoice PDF overlay preview.

Uses a verified approved reference original. No customer release,
signatures, equipment identification, payment, or database writes.
Coordinates are provisional pending visual acceptance.
"""
from hashlib import sha256
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

from .approved_pdf_reference_integrity_4217 import verify_reference
from .msr_document_source import customer_document_data


# PDF coordinates: origin at bottom-left, landscape 792 x 612 points.
# (x, baseline_y, maximum_width)
INVOICE_FIELD_POSITIONS = {
    "invoice_date": (117, 474, 95),
    "invoice_number": (315, 474, 132),
    "project_code": (622, 474, 125),
    "customer_name": (137, 455, 190),
    "project_address": (152, 435, 175),
    "project_city": (369, 435, 117),
    "project_state": (537, 435, 90),
    "project_zip": (699, 435, 48),
    "customer_phone": (140, 416, 187),
    "customer_email": (500, 416, 187),
}


def _safe_text(value):
    if type(value) is not str or not value.strip():
        raise ValueError("A nonempty fictional preview text field is required.")
    if any(ord(char) < 32 or ord(char) > 126 for char in value):
        raise ValueError("Preview text must be printable ASCII.")
    if len(value) > 160:
        raise ValueError("Preview text exceeds the permitted length.")
    return value


def create_invoice_preview(directory, snapshot, project_code,
                           invoice_number, invoice_date):
    verified = verify_reference(directory, "INVOICE")
    source = Path(directory) / verified.filename
    original = source.read_bytes()

    common = customer_document_data(snapshot)

    values = {
        "invoice_date": _safe_text(invoice_date),
        "invoice_number": _safe_text(invoice_number),
        "project_code": _safe_text(project_code),
        "customer_name": _safe_text(common["customer"]),
        "project_address": _safe_text(common["project_location"]),
        "project_city": _safe_text(common["project_city"]),
        "project_state": _safe_text(common["project_state"]),
        "project_zip": _safe_text(common["project_zip"]),
        "customer_phone": _safe_text(common["customer_phone"]),
        "customer_email": _safe_text(common["customer_email"]),
    }

    reader = PdfReader(BytesIO(original), strict=True)
    if len(reader.pages) != 1:
        raise ValueError("Approved Invoice page count changed.")

    width = float(reader.pages[0].mediabox.width)
    height = float(reader.pages[0].mediabox.height)

    if (width, height) != (792.0, 612.0):
        raise ValueError("Approved Invoice page geometry changed.")

    overlay = BytesIO()
    pen = canvas.Canvas(overlay, pagesize=(width, height))

    for key, (x, y, max_width) in INVOICE_FIELD_POSITIONS.items():
        value = values[key]
        font_size = 8.5

        while font_size >= 6.5:
            if pen.stringWidth(value, "Helvetica", font_size) <= max_width:
                break
            font_size -= 0.5
        else:
            raise ValueError(f"Preview field does not fit: {key}")

        # A temporary white area hides only the blank underline.
        # Review visually before approving placement for production.
        pen.setFillColorRGB(1, 1, 1)
        pen.rect(x - 1, y - 3, max_width + 1, 13,
                 fill=1, stroke=0)

        pen.setFillColorRGB(0.04, 0.18, 0.25)
        pen.setFont("Helvetica", font_size)
        pen.drawString(x, y, value)

    # Clearly mark this as fictional development evidence.
    pen.saveState()
    pen.translate(width / 2, height / 2)
    pen.rotate(32)
    pen.setFillColorRGB(0.75, 0.14, 0.14)
    pen.setFont("Helvetica-Bold", 26)
    pen.drawCentredString(
        0, 0, "FICTIONAL DEVELOPMENT PREVIEW"
    )
    pen.restoreState()

    pen.setFillColorRGB(0.75, 0.12, 0.12)
    pen.setFont("Helvetica-Bold", 9)
    pen.drawCentredString(
        width / 2, height - 16,
        "TEST ONLY - NOT AN INVOICE FOR PAYMENT OR CUSTOMER USE"
    )
    pen.save()

    overlay.seek(0)
    writer = PdfWriter()
    page = writer.add_page(reader.pages[0])
    page.merge_page(PdfReader(overlay).pages[0])

    writer.add_metadata({
        "/Title": "VERIDIAN fictional Invoice overlay preview",
        "/Subject": "Development only - no payment or delivery authorization",
        "/VERIDIANApprovedReferenceSHA256": verified.sha256,
    })

    stream = BytesIO()
    writer.write(stream)
    result = stream.getvalue()

    if len(PdfReader(BytesIO(result)).pages) != 1:
        raise ValueError("Preview PDF verification failed.")

    if sha256(source.read_bytes()).digest() != sha256(original).digest():
        raise ValueError("Approved Invoice original changed.")

    return result