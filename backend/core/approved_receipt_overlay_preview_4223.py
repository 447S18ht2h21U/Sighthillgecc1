"""Fictional, development-only overlay of the approved GECC Receipt PDF.

No operational receipt generation, no payment assertion, no signatures,
no delivery, and no database writes. Serial and model identification
require independent installation-stage evidence and remain empty here.
"""
from hashlib import sha256
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import simpleSplit

from .approved_pdf_reference_integrity_4217 import verify_reference
from .equipment_invoice_rows import project_equipment_rows
from .invoice_msr_projection import revised_invoice_projection
from .msr_document_source import customer_document_data


# Development coordinates measured on the approved 792 x 612 PDF.
# Visual acceptance is required before production mapping.
HEADER_FIELDS = {
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

# The Receipt has seven equipment columns, unlike the Invoice.
EQUIPMENT_COLUMNS = (
    ("category", 36, 68),
    ("brand", 112, 64),
    ("system_type", 184, 174),
    ("model_number", 368, 101),
)

AMOUNT_BASELINES = {
    "subtotal": 111,
    "sales_tax": 90,
    "other_charges": 69,
    "invoice_total": 48,
}


def _text(value, label):
    if type(value) is not str or not value.strip():
        raise ValueError(f"Missing Receipt preview value: {label}")
    if len(value) > 160 or any(
        ord(character) < 32 or ord(character) > 126
        for character in value
    ):
        raise ValueError(f"Unsupported Receipt preview value: {label}")
    return value


def create_receipt_preview(
    directory, snapshot, project_code, invoice_number, invoice_date
):
    """Prepare an unsigned and unpaid-claim-free fictional Receipt."""
    verified = verify_reference(directory, "RECEIPT")
    original_path = Path(directory) / verified.filename
    original = original_path.read_bytes()

    common = customer_document_data(snapshot)
    projection = revised_invoice_projection(snapshot)
    rows = project_equipment_rows(snapshot)

    # This one-page approved Receipt has a survey, not an Invoice
    # Notes area. Never silently discard promotion disclosures.
    if projection["notes"]:
        raise ValueError(
            "Promotion details require an approved Receipt disclosure "
            "placement before this document can be prepared."
        )

    values = {
        "invoice_date": _text(invoice_date, "invoice_date"),
        "invoice_number": _text(invoice_number, "invoice_number"),
        "project_code": _text(project_code, "project_code"),
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

    reader = PdfReader(BytesIO(original), strict=True)

    if len(reader.pages) != 1:
        raise ValueError("Approved Receipt page count changed.")

    page = reader.pages[0]
    if (
        float(page.mediabox.width),
        float(page.mediabox.height),
    ) != (792.0, 612.0):
        raise ValueError("Approved Receipt geometry changed.")

    layer = BytesIO()
    pen = canvas.Canvas(layer, pagesize=(792, 612))

    # Customer and project fields from the approved MSR.
    for key, (x, y, maximum) in HEADER_FIELDS.items():
        value = values[key]
        size = 8.5

        while size >= 6.5:
            if pen.stringWidth(value, "Helvetica", size) <= maximum:
                break
            size -= 0.5
        else:
            raise ValueError(f"Receipt field does not fit: {key}")

        pen.setFillColorRGB(1, 1, 1)
        pen.rect(x - 1, y - 3, maximum + 1, 13, stroke=0, fill=1)
        pen.setFillColorRGB(0.04, 0.18, 0.25)
        pen.setFont("Helvetica", size)
        pen.drawString(x, y, value)

    # Eight approved MSR equipment rows. Installation-stage
    # evidence cannot be invented or derived from the MSR.
    for index, row in enumerate(rows):
        if any(row[key] for key in (
            "model_identification", "serial_number", "price"
        )):
            raise ValueError(
                "Unverified unit identification or prices are forbidden."
            )

        top = 353.0 - index * 27.0

        for key, x, maximum in EQUIPMENT_COLUMNS:
            value = row[key]
            if not value:
                continue

            value = _text(value, f"equipment_{index + 1}_{key}")
            size = 7.0
            lines = simpleSplit(
                value, "Helvetica", size, maximum - 3
            )

            if len(lines) > 2:
                size = 6.0
                lines = simpleSplit(
                    value, "Helvetica", size, maximum - 3
                )

            if not lines or len(lines) > 2:
                raise ValueError(
                    f"Receipt equipment row {index + 1} does not fit."
                )

            pen.setFillColorRGB(0.04, 0.18, 0.25)
            pen.setFont("Helvetica", size)

            for number, line in enumerate(lines):
                pen.drawString(x, top - 11 - number * 8, line)

    # Financial figures are projections from the approved MSR,
    # not evidence that the customer has paid.
    for key, y in AMOUNT_BASELINES.items():
        value = _text(projection[key], key)

        if pen.stringWidth(value, "Helvetica", 9) > 74:
            raise ValueError(f"Receipt amount does not fit: {key}")

        pen.setFillColorRGB(1, 1, 1)
        pen.rect(695, y - 3, 68, 13, stroke=0, fill=1)
        pen.setFillColorRGB(0.04, 0.18, 0.25)
        pen.setFont("Helvetica", 9)
        pen.drawRightString(746, y, value)

    # Preserve the approved three-question customer survey.
    # Watermark the complete page as a non-payable test preview.
    pen.saveState()
    pen.translate(396, 295)
    pen.rotate(32)
    pen.setFillColorRGB(0.75, 0.14, 0.14)
    pen.setFont("Helvetica-Bold", 22)
    pen.drawCentredString(
        0, 0, "FICTIONAL RECEIPT PREVIEW"
    )
    pen.restoreState()

    pen.setFillColorRGB(0.73, 0.10, 0.10)
    pen.setFont("Helvetica-Bold", 8)
    pen.drawCentredString(
        396, 598,
        "DEVELOPMENT ONLY - PAYMENT NOT VERIFIED - DO NOT SEND"
    )
    pen.save()

    writer = PdfWriter()
    output_page = writer.add_page(page)
    output_page.merge_page(
        PdfReader(BytesIO(layer.getvalue()), strict=True).pages[0]
    )

    writer.add_metadata({
        "/Title": "VERIDIAN fictional Receipt preview",
        "/Subject": (
            "Development-only Receipt layout. "
            "No payment or delivery verification."
        ),
        "/VERIDIANApprovedReferenceSHA256": verified.sha256,
    })

    stream = BytesIO()
    writer.write(stream)
    result = stream.getvalue()

    check = PdfReader(BytesIO(result), strict=True)
    if len(check.pages) != 1:
        raise ValueError("Receipt preview verification failed.")

    visible = check.pages[0].extract_text() or ""

    for required in (
        values["customer_name"],
        values["invoice_number"],
        "FICTIONAL RECEIPT PREVIEW",
        "PAYMENT NOT VERIFIED",
    ):
        if required not in visible:
            raise ValueError(
                f"Required Receipt preview text missing: {required}"
            )

    if sha256(original_path.read_bytes()).digest() != sha256(original).digest():
        raise ValueError("Approved Receipt original changed.")

    return result