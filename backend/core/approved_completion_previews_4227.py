"""Fictional previews for approved financed/non-financed certificates.

These are not completion evidence, customer signatures, lender requests,
funding assignments, or authorization to release documents.
Original approved legal language is preserved without modification.
"""
from hashlib import sha256
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth

from .approved_pdf_reference_integrity_4217 import verify_reference
from .msr_document_source import customer_document_data


KIND_BY_FINANCING = {
    "FINANCED": "COMPLETION_FINANCED",
    "NON_FINANCED": "COMPLETION_NON_FINANCED",
}

# Provisional positions in a 612 x 792 coordinate system.
# Signatures and completion dates are never populated.
POSITIONS = {
    "COMPLETION_NON_FINANCED": {
        # From the approved original's printed underline positions.
        "customer_name": (113, 333, 106),
        "project_address": (76, 278, 146),
        "project_city": (265, 278, 117),
        "project_state": (431, 278, 26),
        "project_zip": (496, 278, 43),
        "project_code": (189, 234, 100),
    },
    "COMPLETION_FINANCED": {
        "customer_name": (113, 136, 129),
        "project_address": (76, 103, 167),
        "project_city": (288, 103, 116),
        "project_state": (454, 103, 26),
        "project_zip": (519, 103, 43),
        "project_code": (189, 70, 100),
    },
}


def _text(value, field):
    if type(value) is not str or not value.strip():
        raise ValueError(f"Required completion preview field: {field}")
    if len(value) > 150 or any(
        ord(c) < 32 or ord(c) > 126 for c in value
    ):
        raise ValueError(f"Unsupported completion preview text: {field}")
    return value


def create_completion_preview(directory, snapshot, project_code, kind):
    """Overlay shared MSR identity only onto the verified PDF copy."""
    if kind not in POSITIONS:
        raise ValueError("Unknown approved completion type.")
    if type(snapshot) is not dict:
        raise ValueError("An approved MSR snapshot is required.")

    financing = snapshot.get("financing_type")
    if KIND_BY_FINANCING.get(financing) != kind:
        raise ValueError(
            "Completion certificate financing must match the MSR."
        )

    verified = verify_reference(directory, kind)
    original_path = Path(directory) / verified.filename
    original_bytes = original_path.read_bytes()
    common = customer_document_data(snapshot)

    values = {
        "customer_name": _text(common["customer"], "customer_name"),
        "project_address": _text(
            common["project_location"], "project_address"
        ),
        "project_city": _text(common["project_city"], "project_city"),
        "project_state": _text(common["project_state"], "project_state"),
        "project_zip": _text(common["project_zip"], "project_zip"),
        "project_code": _text(project_code, "project_code"),
    }

    reader = PdfReader(BytesIO(original_bytes), strict=True)
    if len(reader.pages) != 1:
        raise ValueError("Completion original must be one page.")

    page = reader.pages[0]
    width = float(page.mediabox.width)
    height = float(page.mediabox.height)

    if not (550 <= width <= 650 and 740 <= height <= 850):
        raise ValueError("Unexpected completion certificate geometry.")

    overlay = BytesIO()
    pen = canvas.Canvas(overlay, pagesize=(width, height))

    # Scale provisional coordinates for matching portrait paper sizes.
    sx = width / 612.0
    sy = height / 792.0

    for field, (x, y, maximum) in POSITIONS[kind].items():
        value = values[field]
        available = maximum * sx
        font_size = 8.0 * min(sx, sy)

        while font_size >= 5.0:
            if stringWidth(value, "Helvetica", font_size) <= available:
                break
            font_size -= 0.5
        else:
            raise ValueError(
                f"Completion preview field does not fit: {field}"
            )

        pen.setFillColorRGB(0.04, 0.18, 0.25)
        pen.setFont("Helvetica", font_size)
        pen.drawString(x * sx, y * sy, value)

    # Never draw on customer signature or date lines.
    # The original's financing clauses remain completely unchanged.
    pen.saveState()
    pen.translate(width / 2, height / 2)
    pen.rotate(32)
    pen.setFillColorRGB(0.74, 0.12, 0.12)
    pen.setFont("Helvetica-Bold", 23)
    pen.drawCentredString(0, 0, "FICTIONAL DEVELOPMENT PREVIEW")
    pen.restoreState()

    pen.setFillColorRGB(0.72, 0.10, 0.10)
    pen.setFont("Helvetica-Bold", 7.5)
    pen.drawCentredString(
        width / 2,
        height - 15,
        "TEST ONLY - WORK NOT VERIFIED - DO NOT SIGN OR SEND",
    )
    pen.save()

    writer = PdfWriter()
    output_page = writer.add_page(page)
    output_page.merge_page(
        PdfReader(BytesIO(overlay.getvalue()), strict=True).pages[0]
    )
    writer.add_metadata({
        "/Title": f"VERIDIAN fictional completion preview {kind}",
        "/Subject": "No verified completion, signature, or financing approval",
        "/VERIDIANApprovedReferenceSHA256": verified.sha256,
    })

    stream = BytesIO()
    writer.write(stream)
    result = stream.getvalue()

    check = PdfReader(BytesIO(result), strict=True)
    if len(check.pages) != 1:
        raise ValueError("Completion preview verification failed.")

    visible = check.pages[0].extract_text() or ""
    for required in (
        values["customer_name"],
        values["project_code"],
        "FICTIONAL DEVELOPMENT PREVIEW",
        "WORK NOT VERIFIED",
    ):
        if required not in visible:
            raise ValueError(f"Missing completion preview text: {required}")

    if sha256(original_path.read_bytes()).digest() != sha256(original_bytes).digest():
        raise ValueError("Approved completion original changed.")

    return result