"""Isolated fictional PDF overlay proof; never authorizes document release."""
from hashlib import sha256
from io import BytesIO

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth

CONFIG = {
    "INVOICE": {
        "sha256": "8665F93C928F146BC3371DEC7153ADA731F39493BE00B240D6B610C9E5BFEB6E",
        "width": 792, "height": 612,
        "name": (143, 434),
        "code": (645, 454),
    },
    "RECEIPT": {
        "sha256": "02F94BA72A5FAE593278A2C781659FC97B0001A692216C8780D066C38155E300",
        "width": 792, "height": 612,
        "name": (143, 439),
        "code": (645, 459),
    },
}


def checked_text(value, label, maximum_width):
    if type(value) is not str or not value.strip():
        raise ValueError(f"{label} must be nonempty text.")
    value = value.strip()
    if any(ord(ch) < 32 or ord(ch) > 126 for ch in value):
        raise ValueError(f"{label} contains unsupported characters.")
    if stringWidth(value, "Helvetica", 9) > maximum_width:
        raise ValueError(f"{label} does not fit the verified preview field.")
    return value


def fictional_preview(reference_bytes, kind, customer, project_code):
    """Return new PDF bytes; never modify the supplied reference."""
    if kind not in CONFIG:
        raise ValueError("Unsupported PDF overlay kind.")
    if type(reference_bytes) is not bytes:
        raise ValueError("Reference must be immutable PDF bytes.")

    spec = CONFIG[kind]
    if sha256(reference_bytes).hexdigest().upper() != spec["sha256"]:
        raise ValueError("PDF reference fingerprint mismatch.")

    customer = checked_text(customer, "Customer", 165)
    project_code = checked_text(project_code, "Project code", 110)

    if "FICTIONAL" not in customer.upper():
        raise ValueError("Only explicitly fictional customers are allowed.")

    reader = PdfReader(BytesIO(reference_bytes), strict=True)
    if len(reader.pages) != 1:
        raise ValueError("Expected exactly one reference page.")

    page = reader.pages[0]
    if (round(float(page.mediabox.width)), round(float(page.mediabox.height))) != (
        spec["width"], spec["height"]
    ):
        raise ValueError("Unexpected reference page dimensions.")

    overlay_buffer = BytesIO()
    sheet = canvas.Canvas(
        overlay_buffer,
        pagesize=(spec["width"], spec["height"]),
        pageCompression=1,
    )
    sheet.setFont("Helvetica", 9)
    sheet.drawString(*spec["name"], customer)
    sheet.drawString(*spec["code"], project_code)
    sheet.save()

    overlay_buffer.seek(0)
    overlay = PdfReader(overlay_buffer, strict=True)
    writer = PdfWriter()
    writer.add_page(page)
    writer.pages[0].merge_page(overlay.pages[0])

    output = BytesIO()
    writer.write(output)
    result = output.getvalue()

    rendered = PdfReader(BytesIO(result), strict=True)
    extracted = rendered.pages[0].extract_text() or ""
    if customer not in extracted or project_code not in extracted:
        raise ValueError("Populated PDF content verification failed.")

    return result