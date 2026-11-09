"""Commercial data contract for approved Project SOW development.

Pure MSR-based projection. No database writes, signing, operational
registration, or modifications to approved PDF pages.
"""
from io import BytesIO
from decimal import Decimal

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import simpleSplit

from .invoice_msr_projection import revised_invoice_projection
from .equipment_invoice_rows import project_equipment_rows
from .msr_document_source import (
    document_customer_name, msr_other_details,
)
from .approved_sow_agreement_previews_4230 import create_sow_preview


WORK_DESCRIPTIONS = frozenset({
    "New installation",
    "Remove existing equipment and replace with new equipment",
    "Service and maintenance of existing equipment",
})
FINANCING = frozenset({"FINANCED", "NON_FINANCED"})


def required_text(snapshot, key, maximum=2500):
    value = snapshot.get(key)
    if type(value) is not str or not value.strip():
        raise ValueError(f"Required SOW field missing: {key}")
    if len(value) > maximum or any(
        ord(c) < 32 and c not in "\n\t" or ord(c) > 126
        for c in value
    ):
        raise ValueError(f"Unsupported SOW text: {key}")
    return value.strip()


def sow_commercial_projection(snapshot):
    """Validate source values and return detached approved commercial data."""
    if type(snapshot) is not dict:
        raise ValueError("Approved MSR snapshot must be an object.")

    customer = document_customer_name(snapshot)
    invoice = revised_invoice_projection(snapshot)
    equipment = project_equipment_rows(snapshot)

    work_type = required_text(snapshot, "description_of_work", 100)
    if work_type not in WORK_DESCRIPTIONS:
        raise ValueError("Unapproved description of work.")

    scope = required_text(snapshot, "scope")
    financing = required_text(snapshot, "financing_type", 20)
    if financing not in FINANCING:
        raise ValueError("Unsupported financing classification.")

    other = msr_other_details(snapshot)
    discount = Decimal(str(snapshot["discount"]))

    if other is not None:
        if other["type"] in ("Reduced Price", "Marketing Promotion"):
            # The invoice projection has already reconciled the amount.
            pass
        elif discount:
            raise ValueError("Non-price promotion cannot reduce selling price.")

    return {
        "customer_name": customer,
        "description_of_work": work_type,
        "scope": scope,
        "financing_type": financing,
        "equipment": equipment,
        "subtotal": invoice["subtotal"],
        "sales_tax": invoice["sales_tax"],
        "other_charges": invoice["other_charges"],
        "total": invoice["invoice_total"],
        "promotion": other,
        "commercial_notes": required_text(
            snapshot, "commercial_notes"
        ) if snapshot.get("commercial_notes") else "",
    }


def make_sow_commercial_review(directory, snapshot, project_code,
                               msr_version, created, associate):
    """Append a clearly marked development review page to the 2-page SOW."""
    data = sow_commercial_projection(snapshot)
    existing = create_sow_preview(
        directory, snapshot, project_code, msr_version, created, associate
    )

    reader = PdfReader(BytesIO(existing), strict=True)
    if len(reader.pages) != 2:
        raise ValueError("Approved SOW preview must contain two pages.")

    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)

    buf = BytesIO()
    pen = canvas.Canvas(buf, pagesize=(612, 792))
    pen.setFont("Helvetica-Bold", 13)
    pen.drawString(45, 744, "PROJECT SOW - FICTIONAL COMMERCIAL REVIEW")
    pen.setFont("Helvetica", 9)
    pen.drawString(45, 722, "Development appendix only - not an approved form page.")
    pen.drawString(45, 707, "No signatures, customer acceptance or payment verification.")

    y = 673

    def section(label, value):
        nonlocal y
        if type(value) is not str:
            raise ValueError("Review value must be text.")
        if any(ord(c) > 126 or ord(c) < 32 and c != "\n" for c in value):
            raise ValueError("Review text contains unsupported characters.")

        pen.setFont("Helvetica-Bold", 9)
        pen.drawString(47, y, label)
        y -= 15
        pen.setFont("Helvetica", 8)
        for paragraph in value.split("\n"):
            lines = simpleSplit(paragraph or " ", "Helvetica", 8, 510)
            for line in lines:
                if y < 82:
                    raise ValueError("Commercial review exceeds one page.")
                pen.drawString(55, y, line)
                y -= 11
        y -= 11

    section("Customer and MSR", f"{data['customer_name']} | {project_code} | {msr_version}")
    section("Description of Work", data["description_of_work"])
    section("Approved Project Scope of Work", data["scope"])
    section("Financing classification", data["financing_type"])
    section("Subtotal", data["subtotal"])
    section("Sales tax", data["sales_tax"])
    section("Other / price reduction", data["other_charges"])
    section("Total customer selling price", data["total"])

    if data["promotion"] is not None:
        p = data["promotion"]
        section(
            "Approved promotion / benefit",
            f"{p['type']} | Amount: {p['amount']} | {p['notes']}"
        )

    if data["commercial_notes"]:
        section("Commercial notes", data["commercial_notes"])

    pen.setFillColorRGB(0.70, 0.10, 0.10)
    pen.setFont("Helvetica-Bold", 9)
    pen.drawCentredString(
        306, 49, "FICTIONAL DATA - DO NOT SIGN, SEND OR COLLECT PAYMENT"
    )
    pen.save()

    writer.add_page(PdfReader(BytesIO(buf.getvalue())).pages[0])
    writer.add_metadata({
        "/Title": "VERIDIAN fictional SOW commercial data review",
        "/Subject": "Two approved-form preview pages plus development appendix",
    })

    out = BytesIO()
    writer.write(out)
    result = out.getvalue()
    if len(PdfReader(BytesIO(result), strict=True).pages) != 3:
        raise ValueError("SOW commercial review page count mismatch.")
    return result