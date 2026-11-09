"""Fictional MSR and Agreement PDF population; never authorizes release."""
from hashlib import sha256
from io import BytesIO

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth

from .v2_document_mapping_4489 import project_document_projection_v2, reference_details

GEOMETRY = {
    "CUSTOMER_SOW": (2, 612, 792),
    "AGREEMENT": (3, 612, 792),
}

def _fit(value, label, maximum, allow_blank=False):
    if type(value) is not str:
        raise ValueError(f"{label} must be text.")
    value = value.strip()
    if not allow_blank and not value:
        raise ValueError(f"{label} is required.")
    if any(ord(c) < 32 or ord(c) > 126 for c in value):
        raise ValueError(f"{label} contains unsupported characters.")
    if stringWidth(value, "Helvetica", 8) > maximum:
        raise ValueError(f"{label} exceeds available PDF field width.")
    return value

def fictional_document_preview(reference_bytes, kind, snapshot,
                               project_code, msr_version,
                               creation_date="", sales_associate=""):
    """Populate an independent preview from the MSR; no approvals are asserted."""
    if kind not in GEOMETRY:
        raise ValueError("Unsupported document kind.")
    if type(reference_bytes) is not bytes:
        raise ValueError("Reference must be immutable bytes.")

    details = reference_details(kind)
    if sha256(reference_bytes).hexdigest().upper() != details["sha256"]:
        raise ValueError("PDF reference fingerprint mismatch.")

    projection = project_document_projection_v2(
        snapshot, kind, project_code, msr_version
    )
    if "FICTIONAL" not in projection["customer_name"].upper():
        raise ValueError("Only fictional customer previews are permitted.")
    if projection["send_authorized"] or projection["legally_eligible_for_installation"]:
        raise ValueError("Preview must not assert release or legal eligibility.")

    reader = PdfReader(BytesIO(reference_bytes), strict=True)
    count, width, height = GEOMETRY[kind]
    if len(reader.pages) != count:
        raise ValueError("Unexpected reference page count.")
    for page in reader.pages:
        if (round(float(page.mediabox.width)),
            round(float(page.mediabox.height))) != (width, height):
            raise ValueError("Unexpected PDF page geometry.")

    # Coordinates were inspected from the approved November 7 references.
    if kind == "CUSTOMER_SOW":
        rows = (
            ("customer_name", 270, 596.6, 282),
            ("customer_phone", 270, 573.1, 282),
            ("customer_email", 270, 549.5, 282),
            ("project_address", 270, 526.0, 282),
            ("creation_date", 270, 502.5, 282),
            ("project_code", 270, 479.0, 282),
            ("sales_associate", 270, 455.6, 282),
        )
        values = dict(projection, creation_date=creation_date,
                      sales_associate=sales_associate)
    else:
        # Only the address blanks on Agreement page one are populated.
        # Legal text, signature fields and later pages remain untouched.
        rows = (
            ("project_address", 278, 510.5, 101),
            ("project_city", 470, 510.5, 90),
            ("project_state", 132, 497.0, 28),
            ("project_zip", 235, 497.0, 64),
        )
        values = projection

    layer = BytesIO()
    pen = canvas.Canvas(layer, pagesize=(width, height))
    pen.setFont("Helvetica", 8)

    checked = []
    for key, x, y, maximum in rows:
        value = _fit(values[key], key, maximum)
        pen.drawString(x, y, value)
        checked.append(value)

    pen.setFont("Helvetica-Bold", 7)
    pen.setFillColorRGB(0.62, 0.10, 0.10)
    pen.drawString(165, 777, "FICTIONAL PREVIEW - NOT FOR SIGNING OR CUSTOMER USE")
    pen.save()

    overlay = PdfReader(BytesIO(layer.getvalue()), strict=True)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.pages[0].merge_page(overlay.pages[0])

    writer.add_metadata({
        "/Title": "VERIDIAN fictional MSR-driven document layout preview",
        "/Subject": "Development-only PDF; not signed, approved or delivered",
        "/VERIDIANReferenceSHA256": details["sha256"],
    })
    output = BytesIO()
    writer.write(output)
    result = output.getvalue()

    verified = PdfReader(BytesIO(result), strict=True)
    if len(verified.pages) != count or verified.get_fields():
        raise ValueError("Unexpected preview output structure.")

    text = verified.pages[0].extract_text() or ""
    for value in checked:
        if value not in text:
            raise ValueError("Missing populated preview value.")
    if "FICTIONAL PREVIEW" not in text:
        raise ValueError("Missing fictional-use restriction.")

    return result
