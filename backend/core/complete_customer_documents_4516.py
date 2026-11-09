"""Development-only combined MSR Invoice and Receipt previews."""
from hashlib import sha256
from io import BytesIO
from datetime import date
from decimal import Decimal

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth

from .v2_document_mapping_4489 import (
    project_document_projection_v2, reference_details,
)
from .invoice_receipt_equipment_4515 import fictional_equipment_document
from .msr_commercial_page2_4510 import page_two_commercial_data


AMOUNT_BASELINES = {
    "INVOICE": (129, 108, 87, 72),
    "RECEIPT": (121, 100, 79, 58),
}
AMOUNT_RIGHT_EDGES = {
    "INVOICE": 740,
    "RECEIPT": 726,
}
AMOUNT_LEFT_LIMITS = {
    "INVOICE": 614,
    "RECEIPT": 600,
}
DATE_NUMBER_BASELINES = {
    "INVOICE": 454,
    "RECEIPT": 459,
}


def _text(value, label, maximum, size=9):
    if type(value) is not str or not value.strip():
        raise ValueError(f"{label} must be nonempty text.")
    value = value.strip()
    if any(ord(ch) < 32 or ord(ch) > 126 for ch in value):
        raise ValueError(f"{label} has unsupported characters.")
    if stringWidth(value, "Helvetica", size) > maximum:
        raise ValueError(f"{label} exceeds PDF field width.")
    return value


def complete_fictional_document(reference_bytes, kind, snapshot,
                                project_code, msr_version,
                                invoice_number, invoice_date):
    """Use one MSR snapshot. Never assert approval, delivery or payment."""
    if kind not in AMOUNT_BASELINES:
        raise ValueError("Unsupported document kind.")
    if type(reference_bytes) is not bytes:
        raise ValueError("Reference must be immutable PDF bytes.")

    spec = reference_details(kind)
    if sha256(reference_bytes).hexdigest().upper() != spec["sha256"]:
        raise ValueError("Protected PDF fingerprint mismatch.")

    projection = project_document_projection_v2(
        snapshot, kind, project_code, msr_version,
    )
    if projection["send_authorized"] or projection["legally_eligible_for_installation"]:
        raise ValueError("No live release or legal decision permitted.")

    commercial = page_two_commercial_data(snapshot)
    if commercial["ceo_approval_verified"] or commercial["send_authorized"]:
        raise ValueError("Fictional data must not assert authorization.")

    number = _text(invoice_number, "Invoice number", 140)
    if not number.startswith("FICTIONAL-"):
        raise ValueError("Only fictional invoice numbers permitted.")

    when = _text(invoice_date, "Invoice date", 100)
    try:
        if date.fromisoformat(when).isoformat() != when:
            raise ValueError()
    except ValueError:
        raise ValueError("Invoice date must be YYYY-MM-DD.")

    fields = {
        "customer_name": projection["customer_name"],
        "project_code": projection["project_code"],
        "project_address": projection["project_address"],
        "project_city": projection["project_city"],
        "project_state": projection["project_state"],
        "project_zip": projection["project_zip"],
        "customer_phone": projection["customer_phone"],
        "customer_email": projection["customer_email"],
    }

    base = fictional_equipment_document(
        reference_bytes, kind, snapshot, fields,
    )
    page = PdfReader(BytesIO(base), strict=True).pages[0]

    # Values are contractual figures, not evidence of receipt of funds.
    from .invoice_msr_projection import revised_invoice_projection
    invoice = revised_invoice_projection(snapshot)
    amounts = (
        invoice["subtotal"],
        invoice["sales_tax"],
        invoice["other_charges"],
        invoice["invoice_total"],
    )

    if invoice["invoice_total"] != commercial["customer_total"]:
        raise ValueError("MSR commercial totals do not match.")

    layer = BytesIO()
    pen = canvas.Canvas(layer, pagesize=(792, 612))
    pen.setFont("Helvetica", 9)
    header_y = DATE_NUMBER_BASELINES[kind]
    pen.drawString(112, header_y, when)
    pen.drawString(365, header_y, number)

    for value, y in zip(amounts, AMOUNT_BASELINES[kind]):
        value = _text(value, "Commercial amount", 98)
        right = AMOUNT_RIGHT_EDGES[kind]
        if right - stringWidth(value, "Helvetica", 9) < AMOUNT_LEFT_LIMITS[kind]:
            raise ValueError("Amount exceeds the Price cell width.")
        pen.drawRightString(right, y, value)

    # Explicitly distinguish an unsigned preview from a paid Receipt.
    pen.setFont("Helvetica-Bold", 7)
    pen.setFillColorRGB(0.65, 0.10, 0.10)
    pen.drawRightString(
        771, 15,
        "FICTIONAL PREVIEW - NOT PAYMENT OR APPROVAL EVIDENCE",
    )
    pen.save()

    writer = PdfWriter()
    writer.add_page(page)
    writer.pages[0].merge_page(
        PdfReader(BytesIO(layer.getvalue()), strict=True).pages[0]
    )
    writer.add_metadata({
        "/Title": f"VERIDIAN fictional combined {kind} preview",
        "/Subject": "Development only; no signature, delivery, or payment evidence",
        "/VERIDIANSourceSHA256": spec["sha256"],
        "/VERIDIANMSRVersion": msr_version,
    })
    output = BytesIO()
    writer.write(output)
    result = output.getvalue()

    verified = PdfReader(BytesIO(result), strict=True)
    if len(verified.pages) != 1 or verified.get_fields():
        raise ValueError("Invalid combined PDF output.")

    text = verified.pages[0].extract_text() or ""
    for required in (number, when, *amounts,
                     "NOT PAYMENT OR APPROVAL EVIDENCE"):
        if required not in text:
            raise ValueError("Combined PDF verification failed.")

    return result
