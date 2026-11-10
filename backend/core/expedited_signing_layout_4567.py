"""Unsigned candidate DocuSign layout for two approved V2 PDFs.

Coordinates are measured candidates, NOT visually approved. This module
does not prepare envelopes, send documents, create evidence, or grant rights.
"""
from hashlib import sha256
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

REFERENCES = {
    "CUSTOMER_SOW": (
        "GECC Project Scope of Work 20261107v2.pdf",
        "E838AD22D5228205E92AD0ED4C73AFA6DCDE5896E8E0462EA1D4466276030BD5",
        2,
    ),
    "EXPEDITED_SERVICE": (
        "GECC Expedite Service Request 20261107v2.pdf",
        "2E822C7C946FD9F909544DF7AE73925CA7E1BE7D33D8FF006CD61FA3D97273FF",
        1,
    ),
}

# DocuSign uses top-left coordinates at 72 DPI for these standard pages.
# These are candidate rectangles for controlled visual review only.
CANDIDATES = {
    "sow_proposed_date": {
        "kind": "CUSTOMER_SOW", "documentId": "1", "pageNumber": "1",
        "tabLabel": "proposed-install-date",
        "xPosition": "230", "yPosition": "466",
        "width": "100", "height": "15",
    },
    "sow_customer_initials": {
        "kind": "CUSTOMER_SOW", "documentId": "1", "pageNumber": "1",
        "tabLabel": "proposed-install-date-initials",
        "xPosition": "380", "yPosition": "480",
        "width": "92", "height": "16",
    },
    "expedited_requested_date": {
        "kind": "EXPEDITED_SERVICE", "documentId": "2",
        "pageNumber": "1", "tabLabel": "requested-installation-date",
        "xPosition": "260", "yPosition": "212",
        "width": "110", "height": "17",
    },
    "expedited_customer_signature": {
        "kind": "EXPEDITED_SERVICE", "documentId": "2",
        "pageNumber": "1",
        "tabLabel": "expedited-service-customer-signature",
        "xPosition": "192", "yPosition": "473",
        "width": "143", "height": "18",
    },
}

ANCHORS = {
    "CUSTOMER_SOW": (
        "Proposed date to start Project",
        "Customer initials indicating approval of date to start Project",
    ),
    "EXPEDITED_SERVICE": (
        "Requested Installation Date",
        "Customer Signature",
    ),
}


def candidate_layout(reference_root):
    root = Path(reference_root)
    checked = {}

    for kind, (filename, fingerprint, page_count) in REFERENCES.items():
        content = (root / filename).read_bytes()
        if sha256(content).hexdigest().upper() != fingerprint:
            raise ValueError("Approved V2 PDF fingerprint mismatch.")

        reader = PdfReader(BytesIO(content), strict=True)
        if reader.is_encrypted or len(reader.pages) != page_count:
            raise ValueError("Approved V2 PDF structure mismatch.")

        if any(
            round(float(page.mediabox.width)) != 612
            or round(float(page.mediabox.height)) != 792
            or int(page.get("/Rotate", 0)) != 0
            for page in reader.pages
        ):
            raise ValueError("Unexpected page geometry or rotation.")

        page_text = reader.pages[0].extract_text(
            extraction_mode="layout"
        ) or ""
        normalized = " ".join(page_text.split()).casefold()
        if any(
            " ".join(anchor.split()).casefold() not in normalized
            for anchor in ANCHORS[kind]
        ):
            raise ValueError("Signing-area text anchors differ.")

        checked[kind] = {
            "filename": filename,
            "sha256": fingerprint,
            "pages": page_count,
        }

    tabs = {}
    for name, definition in CANDIDATES.items():
        tab = dict(definition)
        kind = tab.pop("kind")
        width = int(tab["width"])
        height = int(tab["height"])
        x = int(tab["xPosition"])
        y = int(tab["yPosition"])
        page = int(tab["pageNumber"])

        if (
            width <= 0 or height <= 0
            or x < 0 or y < 0
            or x + width > 612 or y + height > 792
            or not 1 <= page <= checked[kind]["pages"]
        ):
            raise ValueError("Candidate signing rectangle is out of bounds.")
        tabs[name] = tab

    return {
        "status": "CANDIDATE_VISUAL_REVIEW_REQUIRED",
        "documents": checked,
        "tabs": tabs,
        "visually_approved": False,
        "send_authorized": False,
        "customer_signature_verified": False,
        "customer_initials_verified": False,
        "installation_authorized": False,
    }
