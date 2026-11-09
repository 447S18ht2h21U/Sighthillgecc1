"""Strictly fictional V4 customer-field PDF previews. No operational release."""
from io import BytesIO

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

from .v2_pdf_overlay_4495 import fictional_preview, checked_text

# PDF coordinates measured in points, bottom-left origin.
# These positions are for the two verified landscape reference layouts.
POSITIONS = {
    "INVOICE": {
        "address_y": 414,
        "contact_y": 395,
    },
    "RECEIPT": {
        "address_y": 419,
        "contact_y": 400,
    },
}

# X positions and maximum permitted text widths.
FIELDS = {
    "project_address": (157, 164),
    "project_city": (377, 109),
    "project_state": (548, 80),
    "project_zip": (718, 52),
    "customer_phone": (149, 174),
    "customer_email": (511, 180),
}


def fictional_customer_preview(reference_bytes, kind, fields):
    """Populate an independent PDF copy; never write to the reference."""
    if kind not in POSITIONS:
        raise ValueError("Unsupported PDF preview kind.")
    if not isinstance(fields, dict):
        raise ValueError("Customer fields must be a dictionary.")

    required = {
        "customer_name", "project_code", *FIELDS,
    }
    if set(fields) != required:
        raise ValueError("Missing or unexpected customer fields.")

    checked = {}
    for key, value in fields.items():
        if key in FIELDS:
            width = FIELDS[key][1]
        elif key == "customer_name":
            width = 165
        else:
            width = 110
        checked[key] = checked_text(value, key, width)

    # The existing validated overlay is the first layer.
    base = fictional_preview(
        reference_bytes, kind,
        checked["customer_name"], checked["project_code"],
    )

    page = PdfReader(BytesIO(base), strict=True).pages[0]
    spec = POSITIONS[kind]

    buffer = BytesIO()
    sheet = canvas.Canvas(buffer, pagesize=(792, 612))
    sheet.setFont("Helvetica", 9)

    for name in ("project_address", "project_city",
                 "project_state", "project_zip"):
        x, _ = FIELDS[name]
        sheet.drawString(x, spec["address_y"], checked[name])

    for name in ("customer_phone", "customer_email"):
        x, _ = FIELDS[name]
        sheet.drawString(x, spec["contact_y"], checked[name])

    sheet.save()
    buffer.seek(0)

    writer = PdfWriter()
    writer.add_page(page)
    writer.pages[0].merge_page(
        PdfReader(buffer, strict=True).pages[0]
    )

    result_buffer = BytesIO()
    writer.write(result_buffer)
    result = result_buffer.getvalue()

    rendered = PdfReader(BytesIO(result), strict=True)
    if len(rendered.pages) != 1:
        raise ValueError("Unexpected preview page count.")

    extracted = rendered.pages[0].extract_text() or ""
    for value in checked.values():
        if value not in extracted:
            raise ValueError("Missing verified customer preview value.")

    return result
