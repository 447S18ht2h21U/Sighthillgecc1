"""Fictional certificate address extension. No operational actions."""
from hashlib import sha256
from io import BytesIO

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth

from .remaining_document_population_4518 import fictional_remaining_document
from .v2_document_mapping_4489 import (
    project_document_projection_v2,
    reference_details,
)

ADDRESS_POSITIONS = {
    "COMPLETION_FINANCED": {
        "project_city": (288, 95, 56),
        "project_state": (459, 95, 27),
        "project_zip": (516, 95, 52),
    },
    "COMPLETION_NON_FINANCED": {
        "project_city": (265, 270, 56),
        "project_state": (437, 270, 27),
        "project_zip": (494, 270, 52),
    },
}


def fictional_complete_certificate_address(reference_bytes, kind,
                                            snapshot, project_code,
                                            msr_version):
    """Add City, State and ZIP to an existing verified fictional certificate."""
    if kind not in ADDRESS_POSITIONS:
        raise ValueError("Only Completion Certificates are supported.")
    if type(reference_bytes) is not bytes:
        raise ValueError("Reference must be immutable PDF bytes.")

    spec = reference_details(kind)
    if sha256(reference_bytes).hexdigest().upper() != spec["sha256"]:
        raise ValueError("Original certificate fingerprint mismatch.")

    data = project_document_projection_v2(
        snapshot, kind, project_code, msr_version
    )
    if data["send_authorized"] or data["legally_eligible_for_installation"]:
        raise ValueError("Document release not authorized.")

    # Existing function independently validates customer fields,
    # certificate selection and the complete original reference.
    original_preview = fictional_remaining_document(
        reference_bytes, kind, snapshot, project_code, msr_version
    )
    reader = PdfReader(BytesIO(original_preview), strict=True)

    if len(reader.pages) != 1:
        raise ValueError("Unexpected certificate page count.")

    layer = BytesIO()
    pen = canvas.Canvas(layer, pagesize=(612, 792))
    pen.setFont("Helvetica", 8)

    values = {}
    for field, (x, y, width) in ADDRESS_POSITIONS[kind].items():
        value = data[field]
        if type(value) is not str or not value.strip():
            raise ValueError(f"Missing required address value: {field}")

        value = value.strip()
        if any(ord(ch) < 32 or ord(ch) > 126 for ch in value):
            raise ValueError(f"Unsupported address characters: {field}")

        if stringWidth(value, "Helvetica", 8) > width:
            raise ValueError(f"Address field exceeds space: {field}")

        if field == "project_state" and len(value) != 2:
            raise ValueError("State must use two-letter abbreviation.")

        if field == "project_zip" and not (
            len(value) == 5 and value.isascii() and value.isdigit()
        ):
            raise ValueError("Preview ZIP must contain five ASCII digits.")

        pen.drawString(x, y, value)
        values[field] = value

    pen.save()

    overlay = PdfReader(BytesIO(layer.getvalue()), strict=True)
    writer = PdfWriter()
    writer.add_page(reader.pages[0])
    writer.pages[0].merge_page(overlay.pages[0])

    writer.add_metadata({
        "/Title": f"VERIDIAN fictional complete-address {kind}",
        "/Subject": "Development only; no signing, verification or delivery",
        "/VERIDIANReferenceSHA256": spec["sha256"],
    })

    buffer = BytesIO()
    writer.write(buffer)
    result = buffer.getvalue()

    verified = PdfReader(BytesIO(result), strict=True)
    if len(verified.pages) != 1 or verified.get_fields():
        raise ValueError("Unexpected certificate output.")

    text = verified.pages[0].extract_text() or ""
    for value in values.values():
        if value not in text:
            raise ValueError("Address field missing from generated certificate.")

    for value in (data["customer_name"], data["project_address"],
                  data["project_code"], "Customer Signature:"):
        if value not in text:
            raise ValueError("Existing customer/signature-label content lost.")

    if "NOT SIGNED OR AUTHORIZED" not in text:
        raise ValueError("Fictional document warning missing.")

    return result
