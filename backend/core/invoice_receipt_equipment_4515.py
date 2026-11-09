"""Fictional Invoice/Receipt equipment population from a single MSR snapshot.

Never supplies serial numbers, equipment prices, signatures or release authority.
"""
from hashlib import sha256
from io import BytesIO

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import simpleSplit

from .equipment_invoice_rows import project_equipment_rows
from .v4_customer_overlay_4501 import fictional_customer_preview
from .v2_document_mapping_4489 import reference_details


LAYOUTS = {
    "INVOICE": {
        "top": 293,
        "step": 19,
        "columns": (
            ("brand", 51, 120),
            ("description", 185, 570),
        ),
    },
    "RECEIPT": {
        "top": 310,
        "step": 20,
        "columns": (
            ("brand", 52, 130),
            ("system_type", 204, 213),
            ("model_number", 452, 135),
        ),
    },
}


def fictional_equipment_document(reference_bytes, kind, snapshot, fields):
    """Return an isolated, two-stage fictional customer/equipment PDF preview."""
    if kind not in LAYOUTS:
        raise ValueError("Unsupported equipment document type.")
    if type(reference_bytes) is not bytes:
        raise ValueError("Reference must be immutable PDF bytes.")
    if type(snapshot) is not dict:
        raise ValueError("An MSR snapshot object is required.")

    spec = reference_details(kind)
    if sha256(reference_bytes).hexdigest().upper() != spec["sha256"]:
        raise ValueError("Approved reference fingerprint mismatch.")

    rows = project_equipment_rows(snapshot)
    equipment = snapshot.get("equipment")
    if type(equipment) is not list or not equipment:
        raise ValueError("At least one MSR equipment record is required.")

    # The description is an MSR equipment field, not a derived price or serial.
    for index, item in enumerate(equipment):
        if type(item["description"]) is not str or not item["description"].strip():
            raise ValueError(f"Missing equipment description: {index + 1}")

    base = fictional_customer_preview(reference_bytes, kind, fields)
    reader = PdfReader(BytesIO(base), strict=True)
    if len(reader.pages) != 1:
        raise ValueError("Unexpected base PDF page count.")

    layer = BytesIO()
    pen = canvas.Canvas(layer, pagesize=(792, 612))
    layout = LAYOUTS[kind]

    printed = []

    for index, row in enumerate(rows):
        if not row["brand"]:
            continue
        top = layout["top"] - layout["step"] * index

        for key, x, width in layout["columns"]:
            value = (
                equipment[index]["description"]
                if key == "description"
                else row[key]
            )
            if type(value) is not str or not value.strip():
                raise ValueError(f"Invalid equipment field: {key}")
            if len(value) > 150 or any(
                ord(char) < 32 or ord(char) > 126 for char in value
            ):
                raise ValueError(f"Unsupported equipment text: {key}")

            font_size = 8
            lines = simpleSplit(value, "Helvetica", font_size, width)

            if len(lines) > 2:
                font_size = 7
                lines = simpleSplit(value, "Helvetica", font_size, width)

            if not lines or len(lines) > 2:
                raise ValueError(f"Equipment field does not fit: {key}")

            pen.setFont("Helvetica", font_size)
            for line_number, line in enumerate(lines):
                pen.drawString(x, top - 9 * line_number, line)

            printed.append(value)

    pen.save()

    overlay = PdfReader(BytesIO(layer.getvalue()), strict=True)
    writer = PdfWriter()
    writer.add_page(reader.pages[0])
    writer.pages[0].merge_page(overlay.pages[0])

    writer.add_metadata({
        "/Title": f"VERIDIAN fictional {kind} equipment preview",
        "/Subject": "Development only; no serial verification or customer release",
        "/VERIDIANReferenceSHA256": spec["sha256"],
    })

    output = BytesIO()
    writer.write(output)
    result = output.getvalue()

    verified = PdfReader(BytesIO(result), strict=True)
    if len(verified.pages) != 1 or verified.get_fields():
        raise ValueError("Invalid generated equipment preview.")

    extracted = verified.pages[0].extract_text() or ""
    for value in printed:
        # Wrapped values may be split across multiple PDF text lines.
        tokens = value.split()
        if not tokens or any(token not in extracted for token in tokens):
            raise ValueError("Generated equipment value not found.")

    return result
