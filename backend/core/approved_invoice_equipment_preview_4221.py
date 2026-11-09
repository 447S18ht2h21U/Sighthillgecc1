"""Fictional eight-row Invoice preview, not an operational renderer.

The approved MSR provides the four catalog fields and category.
Installation-stage identification and pricing are never inferred.
"""
from io import BytesIO

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import simpleSplit

from .approved_invoice_overlay_preview_4220 import create_invoice_preview
from .equipment_invoice_rows import project_equipment_rows


# Coordinates measured from the approved 792 x 612 Invoice page.
# Layout remains provisional until visual acceptance.
COLUMNS = (
    ("category", 38, 72),
    ("brand", 113, 68),
    ("system_type", 184, 177),
    ("model_number", 366, 102),
)

ROW_TOP = 353.0
ROW_HEIGHT = 27.0
ROW_LEFT = 36.0
ROW_RIGHT = 761.0


def create_equipment_invoice_preview(
    directory, snapshot, project_code, invoice_number, invoice_date
):
    base = create_invoice_preview(
        directory, snapshot, project_code, invoice_number, invoice_date
    )
    rows = project_equipment_rows(snapshot)

    if len(rows) != 8:
        raise ValueError("Exactly eight equipment rows are required.")

    original = PdfReader(BytesIO(base), strict=True)
    if len(original.pages) != 1:
        raise ValueError("Invoice preview must contain one page.")

    page = original.pages[0]
    if (
        float(page.mediabox.width),
        float(page.mediabox.height),
    ) != (792.0, 612.0):
        raise ValueError("Unexpected approved Invoice geometry.")

    layer = BytesIO()
    pen = canvas.Canvas(layer, pagesize=(792, 612))

    for index, row in enumerate(rows):
        top = ROW_TOP - index * ROW_HEIGHT

        # Guidelines are applied to the preview copy only.
        pen.setStrokeColorRGB(0.73, 0.78, 0.80)
        pen.setLineWidth(0.30)
        if index:
            pen.line(ROW_LEFT, top, ROW_RIGHT, top)

        for key, x, max_width in COLUMNS:
            value = row[key]
            if not value:
                continue
            if type(value) is not str or any(
                ord(c) < 32 or ord(c) > 126 for c in value
            ):
                raise ValueError("Unsupported equipment display text.")

            if len(value) > 100:
                raise ValueError("Equipment display text is too long.")

            font_size = 7.0
            lines = simpleSplit(
                value, "Helvetica", font_size, max_width - 3
            )
            if len(lines) > 2:
                font_size = 6.0
                lines = simpleSplit(
                    value, "Helvetica", font_size, max_width - 3
                )
            if not lines or len(lines) > 2:
                raise ValueError(
                    f"Equipment row {index + 1} does not fit: {key}"
                )

            pen.setFillColorRGB(0.04, 0.18, 0.25)
            pen.setFont("Helvetica", font_size)
            baseline = top - 11
            for line in lines:
                pen.drawString(x, baseline, line)
                baseline -= 8

        # Installation-stage information is intentionally absent.
        if any(row[key] for key in (
            "model_identification", "serial_number", "price"
        )):
            raise ValueError(
                "Installation-stage Invoice fields cannot be inferred."
            )

    pen.setStrokeColorRGB(0.73, 0.78, 0.80)
    pen.line(
        ROW_LEFT, ROW_TOP - 8 * ROW_HEIGHT,
        ROW_RIGHT, ROW_TOP - 8 * ROW_HEIGHT
    )

    pen.setFillColorRGB(0.70, 0.10, 0.10)
    pen.setFont("Helvetica-Bold", 7)
    pen.drawString(
        38, 128,
        "FICTIONAL EQUIPMENT DATA - SERIALS AND PRICES NOT VERIFIED"
    )
    pen.save()

    writer = PdfWriter()
    output_page = writer.add_page(page)
    output_page.merge_page(PdfReader(BytesIO(layer.getvalue())).pages[0])
    writer.add_metadata({
        "/Title": "VERIDIAN fictional equipment Invoice preview",
        "/Subject": "Development-only overlay; no customer release",
    })

    stream = BytesIO()
    writer.write(stream)
    return stream.getvalue()