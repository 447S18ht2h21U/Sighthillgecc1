"""Complete candidate overlay for the approved unified expedited envelope.

All new rectangles require visual confirmation. This module cannot send,
verify a signature, record an approval, or authorize installation.
"""
from .expedited_signing_layout_4567 import candidate_layout
from .expedited_envelope_contract_4567 import FIELDS

# x/y are top-left PDF points. Pages are the ORIGINAL document pages.
# A decision rectangle represents a region to be refined into an
# explicit approve/reject choice; it is not a signing/approval decision.
REMAINING = {
    "sow_customer_signature": ("1", "2", 249, 544, 180, 18),
    "sow_customer_signed_date": ("1", "2", 475, 544, 80, 18),
    "sow_manager_signature": ("1", "2", 178, 585, 200, 20),
    "sow_manager_full_name": ("1", "2", 140, 614, 210, 19),
    "sow_manager_signed_date": ("1", "2", 435, 585, 85, 20),
    "expedited_customer_reason": ("2", "1", 82, 321, 433, 73),
    "expedited_customer_signed_date": ("2", "1", 399, 473, 105, 20),
    "expedited_manager_decision": ("2", "1", 260, 625, 220, 18),
    "expedited_manager_initials": ("2", "1", 252, 647, 71, 17),
    "expedited_manager_date": ("2", "1", 107, 647, 128, 17),
    "expedited_comptroller_decision": ("2", "1", 260, 693, 220, 18),
    "expedited_comptroller_initials": ("2", "1", 252, 715, 71, 17),
    "expedited_comptroller_date": ("2", "1", 107, 715, 128, 17),
}


def complete_visual_candidate(reference_root):
    original = candidate_layout(reference_root)
    fields = {item[0]: item for item in FIELDS}

    if len(fields) != len(FIELDS):
        raise ValueError("Duplicate signing requirements.")

    tabs = {key: dict(value) for key, value in original["tabs"].items()}
    if set(tabs).intersection(REMAINING):
        raise ValueError("Candidate layout duplicates existing fields.")

    for name, (document, page, x, y, width, height) in REMAINING.items():
        tabs[name] = {
            "documentId": document,
            "pageNumber": page,
            "tabLabel": name.replace("_", "-"),
            "xPosition": str(x),
            "yPosition": str(y),
            "width": str(width),
            "height": str(height),
        }

    if set(tabs) != set(fields):
        raise ValueError("Missing or unexpected signing requirement.")

    for name, tab in tabs.items():
        expected_document = fields[name][1]
        doc = tab["documentId"]
        page = int(tab["pageNumber"])
        x = int(tab["xPosition"])
        y = int(tab["yPosition"])
        width = int(tab["width"])
        height = int(tab["height"])

        max_page = 2 if doc == "1" else 1
        if (
            doc != expected_document
            or not 1 <= page <= max_page
            or min(x, y) < 0
            or min(width, height) <= 0
            or x + width > 612
            or y + height > 792
        ):
            raise ValueError(f"Invalid signing rectangle: {name}")

    return {
        "status": "ALL_FIELDS_PLACED_VISUAL_APPROVAL_PENDING",
        "documents": original["documents"],
        "tabs": tabs,
        "previously_reviewed_count": len(original["tabs"]),
        "new_candidate_count": len(REMAINING),
        "visual_approval_required": True,
        "provider_verified": False,
        "send_authorized": False,
        "signatures_verified": False,
        "independent_reviews_verified": False,
        "distribution_verified": False,
        "installation_authorized": False,
    }
