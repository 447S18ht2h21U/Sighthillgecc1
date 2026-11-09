"""Fictional commercial Page 2 overlay for the November 7 MSR.

Development-only. Does not create approvals, collect payments, or authorize
document release. Original PDF and MSR input are never modified.
"""
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO
from hashlib import sha256

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth

from .approved_sow_commercial_4231 import sow_commercial_projection
from .msr_document_source import msr_other_details
from .v2_msr_agreement_population_4507 import fictional_document_preview
from .v2_document_mapping_4489 import reference_details


def page_two_commercial_data(snapshot):
    """Strict current-policy view; does not rewrite older financial records."""
    data = sow_commercial_projection(snapshot)
    other = msr_other_details(snapshot)

    base = Decimal(str(snapshot["base_price"]))
    discount = Decimal(str(snapshot["discount"]))
    tax = Decimal(str(snapshot["tax"]))
    total = Decimal(str(snapshot["total_price"]))

    if other is None:
        if discount:
            raise ValueError("New MSR discounts require Marketing Promotion details.")
        category = ""
        market_value = ""
        explanation = ""
        applied = ""
    elif other["type"] == "Marketing Promotion":
        if discount <= 0 or Decimal(other["amount"]) != discount:
            raise ValueError("Marketing Promotion discount must match the price reduction.")
        category = "Marketing Promotion"
        market_value = other["amount"]
        explanation = other["notes"]
        applied = "Retail selling-price discount"
    elif other["type"] in ("Cash Back", "Free Water Heater", "Custom"):
        if discount:
            raise ValueError("Non-price benefits cannot reduce the retail price.")
        category = other["type"]
        market_value = other["amount"]
        explanation = other["notes"]
        applied = "Company-paid benefit; retail price unchanged"
    else:
        raise ValueError("Unsupported new MSR promotion category.")

    if base - discount + tax != total:
        raise ValueError("Commercial amounts do not reconcile.")

    financing = data["financing_type"]
    method = snapshot.get("payment_method", "")
    if method not in ("EFT", "cash", "cashier's check"):
        raise ValueError("Unsupported payment method selection.")

    # Split to cents; remaining balance absorbs any one-cent difference.
    deposit = (total / 2).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    balance = total - deposit

    money = lambda value: f"{value:,.2f}"
    return {
        "category": category,
        "market_value": market_value,
        "explanation": explanation,
        "applied": applied,
        "financing_classification": financing,
        "payment_method": method,
        "quoted_price": money(base),
        "price_discount": money(discount),
        "customer_total": money(total),
        "deposit": money(deposit),
        "balance": money(balance),
        "discount_requires_ceo_approval": bool(discount),
        "ceo_approval_verified": False,
        "send_authorized": False,
    }


def fictional_commercial_sow_preview(reference_bytes, snapshot,
                                     project_code, msr_version,
                                     creation_date, associate):
    """Populate both approved SOW pages with test data, not actual evidence."""
    if type(reference_bytes) is not bytes:
        raise ValueError("Reference PDF must be immutable bytes.")

    info = reference_details("CUSTOMER_SOW")
    if sha256(reference_bytes).hexdigest().upper() != info["sha256"]:
        raise ValueError("SOW reference fingerprint mismatch.")

    data = page_two_commercial_data(snapshot)
    base = fictional_document_preview(
        reference_bytes, "CUSTOMER_SOW", snapshot,
        project_code, msr_version, creation_date, associate,
    )
    reader = PdfReader(BytesIO(base), strict=True)
    if len(reader.pages) != 2:
        raise ValueError("Expected two-page SOW preview.")

    sheet = BytesIO()
    pen = canvas.Canvas(sheet, pagesize=(612, 792))
    pen.setFont("Helvetica", 8)

    def write(x, y, value, width, label):
        if not value:
            return
        if any(ord(ch) < 32 or ord(ch) > 126 for ch in value):
            raise ValueError(f"Unsupported characters: {label}")
        if stringWidth(value, "Helvetica", 8) > width:
            raise ValueError(f"Field too wide: {label}")
        pen.drawString(x, y, value)

    # Page 2 positions are provisional until visual inspection.
    write(230, 566, data["market_value"], 260, "promotion market value")
    write(220, 543, data["explanation"], 315, "promotion explanation")
    write(220, 520, data["applied"], 315, "promotion treatment")

    # Mark only the fictional, explicitly price-reducing promotion.
    # No customer approval, discount authorization, or signature is implied.
    if data["category"] == "Marketing Promotion":
        pen.setLineWidth(1.4)
        pen.line(309, 616, 316, 624)
        pen.line(309, 624, 316, 616)

    # Explicit MSR financing classification; never infer lender approval.
    financing_display = {
        "FINANCED": "YES",
        "NON_FINANCED": "NO",
    }[data["financing_classification"]]
    write(420, 450, financing_display, 95, "financing selection")
    write(420, 427, data["payment_method"], 95, "payment method")

    commercial = (
        ("quoted_price", 401),
        ("price_discount", 377),
        ("customer_total", 354),
        ("deposit", 330),
        ("balance", 307),
    )
    for label, y in commercial:
        write(423, y, data[label], 95, label)

    pen.setFont("Helvetica-Bold", 7)
    pen.setFillColorRGB(0.65, 0.10, 0.10)
    pen.drawString(145, 775, "FICTIONAL PREVIEW - NOT FOR CUSTOMER USE")
    pen.save()

    layer = PdfReader(BytesIO(sheet.getvalue()), strict=True)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.pages[1].merge_page(layer.pages[0])

    writer.add_metadata({
        "/Title": "VERIDIAN fictional commercial MSR layout review",
        "/Subject": "No CEO approval, payment confirmation, or release authority",
    })

    buffer = BytesIO()
    writer.write(buffer)
    result = buffer.getvalue()
    pdf = PdfReader(BytesIO(result), strict=True)
    if len(pdf.pages) != 2 or pdf.get_fields():
        raise ValueError("Unexpected commercial PDF structure.")

    text = pdf.pages[1].extract_text() or ""
    for label, _ in commercial:
        if data[label] not in text:
            raise ValueError(f"Missing rendered commercial value: {label}")
    if sha256(reference_bytes).hexdigest().upper() != info["sha256"]:
        raise ValueError("Source PDF changed.")

    return result


def completion_certificate_reference_kind(snapshot):
    """Select the appropriate reference kind, never authorize delivery.

    Certificate signing, verification, and sending remain separate gates.
    """
    classification = page_two_commercial_data(snapshot)[
        "financing_classification"
    ]
    kinds = {
        "FINANCED": "COMPLETION_FINANCED",
        "NON_FINANCED": "COMPLETION_NON_FINANCED",
    }
    kind = kinds[classification]
    reference_details(kind)
    return kind
