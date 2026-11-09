"""Fictional MSR scope and equipment overlay. No operational release."""
from io import BytesIO
from hashlib import sha256

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth

from .approved_sow_commercial_4231 import sow_commercial_projection
from .equipment_invoice_rows import project_equipment_rows
from .msr_commercial_page2_4510 import fictional_commercial_sow_preview
from .v2_document_mapping_4489 import reference_details


WORK_CHECKBOXES = {
    "New installation": 400.3,
    "Remove existing equipment and replace with new equipment": 384.3,
    "Service and maintenance of existing equipment": 368.3,
}

WORK_CATEGORIES = {
    "New installation": "New installation",
    "Remove existing equipment and replace with new equipment": "Replacing existing equipment",
    "Service and maintenance of existing equipment": "Service & maintenance",
}

ROW_BASELINES = (
    214.9, 192.4, 169.8, 147.4,
    124.8, 102.3, 79.7, 57.1,
)


def fictional_equipment_scope_preview(
    reference_bytes, snapshot, project_code, msr_version,
    creation_date, sales_associate,
):
    """Return a two-page fictional PDF, preserving the source and snapshot."""
    if type(reference_bytes) is not bytes:
        raise ValueError("Reference must be immutable bytes.")

    details = reference_details("CUSTOMER_SOW")
    if sha256(reference_bytes).hexdigest().upper() != details["sha256"]:
        raise ValueError("MSR reference fingerprint mismatch.")

    commercial = sow_commercial_projection(snapshot)
    equipment = project_equipment_rows(snapshot)
    work_type = commercial["description_of_work"]
    scope = commercial["scope"]

    if work_type not in WORK_CHECKBOXES:
        raise ValueError("Unsupported project work category.")

    if not any(row["brand"] for row in equipment):
        raise ValueError("At least one approved equipment row is required.")

    # Do not infer serials, prices, signatures, or installation-date approvals.
    base = fictional_commercial_sow_preview(
        reference_bytes, snapshot, project_code,
        msr_version, creation_date, sales_associate,
    )
    reader = PdfReader(BytesIO(base), strict=True)
    if len(reader.pages) != 2:
        raise ValueError("Unexpected SOW page count.")

    buffer = BytesIO()
    pen = canvas.Canvas(buffer, pagesize=(612, 792))

    pen.setStrokeColorRGB(0.04, 0.18, 0.25)
    pen.setLineWidth(1.25)
    y = WORK_CHECKBOXES[work_type]
    pen.line(60, y - 2, 66, y + 5)
    pen.line(60, y + 5, 66, y - 2)

    def place(value, x, y, width, size, label):
        if type(value) is not str or not value.strip():
            raise ValueError(f"Missing equipment/scope value: {label}")
        if any(ord(c) < 32 or ord(c) > 126 for c in value):
            raise ValueError(f"Unsupported characters: {label}")
        if stringWidth(value, "Helvetica", size) > width:
            raise ValueError(f"Text exceeds approved field width: {label}")
        pen.setFont("Helvetica", size)
        pen.drawString(x, y, value)

    # One line fits inside the present approved SOW description area.
    # Longer descriptions fail closed rather than overlap proposed dates.
    place(scope, 75, 332, 460, 8, "customer scope")

    populated = []
    for index, row in enumerate(equipment):
        if not row["brand"]:
            continue

        baseline = ROW_BASELINES[index]

        place(
            row["brand"], 167, baseline, 119, 8,
            f"equipment {index + 1} brand",
        )
        place(
            row["system_type"], 311, baseline, 205, 8,
            f"equipment {index + 1} system type",
        )

        populated.extend((row["brand"], row["system_type"]))

    pen.setFont("Helvetica-Bold", 7)
    pen.setFillColorRGB(0.64, 0.10, 0.10)
    pen.drawString(173, 765, "FICTIONAL EQUIPMENT PREVIEW - NOT FOR USE")
    pen.save()

    overlay = PdfReader(BytesIO(buffer.getvalue()), strict=True)

    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)

    writer.pages[0].merge_page(overlay.pages[0])
    writer.add_metadata({
        "/Title": "VERIDIAN fictional MSR equipment and scope review",
        "/Subject": "Development only; no signature or installation authority",
        "/VERIDIANReferenceSHA256": details["sha256"],
    })

    result_buffer = BytesIO()
    writer.write(result_buffer)
    result = result_buffer.getvalue()

    verified = PdfReader(BytesIO(result), strict=True)
    if len(verified.pages) != 2 or verified.get_fields():
        raise ValueError("Invalid fictional PDF output.")

    text = verified.pages[0].extract_text() or ""
    for value in (scope, *populated):
        if value not in text:
            raise ValueError("Populated equipment/scope field missing.")

    return result
