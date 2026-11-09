"""Fictional, non-operational SOW and Agreement document previews.

Original approved PDFs remain unchanged. SOW positions require visual
review. Agreement legal pages are reproduced unmodified and a clearly
labeled fictional project-reference page is appended for review only.
No signatures, completion, delivery, or payment claims.
"""
from hashlib import sha256
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import simpleSplit

from .approved_pdf_reference_integrity_4217 import verify_reference
from .msr_document_source import customer_document_data
from .equipment_invoice_rows import project_equipment_rows


def _safe(value, label, allow_blank=False):
    if type(value) is not str:
        raise ValueError(f"{label} must be text.")
    if not allow_blank and not value.strip():
        raise ValueError(f"{label} is required.")
    if len(value) > 180 or any(ord(c) < 32 or ord(c) > 126 for c in value):
        raise ValueError(f"{label} contains unsupported characters.")
    return value


def _write(pen, x, y, width, value, label, size=8):
    value = _safe(value, label)
    current = float(size)
    while current >= 5.5:
        if pen.stringWidth(value, "Helvetica", current) <= width:
            break
        current -= 0.5
    else:
        raise ValueError(f"Text does not fit: {label}")
    pen.setFillColorRGB(0.04, 0.18, 0.25)
    pen.setFont("Helvetica", current)
    pen.drawString(x, y, value)


def _warning(pen, width, height, label):
    pen.saveState()
    pen.setFillColorRGB(0.70, 0.10, 0.10)
    pen.setFont("Helvetica-Bold", 7)
    pen.drawCentredString(width / 2, height - 12,
                          "FICTIONAL PREVIEW - NOT FOR SIGNING OR CUSTOMER USE")
    pen.translate(width / 2, height / 2)
    pen.rotate(32)
    pen.setFont("Helvetica-Bold", 17)
    pen.drawCentredString(0, 0, label)
    pen.restoreState()


def _overlay(page, draw):
    width = float(page.mediabox.width)
    height = float(page.mediabox.height)
    if not (590 <= width <= 630 and 770 <= height <= 810):
        raise ValueError("Unexpected approved form page geometry.")
    layer = BytesIO()
    pen = canvas.Canvas(layer, pagesize=(width, height))
    draw(pen, width, height)
    pen.save()
    page.merge_page(PdfReader(BytesIO(layer.getvalue()), strict=True).pages[0])


def create_sow_preview(directory, snapshot, project_code,
                       msr_version, creation_date, sales_associate):
    verified = verify_reference(directory, "CUSTOMER_SOW")
    original = Path(directory) / verified.filename
    before = sha256(original.read_bytes()).hexdigest()
    common = customer_document_data(snapshot)
    equipment = project_equipment_rows(snapshot)

    fields = [
        ("customer", 620, common["customer"]),
        ("telephone", 602, common["customer_phone"]),
        ("email", 584, common["customer_email"]),
        ("installation address", 566, common["project_location"]),
        ("creation date", 548, creation_date),
        ("project number", 530, project_code),
        ("MSR version", 512, msr_version),
        ("sales associate", 494, sales_associate),
    ]

    reader = PdfReader(BytesIO(original.read_bytes()), strict=True)
    if len(reader.pages) != 2:
        raise ValueError("SOW must have two approved pages.")

    writer = PdfWriter()
    page1 = writer.add_page(reader.pages[0])
    page2 = writer.add_page(reader.pages[1])

    def first(pen, width, height):
        for label, y, value in fields:
            _write(pen, 270, y, 300, value, label)
        columns = (
            ("category", 93, 79),
            ("brand", 197, 70),
            ("system_type", 280, 98),
            ("model_number", 390, 85),
        )
        for index, item in enumerate(equipment):
            y = 299 - index * 31.7
            for key, x, max_width in columns:
                value = item[key]
                if value:
                    _write(pen, x, y, max_width, value,
                           f"equipment {index + 1} {key}", 6.5)
        _warning(pen, width, height, "FICTIONAL SOW PREVIEW")

    def second(pen, width, height):
        # Page 2 is retained intact pending visual alignment of the
        # discount, scope, pricing, and acknowledgment fields.
        _warning(pen, width, height, "FICTIONAL SOW PREVIEW")

    _overlay(page1, first)
    _overlay(page2, second)

    writer.add_metadata({
        "/Title": "VERIDIAN fictional approved SOW layout preview",
        "/Subject": "Development only; page-two commercial positions pending review",
        "/VERIDIANApprovedReferenceSHA256": verified.sha256,
    })
    buffer = BytesIO()
    writer.write(buffer)
    result = buffer.getvalue()
    if len(PdfReader(BytesIO(result)).pages) != 2:
        raise ValueError("SOW preview verification failed.")
    if sha256(original.read_bytes()).hexdigest() != before:
        raise ValueError("Approved SOW original changed.")
    return result


def create_agreement_preview(directory, snapshot, project_code, msr_version):
    verified = verify_reference(directory, "AGREEMENT")
    original = Path(directory) / verified.filename
    before = sha256(original.read_bytes()).hexdigest()
    common = customer_document_data(snapshot)

    reader = PdfReader(BytesIO(original.read_bytes()), strict=True)
    if len(reader.pages) != 3:
        raise ValueError("Approved Agreement must have three pages.")

    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)

    # Keep every approved legal page unchanged. This extra page is
    # explicitly fictional and is not part of the customer Agreement.
    appendix = BytesIO()
    pen = canvas.Canvas(appendix, pagesize=(612, 792))
    pen.setFont("Helvetica-Bold", 15)
    pen.drawString(44, 735, "FICTIONAL PROJECT DATA REVIEW")
    pen.setFont("Helvetica", 9)
    pen.drawString(44, 710, "Development reference only - not contractual text.")
    pen.drawString(44, 695, "Do not sign, deliver, or treat as a completed agreement.")
    rows = [
        ("Customer", common["customer"]),
        ("Project code", project_code),
        ("MSR version", msr_version),
        ("Installation address", common["project_location"]),
        ("City", common["project_city"]),
        ("State", common["project_state"]),
        ("ZIP", common["project_zip"]),
        ("Telephone", common["customer_phone"]),
        ("Email", common["customer_email"]),
    ]
    for index, (label, value) in enumerate(rows):
        y = 650 - 42 * index
        pen.setFont("Helvetica-Bold", 9)
        pen.drawString(48, y, label)
        _write(pen, 185, y, 380, value, label, 9)
    _warning(pen, 612, 792, "NOT PART OF SIGNED AGREEMENT")
    pen.save()
    writer.add_page(PdfReader(BytesIO(appendix.getvalue())).pages[0])
    writer.add_metadata({
        "/Title": "VERIDIAN fictional Agreement project-data review",
        "/Subject": "Three original pages plus separate fictional reference sheet",
        "/VERIDIANApprovedReferenceSHA256": verified.sha256,
    })
    out = BytesIO()
    writer.write(out)
    result = out.getvalue()
    if len(PdfReader(BytesIO(result)).pages) != 4:
        raise ValueError("Agreement preview verification failed.")
    if sha256(original.read_bytes()).hexdigest() != before:
        raise ValueError("Approved Agreement original changed.")
    return result