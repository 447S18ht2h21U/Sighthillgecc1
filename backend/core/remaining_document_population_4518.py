"""Fictional population of expedited and completion documents.

Pure PDF generation only. No legal eligibility, signing, delivery, payment
verification, completion approval, or database operations are performed.
"""
from hashlib import sha256
from io import BytesIO

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth

from .v2_document_mapping_4489 import (
    project_document_projection_v2,
    reference_details,
)
from .msr_commercial_page2_4510 import (
    completion_certificate_reference_kind,
)


POSITIONS = {
    "EXPEDITED_SERVICE": {
        "customer_name": (190, 655, 300),
        "project_address": (211, 627, 310),
        "project_code": (173, 184, 210),
    },
    "COMPLETION_FINANCED": {
        "customer_name": (112, 128, 115),
        "project_address": (91, 95, 143),
        "project_code": (121, 62, 145),
    },
    "COMPLETION_NON_FINANCED": {
        "customer_name": (112, 325, 115),
        "project_address": (91, 270, 143),
        "project_code": (121, 226, 145),
    },
}


def _validated(value, label, width):
    if type(value) is not str or not value.strip():
        raise ValueError(f"Missing field: {label}")
    value = value.strip()

    if any(ord(character) < 32 or ord(character) > 126
           for character in value):
        raise ValueError(f"Unsupported characters: {label}")

    if stringWidth(value, "Helvetica", 8) > width:
        raise ValueError(f"Field exceeds approved area: {label}")

    return value


def fictional_remaining_document(reference_bytes, kind, snapshot,
                                 project_code, msr_version):
    """Overlay only shared facts on a verified one-page reference PDF."""
    if kind not in POSITIONS:
        raise ValueError("Unsupported document type.")
    if type(reference_bytes) is not bytes:
        raise ValueError("Reference must be immutable PDF bytes.")

    spec = reference_details(kind)

    if sha256(reference_bytes).hexdigest().upper() != spec["sha256"]:
        raise ValueError("Reference PDF fingerprint mismatch.")

    projection = project_document_projection_v2(
        snapshot, kind, project_code, msr_version,
    )

    if "FICTIONAL" not in projection["customer_name"].upper():
        raise ValueError("Only fictional customer previews permitted.")

    if projection["send_authorized"] or projection["legally_eligible_for_installation"]:
        raise ValueError("Document must not assert authorization.")

    if kind.startswith("COMPLETION_"):
        chosen = completion_certificate_reference_kind(snapshot)
        if chosen != kind:
            raise ValueError("Completion Certificate financing classification mismatch.")

    reader = PdfReader(BytesIO(reference_bytes), strict=True)

    if len(reader.pages) != 1:
        raise ValueError("Expected one-page reference.")

    page = reader.pages[0]

    if (round(float(page.mediabox.width)),
        round(float(page.mediabox.height))) != (612, 792):
        raise ValueError("Unexpected page geometry.")

    values = {
        "customer_name": projection["customer_name"],
        "project_address": projection["project_address"],
        "project_code": projection["project_code"],
    }

    layer = BytesIO()
    pen = canvas.Canvas(layer, pagesize=(612, 792))
    pen.setFont("Helvetica", 8)

    for key, (x, y, width) in POSITIONS[kind].items():
        value = _validated(values[key], key, width)
        pen.drawString(x, y, value)

    pen.setFont("Helvetica-Bold", 7)
    pen.setFillColorRGB(0.65, 0.10, 0.10)
    pen.drawCentredString(
        306, 770,
        "FICTIONAL PREVIEW - NOT SIGNED OR AUTHORIZED",
    )
    pen.save()

    writer = PdfWriter()
    writer.add_page(page)
    writer.pages[0].merge_page(
        PdfReader(BytesIO(layer.getvalue()), strict=True).pages[0]
    )

    writer.add_metadata({
        "/Title": f"VERIDIAN fictional {kind} document",
        "/Subject": "Development only; no signing, legal or completion evidence",
        "/VERIDIANReferenceSHA256": spec["sha256"],
        "/VERIDIANMSRVersion": msr_version,
    })

    output = BytesIO()
    writer.write(output)
    result = output.getvalue()

    verified = PdfReader(BytesIO(result), strict=True)

    if len(verified.pages) != 1 or verified.get_fields():
        raise ValueError("Invalid fictional output structure.")

    extracted = verified.pages[0].extract_text() or ""

    for key in POSITIONS[kind]:
        if values[key] not in extracted:
            raise ValueError(f"Populated field missing: {key}")

    if "Customer Signature:" not in extracted:
        raise ValueError("Original signature label missing.")

    if "FICTIONAL PREVIEW" not in extracted:
        raise ValueError("Fictional warning missing.")

    return result
