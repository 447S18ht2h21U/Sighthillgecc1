"""Read-only PDF continuation schedules for approved GECC documents.

No per-item prices, issuance authority, database writes, or email delivery.
The caller remains responsible for verifying the MSR, first-page content,
and approved promotional disclosure.
"""
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.utils import simpleSplit

from .equipment_invoice_rows import project_equipment_rows

WIDTH, HEIGHT = 792, 612
LEFT, RIGHT = 42, 750
BOTTOM = 49


def _required(value, label, maximum=10000):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} is required.")
    if len(value) > maximum:
        raise ValueError(f"{label} exceeds the permitted length.")
    return value.strip()


def _entries(snapshot, equipment_start):
    if type(snapshot) is not dict:
        raise ValueError("An MSR snapshot object is required.")
    if type(equipment_start) is not int or equipment_start < 0:
        raise ValueError("Invalid equipment continuation offset.")

    equipment = snapshot.get("equipment")
    materials = snapshot.get("materials", [])

    if type(equipment) is not list or len(equipment) > 100:
        raise ValueError("Equipment must contain at most 100 entries.")
    if type(materials) is not list or len(materials) > 100:
        raise ValueError("Materials must contain at most 100 entries.")

    # Preserve upstream catalog-row validation.
    validated_rows = project_equipment_rows({"equipment": equipment})

    # Fewer than eight equipment entries is normal: there is no overflow.
    # The offset is capped at the actual number of equipment entries.
    first_overflow = min(equipment_start, len(equipment))
    entries = []

    for index in range(first_overflow, len(equipment)):
        row = validated_rows[index]
        source = equipment[index]
        description = _required(
            source["description"], f"Equipment {index + 1}", 10000
        )
        entries.append((
            "Equipment",
            f"{index + 1}. {row['brand']} | {row['system_type']} | "
            f"{row['model_number']} | {row['category']} | "
            f"Quantity: {source['quantity']} | {description}"
        ))

    for index, material in enumerate(materials, 1):
        if type(material) is not dict or set(material) != {
            "description", "quantity"
        }:
            raise ValueError(f"Material {index} has invalid fields.")

        description = _required(
            material["description"], f"Material {index}", 1000
        )
        quantity = material["quantity"]
        if type(quantity) not in (str, int, float):
            raise ValueError(f"Material {index} has an invalid quantity.")
        quantity_text = str(quantity).strip()
        if not quantity_text:
            raise ValueError(f"Material {index} has no quantity.")

        entries.append((
            "Materials",
            f"{index}. {description} | Quantity: {quantity_text}"
        ))

    return entries


def render_schedule_continuation(
    *,
    snapshot,
    project_code,
    document_kind,
    equipment_start=8,
    promotion_notes=None,
):
    """Render overflow equipment, materials, and supplied approved notes.

    No additional PDF is returned when there is no overflow or other content.
    """
    project_code = _required(project_code, "Project code", 100)
    document_kind = _required(document_kind, "Document kind", 100)

    if document_kind not in ("AGREEMENT", "INVOICE", "RECEIPT"):
        raise ValueError("Unsupported customer document type.")

    entries = _entries(snapshot, equipment_start)

    if promotion_notes is not None and not isinstance(
        promotion_notes, str
    ):
        raise ValueError("Promotion notes must be text.")

    notes = (promotion_notes or "").strip()

    if not entries and not notes:
        return b""

    output = BytesIO()
    pen = canvas.Canvas(output, pagesize=(WIDTH, HEIGHT))
    pen.setTitle(f"{document_kind} continuation - {project_code}")

    page = 0
    y = 0

    def new_page():
        nonlocal page, y
        if page:
            pen.showPage()
        page += 1
        pen.setFillColorRGB(0.08, 0.17, 0.23)
        pen.setFont("Helvetica-Bold", 14)
        pen.drawString(
            LEFT, 563, "GECC - Equipment & Materials Schedule"
        )
        pen.setFont("Helvetica", 9)
        pen.drawString(
            LEFT, 544, f"{document_kind} | Project: {project_code}"
        )
        pen.line(LEFT, 533, RIGHT, 533)
        pen.setFont("Helvetica", 8)
        pen.drawString(
            LEFT, 28,
            "Included in the agreed all-inclusive project price."
        )
        pen.drawRightString(
            RIGHT, 28, f"Continuation page {page}"
        )
        y = 510

    def write_item(group, description, heading=False):
        nonlocal y

        lines = simpleSplit(
            description, "Helvetica", 8.5, RIGHT - LEFT - 24
        )
        if not lines:
            raise ValueError("Empty continuation entry.")

        # Keep an item's heading and first text line together.
        minimum = 30 if heading else 14
        if y - minimum < BOTTOM:
            new_page()

        if heading:
            y -= 8
            pen.setFont("Helvetica-Bold", 10)
            pen.drawString(LEFT, y, group)
            y -= 19

        for line in lines:
            if y < BOTTOM + 10:
                new_page()
            pen.setFont("Helvetica", 8.5)
            pen.drawString(LEFT + 8, y, line)
            y -= 13
        y -= 6

    new_page()
    previous_group = None

    for group, description in entries:
        write_item(
            group, description,
            heading=(group != previous_group)
        )
        previous_group = group

    if notes:
        # Notes must be provided from an independently approved source.
        # Never derive promotional amounts from individual item prices.
        for index, paragraph in enumerate(notes.splitlines()):
            if not paragraph.strip():
                continue
            write_item(
                "Promotional Offer / Other Notes",
                paragraph,
                heading=(index == 0)
            )

    pen.save()
    return output.getvalue()
