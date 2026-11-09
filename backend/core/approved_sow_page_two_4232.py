"""Development-only overlay on page two of the approved two-page SOW.

Keeps original artwork and wording unchanged. Does not populate signatures,
authorize payment, or register operational routes. Long explanations remain
available in the separate development appendix, without silent truncation.
"""
from hashlib import sha256
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth

from .approved_sow_commercial_4231 import (
    make_sow_commercial_review,
    sow_commercial_projection,
)


# Coordinates from the approved 612 x 792 point page-two design.
# Provisional until user visual acceptance.
POSITIONS = {
    "promotion_amount": (261, 577, 285),
    "promotion_description": (261, 561, 285),
    "promotion_notes": (261, 544, 285),
    "work_scope": (218, 492, 344),
    "installation_details": (218, 471, 344),
    "additional_notes": (218, 450, 344),
    "base_price": (283, 385, 265),
    "discount": (283, 369, 265),
    "total_price": (283, 353, 265),
    "payment_notes": (283, 320, 265),
    "financing": (283, 304, 265),
}


def _text(value, label):
    if type(value) is not str:
        raise ValueError(f"Invalid SOW display value: {label}.")
    if any(ord(c) < 32 or ord(c) > 126 for c in value):
        raise ValueError(f"Unsupported SOW display characters: {label}.")
    return value


def _draw(pen, key, value):
    x, y, maximum = POSITIONS[key]
    text = _text(value, key).strip()
    if not text:
        return
    font = 8.0
    while font >= 6.0 and stringWidth(text, "Helvetica", font) > maximum:
        font -= 0.5
    if font < 6.0:
        # Do not truncate. Detailed wording remains in the appended
        # fictional review page for explicit visual review.
        text = "See development detail appendix"
        font = 8.0
    pen.setFillColorRGB(0.04, 0.18, 0.25)
    pen.setFont("Helvetica", font)
    pen.drawString(x, y, text)


def create_page_two_sow_preview(directory, snapshot, project_code,
                                msr_version, created, associate):
    data = sow_commercial_projection(snapshot)
    reference = Path(directory) / "GECC Project Scope of Work ref1103a.pdf"
    original_hash = sha256(reference.read_bytes()).hexdigest()

    # Reuse the existing full MSR projection and retained review appendix.
    base = make_sow_commercial_review(
        directory, snapshot, project_code, msr_version, created, associate
    )
    reader = PdfReader(BytesIO(base), strict=True)
    if len(reader.pages) != 3:
        raise ValueError("Expected two SOW pages and a development appendix.")

    original = PdfReader(BytesIO(reference.read_bytes()), strict=True)
    if len(original.pages) != 2:
        raise ValueError("Approved SOW original page count changed.")

    page = reader.pages[1]
    width = float(page.mediabox.width)
    height = float(page.mediabox.height)
    if (width, height) != (612.0, 792.0):
        raise ValueError("Approved page-two geometry changed.")

    other = data["promotion"]
    notes = data["commercial_notes"]
    # The printed promotional checkbox selection will require separate
    # visual approval; classification remains explicit in its text entry.
    values = {
        "promotion_amount": other["amount"] if other else "0.00",
        "promotion_description": (
            f'{other["type"]}: {other["notes"]}' if other else "None"
        ),
        "promotion_notes": notes,
        "work_scope": data["scope"],
        "installation_details": snapshot.get("installation_details", ""),
        "additional_notes": snapshot.get("additional_project_notes", ""),
        "base_price": data["subtotal"],
        "discount": data["other_charges"],
        "total_price": data["total"],
        "payment_notes": snapshot.get("payment_terms", ""),
        "financing": data["financing_type"].replace("_", "-").title(),
    }

    layer = BytesIO()
    pen = canvas.Canvas(layer, pagesize=(width, height))
    for key, value in values.items():
        _draw(pen, key, value)

    pen.setFillColorRGB(0.70, 0.10, 0.10)
    pen.setFont("Helvetica-Bold", 7)
    pen.drawCentredString(
        width / 2, 778,
        "DEVELOPMENT PREVIEW - FIELD POSITIONS NOT YET APPROVED"
    )
    pen.save()

    writer = PdfWriter()
    for original_page in reader.pages:
        writer.add_page(original_page)

    writer.pages[1].merge_page(
        PdfReader(BytesIO(layer.getvalue()), strict=True).pages[0]
    )
    writer.add_metadata({
        "/Title": "VERIDIAN fictional SOW page-two integration preview",
        "/Subject": "Unapproved visual layout; no signature or customer delivery",
        "/VERIDIANOriginalSHA256": original_hash.upper(),
    })

    output = BytesIO()
    writer.write(output)
    result = output.getvalue()
    verified = PdfReader(BytesIO(result), strict=True)
    if len(verified.pages) != 3:
        raise ValueError("Final preview page-count mismatch.")

    page_text = verified.pages[1].extract_text() or ""
    for value in (data["subtotal"], data["other_charges"], data["total"]):
        if value not in page_text:
            raise ValueError("Missing SOW commercial value in actual page two.")

    if sha256(reference.read_bytes()).hexdigest() != original_hash:
        raise ValueError("Approved SOW original changed.")

    return result