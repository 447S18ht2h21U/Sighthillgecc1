"""Read-only placement inventory for the six approved PDF originals.

No PDF editing, form generation, signatures, or customer delivery.
Coordinates are provisional until reviewed against rendered page images.
"""
import json
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

from .approved_pdf_reference_integrity_4217 import (
    APPROVED_PDFS,
    verify_reference,
)

ANCHORS = {
    "CUSTOMER_SOW": (
        "Customer name", "Telephone", "Email",
        "Project", "Equipment", "Discount",
    ),
    "AGREEMENT": (
        "Customer", "Project", "Signature",
        "Street", "Date",
    ),
    "INVOICE": (
        "Invoice Date", "Invoice Number",
        "Customer Name", "Customer Address",
        "Customer Phone", "Customer Email",
        "Subtotal", "Total",
    ),
    "RECEIPT": (
        "Invoice Date", "Invoice Number",
        "Customer Name", "Customer Address",
        "Customer Phone", "Customer Email",
        "Subtotal", "Total",
    ),
    "COMPLETION_NON_FINANCED": (
        "Customer Name", "Customer Signature",
        "Address", "Project Statement of Work Code",
    ),
    "COMPLETION_FINANCED": (
        "Customer Name", "Customer Signature",
        "Address", "Project Statement of Work Code",
    ),
}


def build_placement_inventory(directory):
    """Collect verified PDF page geometry and candidate label matches."""
    directory = Path(directory)
    result = {}

    for kind, (filename, _, expected_pages) in APPROVED_PDFS.items():
        verified = verify_reference(directory, kind)
        content = (directory / filename).read_bytes()
        reader = PdfReader(BytesIO(content), strict=True)

        pages = []
        for page_number, page in enumerate(reader.pages, 1):
            width = float(page.mediabox.width)
            height = float(page.mediabox.height)

            if not (0 < width <= 2000 and 0 < height <= 2000):
                raise ValueError("Unexpected approved PDF page geometry.")

            text = page.extract_text() or ""
            normalized = " ".join(text.split()).casefold()
            found = [
                anchor for anchor in ANCHORS[kind]
                if anchor.casefold() in normalized
            ]

            pages.append({
                "page_number": page_number,
                "width_points": width,
                "height_points": height,
                "candidate_labels": found,
                "placement_status": "REQUIRES_VISUAL_REVIEW",
            })

        if len(pages) != expected_pages:
            raise ValueError("PDF page count changed.")

        result[kind] = {
            "approved_filename": filename,
            "approved_sha256": verified.sha256,
            "pages": pages,
            "overlay_authorized": False,
            "customer_document_release_authorized": False,
        }

    return result


def save_placement_inventory(directory, destination):
    destination = Path(destination)
    if destination.exists():
        raise ValueError("Placement inventory already exists.")
    result = build_placement_inventory(directory)
    destination.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result